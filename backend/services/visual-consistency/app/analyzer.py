"""Region-level visual measurements for cautious consistency review.

This baseline reports descriptive illumination, colour and edge/texture
variation. It does not infer physical lighting, shadows, perspective, objects,
manipulation, or authenticity.
"""
from __future__ import annotations

import hashlib
import io
import math
import statistics
import time
from typing import Any
from uuid import UUID, uuid4

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
import warnings

ENGINE = "visual-consistency"
ENGINE_VERSION = "0.1.0"
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_ANALYSIS_SIDE = 512
MAX_GRID_SIDE = 4
MIN_TILE_SIDE = 16
ROBUST_Z_THRESHOLD = 3.5


class UnsupportedImageError(ValueError):
    """Raised when an uploaded image is unsupported or unsafe to decode."""


def _median_absolute_deviation(values: list[float]) -> tuple[float, float]:
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    return median, statistics.median(deviations)


def _robust_outliers(values: list[float]) -> list[dict[str, float | bool | None]]:
    """Return descriptive MAD-based outlier measurements, not probabilities."""
    if len(values) < 3:
        return [{"robust_z": None, "is_statistical_outlier": False} for _ in values]
    median, mad = _median_absolute_deviation(values)
    if mad <= 1e-12:
        return [{"robust_z": None, "is_statistical_outlier": False} for _ in values]
    output = []
    for value in values:
        robust_z = 0.67448975 * (value - median) / mad
        output.append({
            "robust_z": round(robust_z, 4),
            "is_statistical_outlier": abs(robust_z) >= ROBUST_Z_THRESHOLD,
        })
    return output


def _tile_grid(width: int, height: int) -> int:
    return max(1, min(MAX_GRID_SIDE, width // MIN_TILE_SIDE, height // MIN_TILE_SIDE))


def _measure_regions(image: Image.Image, source_width: int, source_height: int) -> list[dict[str, Any]]:
    width, height = image.size
    grid = _tile_grid(width, height)
    gray = image.convert("L")
    saturation = image.convert("HSV").getchannel("S")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    regions: list[dict[str, Any]] = []

    for row in range(grid):
        top, bottom = row * height // grid, (row + 1) * height // grid
        for column in range(grid):
            left, right = column * width // grid, (column + 1) * width // grid
            bounds = (left, top, right, bottom)
            gray_stats = ImageStat.Stat(gray.crop(bounds))
            saturation_stats = ImageStat.Stat(saturation.crop(bounds))
            edge_stats = ImageStat.Stat(edges.crop(bounds))
            rgb_stats = ImageStat.Stat(image.crop(bounds))
            regions.append({
                "region_id": f"r{row:02d}c{column:02d}",
                "grid": {"row": row, "column": column},
                "sample_bounds_px": {"left": left, "top": top, "right": right, "bottom": bottom},
                "source_bounds_px": {
                    "left": math.floor(left * source_width / width),
                    "top": math.floor(top * source_height / height),
                    "right": math.ceil(right * source_width / width),
                    "bottom": math.ceil(bottom * source_height / height),
                },
                "measurements": {
                    "mean_luminance_0_255": round(gray_stats.mean[0], 4),
                    "luminance_stddev_0_255": round(gray_stats.stddev[0], 4),
                    "mean_saturation_0_255": round(saturation_stats.mean[0], 4),
                    "mean_rgb_0_255": [round(channel, 4) for channel in rgb_stats.mean],
                    "edge_response_mean_0_255": round(edge_stats.mean[0], 4),
                    "edge_response_stddev_0_255": round(edge_stats.stddev[0], 4),
                },
            })

    metric_keys = (
        "mean_luminance_0_255",
        "mean_saturation_0_255",
        "edge_response_mean_0_255",
    )
    for key in metric_keys:
        values = [region["measurements"][key] for region in regions]
        outliers = _robust_outliers(values)
        for region, outlier in zip(regions, outliers):
            region.setdefault("within_image_comparison", {})[key] = outlier

    return regions


def inspect_image(content: bytes) -> dict[str, Any]:
    if not content:
        raise UnsupportedImageError("Image content is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise UnsupportedImageError("Image exceeds the 20 MB analysis limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                image_format = (probe.format or "").upper()
                width, height = probe.size
                if image_format not in SUPPORTED_FORMATS:
                    raise UnsupportedImageError("Only JPEG, PNG and WebP images are supported.")
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise UnsupportedImageError("Image dimensions exceed the 40-megapixel analysis limit.")
                probe.verify()
            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
                sample = decoded.convert("RGB")
                sample.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE), Image.Resampling.BILINEAR)
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
        "sample": sample,
    }


