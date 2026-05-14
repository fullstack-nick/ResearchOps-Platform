import re
import uuid
from hashlib import sha256
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings

PDF_CONTENT_TYPE = "application/pdf"
SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str | None) -> str:
    normalized = (filename or "document.pdf").replace("\\", "/")
    raw_name = PurePosixPath(normalized).name
    if not raw_name:
        raw_name = "document.pdf"
    cleaned = SAFE_NAME_PATTERN.sub("_", raw_name).strip("._")
    if not cleaned:
        cleaned = "document.pdf"
    if len(cleaned) > 180:
        stem = Path(cleaned).stem[:150]
        suffix = Path(cleaned).suffix[:20]
        cleaned = f"{stem}{suffix}"
    return cleaned


def validate_pdf_upload(upload: UploadFile) -> str:
    safe_filename = sanitize_filename(upload.filename)
    if Path(safe_filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported in Phase 1.",
        )
    if upload.content_type != PDF_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload content type must be application/pdf.",
        )
    return safe_filename


async def read_limited_upload(upload: UploadFile, max_bytes: int) -> tuple[bytes, str]:
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF uploads must be at most {max_bytes} bytes.",
        )
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file does not look like a PDF.",
        )
    return content, sha256(content).hexdigest()


def write_document_bytes(
    settings: Settings,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    safe_filename: str,
    content: bytes,
) -> str:
    storage_root = settings.storage_dir.resolve()
    document_dir = storage_root / str(document_id)
    document_dir.mkdir(parents=True, exist_ok=True)
    destination = (document_dir / f"{version_id}_{safe_filename}").resolve()
    if not destination.is_relative_to(storage_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolved upload path is outside the configured storage directory.",
        )
    destination.write_bytes(content)
    return str(destination.relative_to(storage_root))


def resolve_storage_path(settings: Settings, relative_storage_path: str) -> Path:
    storage_root = settings.storage_dir.resolve()
    resolved = (storage_root / relative_storage_path).resolve()
    if not resolved.is_relative_to(storage_root):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return resolved
