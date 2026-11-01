"""FastAPI entry point for the AI Content Detection Engine."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder

from app.analyzer import ENGINE_VERSION, MAX_IMAGE_BYTES, UnsupportedImageError, analyze_image
from app.dda_model import model_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("imforensic.ai_content_detection")

IDEMPOTENCY_DB = Path(os.getenv("DDA_IDEMPOTENCY_DB_PATH", "/app/data/dda_idempotency.sqlite3"))
IDEMPOTENCY_LEASE_SECONDS = int(os.getenv("DDA_IDEMPOTENCY_LEASE_SECONDS", "1800"))
IDEMPOTENCY_WAIT_SECONDS = int(os.getenv("DDA_IDEMPOTENCY_WAIT_SECONDS", "570"))
MAX_CONCURRENT_INFERENCES = max(1, int(os.getenv("DDA_MAX_CONCURRENT_INFERENCES", "1")))
INFERENCE_SEMAPHORE = BoundedSemaphore(MAX_CONCURRENT_INFERENCES)

app = FastAPI(
    title="ImForensic AI Content Detection Engine",
    version=ENGINE_VERSION,
    description="Experimental whole-image AI-generated image screening; scores are uncalibrated.",
)


def _connect_idempotency_db() -> sqlite3.Connection:
    IDEMPOTENCY_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(IDEMPOTENCY_DB, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS dda_inference_cache (
            analysis_id TEXT PRIMARY KEY,
            image_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_token TEXT,
            result_json TEXT,
            updated_at REAL NOT NULL
        )
    """)
    return db


def _claim_or_read(analysis_id: str, image_sha256: str, owner_token: str):
    now = time.time()
    with _connect_idempotency_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT image_sha256, status, owner_token, result_json, updated_at "
            "FROM dda_inference_cache WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()

        if row and row[0] != image_sha256:
            raise HTTPException(
                status_code=409,
                detail="This analysis_id is already associated with a different image.",
            )

        if row and row[1] == "completed" and row[3]:
            return "completed", json.loads(row[3])

        if row and row[1] == "running" and now - row[4] < IDEMPOTENCY_LEASE_SECONDS:
            return "running", None

        db.execute(
            """
            INSERT INTO dda_inference_cache
                (analysis_id, image_sha256, status, owner_token, result_json, updated_at)
            VALUES (?, ?, 'running', ?, NULL, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                status='running', owner_token=excluded.owner_token,
                result_json=NULL, updated_at=excluded.updated_at
            """,
            (analysis_id, image_sha256, owner_token, now),
        )
        return "claimed", None


def _save_completed(analysis_id: str, owner_token: str, result: dict) -> None:
    encoded = json.dumps(jsonable_encoder(result), separators=(",", ":"), ensure_ascii=False)
    with _connect_idempotency_db() as db:
        db.execute(
            """
            UPDATE dda_inference_cache
            SET status='completed', result_json=?, updated_at=?
            WHERE analysis_id=? AND owner_token=? AND status='running'
            """,
            (encoded, time.time(), analysis_id, owner_token),
        )


def _release_claim(analysis_id: str, owner_token: str) -> None:
    with _connect_idempotency_db() as db:
        db.execute(
            "DELETE FROM dda_inference_cache WHERE analysis_id=? AND owner_token=? AND status='running'",
            (analysis_id, owner_token),
        )


def _analyze_idempotently(content: bytes, analysis_id: str) -> dict:
    image_sha256 = hashlib.sha256(content).hexdigest()
    owner_token = str(uuid.uuid4())
    deadline = time.monotonic() + IDEMPOTENCY_WAIT_SECONDS

    # Acquire the local inference slot before claiming the durable lease. This
    # prevents queued requests from holding leases while waiting for CPU capacity.
    with INFERENCE_SEMAPHORE:
        while True:
            state, cached_result = _claim_or_read(analysis_id, image_sha256, owner_token)
            if state == "completed":
                logger.info("Returning cached DDA result analysis_id=%s", analysis_id)
                return cached_result
            if state == "claimed":
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for the existing DDA inference to finish.")
            time.sleep(1)

        try:
            result = analyze_image(content, analysis_id)
            _save_completed(analysis_id, owner_token, result)
            return jsonable_encoder(result)
        except Exception:
            _release_claim(analysis_id, owner_token)
            raise


@app.get("/health")
def health():
    # Liveness must not trigger a model load or a network download.
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

    # Requests without an analysis_id cannot be safely deduplicated. Assign a
    # fresh ID so they still use the same execution path without colliding.
    effective_analysis_id = (analysis_id or str(uuid.uuid4())).strip()
    if not effective_analysis_id:
        effective_analysis_id = str(uuid.uuid4())

    try:
        return await asyncio.to_thread(
            _analyze_idempotently,
            content,
            effective_analysis_id,
        )
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
