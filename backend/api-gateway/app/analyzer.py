
from io import BytesIO
from pathlib import Path
from PIL import Image, ExifTags
import hashlib
import json


def analyze_image(image_path: str) -> dict:
    """
    Extract basic image properties and available EXIF metadata.
    This reports observations; it does not determine whether
    an image is AI-generated.
    """
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError("Image file not found.")

    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    with Image.open(BytesIO(content)) as image:
        image_format = image.format
        width, height = image.size
        image_mode = image.mode

        exif_data = image.getexif()
        exif = {}

        for tag_id, value in exif_data.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

            # Convert metadata values into JSON-safe values.
            if isinstance(value, bytes):
                value = f"<binary data: {len(value)} bytes>"
            elif not isinstance(value, (str, int, float, bool, type(None))):
                value = str(value)

            exif[tag_name] = value

        info_keys = sorted(image.info.keys())

    software = exif.get("Software")

    return {
        "sha256": sha256,
        "file_size_bytes": len(content),
        "format": image_format,
        "width": width,
        "height": height,
        "mode": image_mode,
        "exif_present": bool(exif),
        "exif": exif,
        "software_tag": software,
        "embedded_info_keys": info_keys,
        "observations": {
            "metadata_available": bool(exif or info_keys),
            "software_tag_present": bool(software),
        },
        "limitations": [
            "Missing metadata does not prove AI generation.",
            "Metadata can be removed or modified by editing and sharing tools.",
            "This service does not authenticate metadata or verify C2PA credentials.",
        ],
    }
