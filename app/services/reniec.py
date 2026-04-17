from app.config import Settings
from app.models import CertificateRequestCreate, ReniecIdentityResult
from app.services.reniec_http import ReniecHTTPClient


class ReniecClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http_client = ReniecHTTPClient(settings)

    def verify_identity(self, request: CertificateRequestCreate) -> ReniecIdentityResult:
        mode = self.settings.reniec_mode.lower().strip()
        if mode == "mock":
            return self._verify_mock(request)
        if mode == "api":
            return self.http_client.verify_identity(request)
        raise ValueError(f"Modo RENIEC no soportado: {self.settings.reniec_mode}")

    def _verify_mock(self, request: CertificateRequestCreate) -> ReniecIdentityResult:
        return ReniecIdentityResult(
            success=True,
            official_given_name=request.given_name.upper(),
            official_first_surname=request.first_surname.upper(),
            official_second_surname=(request.second_surname or "").upper() or None,
            facial_match=True,
            liveness_passed=True,
            similarity_score=0.98,
            verification_id=f"MOCK-{request.dni}",
            source="reniec-mock",
            detail="Validacion facial remota simulada. No usar en produccion.",
        )
