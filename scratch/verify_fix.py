
import sqlite3
import json
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from typing import Literal

# Re-matching models from app/models.py
class ApplicantSummary(BaseModel):
    dni: str
    given_name: str
    first_surname: str
    second_surname: str | None = None
    email: str | None = None
    issuance_mode: Literal["local", "remote"] = "local"

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

class RegistrationStatusResponse(BaseModel):
    request_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    applicant: ApplicantSummary
    review_note: str | None = None
    reniec_result: ReniecIdentityResult
    certificate_pem: str | None = None

def check_db():
    conn = sqlite3.connect('data/ra.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT request_id, status, created_at, updated_at, applicant_json, reniec_result_json, review_note, certificate_pem FROM registration_requests LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            request_id, status, created_at, updated_at, applicant_json, reniec_json, review_note, cert_pem = row
            print(f"ID: {request_id}")
            
            applicant_payload = json.loads(applicant_json)
            reniec_payload = json.loads(reniec_json)
            
            # Mimic RegistrationService.list_requests logic
            summary = {
                "dni": applicant_payload.get("dni", "N/A"),
                "given_name": applicant_payload.get("given_name", "N/A"),
                "first_surname": applicant_payload.get("first_surname", "N/A"),
                "second_surname": applicant_payload.get("second_surname"),
                "email": applicant_payload.get("email"),
                "issuance_mode": applicant_payload.get("issuance_mode") or "local",
            }
            
            try:
                # This validates our Pydantic mapping
                resp = RegistrationStatusResponse(
                    request_id=request_id,
                    status=status,
                    created_at=datetime.fromisoformat(created_at.replace('Z', '+00:00')) if isinstance(created_at, str) else datetime.now(),
                    updated_at=datetime.fromisoformat(updated_at.replace('Z', '+00:00')) if isinstance(updated_at, str) else datetime.now(),
                    applicant=summary,
                    review_note=review_note,
                    reniec_result=reniec_payload,
                    certificate_pem=cert_pem
                )
                print(f"SUCCESS mapping {request_id}")
                print(f"Mode: {resp.applicant.issuance_mode}")
            except Exception as e:
                print(f"FAILED mapping {request_id}: {e}")
            
            print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
