from pathlib import Path
import subprocess
import tempfile

from app.config import Settings


class OpenSSLCAClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_certificate(self, csr_pem: str) -> str:
        workdir = Path(self.settings.openssl_ca_workdir)
        workdir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csr.pem",
            delete=False,
            dir=workdir,
            encoding="utf-8",
        ) as csr_file:
            csr_file.write(csr_pem)
            csr_path = Path(csr_file.name)

        cert_path = csr_path.with_suffix(".crt.pem")

        try:
            command = [
                self.settings.openssl_bin,
                "ca",
                "-batch",
                "-config",
                self.settings.openssl_ca_config,
                "-extensions",
                self.settings.openssl_ca_profile,
                "-in",
                str(csr_path),
                "-out",
                str(cert_path),
            ]

            process = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode != 0:
                stderr = process.stderr.strip() or process.stdout.strip()
                raise RuntimeError(f"OpenSSL rechazo la emision: {stderr}")

            return cert_path.read_text(encoding="utf-8")
        finally:
            if csr_path.exists():
                csr_path.unlink()
