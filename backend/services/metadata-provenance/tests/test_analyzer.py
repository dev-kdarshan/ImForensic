from io import BytesIO

import pytest
from PIL import Image

from app.analyzer import analyze_image


def image_bytes(fmt="PNG", size=(32, 24)):
    stream = BytesIO()
    Image.new("RGB", size, "navy").save(stream, format=fmt)
    return stream.getvalue()


def test_extracts_dimensions_hash_and_engine_name():
    result = analyze_image(image_bytes(), "sample.png")
    assert result["engine"] == "metadata-provenance"
    assert result["file"]["width"] == 32
    assert result["file"]["height"] == 24
    assert len(result["file"]["sha256"]) == 64
    assert result["file"]["filename"] == "sample.png"


def test_rejects_non_image_bytes():
    with pytest.raises(ValueError, match="valid supported image"):
        analyze_image(b"not an image")


def test_rejects_unsupported_image_format():
    with pytest.raises(ValueError, match="Only JPEG, PNG and WebP"):
        analyze_image(image_bytes("BMP"))


def test_rejects_oversized_pixel_dimensions():
    with pytest.raises(ValueError, match="pixel limit"):
        analyze_image(image_bytes(size=(7000, 7000)))
