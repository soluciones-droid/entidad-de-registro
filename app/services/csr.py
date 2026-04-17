from pathlib import Path
import re
import subprocess
import tempfile

from app.config import Settings
from app.models import RegistrationRecord


class CSRValidationError(ValueError):
    """Raised when the CSR does not match the validated identity."""


class CSRInspector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_subject(self, record: RegistrationRecord) -> None:
        subject = self.extract_subject(record.applicant.csr_pem)
        expected_cn = self._build_expected_common_name(record)
        actual_cn = subject.get("CN")
        actual_serial = subject.get("serialNumber")

        if not actual_cn:
            raise CSRValidationError("El CSR no contiene CN en el subject.")
        if self._normalize(actual_cn) != self._normalize(expected_cn):
            raise CSRValidationError(
                f"El CN del CSR no coincide con la identidad validada. Esperado: {expected_cn}"
            )

        if not actual_serial:
            raise CSRValidationError("El CSR no contiene serialNumber con el DNI del titular.")
        normalized_serial = re.sub(r"[^0-9]", "", actual_serial)
        if normalized_serial != record.applicant.dni:
            raise CSRValidationError("El serialNumber del CSR no coincide con el DNI validado.")

    def extract_subject(self, csr_pem: str) -> dict[str, str]:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csr.pem",
            delete=False,
            encoding="utf-8",
        ) as csr_file:
            csr_file.write(csr_pem)
            csr_path = Path(csr_file.name)

        try:
            command = [
                self.settings.openssl_bin,
                "req",
                "-in",
                str(csr_path),
                "-noout",
                "-subject",
                "-nameopt",
                "RFC2253",
            ]
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode != 0:
                stderr = process.stderr.strip() or process.stdout.strip()
                raise CSRValidationError(f"No se pudo leer el subject del CSR: {stderr}")

            return self._parse_subject_output(process.stdout.strip())
        finally:
            if csr_path.exists():
                csr_path.unlink()

    def _parse_subject_output(self, output: str) -> dict[str, str]:
        prefix = "subject="
        subject_line = output[len(prefix):] if output.startswith(prefix) else output
        result: dict[str, str] = {}
        for component in self._split_rfc2253(subject_line):
            if "=" not in component:
                continue
            key, value = component.split("=", 1)
            result[key.strip()] = value.strip()
        return result

    def _split_rfc2253(self, subject_line: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        escaped = False
        for char in subject_line:
            if escaped:
                current.append(char)
                escaped = False
                continue
            if char == "\\":
                current.append(char)
                escaped = True
                continue
            if char == ",":
                parts.append("".join(current))
                current = []
                continue
            current.append(char)
        if current:
            parts.append("".join(current))
        return parts

    def _build_expected_common_name(self, record: RegistrationRecord) -> str:
        parts = [
            record.reniec_result.official_given_name or record.applicant.given_name,
            record.reniec_result.official_first_surname or record.applicant.first_surname,
            record.reniec_result.official_second_surname or record.applicant.second_surname or "",
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())

    def _normalize(self, value: str) -> str:
        normalized = value.upper().replace(",", " ")
        return " ".join(normalized.split())
