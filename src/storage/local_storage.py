"""Local filesystem storage (replaces Azure Blob Storage)."""

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("local_store/uploads")


class LocalStorage:
    def __init__(self):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, filename: str) -> str:
        path = UPLOAD_DIR / filename
        path.write_bytes(content)
        logger.info(f"Saved file: {path}")
        return str(path)

    def load_file(self, filename: str) -> Optional[bytes]:
        path = UPLOAD_DIR / filename
        if path.exists():
            return path.read_bytes()
        return None

    def list_files(self):
        return [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]

    def delete_file(self, filename: str) -> bool:
        path = UPLOAD_DIR / filename
        if path.exists():
            path.unlink()
            return True
        return False
