from pathlib import Path
from uuid import uuid4

from app.config import Settings


class EvidenceStorage:
    def __init__(self, settings: Settings) -> None:
        self.base_dir = Path(settings.ra_uploads_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, request_id: str, filename: str, payload: bytes) -> str:
        safe_name = filename.lower().replace(" ", "_")
        target_dir = self.base_dir / request_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4()}_{safe_name}"
        target_path.write_bytes(payload)
        return str(target_path.relative_to(self.base_dir))
