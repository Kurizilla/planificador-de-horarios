"""
Shared utilities (upload size limit, email whitelist, etc.).
"""
from fastapi import HTTPException, UploadFile, status


def email_allowed(email: str) -> bool:
    """True if USER_WHITELIST is empty or the email is in it (case-insensitive)."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.user_whitelist:
        return True
    return email.strip().lower() in settings.user_whitelist


def read_upload_file_with_limit(upload: UploadFile, max_size: int) -> bytes:
    """
    Read upload file content without loading more than max_size bytes into memory.
    Raises HTTP 413 if the file exceeds max_size.
    """
    chunk_size = 512 * 1024  # 512 KB — reasonable for Excel uploads (fewer reads than 64 KB)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Max 20MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)