def analyze_image(content: bytes, analysis_id: str | None = None) -> dict[str, Any]:
    """Compute bounded region measurements; never issue a manipulation verdict."""
    started = time.perf_counter()
    image = inspect_image(content)
    try:
        resolved_id = str(UUID(analysis_id)) if analysis_id else str(uuid4())
    except ValueError:
        raise ValueError("analysis_id must be a UUID.") from None

    regions = _measure_regions(image["sample"], image["width"], image["height"])
    outlier_count = sum(
        1
        for region in regions
        for result in region.get("within_image_comparison", {}).values()
        if result["is_statistical_outlier"]
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "analysis_id": resolved_id,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "status": "completed",
        "model_version": None,
        "image": {key: image[key] for key in ("format", "width", "height", "size_bytes", "sha256")},
        "methods": [
            {
                "id": "region-illumination-colour-texture-summary",
                "version": "0.1.0",
                "status": "completed",
                "algorithm": "Pillow RGB/L/HSV conversion, regional descriptive statistics, FIND_EDGES response, and within-image median absolute deviation comparison",
                "configuration": {
                    "maximum_sample_side_px": MAX_ANALYSIS_SIDE,
                    "maximum_grid_side": MAX_GRID_SIDE,
                    "minimum_tile_side_px": MIN_TILE_SIDE,
                    "robust_z_threshold": ROBUST_Z_THRESHOLD,
                    "resampling": "Pillow BILINEAR thumbnail",
                },
            }
        ],
        "findings": {
            "outcome": "inconclusive",
            "manipulation_supported": False,
            "task": "region_level_illumination_colour_and_edge_texture_variation",
            "comparison_semantics": (
                "MAD-based robust z values compare regions within this image only. "
                "They are descriptive heuristics, not calibrated anomaly scores or probabilities."
            ),
            "regions": regions,
            "summary": {
                "region_count": len(regions),
                "statistical_outlier_measurement_count": outlier_count,
                "interpretation": (
                    "Regional measurements describe variation in the decoded image. "
                    "Variation may be caused by ordinary scene content, materials, lighting, "
                    "shadows, camera processing, edits, or compression; it is not evidence of manipulation by itself."
                ),
            },
            "preprocessing": {
                "decoded_color_space": "RGB",
                "measurement_spaces": ["grayscale luminance proxy", "HSV saturation", "RGB channel means"],
                "texture_proxy": "Pillow FIND_EDGES response statistics",
                "sample_dimensions_px": {"width": image["sample"].width, "height": image["sample"].height},
                "coordinate_system": "decoded raster pixel coordinates; origin top-left; right/bottom exclusive",
                "exif_orientation_applied": False,
            },
            "score_semantics": {
                "robust_z": "Uncalibrated within-image robust standardized deviation using 0.67448975 * (x - median) / MAD.",
                "threshold": ROBUST_Z_THRESHOLD,
                "calibrated_probability": False,
                "global_manipulation_score": None,
            },
        },
        "warnings": [
            "This baseline does not estimate physical light-source direction or validate shadow geometry.",
            "This baseline does not estimate vanishing points, camera geometry, object boundaries, occlusion, or scene semantics.",
            "A regional statistical outlier is not a suspicious-object label and does not establish editing.",
            "Natural scene structure, mixed materials, illumination gradients, shadows, and camera processing can create strong regional differences.",
            "No labelled benchmark is configured; no accuracy or localization performance is claimed.",
        ],
        "limitations": [
            "No learned model or pretrained weights are used.",
            "No calibrated anomaly or manipulation probability is produced.",
            "No manipulated-region mask or object-level localization is produced.",
            "EXIF orientation is not applied; coordinates refer to the decoded raster.",
            "Small images may produce a single region and therefore no within-image outlier comparison.",
        ],
        "processing_time_ms": elapsed_ms,
        "resource_profile": {
            "maximum_input_bytes": MAX_IMAGE_BYTES,
            "maximum_source_pixels": MAX_IMAGE_PIXELS,
            "maximum_analysis_side_px": MAX_ANALYSIS_SIDE,
            "gpu_required": False,
        },
    }
