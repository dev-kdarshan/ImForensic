"""AI-content detector with an explicit not-configured fallback."""
from __future__ import annotations

import hashlib
import io
import time
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

ENGINE = "ai-content-detection"
ENGINE_VERSION = "0.2.0"
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


class UnsupportedImageError(ValueError):
    """Raised when an uploaded image is unsupported or unsafe to decode."""


def inspect_image(content: bytes) -> dict:
    if not content:
        raise UnsupportedImageError("Image content is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise UnsupportedImageError("Image exceeds the 20 MB analysis limit.")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            if image_format not in SUPPORTED_FORMATS:
                raise UnsupportedImageError("Only JPEG, PNG and WebP images are supported.")
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise UnsupportedImageError("Image dimensions exceed the 40-megapixel analysis limit.")
            image.verify()
    except UnsupportedImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UnsupportedImageError("Image is invalid or could not be decoded safely.") from None
    return {
        "format": image_format, "width": width, "height": height,
        "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
    }


def analyze_image(content: bytes, analysis_id: str | None = None) -> dict:
    started = time.perf_counter()
    image = inspect_image(content)
    try:
        resolved_id = str(UUID(analysis_id)) if analysis_id else str(uuid4())
    except ValueError:
        raise ValueError("analysis_id must be a UUID.") from None

    findings = {
        "task": "whole_image_real_photograph_vs_fully_ai_generated_screening",
        "outcome": "inconclusive",
        "reason_code": "MODEL_NOT_CONFIGURED",
        "detector": None, "detector_version": None, "model_artifact": None,
        "input": image,
        "preprocessing": {"status": "validation_only", "orientation": "model EXIF transpose only when DDA is enabled", "model_transform": None},
        "score": None,
        "score_semantics": "No detector score is available; no inference model is configured.",
        "decision": "inconclusive", "decision_threshold": None, "calibrated_probability": None,
    }
    status = "partial"
    warnings = ["No calibrated probability or authenticity/provenance verdict is produced."]
    try:
        from app.dda_model import ModelNotConfigured, predict
        result = predict(content)
        findings.update({
            "outcome": "scored",
            "reason_code": None,
            "detector": result["detector"],
            "detector_version": result["detector_version"],
            "model_artifact": result["model_artifact"],
            "preprocessing": {
                "status": "applied",
                "orientation": "EXIF transpose before RGB conversion",
                "model_transform": result["preprocessing_version"],
            },
            "score": result["score"],
            "score_semantics": result["score_semantics"],
            "raw_logit": result["raw_logit"],
            "device": result["device"],
            "decision": "unthresholded",
        })
        status = "completed"
        warnings.append("DDA score is uncalibrated and must not be interpreted as a probability.")
    except ModelNotConfigured as exc:
        findings["reason_code"] = "MODEL_NOT_CONFIGURED"
        findings["score_semantics"] = str(exc)
        warnings.append("DDA inference is disabled until a verified checkpoint and model dependencies are configured.")
    except Exception as exc:
        findings["reason_code"] = "MODEL_INFERENCE_FAILED"
        findings["score_semantics"] = f"Inference unavailable: {type(exc).__name__}."
        warnings.append("Model inference failed; no classification was produced.")

    return {
        "analysis_id": resolved_id, "engine": ENGINE, "status": status,
        "findings": findings, "warnings": warnings,
        "model_version": findings["detector_version"],
        "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
    }
