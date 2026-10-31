"""UUID-scoped local image storage; callers never supply filesystem paths."""
import os
from pathlib import Path
from uuid import UUID
STORAGE_DIR = Path(os.getenv("IMFORENSIC_UPLOAD_DIR", "./data/uploads")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
def save_image(analysis_id: str, content: bytes, extension: str) -> str:
    safe_id = str(UUID(analysis_id))
    if extension not in {".jpg", ".png", ".webp"}: raise ValueError("Unsupported extension")
    destination = STORAGE_DIR / f"{safe_id}{extension}"
    temporary = STORAGE_DIR / f".{safe_id}.tmp"
    try:
        with temporary.open("xb") as output: output.write(content)
        os.replace(temporary, destination)
    finally: temporary.unlink(missing_ok=True)
    return str(destination)
def image_path(storage_ref: str) -> Path:
    if not storage_ref or Path(storage_ref).name != storage_ref: raise ValueError("Invalid stored object reference")
    candidate = (STORAGE_DIR / storage_ref).resolve()
    if candidate.parent != STORAGE_DIR or candidate.suffix.lower() not in {".jpg", ".png", ".webp"}:
        raise ValueError("Invalid stored object reference")
    return candidate
def delete_image(analysis_id: str) -> bool:
    safe_id = str(UUID(analysis_id)); deleted = False
    for extension in (".jpg", ".png", ".webp"):
        path = STORAGE_DIR / f"{safe_id}{extension}"
        if path.exists(): path.unlink(); deleted = True
    return deleted
