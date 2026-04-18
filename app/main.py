import base64
from pathlib import Path
from ipaddress import ip_address

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal, init_db
from app.models import (
    BiometricEvidence,
    CaptureSessionResponse,
    CertificateRequestCreate,
    HealthResponse,
    RegistrationStatusResponse,
    ReviewRequest,
)
from app.security import require_api_key
from app.services.registration import RegistrationService
from app.services.storage import EvidenceStorage
from app.db_models import CaptureSessionORM, RegistrationRequestORM
from uuid import uuid4
from datetime import datetime, timezone, timedelta

app = FastAPI(
    title="Entidad de Registro RA",
    version="0.1.0",
    description="RA para integrar validacion de identidad con una CA existente en OpenSSL.",
)

# Configuración de CORS para el frontend (Vite corre en 5173 por defecto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir al origen del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# Montar archivos estáticos
# Se asume que la carpeta 'app/static' existirá
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_registration_service(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> RegistrationService:
    return RegistrationService(settings, db)


@app.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@app.post("/api/v1/requests", response_model=RegistrationStatusResponse)
def create_request(
    payload: CertificateRequestCreate,
    service: RegistrationService = Depends(get_registration_service),
) -> RegistrationStatusResponse:
    return service.create_request(payload)


@app.get("/api/v1/requests", response_model=list[RegistrationStatusResponse])
def list_requests(
    status: str | None = None,
    service: RegistrationService = Depends(get_registration_service),
    _: None = Depends(require_api_key),
) -> list[RegistrationStatusResponse]:
    return service.list_requests(status_filter=status)


@app.post("/api/v1/requests/multipart", response_model=RegistrationStatusResponse)
async def create_request_multipart(
    dni: str = Form(...),
    given_name: str = Form(...),
    first_surname: str = Form(...),
    second_surname: str | None = Form(default=None),
    email: str | None = Form(default=None),
    certificate_profile: str = Form(default="natural_person"),
    csr_pem: str | None = Form(default=None),
    consent_text: str = Form(...),
    issuance_mode: str = Form(default="local"),
    device_id: str | None = Form(default=None),
    capture_ip: str | None = Form(default=None),
    dni_front_image: UploadFile | None = File(default=None),
    dni_back_image: UploadFile | None = File(default=None),
    selfie_image: UploadFile = File(...),
    liveness_image: UploadFile | None = File(default=None),
    service: RegistrationService = Depends(get_registration_service),
    settings: Settings = Depends(get_settings),
) -> RegistrationStatusResponse:
    if capture_ip:
        try:
            ip_address(capture_ip)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="capture_ip no es una IP valida.",
            ) from error

    uploads = [selfie_image]
    if dni_front_image:
        uploads.append(dni_front_image)
    if dni_back_image:
        uploads.append(dni_back_image)
    if liveness_image:
        uploads.append(liveness_image)
    for upload in uploads:
        if upload.content_type not in {"image/jpeg", "image/jpg"}:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Solo se aceptan imagenes JPG/JPEG.",
            )

    storage = EvidenceStorage(settings)
    dni_front_bytes = await dni_front_image.read() if dni_front_image else None
    selfie_bytes = await selfie_image.read()
    dni_back_bytes = await dni_back_image.read() if dni_back_image else None
    liveness_bytes = await liveness_image.read() if liveness_image else None
    request_id = service.generate_request_id()

    storage_metadata = {
        "selfie_path": storage.save_bytes(
            request_id,
            selfie_image.filename or "selfie.jpg",
            selfie_bytes,
        ),
    }
    if dni_front_image:
        storage_metadata["dni_front_path"] = storage.save_bytes(
            request_id,
            dni_front_image.filename or "dni_front.jpg",
            dni_front_bytes,
        )
    if dni_back_bytes:
        storage_metadata["dni_back_path"] = storage.save_bytes(
            request_id,
            dni_back_image.filename or "dni_back.jpg",
            dni_back_bytes,
        )
    if liveness_bytes:
        storage_metadata["liveness_path"] = storage.save_bytes(
            request_id,
            liveness_image.filename or "liveness.jpg",
            liveness_bytes,
        )

    payload = CertificateRequestCreate(
        dni=dni,
        given_name=given_name,
        first_surname=first_surname,
        second_surname=second_surname,
        email=email,
        certificate_profile=certificate_profile,
        issuance_mode=issuance_mode,
        csr_pem=csr_pem,
        consent_text=consent_text,
        biometric_evidence=BiometricEvidence(
            dni_front_image_b64=base64.b64encode(dni_front_bytes).decode("ascii") if dni_front_bytes else None,
            dni_back_image_b64=base64.b64encode(dni_back_bytes).decode("ascii") if dni_back_bytes else None,
            selfie_image_b64=base64.b64encode(selfie_bytes).decode("ascii"),
            liveness_image_b64=base64.b64encode(liveness_bytes).decode("ascii") if liveness_bytes else None,
            device_id=device_id,
            capture_ip=capture_ip,
        ),
    )
    return service.create_request(
        payload,
        request_id=request_id,
        storage_metadata=storage_metadata,
    )


