
import os
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Añadir el directorio actual al path para poder importar la app
sys.path.append(os.getcwd())

from app.db import Base
from app.db_models import RegistrationRequestORM
from app.config import get_settings

def migrate():
    settings = get_settings()
    
    # Origen: SQLite (fijo basado en env actual o default)
    sqlite_url = "sqlite:///./data/ra.db"
    if not os.path.exists("./data/ra.db"):
        print("No se encontró el archivo SQLite en ./data/ra.db")
        return

    # Destino: Tomado de DATABASE_URL (asegúrate de haberlo cambiado en el .env)
    target_url = settings.database_url
    
    if target_url.startswith("sqlite"):
        print("La URL de destino sigue siendo SQLite. Cambia DATABASE_URL en el .env antes de migrar.")
        return

    print(f"Migrando datos de {sqlite_url} a {target_url}...")

    # Motores y Sesiones
    src_engine = create_engine(sqlite_url)
    dst_engine = create_engine(target_url)
    
    # Crear tablas en el destino
    Base.metadata.create_all(dst_engine)
    
    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)
    
    src_session = SrcSession()
    dst_session = DstSession()
    
    try:
        # 1. Migrar solicitudes
        requests = src_session.query(RegistrationRequestORM).all()
        print(f"Encontradas {len(requests)} solicitudes.")
        
        for req in requests:
            # Creamos una instancia nueva para el destino (evitando conflictos de sesión)
            new_req = RegistrationRequestORM(
                request_id=req.request_id,
                created_at=req.created_at,
                updated_at=req.updated_at,
                status=req.status,
                applicant_json=req.applicant_json,
                reniec_result_json=req.reniec_result_json,
                review_note=req.review_note,
                certificate_pem=req.certificate_pem,
                dni_front_path=req.dni_front_path,
                dni_back_path=req.dni_back_path,
                selfie_path=req.selfie_path,
                liveness_path=req.liveness_path,
                issuance_mode=req.issuance_mode
            )
            dst_session.merge(new_req)
        
        dst_session.commit()
        print("Migración completada con éxito.")
        
    except Exception as e:
        print(f"Error durante la migración: {e}")
        dst_session.rollback()
    finally:
        src_session.close()
        dst_session.close()

if __name__ == "__main__":
    migrate()
