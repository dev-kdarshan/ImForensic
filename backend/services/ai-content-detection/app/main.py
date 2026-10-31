"""FastAPI entry point for the AI Content Detection Engine."""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.analyzer import ENGINE_VERSION, MAX_IMAGE_BYTES, UnsupportedImageError, analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("imforensic.ai_content_detection")

app = FastAPI(
    title="ImForensic AI Content Detection Engine",
    version=ENGINE_VERSION,
    description="Conservative detector service boundary; inference remains disabled until a vetted model is configured.",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-content-detection",
        "version": ENGINE_VERSION,
        "model_configured": False,
    }


@app.get("/ready")
def readiness():
    # Liveness is separate from detector readiness. This service is intentionally
    # not inference-ready until a model and its manifest have been approved.
    raise HTTPException(
        status_code=503,
        detail={
            "status": "not_ready",
            "service": "ai-content-detection",
            "reason": "MODEL_NOT_CONFIGURED",
        },
    )


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
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
