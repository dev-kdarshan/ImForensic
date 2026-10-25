
import os
from pathlib import Path
from uuid import UUID

STORAGE_DIR = Path(__file__).resolve().parents[2] / "temp_uploads"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_image(analysis_id: str, content: bytes, extension: str) -> str:
    """Save an image under a server-generated UUID filename."""
    safe_id = str(UUID(analysis_id))

    if extension not in {".jpg", ".png", ".webp"}:
        raise ValueError("Unsupported extension")

    destination = STORAGE_DIR / f"{safe_id}{extension}"
    temporary = STORAGE_DIR / f".{safe_id}.tmp"

    try:
        with temporary.open("xb") as output:
            output.write(content)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return str(destination)


def delete_image(analysis_id: str) -> bool:
    """Delete files associated with an analysis ID."""
    safe_id = str(UUID(analysis_id))
    deleted = False

    for extension in (".jpg", ".png", ".webp"):
        path = STORAGE_DIR / f"{safe_id}{extension}"
        if path.exists():
            path.unlink()
            deleted = True

    return deleted
