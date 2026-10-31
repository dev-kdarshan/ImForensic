"""Conservative watermark and Content Credentials evidence extraction.

C2PA credentials are provenance records, not invisible watermarks. This engine
reports the two evidence classes separately and does not infer authenticity.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import warnings
from uuid import UUID, uuid4
from typing import Any

from PIL import ExifTags, Image, UnidentifiedImageError

ENGINE = "watermark-detection"
ENGINE_VERSION = "0.1.0"
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_MANIFEST_SUMMARY_ITEMS = 20
logger = logging.getLogger(__name__)


def _extract_metadata_candidates(image: Image.Image) -> list[dict[str, str]]:
    """Report metadata key names only; never treat a tag as proof of a watermark."""
    candidates: list[dict[str, str]] = []
    keys = set(str(key) for key in image.info.keys())
    try:
        exif = image.getexif()
        keys.update(ExifTags.TAGS.get(tag_id, str(tag_id)) for tag_id in exif.keys())
    except Exception:
        pass
    for key in sorted(keys):
        normalized = key.casefold()
        if any(term in normalized for term in ("watermark", "contentcredential", "c2pa")):
            candidates.append({
                "metadata_key": key[:128],
                "candidate_type": "metadata_marker",
                "interpretation": "A metadata key name is suggestive only; it is not a decoded or verified watermark.",
            })
    return candidates[:MAX_MANIFEST_SUMMARY_ITEMS]


def _summarize_manifest_store(store: dict[str, Any]) -> dict[str, Any]:
    manifests = store.get("manifests") if isinstance(store, dict) else None
    active = store.get("active_manifest") if isinstance(store, dict) else None
    active_manifest = manifests.get(active) if isinstance(manifests, dict) and isinstance(active, str) else None
    if not isinstance(active_manifest, dict):
        active_manifest = {}
    validation = store.get("validation_status", [])
    if not isinstance(validation, list):
        validation = []
    validation_summary = []
    for item in validation[:MAX_MANIFEST_SUMMARY_ITEMS]:
        if isinstance(item, dict):
            validation_summary.append({
                key: str(item[key])[:256]
                for key in ("code", "url", "explanation", "success")
                if key in item and isinstance(item[key], (str, int, float, bool))
            })
    generator_info = active_manifest.get("claim_generator_info", [])
    if not isinstance(generator_info, list):
        generator_info = []
    assertions = active_manifest.get("assertions", [])
    if not isinstance(assertions, list):
        assertions = []
    return {
        "active_manifest": active if isinstance(active, str) else None,
        "manifest_count": len(manifests) if isinstance(manifests, dict) else 0,
        "claim_generator": str(active_manifest.get("claim_generator", ""))[:256] or None,
        "claim_generator_info": [
            {"name": str(item.get("name", ""))[:128], "version": str(item.get("version", ""))[:64]}
            for item in generator_info[:10] if isinstance(item, dict)
        ],
        "assertion_labels": [
            str(item.get("label", ""))[:160]
            for item in assertions[:MAX_MANIFEST_SUMMARY_ITEMS]
            if isinstance(item, dict) and item.get("label")
        ],
        "validation_status": validation_summary,
        "validation_status_count": len(validation),
    }


def _read_c2pa(content: bytes, mime_type: str) -> dict[str, Any]:
    """Read a C2PA manifest with the official Python binding; never sign or mutate."""
    try:
        from c2pa import Reader
    except ImportError:
        return {"status": "unavailable", "reason_code": "C2PA_SDK_NOT_INSTALLED"}

    try:
        with io.BytesIO(content) as stream:
            with Reader(mime_type, stream) as reader:
                raw_report = reader.json()
        report = json.loads(raw_report)
        if not isinstance(report, dict) or not isinstance(report.get("manifests"), dict):
            return {"status": "inconclusive", "reason_code": "C2PA_REPORT_UNEXPECTED"}
        if not report.get("manifests"):
            return {"status": "not_detected", "reason_code": None}
        return {"status": "detected", "summary": _summarize_manifest_store(report)}
    except Exception as exc:
        # A parser failure on an otherwise valid supported image is not a
        # positive detection. Do not expose native exception text to clients.
        logger.warning("c2pa_read_failed", extra={"error_type": type(exc).__name__})
        return {"status": "inconclusive", "reason_code": "C2PA_READ_FAILED"}


def _validate_image(content: bytes) -> tuple[str, int, int, list[dict[str, str]]]:
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
            with Image.open(io.BytesIO(content)) as image:
                candidates = _extract_metadata_candidates(image)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Image dimensions exceed the safe decoding limit.") from None
    except UnidentifiedImageError:
        raise ValueError("Uploaded content is not a valid supported image.") from None
    except OSError:
        raise ValueError("Image is truncated or could not be decoded safely.") from None
    return image_format, width, height, candidates


def analyze_image(content: bytes, analysis_id: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    image_format, width, height, metadata_candidates = _validate_image(content)
    try:
        resolved_id = str(UUID(analysis_id)) if analysis_id else str(uuid4())
    except ValueError:
        raise ValueError("analysis_id must be a UUID.") from None

    c2pa = _read_c2pa(content, SUPPORTED_FORMATS[image_format])
    if c2pa["status"] == "detected":
        overall_outcome = "detected"
    elif metadata_candidates:
        overall_outcome = "potential_candidate"
    elif c2pa["status"] == "not_detected":
        overall_outcome = "not_detected"
    else:
        overall_outcome = "inconclusive"

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    result = {
        "analysis_id": resolved_id,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "status": "completed" if c2pa["status"] in {"detected", "not_detected"} else "partial",
        "findings": {
            "outcome": overall_outcome,
            "watermark_evidence": {
                "visible": {
                    "status": "unsupported",
                    "detector": None,
                    "regions": [],
                    "note": "No OCR, logo-template matcher, or visible-mark classifier is enabled in this baseline.",
                },
                "invisible": {
                    "status": "unsupported",
                    "schemes_tested": [],
                    "note": "No generic invisible-watermark detector exists. Scheme-specific decoders and keys are not configured.",
                },
                "metadata_candidates": metadata_candidates,
                "metadata_candidate_status": "potential_candidate" if metadata_candidates else "not_detected",
            },
            "content_credentials": {
                "category": "provenance_credentials_not_watermark",
                "scheme": "C2PA",
                "detector": "c2pa-python Reader",
                "detector_version": "0.38.3",
                "status": c2pa["status"],
                "reason_code": c2pa.get("reason_code"),
                "manifest": c2pa.get("summary"),
                "verification": {
                    "status": "validation_report_available" if c2pa.get("summary", {}).get("validation_status_count", 0) else "not_established",
                    "validation_status": c2pa.get("summary", {}).get("validation_status", []),
                    "trust_anchor_validation_configured": False,
                    "identity_trust": "not_assessed",
                    "note": "A manifest being present is not proof that its signer is trusted or that depicted content is true.",
                },
            },
            "decoding": {
                "status": "succeeded" if c2pa["status"] == "detected" else "not_available",
                "decoded_watermark_payload": None,
                "note": "C2PA manifest summary is reported separately; no invisible watermark payload was decoded.",
            },
            "interpretation": (
                "C2PA is a provenance credential format, not a watermark detector. "
                "A C2PA manifest can describe origin and edits but does not itself prove factual authenticity."
            ),
        },
        "warnings": [
            "No supported watermark signal does not prove that no watermark exists.",
            "A visible logo or metadata marker does not prove ownership, authorship, or authenticity.",
            "C2PA manifest discovery, signature validation, trust-chain validation, and identity trust are distinct questions.",
            "No platform-specific invisible watermark scheme (including proprietary schemes) is claimed as supported.",
        ],
        "limitations": [
            "Visible watermark localization via OCR or template matching is not implemented.",
            "No invisible or robust watermark scheme decoder is implemented.",
            "Metadata candidate detection inspects tag names only and can produce false positives.",
            "C2PA trust-anchor validation is not configured by this service.",
            "Only JPEG, PNG and WebP are accepted; other formats return unsupported.",
        ],
        "input": {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "format": image_format,
            "width": width,
            "height": height,
        },
        "methods": [
            {"id": "c2pa-manifest-reader", "category": "provenance_credentials", "status": c2pa["status"]},
            {"id": "metadata-key-candidate-scan", "category": "metadata_candidate", "status": "completed"},
        ],
        "processing_time_ms": elapsed_ms,
        "resource_profile": {
            "maximum_input_bytes": MAX_IMAGE_BYTES,
            "maximum_source_pixels": MAX_IMAGE_PIXELS,
            "gpu_required": False,
            "temporary_files_created": False,
        },
    }
    logger.info(
        "watermark_analysis_complete",
        extra={"analysis_id": resolved_id, "outcome": overall_outcome, "c2pa_status": c2pa["status"],
               "metadata_candidate_count": len(metadata_candidates), "processing_time_ms": elapsed_ms},
    )
    return result
