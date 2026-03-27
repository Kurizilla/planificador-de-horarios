"""
Storage abstracto: LocalStorageBackend.
Diseño permite S3/GCS después.
"""
import re
from pathlib import Path
from typing import BinaryIO, Union

from app.core.config import get_settings


def _sanitize_path_segment(segment: str) -> str:
    """Evita path traversal; solo alfanuméricos, guión, underscore."""
    if not segment:
        return "_"
    safe = re.sub(r"[^a-zA-Z0-9_\-.]", "_", segment)
    return safe[:200] or "_"


class LocalStorageBackend:
    def __init__(self) -> None:
        self.root = get_settings().storage_root

    def _path(self, rel_path: str) -> Path:
        """Path absoluto; rel_path no debe contener '..'."""
        if ".." in rel_path or rel_path.startswith("/"):
            raise ValueError("Invalid path")
        full = (self.root / rel_path).resolve()
        if not str(full).startswith(str(self.root.resolve())):
            raise ValueError("Path outside storage root")
        return full

    def store(self, rel_path: str, content: Union[BinaryIO, bytes], *, mkdir: bool = True) -> Path:
        full = self._path(rel_path)
        if mkdir:
            full.parent.mkdir(parents=True, exist_ok=True)
        data = content.read() if hasattr(content, "read") else content
        full.write_bytes(data)
        return full

    def read(self, rel_path: str) -> bytes:
        return self._path(rel_path).read_bytes()

    def exists(self, rel_path: str) -> bool:
        return self._path(rel_path).exists()

    def get_download_path(self, rel_path: str) -> Path:
        """Para streaming: devuelve el Path (el caller hace stream)."""
        return self._path(rel_path)

    def delete_tree(self, rel_dir: str) -> None:
        """Elimina recursivamente un directorio dentro del storage root. Silencioso si no existe."""
        import shutil
        try:
            full = self._path(rel_dir)
            if full.exists() and full.is_dir():
                shutil.rmtree(full, ignore_errors=True)
        except Exception:
            pass


def get_storage() -> LocalStorageBackend:
    return LocalStorageBackend()
