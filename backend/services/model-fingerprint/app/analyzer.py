"""Deterministic descriptive baseline for image-fingerprint research.

This module extracts image statistics. It does NOT identify a generator or model.
Candidate attribution is intentionally inconclusive until a labelled reference
dataset, trained/validated method, and open-set evaluation exist.
"""
from __future__ import annotations

import hashlib
import io
import math
import statistics
from typing import Any

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

ENGINE_VERSION = "0.1.0"
FEATURE_SCHEMA_VERSION = "1.0"
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_ANALYSIS_SIDE = 256
HISTOGRAM_BINS = 16


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return round(
        -sum((count / total) * math.log2(count / total) for count in counts if count),
        6,
    )


def _binned_histogram(histogram: list[int], bins: int = HISTOGRAM_BINS) -> list[float]:
    width = 256 // bins
    total = sum(histogram)
    if not total:
        return [0.0] * bins
    return [
        round(sum(histogram[index * width : (index + 1) * width]) / total, 6)
        for index in range(bins)
    ]


def _tile_luminance_means(gray: Image.Image, grid_size: int = 4) -> list[float]:
    width, height = gray.size
    grid = max(1, min(grid_size, width, height))
    means: list[float] = []
    for row in range(grid):
        top, bottom = row * height // grid, (row + 1) * height // grid
        for column in range(grid):
            left, right = column * width // grid, (column + 1) * width // grid
            tile = gray.crop((left, top, right, bottom))
            means.append(round(ImageStat.Stat(tile).mean[0], 4))
    return means


def _feature_profile(image: Image.Image) -> dict[str, Any]:
    original_width, original_height = image.size
    sample = image.convert("RGB")
    sample.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE), Image.Resampling.BILINEAR)

    channel_stats = ImageStat.Stat(sample)
    channel_histograms = sample.histogram()
    channels = {}
    for index, name in enumerate(("red", "green", "blue")):
        histogram = channel_histograms[index * 256 : (index + 1) * 256]
        channels[name] = {
            "mean": round(channel_stats.mean[index], 4),
            "stddev": round(channel_stats.stddev[index], 4),
            "histogram_16_bins": _binned_histogram(histogram),
            "entropy_bits": _entropy(histogram),
        }

    gray = sample.convert("L")
    gray_histogram = gray.histogram()
    gray_bins = _binned_histogram(gray_histogram, bins=32)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stats = ImageStat.Stat(edges)
    tile_means = _tile_luminance_means(gray)
    tile_variance = statistics.pvariance(tile_means) if len(tile_means) > 1 else 0.0

    return {
        "preprocessing": {
            "color_space": "RGB",
            "analysis_max_side": MAX_ANALYSIS_SIDE,
            "resampling": "Pillow BILINEAR",
            "grayscale_conversion": "Pillow L",
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
        },
        "source_dimensions": {"width": original_width, "height": original_height},
        "sample_dimensions": {"width": sample.width, "height": sample.height},
        "channels": channels,
        "grayscale": {
            "entropy_bits": _entropy(gray_histogram),
            "histogram_32_bins": gray_bins,
        },
        "edge_response_proxy": {
            "operator": "Pillow FIND_EDGES",
            "mean": round(edge_stats.mean[0], 4),
            "stddev": round(edge_stats.stddev[0], 4),
            "note": "A simple edge-response statistic; not a validated generator fingerprint.",
        },
        "spatial_luminance": {
            "grid": "up to 4x4 equal-sized tiles",
            "tile_means": tile_means,
            "tile_mean_variance": round(tile_variance, 6),
        },
    }


def analyze_image(content: bytes, filename: str | None = None) -> dict[str, Any]:
    """Return descriptive features and an explicitly inconclusive attribution."""
    if not content:
        raise ValueError("Image content is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 20 MB analysis limit.")

    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in SUPPORTED_FORMATS:
                raise ValueError("Only JPEG, PNG and WebP images are supported.")
            if source.width < 1 or source.height < 1 or source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed the 40-megapixel analysis limit.")
            source.load()
            profile = _feature_profile(source)
            image_format = source.format
            dimensions = source.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("Image is invalid or could not be decoded safely.") from None

    digest = hashlib.sha256(content).hexdigest()
    return {
        "analysis_id": None,
        "engine": "model-fingerprint",
        "engine_version": ENGINE_VERSION,
        "model_version": None,
        "status": "completed",
        "image": {
            "sha256": digest,
            "format": image_format,
            "width": dimensions[0],
            "height": dimensions[1],
        },
        "findings": {
            "task": "descriptive_image_feature_extraction",
            "outcome": "inconclusive",
            "attribution_supported": False,
            "candidate_scores": [],
            "feature_profile": profile,
            "interpretation": (
                "The engine extracted reproducible descriptive image features. "
                "No generator/model attribution is made because no labelled reference "
                "dataset or experimentally validated classifier is configured."
            ),
        },
        "warnings": [
            "Feature statistics are not unique model fingerprints.",
            "Resizing, compression, screenshots, editing and image content can change these measurements.",
            "No calibrated probability or model confidence is available.",
        ],
    }
