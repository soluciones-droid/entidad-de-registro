from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db_models import (
    ApplicantORM,
    BiometricVerificationORM,
    CertificateORM,
    RegistrationRequestORM,
)
from app.models import (
    CertificateRequestCreate,
    RegistrationRecord,
    RegistrationStatusResponse,
    ReviewRequest,
)
from app.services.csr import CSRInspector, CSRValidationError
from app.services.ec_remote import ECRemoteClient
from app.services.openssl_ca import OpenSSLCAClient
from app.services.reniec import ReniecClient


class RegistrationService:
    def __init__(self, settings: Settings, db: Session) -> None:
        self.settings = settings
        self.db = db
        self.reniec = ReniecClient(settings)
        self.csr_inspector = CSRInspector(settings)
        self.openssl = OpenSSLCAClient(settings)
        self.ec_remote = ECRemoteClient(settings)

    def generate_request_id(self) -> str:
        return str(uuid4())

    def create_request(
        self,
        payload: CertificateRequestCreate,
        request_id: str | None = None,
        storage_metadata: dict[str, str] | None = None,
    ) -> RegistrationStatusResponse:
        reniec_result = self.reniec.verify_identity(payload)
        record = RegistrationRecord(
            request_id=request_id or self.generate_request_id(),
            applicant=payload,
            reniec_result=reniec_result,
        )

        # Guardar inicialmente para tener el registro en DB
        self._save_record(record, storage_metadata=storage_metadata)

        # Emision automatica: si la verificacion de identidad fue exitosa, intentar de inmediato.
        if reniec_result.success and reniec_result.facial_match and reniec_result.liveness_passed:
            print(f"INFO: Automatic issuance triggered for request {record.request_id}")
            try:
                if record.applicant.csr_pem:
                    self.csr_inspector.validate_subject(record)
                    self._process_issuance(record, "Auto-aprobado por verificacion biometrica exitosa")
                elif record.applicant.issuance_mode == "remote":
                    # En modo remoto la EC puede encargarse del material criptografico.
                    self._process_issuance(record, "Auto-aprobado por verificacion biometrica exitosa (sin CSR)")
                # Si es local y no hay CSR, queda en pending_manual_review.
            except Exception as error:
                print(f"ERROR: Automatic issuance failed for {record.request_id}: {error}")
                if record.applicant.issuance_mode == "remote":
                    self._mark_remote_delivery_pending(
                        record,
                        "Auto-aprobado por verificacion biometrica exitosa",
                        error,
                    )

        return self._to_status(record)

    def get_request(self, request_id: str) -> RegistrationStatusResponse:
        record = self._load_record(request_id)
        return self._to_status(record)

    def list_requests(self, status_filter: str | None = None) -> list[RegistrationStatusResponse]:
        query = self.db.query(RegistrationRequestORM)
        if status_filter:
            query = query.filter(RegistrationRequestORM.status == status_filter)

        orm_records = query.order_by(RegistrationRequestORM.created_at.desc()).all()
        results = []
        for orm_record in orm_records:
            try:
                applicant_summary = {
                    "dni": orm_record.applicant.dni if orm_record.applicant else "N/A",
                    "given_name": orm_record.applicant.given_name if orm_record.applicant else "N/A",
                    "first_surname": orm_record.applicant.first_surname if orm_record.applicant else "N/A",
                    "second_surname": orm_record.applicant.second_surname if orm_record.applicant else None,
                    "email": orm_record.applicant.email if orm_record.applicant else None,
                    "issuance_mode": orm_record.issuance_mode,
                }

                biometric_orm = orm_record.biometric_verification
                reniec_payload = {
                    "success": biometric_orm.success if biometric_orm else False,
                    "official_given_name": biometric_orm.official_given_name if biometric_orm else None,
                    "official_first_surname": biometric_orm.official_first_surname if biometric_orm else None,
                    "official_second_surname": biometric_orm.official_second_surname if biometric_orm else None,
                    "facial_match": biometric_orm.facial_match if biometric_orm else False,
                    "liveness_passed": biometric_orm.liveness_passed if biometric_orm else False,
                    "similarity_score": biometric_orm.similarity_score if biometric_orm else None,
                    "verification_id": biometric_orm.verification_id if biometric_orm else None,
                    "source": biometric_orm.source if biometric_orm else "unknown",
                    "detail": biometric_orm.detail if biometric_orm else "Información migrada",
                }

                cert_pem = orm_record.certificate.certificate_pem if orm_record.certificate else None

                results.append(
                    RegistrationStatusResponse(
                        request_id=orm_record.request_id,
                        status=orm_record.status,
                        created_at=orm_record.created_at,
                        updated_at=orm_record.updated_at,
                        applicant=applicant_summary,
                        review_note=orm_record.review_note,
                        reniec_result=reniec_payload,
                        certificate_pem=cert_pem,
                    )
                )
            except Exception as error:
                print(f"ERROR: Skipping request {orm_record.request_id} due to mapping error: {error}")
                continue
        return results

    def approve_request(self, request_id: str, review: ReviewRequest) -> RegistrationStatusResponse:
        record = self._load_record(request_id)
        if not record.reniec_result.success:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La identidad no fue validada correctamente.",
            )
        if not record.reniec_result.facial_match:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La biometria facial no coincide con la identidad consultada.",
            )
        if not record.reniec_result.liveness_passed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La prueba de vida no fue superada.",
            )
        if record.status in {"rejected", "issued"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede aprobar una solicitud en estado {record.status}.",
            )

        # Validacion de CSR solo si esta presente o si es modo local.
        if record.applicant.csr_pem:
            try:
                self.csr_inspector.validate_subject(record)
            except CSRValidationError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
        elif record.applicant.issuance_mode == "local":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El modo de emision LOCAL requiere un CSR generado por el solicitante.",
            )

        self._process_issuance(record, review.note)
        return self._to_status(record)

    def retry_remote_delivery(self, request_id: str) -> RegistrationStatusResponse:
        record = self._load_record(request_id)

        if record.applicant.issuance_mode != "remote":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede reintentar entrega para solicitudes remotas.",
            )

        if record.status == "issued":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La solicitud ya fue emitida.",
            )

        if record.status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede reenviar una solicitud rechazada.",
            )

        retry_note = self._strip_pending_delivery_suffix(record.review_note)
        self._process_issuance(record, retry_note)
        return self._to_status(record)

    def _process_issuance(self, record: RegistrationRecord, note: str) -> None:
        """Logica central de emision compartida entre auto-issue, aprobacion y reintento."""
        if self.settings.ec_mode.lower().strip() == "remote":
            try:
                ec_response = self.ec_remote.send_approved_request(record, note)
            except Exception as error:
                self._mark_remote_delivery_pending(record, note, error)
                return

            certificate_pem = ec_response.get("certificate_pem")
            record.status = "issued" if certificate_pem else "approved"
            record.certificate_pem = certificate_pem
            record.review_note = note
            record.updated_at = datetime.now(timezone.utc)
            self._save_record(record)
            return

        if not record.applicant.csr_pem:
            raise ValueError("Se requiere CSR para emision en modo LOCAL")

        certificate_pem = self.openssl.issue_certificate(record.applicant.csr_pem)
        record.status = "issued"
        record.certificate_pem = certificate_pem
        record.review_note = note
        record.updated_at = datetime.now(timezone.utc)
        self._save_record(record)

    def _mark_remote_delivery_pending(self, record: RegistrationRecord, note: str, error: Exception) -> None:
        record.status = "approved"
        record.certificate_pem = None
        record.review_note = self._build_pending_delivery_note(note, error)
        record.updated_at = datetime.now(timezone.utc)
        self._save_record(record)

    def _build_pending_delivery_note(self, note: str, error: Exception) -> str:
        base_note = (note or "Aprobada en la ER").strip()
        return f"{base_note}\n\nEntrega a EC pendiente: {error}"

    def _strip_pending_delivery_suffix(self, note: str | None) -> str:
        normalized = (note or "").strip()
        if not normalized:
            return "Aprobada en la ER"
        return normalized.split("\n\nEntrega a EC pendiente:", 1)[0].strip()

    def reject_request(self, request_id: str, review: ReviewRequest) -> RegistrationStatusResponse:
        record = self._load_record(request_id)
        if record.status == "issued":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede rechazar una solicitud ya emitida.",
            )
        record.status = "rejected"
        record.review_note = review.note
        record.updated_at = datetime.now(timezone.utc)
        self._save_record(record)
        return self._to_status(record)

    def _save_record(
        self,
        record: RegistrationRecord,
        storage_metadata: dict[str, str] | None = None,
    ) -> None:
        # Applicant
        applicant_orm = self.db.query(ApplicantORM).filter_by(dni=record.applicant.dni).first()
        if not applicant_orm:
            applicant_orm = ApplicantORM(
                applicant_id=str(uuid4()),
                dni=record.applicant.dni,
                given_name=record.applicant.given_name,
                first_surname=record.applicant.first_surname,
                second_surname=record.applicant.second_surname,
                email=record.applicant.email
            )
            self.db.add(applicant_orm)
            self.db.flush()
        else:
            applicant_orm.given_name = record.applicant.given_name
            applicant_orm.first_surname = record.applicant.first_surname
            applicant_orm.second_surname = record.applicant.second_surname
            applicant_orm.email = record.applicant.email

        # Request
        orm_record = self.db.get(RegistrationRequestORM, record.request_id)
        if orm_record is None:
            orm_record = RegistrationRequestORM(
                request_id=record.request_id,
                applicant_id=applicant_orm.applicant_id,
                created_at=record.created_at,
            )
            self.db.add(orm_record)

        orm_record.updated_at = record.updated_at
        orm_record.status = record.status
        orm_record.certificate_profile = record.applicant.certificate_profile
        orm_record.issuance_mode = record.applicant.issuance_mode
        orm_record.csr_pem = record.applicant.csr_pem
        orm_record.consent_text = record.applicant.consent_text
        orm_record.review_note = record.review_note

        # Biometric Verification
        biometric_orm = self.db.query(BiometricVerificationORM).filter_by(request_id=record.request_id).first()
        if not biometric_orm:
            biometric_orm = BiometricVerificationORM(
                verification_id=str(uuid4()),
                request_id=record.request_id,
            )
            self.db.add(biometric_orm)

        biometric_orm.success = record.reniec_result.success
        biometric_orm.facial_match = record.reniec_result.facial_match
        biometric_orm.liveness_passed = record.reniec_result.liveness_passed
        biometric_orm.similarity_score = record.reniec_result.similarity_score
        biometric_orm.official_given_name = record.reniec_result.official_given_name
        biometric_orm.official_first_surname = record.reniec_result.official_first_surname
        biometric_orm.official_second_surname = record.reniec_result.official_second_surname
        biometric_orm.source = record.reniec_result.source
        biometric_orm.detail = record.reniec_result.detail
        biometric_orm.device_id = record.applicant.biometric_evidence.device_id
        biometric_orm.capture_ip = record.applicant.biometric_evidence.capture_ip
        biometric_orm.dni_front_path = self._extract_path(storage_metadata, "dni_front_path", biometric_orm.dni_front_path)
        biometric_orm.dni_back_path = self._extract_path(storage_metadata, "dni_back_path", biometric_orm.dni_back_path)
        biometric_orm.selfie_path = self._extract_path(storage_metadata, "selfie_path", biometric_orm.selfie_path)
        biometric_orm.liveness_path = self._extract_path(storage_metadata, "liveness_path", biometric_orm.liveness_path)

        # Certificate
        if record.certificate_pem:
            cert_orm = self.db.query(CertificateORM).filter_by(request_id=record.request_id).first()
            if not cert_orm:
                cert_orm = CertificateORM(
                    certificate_id=str(uuid4()),
                    request_id=record.request_id,
                    certificate_pem=record.certificate_pem,
                    status="active" if record.status == "issued" else "pending"
                )
                self.db.add(cert_orm)
            else:
                cert_orm.certificate_pem = record.certificate_pem

        self.db.commit()
        self.db.refresh(orm_record)

    def _extract_path(
        self,
        storage_metadata: dict[str, Any] | None,
        key: str,
        fallback: str | None,
    ) -> str | None:
        if not storage_metadata:
            return fallback
        value = storage_metadata.get(key)
        return str(value) if value else fallback

    def _load_record(self, request_id: str) -> RegistrationRecord:
        orm_record = self.db.get(RegistrationRequestORM, request_id)
        if not orm_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud no encontrada.",
            )
        
        applicant_payload = {
            "dni": orm_record.applicant.dni if orm_record.applicant else "",
            "given_name": orm_record.applicant.given_name if orm_record.applicant else "",
            "first_surname": orm_record.applicant.first_surname if orm_record.applicant else "",
            "second_surname": orm_record.applicant.second_surname if orm_record.applicant else None,
            "email": orm_record.applicant.email if orm_record.applicant else None,
            "certificate_profile": orm_record.certificate_profile,
            "issuance_mode": orm_record.issuance_mode,
            "csr_pem": orm_record.csr_pem,
            "consent_text": orm_record.consent_text or "Consent text migrated",
            "biometric_evidence": {
                "mode": "facial_remote",
                "device_id": orm_record.biometric_verification.device_id if orm_record.biometric_verification else None,
                "capture_ip": orm_record.biometric_verification.capture_ip if orm_record.biometric_verification else None,
                "selfie_image_b64": "dummy_b64_string_for_validation_min_length_32_characters", # Validation bypass
            }
        }
        
        biometric_orm = orm_record.biometric_verification
        reniec_payload = {
            "success": biometric_orm.success if biometric_orm else False,
            "official_given_name": biometric_orm.official_given_name if biometric_orm else None,
            "official_first_surname": biometric_orm.official_first_surname if biometric_orm else None,
            "official_second_surname": biometric_orm.official_second_surname if biometric_orm else None,
            "facial_match": biometric_orm.facial_match if biometric_orm else False,
            "liveness_passed": biometric_orm.liveness_passed if biometric_orm else False,
            "similarity_score": biometric_orm.similarity_score if biometric_orm else None,
            "verification_id": biometric_orm.verification_id if biometric_orm else None,
            "source": biometric_orm.source if biometric_orm else "unknown",
            "detail": biometric_orm.detail if biometric_orm else "Información migrada",
        }
        
        cert_pem = orm_record.certificate.certificate_pem if orm_record.certificate else None

        return RegistrationRecord.model_validate(
            {
                "request_id": orm_record.request_id,
                "created_at": orm_record.created_at,
                "updated_at": orm_record.updated_at,
                "status": orm_record.status,
                "applicant": applicant_payload,
                "reniec_result": reniec_payload,
                "review_note": orm_record.review_note,
                "certificate_pem": cert_pem,
            }
        )

    def _to_status(self, record: RegistrationRecord) -> RegistrationStatusResponse:
        applicant_summary = {
            "dni": record.applicant.dni,
            "given_name": record.applicant.given_name,
            "first_surname": record.applicant.first_surname,
            "second_surname": record.applicant.second_surname,
            "email": record.applicant.email,
            "issuance_mode": record.applicant.issuance_mode,
        }
        return RegistrationStatusResponse(
            request_id=record.request_id,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
            applicant=applicant_summary,
            review_note=record.review_note,
            reniec_result=record.reniec_result,
            certificate_pem=record.certificate_pem,
        )
