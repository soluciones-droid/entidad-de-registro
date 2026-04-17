from pathlib import Path

import httpx

from app.config import Settings
from app.models import CertificateRequestCreate, ReniecIdentityResult


class ReniecHTTPClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_identity(self, request: CertificateRequestCreate) -> ReniecIdentityResult:
        if not self.settings.reniec_api_url or not self.settings.reniec_api_token:
            raise ValueError("RENIEC_API_URL y RENIEC_API_TOKEN son obligatorios en modo api.")

        cert = self._build_client_cert()
        payload = {
            "dni": request.dni,
            "given_name": request.given_name,
            "first_surname": request.first_surname,
            "second_surname": request.second_surname,
            "certificate_profile": request.certificate_profile,
            "device_id": request.biometric_evidence.device_id,
            "capture_ip": request.biometric_evidence.capture_ip,
            "images": {
                "dni_front_jpg_b64": request.biometric_evidence.dni_front_image_b64,
                "dni_back_jpg_b64": request.biometric_evidence.dni_back_image_b64,
                "selfie_jpg_b64": request.biometric_evidence.selfie_image_b64,
                "liveness_jpg_b64": request.biometric_evidence.liveness_image_b64,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.reniec_api_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.settings.reniec_http_timeout,
                verify=self.settings.reniec_verify_ssl,
                cert=cert,
                trust_env=False,
            ) as client:
                response = client.post(
                    self.settings.reniec_api_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"Fallo la validacion biometrica remota: {error}") from error

        body = response.json()
        return ReniecIdentityResult(
            success=bool(body.get("success")),
            official_given_name=body.get("official_given_name"),
            official_first_surname=body.get("official_first_surname"),
            official_second_surname=body.get("official_second_surname"),
            facial_match=bool(body.get("facial_match")),
            liveness_passed=bool(body.get("liveness_passed")),
            similarity_score=body.get("similarity_score"),
            verification_id=body.get("verification_id") or body.get("transaction_id"),
            source=body.get("source", "reniec-api"),
            detail=body.get("detail", "Respuesta recibida del proveedor biometrico."),
        )

    def _build_client_cert(self) -> str | tuple[str, str] | None:
        cert_path = self.settings.reniec_client_cert_path
        key_path = self.settings.reniec_client_key_path
        if cert_path and key_path:
            return (str(cert_path), str(key_path))
        if cert_path:
            return str(cert_path)
        return None
