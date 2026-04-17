from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


RequestStatus = Literal["pending_manual_review", "approved", "rejected", "issued"]


class BiometricEvidence(BaseModel):
    mode: Literal["facial_remote"] = "facial_remote"
    dni_front_image_b64: str | None = Field(default=None, min_length=32)
    dni_back_image_b64: str | None = Field(default=None, min_length=32)
    selfie_image_b64: str = Field(min_length=32)
    liveness_image_b64: str | None = Field(default=None, min_length=32)
    device_id: str | None = Field(default=None, max_length=120)
    capture_ip: str | None = Field(default=None, max_length=64)


class CertificateRequestCreate(BaseModel):
    dni: str = Field(min_length=8, max_length=8)
    given_name: str = Field(min_length=2, max_length=80)
    first_surname: str = Field(min_length=2, max_length=80)
    second_surname: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    certificate_profile: str = Field(default="natural_person", max_length=50)
    issuance_mode: Literal["local", "remote"] = Field(default="local")
    csr_pem: str | None = Field(default=None)
    consent_text: str = Field(min_length=10, max_length=2000)
    biometric_evidence: BiometricEvidence

    @field_validator("dni")
    @classmethod
    def validate_dni(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("El DNI debe contener solo digitos.")
        return value

    @field_validator("csr_pem")
    @classmethod
    def validate_csr_pem(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "BEGIN CERTIFICATE REQUEST" not in value:
            raise ValueError("El CSR debe estar en formato PEM.")
        return value.strip()


class ReniecIdentityResult(BaseModel):
    success: bool
    official_given_name: str | None = None
    official_first_surname: str | None = None
    official_second_surname: str | None = None
    facial_match: bool = False
    liveness_passed: bool = False
    similarity_score: float | None = None
    verification_id: str | None = None
    source: str = "unknown"
    detail: str = "Información migrada"


class RegistrationRecord(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: RequestStatus = "pending_manual_review"
    applicant: CertificateRequestCreate
    reniec_result: ReniecIdentityResult
    review_note: str | None = None
    certificate_pem: str | None = None


class ApplicantSummary(BaseModel):
    dni: str
    given_name: str
    first_surname: str
    second_surname: str | None = None
    email: str | None = None
    issuance_mode: Literal["local", "remote"] = "local"


class RegistrationStatusResponse(BaseModel):
    request_id: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    applicant: ApplicantSummary
    review_note: str | None = None
    reniec_result: ReniecIdentityResult
    certificate_pem: str | None = None


class ReviewRequest(BaseModel):
    note: str = Field(min_length=3, max_length=500)


class HealthResponse(BaseModel):
    status: str
    app: str


class CaptureSessionResponse(BaseModel):
    session_id: str
    expires_at: datetime
    status: str
    selfie_b64: str | None = None
