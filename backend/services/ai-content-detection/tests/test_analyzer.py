from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.analyzer import MAX_IMAGE_BYTES, UnsupportedImageError, analyze_image, inspect_image
from app.main import app


def make_image(fmt="PNG", size=(48, 32)):
    stream = BytesIO()
    Image.new("RGB", size, (70, 120, 160)).save(stream, format=fmt)
    return stream.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_supported_formats_are_inspected(fmt):
    result = inspect_image(make_image(fmt))
    assert result["format"] == fmt
    assert result["width"] == 48
    assert len(result["sha256"]) == 64


def test_analysis_is_partial_and_inconclusive_without_model():
    result = analyze_image(make_image())
    assert UUID(result["analysis_id"])
    assert result["engine"] == "ai-content-detection"
    assert result["status"] == "partial"
    assert result["findings"]["outcome"] == "inconclusive"
    assert result["findings"]["reason_code"] == "MODEL_NOT_CONFIGURED"
    assert result["findings"]["score"] is None
    assert result["findings"]["calibrated_probability"] is None
    assert result["model_version"] is None


def test_analysis_id_is_preserved():
    analysis_id = "a24d0b0a-8b63-4d45-85ce-4a3a9a234d87"
    assert analyze_image(make_image(), analysis_id)["analysis_id"] == analysis_id


@pytest.mark.parametrize("content", [b"", b"not-an-image"])
def test_invalid_content_is_rejected(content):
    with pytest.raises(UnsupportedImageError):
        inspect_image(content)


def test_oversized_content_is_rejected(monkeypatch):
    monkeypatch.setattr("app.analyzer.MAX_IMAGE_BYTES", 4)
    with pytest.raises(UnsupportedImageError, match="20 MB"):
        inspect_image(b"12345")


def test_api_health_and_not_ready_contract():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["model_configured"] is False
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["detail"]["reason"] == "MODEL_NOT_CONFIGURED"


def test_api_returns_partial_result_without_claiming_detection():
    response = TestClient(app).post(
        "/analyze",
        files={"file": ("sample.png", make_image(), "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["findings"]["outcome"] == "inconclusive"
    assert payload["findings"]["decision"] == "inconclusive"
    assert payload["findings"]["score"] is None


def test_api_rejects_invalid_uuid():
    response = TestClient(app).post(
        "/analyze",
        data={"analysis_id": "invalid"},
        files={"file": ("sample.png", make_image(), "image/png")},
    )
    assert response.status_code == 422


def test_api_rejects_upload_over_limit():
    response = TestClient(app).post(
        "/analyze",
        files={"file": ("large.png", b"x" * (MAX_IMAGE_BYTES + 1), "image/png")},
    )
    assert response.status_code == 413
