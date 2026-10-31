"""HTTP API for the descriptive Model Fingerprinting baseline."""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.analyzer import ENGINE_VERSION, analyze_image

app = FastAPI(
    title="ImForensic Model Fingerprinting Engine",
    version=ENGINE_VERSION,
    description=(
        "Extracts deterministic descriptive image features. It does not claim "
        "generator attribution without a validated reference dataset and model."
    ),
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "model-fingerprint", "version": ENGINE_VERSION}


@app.get("/ready")
def readiness():
    return {
        "status": "ready",
        "service": "model-fingerprint",
        "mode": "descriptive-baseline",
        "attribution_model_loaded": False,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), analysis_id: str | None = None):
    content = await file.read(20 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB.")
    try:
        result = analyze_image(content, file.filename)
        if analysis_id is not None:
            try:
                result["analysis_id"] = str(UUID(analysis_id))
            except ValueError:
                raise HTTPException(status_code=422, detail="analysis_id must be a UUID.") from None
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
