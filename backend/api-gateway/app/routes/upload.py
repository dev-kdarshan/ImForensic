import httpx
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.storage import save_image

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/analyses")
async def create_analysis(file: UploadFile = File(...)):
    from pathlib import Path
    from uuid import uuid4
    import hashlib
    import httpx

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    extension = allowed_types.get(file.content_type)
    if not extension:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image type.",
        )

    content = await file.read(20 * 1024 * 1024 + 1)

    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB.")

    signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ),
    }

    if not signatures[extension]:
        raise HTTPException(
            status_code=415,
            detail="Image content does not match its declared type.",
        )

    sha256 = hashlib.sha256(content).hexdigest()
    analysis_id = str(uuid4())

    try:
        image_path = save_image(analysis_id, content, extension)
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Could not store the uploaded image.",
        ) from None

    metadata_result = None
    metadata_status = "failed"

    try:
        response = httpx.post(
            "http://127.0.0.1:8001/analyze",
            json={"image_path": image_path},
            timeout=15.0,
        )
        response.raise_for_status()
        metadata_result = response.json()
        metadata_status = "completed"
    except httpx.HTTPError:
        metadata_status = "failed"

    return {
        "analysis_id": analysis_id,
        "filename": Path(file.filename or "image").name,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "sha256": sha256,
        "status": "accepted",
        "storage_ref": Path(image_path).name,
        "metadata_status": metadata_status,
        "metadata": metadata_result,
        "message": (
            "Image stored and metadata analysis completed."
            if metadata_status == "completed"
            else "Image stored; metadata analysis failed."
        ),
    }
