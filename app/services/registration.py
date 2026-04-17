from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db_models import RegistrationRequestORM
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
        self._save_record(record, storage_metadata=storage_metadata)
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
                applicant_payload = json.loads(orm_record.applicant_json)
                reniec_payload = json.loads(orm_record.reniec_result_json)
                
                # Optimización Crítica: Construimos el resumen sin validar el objeto completo
                summary = {
                    "dni": applicant_payload.get("dni", "N/A"),
                    "given_name": applicant_payload.get("given_name", "N/A"),
                    "first_surname": applicant_payload.get("first_surname", "N/A"),
                    "second_surname": applicant_payload.get("second_surname"),
                    "email": applicant_payload.get("email"),
                    "issuance_mode": applicant_payload.get("issuance_mode") or "local",
                }
                
                results.append(RegistrationStatusResponse(
                    request_id=orm_record.request_id,
                    status=orm_record.status,
                    created_at=orm_record.created_at,
                    updated_at=orm_record.updated_at,
                    applicant=summary,
                    review_note=orm_record.review_note,
                    reniec_result=reniec_payload,
                    certificate_pem=orm_record.certificate_pem
                ))
            except Exception as e:
                print(f"ERROR: Skipping request {orm_record.request_id} due to mapping error: {e}")
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
        # Validación de CSR solo si está presente o si es modo LOCAL
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
                detail="El modo de emisión LOCAL requiere un CSR generado por el solicitante.",
            )

        if self.settings.ec_mode.lower().strip() == "remote":
            ec_response = self.ec_remote.send_approved_request(record, review.note)
            certificate_pem = ec_response.get("certificate_pem")
            record.status = "issued" if certificate_pem else "approved"
            record.certificate_pem = certificate_pem
        else:
            # En modo local el CSR es obligatorio (validado arriba)
            certificate_pem = self.openssl.issue_certificate(record.applicant.csr_pem)
            record.status = "issued"
            record.certificate_pem = certificate_pem
        record.review_note = review.note
        record.updated_at = datetime.now(timezone.utc)
        self._save_record(record)
        return self._to_status(record)

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
        payload = record.model_dump(mode="json")
        orm_record = self.db.get(RegistrationRequestORM, record.request_id)
        if orm_record is None:
            orm_record = RegistrationRequestORM(
                request_id=record.request_id,
                created_at=record.created_at,
            )
            self.db.add(orm_record)

        orm_record.updated_at = record.updated_at
        orm_record.status = record.status
        orm_record.applicant_json = json.dumps(payload["applicant"], ensure_ascii=False)
        orm_record.reniec_result_json = json.dumps(payload["reniec_result"], ensure_ascii=False)
        orm_record.review_note = record.review_note
        orm_record.certificate_pem = record.certificate_pem
        orm_record.issuance_mode = record.applicant.issuance_mode
        orm_record.dni_front_path = self._extract_path(storage_metadata, "dni_front_path", orm_record.dni_front_path)
        orm_record.dni_back_path = self._extract_path(storage_metadata, "dni_back_path", orm_record.dni_back_path)
        orm_record.selfie_path = self._extract_path(storage_metadata, "selfie_path", orm_record.selfie_path)
        orm_record.liveness_path = self._extract_path(storage_metadata, "liveness_path", orm_record.liveness_path)
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
        applicant_payload = json.loads(orm_record.applicant_json)
        reniec_payload = json.loads(orm_record.reniec_result_json)
        return RegistrationRecord.model_validate(
            {
                "request_id": orm_record.request_id,
                "created_at": orm_record.created_at,
                "updated_at": orm_record.updated_at,
                "status": orm_record.status,
                "applicant": applicant_payload,
                "reniec_result": reniec_payload,
                "review_note": orm_record.review_note,
                "certificate_pem": orm_record.certificate_pem,
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
