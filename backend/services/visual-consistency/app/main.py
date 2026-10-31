"""FastAPI service for the Visual Consistency Engine."""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.analyzer import (
    ENGINE_VERSION,
    MAX_IMAGE_BYTES,
    UnsupportedImageError,
    analyze_image,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("imforensic.visual_consistency")

app = FastAPI(
    title="ImForensic Visual Consistency Engine",
    version=ENGINE_VERSION,
    description="Reports bounded regional visual measurements without issuing an authenticity verdict.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "visual-consistency", "version": ENGINE_VERSION}


@app.get("/ready")
def readiness():
    return {
        "status": "ready",
        "service": "visual-consistency",
        "mode": "descriptive-region-measurements",
        "gpu_required": False,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), analysis_id: str | None = Form(default=None)):
    content = await file.read(MAX_IMAGE_BYTES + 1)
    await file.close()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 20 MB analysis limit.")
    try:
        return analyze_image(content, analysis_id)
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
