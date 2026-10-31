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
MODEL_FINGERPRINT_SERVICE_URL = os.getenv("MODEL_FINGERPRINT_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT_SECONDS", "30"))


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


async def _call_engine(service_url: str, filename: str, content: bytes, content_type: str, analysis_id: str) -> dict:
    async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT) as client:
        response = await client.post(
            f"{service_url}/analyze",
            data={"analysis_id": analysis_id},
            files={"file": (filename, content, content_type)},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Engine response must be a JSON object.")
        return payload


async def _run_engine(engine: str, service_url: str, filename: str, content: bytes,
                      content_type: str, analysis_id: str, expected_sha256: str,
                      hash_path: tuple[str, ...]) -> tuple[dict, dict | None]:
    try:
        payload = await _call_engine(service_url, filename, content, content_type, analysis_id)
        actual = payload
        for key in hash_path:
            actual = actual.get(key, {}) if isinstance(actual, dict) else {}
        if not isinstance(actual, dict) or actual.get("sha256") != expected_sha256:
            raise ValueError("Engine SHA-256 did not match the Gateway SHA-256.")
        return {"status": "completed", "engine": engine}, payload
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        return {
            "status": "failed",
            "engine": engine,
            "error": f"{type(exc).__name__}: engine did not return a verified result",
        }, None


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
    metadata_state, metadata_payload = await _run_engine(
        "metadata-provenance", METADATA_SERVICE_URL, filename, content,
        file.content_type, analysis_id, sha256, ("file",)
    )
    fingerprint_state, fingerprint_payload = await _run_engine(
        "model-fingerprint", MODEL_FINGERPRINT_SERVICE_URL, filename, content,
        file.content_type, analysis_id, sha256, ("image",)
    )
    engine_results = {
        "metadata-provenance": {**metadata_state, "result": metadata_payload},
        "model-fingerprint": {**fingerprint_state, "result": fingerprint_payload},
    }
    status = "completed" if all(item["status"] == "completed" for item in engine_results.values()) else "partial"
    failed = [name for name, item in engine_results.items() if item["status"] != "completed"]
    error = "One or more analysis engines did not return a verified result: " + ", ".join(failed) if failed else None

    record = {
        "analysis_id": analysis_id,
        "status": status,
        "created_at": created_at,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "sha256": sha256,
        "storage_ref": Path(stored_path).name,
        "result": metadata_payload,
        "engine_results": engine_results,
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
