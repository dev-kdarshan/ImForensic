"""Explainable pixel-level evidence extraction; never a stand-alone tamper verdict."""
from __future__ import annotations

import hashlib
import io
import logging
import math
import time
import warnings
from datetime import datetime, timezone
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageStat, UnidentifiedImageError

ENGINE = "pixel-forensics"
ENGINE_VERSION = "0.1.0"
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_ANALYSIS_SIDE = 512
RESIDUAL_TILE_GRID = 4
logger = logging.getLogger(__name__)


def _jpeg_quantization(image: Image.Image) -> dict[str, Any]:
    tables = getattr(image, "quantization", None)
    if not tables:
        return {
            "applicable": image.format == "JPEG",
            "available": False,
            "tables": [],
            "interpretation": "Quantization tables were not exposed by the decoder.",
        }
    result = []
    for table_id, values in sorted(tables.items()):
        if not isinstance(values, (list, tuple)) or len(values) != 64:
            continue
        result.append({
            "table_id": int(table_id),
            "coefficient_count": len(values),
            "minimum": int(min(values)),
            "maximum": int(max(values)),
            "mean": round(sum(values) / len(values), 4),
            "values_zigzag_order": [int(value) for value in values],
        })
    return {
        "applicable": True,
        "available": bool(result),
        "tables": result,
        "interpretation": (
            "Decoder-exposed JPEG quantization tables are descriptive compression evidence. "
            "They do not establish a prior edit or identify an encoder."
        ),
    }


def _tile_residuals(residual: Image.Image, source_width: int, source_height: int) -> list[dict[str, Any]]:
    width, height = residual.size
    grid = max(1, min(RESIDUAL_TILE_GRID, width, height))
    output = []
    for row in range(grid):
        top, bottom = row * height // grid, (row + 1) * height // grid
        for column in range(grid):
            left, right = column * width // grid, (column + 1) * width // grid
            tile = residual.crop((left, top, right, bottom))
            stats = ImageStat.Stat(tile)
            output.append({
                "tile": {"row": row, "column": column},
                "sample_bounds_px": {"left": left, "top": top, "right": right, "bottom": bottom},
                "source_bounds_px": {
                    "left": math.floor(left * source_width / width),
                    "top": math.floor(top * source_height / height),
                    "right": math.ceil(right * source_width / width),
                    "bottom": math.ceil(bottom * source_height / height),
                },
                "mean_absolute_residual_intensity_0_255": round(stats.mean[0], 4),
                "residual_stddev_intensity_0_255": round(stats.stddev[0], 4),
            })
    return output


def _pixel_evidence(image: Image.Image) -> dict[str, Any]:
    source_width, source_height = image.size
    sample = image.convert("RGB")
    sample.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE), Image.Resampling.BILINEAR)
    gray = sample.convert("L")

    # High-pass proxy: absolute difference from a Gaussian-smoothed image.
    # This is a descriptive residual, not a sensor-noise or tamper detector.
    smooth = gray.filter(ImageFilter.GaussianBlur(radius=1.0))
    residual = ImageChops.difference(gray, smooth)
    residual_stats = ImageStat.Stat(residual)
    tile_stats = _tile_residuals(residual, source_width, source_height)

    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stats = ImageStat.Stat(edges)

    return {
        "preprocessing": {
            "color_space": "RGB then Pillow L grayscale",
            "maximum_sample_side_px": MAX_ANALYSIS_SIDE,
            "resampling": "Pillow BILINEAR thumbnail",
            "residual": "absolute difference between grayscale sample and GaussianBlur(radius=1.0)",
            "tile_grid": f"up to {RESIDUAL_TILE_GRID}x{RESIDUAL_TILE_GRID} equal-sized tiles",
            "coordinate_system": "pixel coordinates in the original decoded image; origin at top-left; right/bottom exclusive",
        },
        "sample_dimensions_px": {"width": sample.width, "height": sample.height},
        "high_pass_residual": {
            "mean_absolute_intensity_0_255": round(residual_stats.mean[0], 4),
            "stddev_intensity_0_255": round(residual_stats.stddev[0], 4),
            "tile_measurements": tile_stats,
            "interpretation": "Spatial measurements of a simple high-pass residual; not calibrated noise estimates or manipulation scores.",
        },
        "edge_response_proxy": {
            "operator": "Pillow FIND_EDGES",
            "mean_intensity_0_255": round(edge_stats.mean[0], 4),
            "stddev_intensity_0_255": round(edge_stats.stddev[0], 4),
            "interpretation": "Descriptive edge-response statistics; not a validated resampling or tamper detector.",
        },
    }


