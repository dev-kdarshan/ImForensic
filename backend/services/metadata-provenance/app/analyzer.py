"""Safe metadata and provenance-signal extraction for supported raster images."""
from __future__ import annotations

import hashlib
import warnings
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from PIL import ExifTags, Image, UnidentifiedImageError

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"type": "binary", "length_bytes": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value[:100]]
    try:
        return str(value)
    except Exception:
        return "<unavailable>"


def analyze_image(content: bytes, filename: str | None = None) -> dict[str, Any]:
    """Inspect image bytes; never accept a caller-supplied filesystem path."""
    if not content:
        raise ValueError("The uploaded image is empty.")

    sha256 = hashlib.sha256(content).hexdigest()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                image_format = (probe.format or "").upper()
                width, height = probe.size
                if image_format not in SUPPORTED_FORMATS:
                    raise ValueError("Only JPEG, PNG and WebP images are supported.")
                if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                    raise ValueError("Image dimensions exceed the supported pixel limit.")
                probe.verify()

            with Image.open(BytesIO(content)) as image:
                exif_raw = image.getexif()
                exif = {
                    ExifTags.TAGS.get(tag_id, str(tag_id)): _json_value(value)
                    for tag_id, value in exif_raw.items()
                }
                info = image.info
                embedded_info = {
                    str(key): _json_value(value)
                    for key, value in info.items()
                    if key.lower() not in {"icc_profile", "exif", "xmp"}
                }
                info_keys = sorted(str(key) for key in info.keys())
                icc_present = bool(info.get("icc_profile"))
                xmp_present = bool(info.get("xmp") or info.get("XML:com.adobe.xmp"))
                c2pa_signal = any("c2pa" in key.lower() for key in info_keys)
                software = exif.get("Software")
                date_taken = exif.get("DateTimeOriginal") or exif.get("DateTime")
                orientation = exif.get("Orientation")
                mode = image.mode
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Image dimensions exceed the safe decoding limit.") from None
    except UnidentifiedImageError:
        raise ValueError("The uploaded content is not a valid supported image.") from None
    except OSError:
        raise ValueError("The uploaded image could not be decoded.") from None

    return {
        "engine": "metadata-provenance",
        "engine_version": "1.0.0",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "file": {
            "filename": filename,
            "size_bytes": len(content),
            "sha256": sha256,
            "format": image_format,
            "width": width,
            "height": height,
            "mode": mode,
        },
        "metadata": {
            "exif_present": bool(exif),
            "exif": exif,
            "software_tag": software,
            "datetime_original": date_taken,
            "orientation": orientation,
            "embedded_info_keys": info_keys,
            "embedded_info": embedded_info,
            "icc_profile_present": icc_present,
            "xmp_present": xmp_present,
        },
        "provenance_signals": {
            "metadata_available": bool(exif or info_keys),
            "software_tag_present": bool(software),
            "xmp_present": xmp_present,
            "c2pa_manifest_signal": c2pa_signal,
            "c2pa_verified": False,
        },
        "observations": [
            "Metadata is descriptive evidence and can be edited or removed.",
            "A software tag identifies a claimed editing or exporting application, not proof of authorship.",
            "A C2PA signal is not cryptographic verification; this engine does not validate manifests or signatures.",
            "Missing metadata does not establish AI generation or manipulation.",
        ],
        "limitations": [
            "C2PA credentials and digital signatures are not verified.",
            "Camera identity and timestamps can be forged or altered.",
            "The analysis does not determine whether an image is AI-generated.",
        ],
    }
