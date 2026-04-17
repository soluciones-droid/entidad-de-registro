from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RegistrationRequestORM(Base):
    __tablename__ = "registration_requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(32), default="pending_manual_review")
    applicant_json: Mapped[str] = mapped_column(Text())
    reniec_result_json: Mapped[str] = mapped_column(Text())
    review_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    certificate_pem: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dni_front_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dni_back_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selfie_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    liveness_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    issuance_mode: Mapped[str] = mapped_column(String(20), default="local")


class CaptureSessionORM(Base):
    __tablename__ = "capture_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, completed
    selfie_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
