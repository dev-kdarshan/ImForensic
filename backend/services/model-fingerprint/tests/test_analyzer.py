from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.analyzer import analyze_image
from app.main import app


client = TestClient(app)


def make_png(size=(64, 48), color=(120, 80, 200)):
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_extracts_deterministic_features_without_attribution():
    content = make_png()
    first = analyze_image(content)
    second = analyze_image(content)

    assert first == second
    assert first["status"] == "completed"
    assert first["findings"]["outcome"] == "inconclusive"
    assert first["findings"]["attribution_supported"] is False
    assert first["findings"]["candidate_scores"] == []
    assert first["image"]["sha256"]


def test_feature_profile_has_documented_descriptors():
    result = analyze_image(make_png())
    profile = result["findings"]["feature_profile"]

    assert profile["preprocessing"]["feature_schema_version"] == "1.0"
    assert set(profile["channels"]) == {"red", "green", "blue"}
    assert len(profile["channels"]["red"]["histogram_16_bins"]) == 16
    assert len(profile["grayscale"]["histogram_32_bins"]) == 32
    assert "edge_response_proxy" in profile
    assert "spatial_luminance" in profile


def test_rejects_invalid_image():
    with pytest.raises(ValueError, match="invalid"):
        analyze_image(b"not an image")


def test_rejects_empty_image():
    with pytest.raises(ValueError, match="empty"):
        analyze_image(b"")


def test_http_health_and_readiness():
    assert client.get("/health").status_code == 200
    ready = client.get("/ready").json()
    assert ready["status"] == "ready"
    assert ready["attribution_model_loaded"] is False


def test_http_analyze_returns_inconclusive_result():
    response = client.post(
        "/analyze",
        files={"file": ("sample.png", make_png(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "model-fingerprint"
    assert body["findings"]["outcome"] == "inconclusive"
    assert body["findings"]["attribution_supported"] is False


def test_http_rejects_unsupported_format():
    response = client.post(
        "/analyze",
        files={"file": ("sample.gif", b"GIF89a", "image/gif")},
    )
    assert response.status_code == 422
