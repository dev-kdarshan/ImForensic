"""FastAPI entry point for the AI Content Detection Engine."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.analyzer import ENGINE_VERSION, MAX_IMAGE_BYTES, UnsupportedImageError, analyze_image
from app.dda_model import model_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("imforensic.ai_content_detection")

app = FastAPI(
    title="ImForensic AI Content Detection Engine",
    version=ENGINE_VERSION,
    description="Experimental whole-image AI-generated image screening; scores are uncalibrated.",
)


@app.get("/health")
def health():
    # Liveness must not trigger a 1.26 GB model load or a network download.
    checkpoint = os.getenv("DDA_CHECKPOINT_PATH", "").strip()
    configured = bool(checkpoint and Path(checkpoint).is_file())
    return {
        "status": "ok",
        "service": "ai-content-detection",
        "version": ENGINE_VERSION,
        "model_configured": configured,
    }


@app.get("/ready")
def readiness():
    status = model_status()
    if not status.get("configured"):
        raise HTTPException(status_code=503, detail={"status": "not_ready", "service": "ai-content-detection", **status})
    return {"status": "ready", "service": "ai-content-detection", **status}


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
