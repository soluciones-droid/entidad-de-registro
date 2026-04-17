import hashlib
import hmac
import json
from time import time
from uuid import uuid4

import httpx

from app.config import Settings
from app.models import RegistrationRecord


class ECRemoteClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_approved_request(self, record: RegistrationRecord, review_note: str) -> dict:
        if not self.settings.ec_api_url:
            raise ValueError("EC_API_URL es obligatorio en modo remoto.")
        if not self.settings.ec_shared_secret or not self.settings.ec_hmac_secret:
            raise ValueError("EC_SHARED_SECRET y EC_HMAC_SECRET son obligatorios en modo remoto.")

        timestamp = str(int(time() * 1000))
        nonce = str(uuid4())
        payload = {
            "sourceSystem": self.settings.ec_source_system,
            "externalRequestId": record.request_id,
            "securityOfficer": self.settings.ec_security_officer,
            "approvedAt": record.updated_at.isoformat().replace("+00:00", "Z"),
            "commonName": f"{record.applicant.given_name} {record.applicant.first_surname} {record.applicant.second_surname or ''}".strip(),
            "profile": record.applicant.certificate_profile,
            "algorithm": "rsa",
            "documentId": record.applicant.dni,
            "documentType": "DNI",
            "email": str(record.applicant.email) if record.applicant.email else None,
            "organization": self.settings.ec_organization,
            "registeredBy": self.settings.ec_registered_by,
            "registeredAt": record.created_at.isoformat().replace("+00:00", "Z"),
            "approvalNotes": review_note or "Verificado presencialmente",
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(
            self.settings.ec_hmac_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "x-er-shared-secret": self.settings.ec_shared_secret,
            "x-er-signature": signature,
            "x-er-timestamp": timestamp,
            "x-er-nonce": nonce,
            "Origin": "http://localhost:3001",
        }

        try:
            with httpx.Client(timeout=self.settings.ec_http_timeout, trust_env=False) as client:
                response = client.post(self.settings.ec_api_url, content=body.encode("utf-8"), headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"Fallo el envio a la EC remota: {error}") from error

        if not response.content:
            return {"status": "accepted"}

        return response.json()
