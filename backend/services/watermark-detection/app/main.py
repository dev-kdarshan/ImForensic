"""FastAPI entry point for the Watermark Detection Engine."""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.analyzer import ENGINE_VERSION, MAX_IMAGE_BYTES, analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("imforensic.watermark_detection")

app = FastAPI(
    title="ImForensic Watermark Detection Engine",
    version=ENGINE_VERSION,
    description="Reports supported watermark evidence separately from C2PA provenance credentials.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "watermark-detection", "version": ENGINE_VERSION}


@app.get("/ready")
def readiness():
    try:
        import c2pa  # noqa: F401
        c2pa_available = True
    except ImportError:
        c2pa_available = False
    return {
        "status": "ready" if c2pa_available else "partial",
        "service": "watermark-detection",
        "c2pa_sdk_available": c2pa_available,
        "visible_watermark_detector": False,
        "invisible_watermark_detectors": [],
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    analysis_id: str | None = Form(default=None),
):
    content = await file.read(MAX_IMAGE_BYTES + 1)
    await file.close()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 20 MB analysis limit.")
    try:
        return analyze_image(content, analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
