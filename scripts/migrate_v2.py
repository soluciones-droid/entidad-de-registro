import sys
from pathlib import Path
import json
from uuid import uuid4
from datetime import datetime, timezone

# Añadir la carpeta raíz al path para que pueda importar la app
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from sqlalchemy import create_engine, text
from app.db import Base, engine, settings
from app.db_models import (
    ApplicantORM,
    RegistrationRequestORM,
    BiometricVerificationORM,
    CertificateORM
)
from sqlalchemy.orm import Session

def migrate_database():
    print(f"Iniciando migración en: {settings.database_url}")
    
    with engine.begin() as conn:
        # Verificar si ya migramos o no (si existe old_registration_requests)
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='old_registration_requests';")).fetchone()
        if result:
            print("ERROR: La base de datos parece ya haber sido migrada anteriormente (existe 'old_registration_requests').")
            return
            
        # Verificar si existe la tabla vieja
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='registration_requests';")).fetchone()
        if not result:
            print("ERROR: No se encontró la tabla 'registration_requests'. ¿Base de datos vacía?")
            return
            
        print("1. Respaldando la tabla monolítica a 'old_registration_requests'...")
        conn.execute(text("ALTER TABLE registration_requests RENAME TO old_registration_requests;"))
        print("   Tabla respaldada correctamente.")
        
    print("2. Creando la nueva arquitectura de 5 tablas independientes...")
    # Esto creará `applicants`, la NUEVA `registration_requests`, etc.
    Base.metadata.create_all(bind=engine)
    
    print("3. Independizando y migrando datos (Desglosando JSONs)...")
    with Session(engine) as session:
        # Leer datos antiguos en formato crudo
        old_records = session.execute(text("SELECT * FROM old_registration_requests")).mappings().all()
        
        for old in old_records:
            try:
                applicant_data = json.loads(old["applicant_json"])
                reniec_data = json.loads(old["reniec_result_json"])
                
                def parse_dt(dt_val):
                    if not dt_val: return None
                    if isinstance(dt_val, datetime): return dt_val
                    try:
                        return datetime.fromisoformat(dt_val)
                    except:
                        try:
                            return datetime.strptime(dt_val, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc)
                        except:
                            return datetime.now(timezone.utc)

                old_created_at = parse_dt(old["created_at"])
                old_updated_at = parse_dt(old["updated_at"])

                # 3.1 Insertar Applicant
                dni = applicant_data.get("dni")
                applicant = session.query(ApplicantORM).filter_by(dni=dni).first()
                if not applicant:
                    applicant = ApplicantORM(
                        applicant_id=str(uuid4()),
                        dni=dni,
                        given_name=applicant_data.get("given_name", ""),
                        first_surname=applicant_data.get("first_surname", ""),
                        second_surname=applicant_data.get("second_surname"),
                        email=applicant_data.get("email"),
                        created_at=old_created_at
                    )
                    session.add(applicant)
                    session.flush()

                # 3.2 Insertar Registration Request nuevo
                new_req = RegistrationRequestORM(
                    request_id=old["request_id"],
                    applicant_id=applicant.applicant_id,
                    created_at=old_created_at,
                    updated_at=old_updated_at,
                    status=old["status"],
                    certificate_profile=applicant_data.get("certificate_profile", "natural_person"),
                    issuance_mode=applicant_data.get("issuance_mode", "local"),
                    csr_pem=applicant_data.get("csr_pem"),
                    consent_text=applicant_data.get("consent_text"),
                    review_note=old["review_note"]
                )
                session.add(new_req)

                # 3.3 Insertar Verificación Biométrica Independiente
                bio_evidence = applicant_data.get("biometric_evidence", {})
                new_bio = BiometricVerificationORM(
                    verification_id=str(uuid4()),
                    request_id=old["request_id"],
                    success=reniec_data.get("success", False),
                    facial_match=reniec_data.get("facial_match", False),
                    liveness_passed=reniec_data.get("liveness_passed", False),
                    similarity_score=reniec_data.get("similarity_score"),
                    official_given_name=reniec_data.get("official_given_name"),
                    official_first_surname=reniec_data.get("official_first_surname"),
                    official_second_surname=reniec_data.get("official_second_surname"),
                    source=reniec_data.get("source", "unknown"),
                    detail=reniec_data.get("detail"),
                    device_id=bio_evidence.get("device_id"),
                    capture_ip=bio_evidence.get("capture_ip"),
                    dni_front_path=old.get("dni_front_path"),
                    dni_back_path=old.get("dni_back_path"),
                    selfie_path=old.get("selfie_path"),
                    liveness_path=old.get("liveness_path")
                )
                session.add(new_bio)

                # 3.4 Insertar el Certificado si ya había sido emitido
                if old.get("certificate_pem"):
                    new_cert = CertificateORM(
                        certificate_id=str(uuid4()),
                        request_id=old["request_id"],
                        certificate_pem=old["certificate_pem"],
                        status="active" if old["status"] == "issued" else "pending",
                        created_at=old_updated_at
                    )
                    session.add(new_cert)

                print(f"   [OK] Migrado request: {old['request_id']}")
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"   [ERROR] Falló al migrar el request {old['request_id']}: {str(e)}")
                
        session.commit()
    print("¡Migración completada exitosamente! Tu base de datos ahora usa las tablas independientes.")
    print("Nota: La tabla original todavía existe con nombre 'old_registration_requests' como respaldo de seguridad.")

if __name__ == "__main__":
    migrate_database()
