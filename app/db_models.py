from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ApplicantORM(Base):
    __tablename__ = "applicants"

    applicant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dni: Mapped[str] = mapped_column(String(20), index=True)
    given_name: Mapped[str] = mapped_column(String(80))
    first_surname: Mapped[str] = mapped_column(String(80))
    second_surname: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    requests: Mapped[List["RegistrationRequestORM"]] = relationship(back_populates="applicant", cascade="all, delete-orphan")


class RegistrationRequestORM(Base):
    __tablename__ = "registration_requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    applicant_id: Mapped[str] = mapped_column(ForeignKey("applicants.applicant_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(32), default="pending_manual_review")
    
    certificate_profile: Mapped[str] = mapped_column(String(50), default="natural_person")
    issuance_mode: Mapped[str] = mapped_column(String(20), default="local")
    csr_pem: Mapped[str | None] = mapped_column(Text(), nullable=True)
    consent_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text(), nullable=True)

    applicant: Mapped["ApplicantORM"] = relationship(back_populates="requests")
    biometric_verification: Mapped[Optional["BiometricVerificationORM"]] = relationship(back_populates="request", cascade="all, delete-orphan", uselist=False)
    certificate: Mapped[Optional["CertificateORM"]] = relationship(back_populates="registration_request", cascade="all, delete-orphan", uselist=False)


class BiometricVerificationORM(Base):
    __tablename__ = "biometric_verifications"

    verification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("registration_requests.request_id"), unique=True)
    
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    facial_match: Mapped[bool] = mapped_column(Boolean, default=False)
    liveness_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    official_given_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    official_first_surname: Mapped[str | None] = mapped_column(String(80), nullable=True)
    official_second_surname: Mapped[str | None] = mapped_column(String(80), nullable=True)
    
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capture_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    dni_front_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dni_back_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selfie_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    liveness_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    request: Mapped["RegistrationRequestORM"] = relationship(back_populates="biometric_verification")


class CertificateORM(Base):
    __tablename__ = "certificates"

    certificate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("registration_requests.request_id"), unique=True)
    
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    certificate_pem: Mapped[str] = mapped_column(Text())
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active") # active, revoked, expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    registration_request: Mapped["RegistrationRequestORM"] = relationship(back_populates="certificate")
    revocation_requests: Mapped[List["RevocationRequestORM"]] = relationship(back_populates="certificate", cascade="all, delete-orphan")


class RevocationRequestORM(Base):
    __tablename__ = "revocation_requests"

    revocation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    certificate_id: Mapped[str] = mapped_column(ForeignKey("certificates.certificate_id"))
    
    reason: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(32), default="pending_approval") # pending_approval, approved, rejected
    request_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolution_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    certificate: Mapped["CertificateORM"] = relationship(back_populates="revocation_requests")


class CaptureSessionORM(Base):
    __tablename__ = "capture_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, completed
    selfie_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
