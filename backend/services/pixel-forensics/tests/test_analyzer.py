from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.analyzer import MAX_IMAGE_BYTES, analyze_image
from app.main import app


def make_image(fmt="PNG", size=(48, 32)):
    stream = BytesIO()
    Image.new("RGB", size, (110, 80, 40)).save(stream, format=fmt, quality=88)
    return stream.getvalue()


def test_png_returns_inconclusive_descriptive_evidence():
    result = analyze_image(make_image("PNG"))
    assert result["engine"] == "pixel-forensics"
    assert result["status"] == "completed"
    assert result["findings"]["outcome"] == "inconclusive"
    assert result["findings"]["tampering_supported"] is False
    assert {item["id"] for item in result["findings"]["items"]} == {
        "PIXEL-JPEG-QTABLE-001", "PIXEL-RESIDUAL-001", "PIXEL-EDGE-001"
    }
    residual = result["findings"]["items"][1]["evidence"]
    assert len(residual["tile_measurements"]) == 16
    assert residual["tile_measurements"][0]["source_bounds_px"]["right"] > 0


def test_jpeg_exposes_quantization_details_when_available():
    result = analyze_image(make_image("JPEG"))
    quant = result["findings"]["items"][0]["evidence"]
    assert quant["applicable"] is True
    assert isinstance(quant["tables"], list)
    assert result["image"]["format"] == "JPEG"


def test_repeat_analysis_is_deterministic_except_timing():
    content = make_image("PNG")
    first = analyze_image(content)
    second = analyze_image(content)
    assert first["sha256"] == second["sha256"]
    assert first["findings"] == second["findings"]
    assert first["methods"] == second["methods"]


def test_empty_and_malformed_inputs_are_rejected():
    with pytest.raises(ValueError, match="empty"):
        analyze_image(b"")
    with pytest.raises(ValueError, match="valid supported image"):
        analyze_image(b"not an image")


def test_oversized_input_is_rejected(monkeypatch):
    monkeypatch.setattr("app.analyzer.MAX_IMAGE_BYTES", 4)
    with pytest.raises(ValueError, match="20 MB"):
        analyze_image(b"12345")


def test_truncated_image_is_rejected():
    content = make_image("PNG")
    with pytest.raises(ValueError):
        analyze_image(content[:24])


def test_api_health_readiness_and_analysis():
    client = TestClient(app)
    assert client.get("/health").json()["service"] == "pixel-forensics"
    assert client.get("/ready").json()["status"] == "ready"
    response = client.post(
        "/analyze",
        files={"file": ("sample.png", make_image("PNG"), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["findings"]["outcome"] == "inconclusive"


def test_api_rejects_invalid_analysis_uuid():
    response = TestClient(app).post(
        "/analyze",
        data={"analysis_id": "not-a-uuid"},
        files={"file": ("sample.png", make_image("PNG"), "image/png")},
    )
    assert response.status_code == 422


def test_api_rejects_upload_over_20mb():
    response = TestClient(app).post(
        "/analyze",
        files={"file": ("large.png", b"x" * (MAX_IMAGE_BYTES + 1), "image/png")},
    )
    assert response.status_code == 413
