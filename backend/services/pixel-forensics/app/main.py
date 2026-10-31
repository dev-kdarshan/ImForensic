"""HTTP API for the Pixel Forensics baseline."""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.analyzer import ENGINE_VERSION, analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="ImForensic Pixel Forensics Engine",
    version=ENGINE_VERSION,
    description="Extracts explainable pixel-level measurements without issuing a tampering verdict.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "pixel-forensics", "version": ENGINE_VERSION}


@app.get("/ready")
def readiness():
    return {
        "status": "ready",
        "service": "pixel-forensics",
        "mode": "signal-processing-baseline",
        "gpu_required": False,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), analysis_id: str | None = None):
    content = await file.read(20 * 1024 * 1024 + 1)
    filename = file.filename
    await file.close()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB.")
    try:
        result = analyze_image(content, filename)
        if analysis_id is not None:
            try:
                result["analysis_id"] = str(UUID(analysis_id))
            except ValueError:
                raise HTTPException(status_code=422, detail="analysis_id must be a UUID.") from None
        else:
            result["analysis_id"] = str(uuid4())
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
