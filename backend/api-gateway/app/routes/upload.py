from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.services.repository import get_analysis, save_analysis
from app.services.storage import save_image

router = APIRouter()
MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
METADATA_SERVICE_URL = os.getenv("METADATA_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
METADATA_TIMEOUT = float(os.getenv("METADATA_TIMEOUT_SECONDS", "30"))


def _validate_image(content: bytes, extension: str) -> None:
    signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    if not signatures[extension]:
        raise HTTPException(status_code=415, detail="Image content does not match its declared type.")
    try:
        with Image.open(__import__("io").BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=415, detail="Unsupported image format.")
            if image.width * image.height > 40_000_000:
                raise HTTPException(status_code=413, detail="Image dimensions exceed the 40-megapixel limit.")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid safe image.") from None


@router.post("/analyses", status_code=201)
async def create_analysis(file: UploadFile = File(...)):
    extension = ALLOWED_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG and WebP images are supported.")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Image exceeds {MAX_UPLOAD_MB} MB.")
    _validate_image(content, extension)

    analysis_id = str(uuid4())
    filename = Path(file.filename or "image").name.replace("\\", "_")
    sha256 = hashlib.sha256(content).hexdigest()
    try:
        stored_path = save_image(analysis_id, content, extension)
    except OSError:
        raise HTTPException(status_code=500, detail="Could not store the uploaded image.") from None

    created_at = datetime.now(timezone.utc).isoformat()
    result = None
    error = None
    status = "failed"
    try:
        async with httpx.AsyncClient(timeout=METADATA_TIMEOUT) as client:
            response = await client.post(
                f"{METADATA_SERVICE_URL}/analyze",
                files={"file": (filename, content, file.content_type)},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("file", {}).get("sha256") != sha256:
                raise RuntimeError("Metadata service hash did not match the gateway hash.")
            status = "completed"
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        error = f"Metadata analysis unavailable: {type(exc).__name__}"
        status = "partial"

    record = {
        "analysis_id": analysis_id,
        "status": status,
        "created_at": created_at,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "sha256": sha256,
        "storage_ref": Path(stored_path).name,
        "result": result,
        "error": error,
    }
    save_analysis(record)
    await file.close()
    return record


@router.get("/analyses/{analysis_id}")
def read_analysis(analysis_id: str):
    record = get_analysis(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return record