def analyze_image(content: bytes, filename: str | None = None) -> dict[str, Any]:
    """Analyze supported image bytes with bounded, deterministic Pillow operations."""
    started = time.perf_counter()
    if not content:
        raise ValueError("Image content is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 20 MB analysis limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                image_format = (probe.format or "").upper()
                width, height = probe.size
                if image_format not in SUPPORTED_FORMATS:
                    raise ValueError("Only JPEG, PNG and WebP images are supported.")
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image dimensions exceed the 40-megapixel analysis limit.")
                probe.verify()

            with Image.open(io.BytesIO(content)) as source:
                source.load()
                quantization = _jpeg_quantization(source)
                evidence = _pixel_evidence(source)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Image dimensions exceed the safe decoding limit.") from None
    except UnidentifiedImageError:
        raise ValueError("Uploaded content is not a valid supported image.") from None
    except OSError:
        raise ValueError("Image is truncated or could not be decoded safely.") from None

    digest = hashlib.sha256(content).hexdigest()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    logger.info(
        "pixel_forensics_analysis_complete",
        extra={"engine": ENGINE, "engine_version": ENGINE_VERSION, "sha256": digest,
               "width": width, "height": height, "processing_time_ms": elapsed_ms},
    )
    methods = [
        {
            "id": "jpeg-quantization-inspection",
            "status": "completed" if quantization["available"] else (
                "not_applicable" if image_format != "JPEG" else "unavailable"
            ),
            "configuration": {"decoder": "Pillow", "table_order": "JPEG zig-zag order"},
        },
        {
            "id": "high-pass-residual-summary",
            "status": "completed",
            "configuration": {"gaussian_blur_radius": 1.0, "tile_grid_max": RESIDUAL_TILE_GRID},
        },
        {
            "id": "edge-response-summary",
            "status": "completed",
            "configuration": {"operator": "Pillow FIND_EDGES"},
        },
    ]
    return {
        "analysis_id": None,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "model_version": None,
        "status": "completed",
        "sha256": digest,
        "image": {"format": image_format, "width": width, "height": height, "size_bytes": len(content)},
        "methods": methods,
        "findings": {
            "outcome": "inconclusive",
            "tampering_supported": False,
            "items": [
                {
                    "id": "PIXEL-JPEG-QTABLE-001",
                    "method": "jpeg-quantization-inspection",
                    "evidence": quantization,
                    "score": None,
                    "score_semantics": "No tampering score is computed.",
                },
                {
                    "id": "PIXEL-RESIDUAL-001",
                    "method": "high-pass-residual-summary",
                    "evidence": evidence["high_pass_residual"],
                    "score": None,
                    "score_semantics": "Residual intensity measurements are not probabilities or anomaly scores.",
                },
                {
                    "id": "PIXEL-EDGE-001",
                    "method": "edge-response-summary",
                    "evidence": evidence["edge_response_proxy"],
                    "score": None,
                    "score_semantics": "Edge response is descriptive and not a manipulation likelihood.",
                },
            ],
            "preprocessing": evidence["preprocessing"],
            "sample_dimensions_px": evidence["sample_dimensions_px"],
            "interpretation": (
                "The engine reports compression and pixel-residual measurements only. "
                "No manipulation type, authenticity verdict, or localization claim is made."
            ),
        },
        "warnings": [
            "JPEG quantization tables can be changed by recompression and do not identify a unique editor.",
            "High-pass residuals are affected by scene texture, sensor noise, denoising, sharpening, resizing and recompression.",
            "Edge-response statistics are not validated resampling evidence.",
            "This baseline does not implement copy-move detection, inpainting detection, or compositing classification.",
        ],
        "limitations": [
            "No labelled genuine/manipulated benchmark dataset is configured; no accuracy metrics are claimed.",
            "No pixel-level tampering masks are produced.",
            "No calibrated anomaly or tampering probability is produced.",
            "Coordinates refer to the decoded image dimensions; EXIF orientation is not applied.",
        ],
        "failure_reasons": [],
        "processing_time_ms": elapsed_ms,
        "resource_profile": {
            "maximum_input_bytes": MAX_IMAGE_BYTES,
            "maximum_source_pixels": MAX_IMAGE_PIXELS,
            "maximum_analysis_side_px": MAX_ANALYSIS_SIDE,
            "gpu_required": False,
        },
    }
