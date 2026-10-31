"""Conservative AI-content detector service boundary.

No model is bundled or loaded in this initial implementation. Until a model
artifact, preprocessing contract, license review, and benchmark are approved,
requests return a partial/inconclusive EngineResult rather than a guessed label.
"""
from __future__ import annotations

import hashlib
import io
import time
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

ENGINE = "ai-content-detection"
ENGINE_VERSION = "0.1.0"
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
        "format": image_format,
        "width": width,
        "height": height,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def analyze_image(content: bytes, analysis_id: str | None = None) -> dict:
    """Validate input and return explicit not-configured semantics.

    This is intentionally not a fake detector: no score or class is emitted
    until a vetted model adapter has been installed and evaluated.
    """
    started = time.perf_counter()
    image = inspect_image(content)
    try:
        resolved_id = str(UUID(analysis_id)) if analysis_id else str(uuid4())
    except ValueError:
        raise ValueError("analysis_id must be a UUID.") from None

    return {
        "analysis_id": resolved_id,
        "engine": ENGINE,
        "status": "partial",
        "findings": {
            "task": "whole_image_real_photograph_vs_fully_ai_generated_screening",
            "outcome": "inconclusive",
            "reason_code": "MODEL_NOT_CONFIGURED",
            "detector": None,
            "detector_version": None,
            "model_artifact": None,
            "input": image,
            "preprocessing": {
                "status": "validation_only",
                "decoded_format": image["format"],
                "orientation": "EXIF orientation is not applied",
                "model_transform": None,
            },
            "score": None,
            "score_semantics": "No detector score is available; no inference model is configured.",
            "decision": "inconclusive",
            "decision_threshold": None,
            "calibrated_probability": None,
            "interpretation": (
                "The image passed format, integrity, and resource validation, but no AI-content "
                "classification was performed because a vetted model artifact is not configured."
            ),
        },
        "warnings": [
            "This service currently validates image input only; it does not detect AI-generated content.",
            "No raw model score, probability, or real/AI label is produced.",
            "A future model must be evaluated on source-disjoint and generator-disjoint data before deployment.",
        ],
        "model_version": None,
        "processing_time_ms": round((time.perf_counter() - started) * 1000, 3),
    }