@app.get("/api/v1/requests/{request_id}", response_model=RegistrationStatusResponse)
def get_request(
    request_id: str,
    service: RegistrationService = Depends(get_registration_service),
    _: None = Depends(require_api_key),
) -> RegistrationStatusResponse:
    return service.get_request(request_id)


@app.post("/api/v1/requests/{request_id}/approve", response_model=RegistrationStatusResponse)
def approve_request(
    request_id: str,
    review: ReviewRequest,
    service: RegistrationService = Depends(get_registration_service),
    _: None = Depends(require_api_key),
) -> RegistrationStatusResponse:
    return service.approve_request(request_id, review)


@app.post("/api/v1/requests/{request_id}/retry-ec-delivery", response_model=RegistrationStatusResponse)
def retry_ec_delivery(
    request_id: str,
    service: RegistrationService = Depends(get_registration_service),
    _: None = Depends(require_api_key),
) -> RegistrationStatusResponse:
    return service.retry_remote_delivery(request_id)


@app.post("/api/v1/requests/{request_id}/reject", response_model=RegistrationStatusResponse)
def reject_request(
    request_id: str,
    review: ReviewRequest,
    service: RegistrationService = Depends(get_registration_service),
    _: None = Depends(require_api_key),
) -> RegistrationStatusResponse:
    return service.reject_request(request_id, review)


@app.get("/api/v1/requests/{request_id}/evidence/{evidence_key}")
def get_evidence(
    request_id: str,
    evidence_key: str,
    service: RegistrationService = Depends(get_registration_service),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_api_key),
) -> FileResponse:
    # Obtener el registro para sacar el path
    record = service.db.get(RegistrationRequestORM, request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")

    path_map = {
        "dni_front": record.dni_front_path,
        "dni_back": record.dni_back_path,
        "selfie": record.selfie_path,
        "liveness": record.liveness_path,
    }

    file_path = path_map.get(evidence_key)
    if not file_path or not settings.ra_uploads_dir.joinpath(file_path).exists():
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

    return FileResponse(settings.ra_uploads_dir.joinpath(file_path))


@app.post("/api/v1/sessions", response_model=CaptureSessionResponse)
def init_capture_session(
    db: Session = Depends(get_db),
) -> CaptureSessionResponse:
    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    new_session = CaptureSessionORM(
        session_id=session_id,
        expires_at=expires_at,
        status="pending"
    )
    db.add(new_session)
    db.commit()
    return CaptureSessionResponse(
        session_id=session_id,
        expires_at=expires_at,
        status="pending"
    )


@app.get("/api/v1/sessions/{session_id}", response_model=CaptureSessionResponse)
def get_capture_session(
    session_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
) -> CaptureSessionResponse:
    session = db.query(CaptureSessionORM).filter(CaptureSessionORM.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    
    # Verificar expiracion
    if datetime.now(timezone.utc) > session.expires_at.replace(tzinfo=timezone.utc):
        session.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="La sesion ha expirado.")

    selfie_b64 = None
    if session.selfie_path:
        storage = EvidenceStorage(settings)
        # Intentamos resolver la ruta absoluta o relativa de forma segura
        raw_path = Path(session.selfie_path)
        if raw_path.is_absolute():
            file_path = raw_path
        else:
            file_path = settings.ra_uploads_dir.joinpath(raw_path)
        if file_path.exists():
            with open(file_path, "rb") as f:
                selfie_b64 = base64.b64encode(f.read()).decode("ascii")

    return CaptureSessionResponse(
        session_id=session.session_id,
        expires_at=session.expires_at,
        status=session.status,
        selfie_b64=selfie_b64
    )


@app.post("/api/v1/sessions/{session_id}/upload")
async def upload_capture_session(
    session_id: str,
    selfie_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    session = db.query(CaptureSessionORM).filter(CaptureSessionORM.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    
    if selfie_image.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=415, detail="Solo se aceptan imagenes JPG.")

    storage = EvidenceStorage(settings)
    content = await selfie_image.read()
    
    filename = f"temp_selfie_{session_id}.jpg"
    path = storage.save_bytes(f"temp_{session_id}", filename, content)
    
    session.selfie_path = path
    session.status = "completed"
    db.commit()
    
    return {"status": "ok", "message": "Imagen subida con exito"}
