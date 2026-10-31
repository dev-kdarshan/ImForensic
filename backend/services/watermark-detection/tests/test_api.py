from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image

from app import analyzer
from app.main import app

client = TestClient(app)


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (16, 12), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_health_and_readiness_are_explicit():
    assert client.get("/health").json()["service"] == "watermark-detection"
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert "visible_watermark_detector" in ready.json()


def test_rejects_unsupported_and_malformed_uploads():
    response = client.post("/analyze", files={"file": ("bad.gif", b"not an image", "image/gif")})
    assert response.status_code == 422


def test_no_manifest_is_not_a_claim_that_no_watermark_exists(monkeypatch):
    monkeypatch.setattr(analyzer, "_read_c2pa", lambda content, mime: {
        "status": "not_detected", "reason_code": None
    })
    response = client.post("/analyze", files={"file": ("sample.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["findings"]["outcome"] == "not_detected"
    assert body["findings"]["watermark_evidence"]["invisible"]["status"] == "unsupported"
    assert any("does not prove" in warning for warning in body["warnings"])


def test_c2pa_manifest_is_reported_as_credentials_not_watermark(monkeypatch):
    summary = {
        "active_manifest": "urn:test",
        "manifest_count": 1,
        "claim_generator": "unit-test",
        "claim_generator_info": [],
        "assertion_labels": ["c2pa.actions"],
        "validation_status": [],
        "validation_status_count": 0,
    }
    monkeypatch.setattr(analyzer, "_read_c2pa", lambda content, mime: {
        "status": "detected", "summary": summary
    })
    response = client.post("/analyze", files={"file": ("sample.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["findings"]["outcome"] == "detected"
    assert body["findings"]["content_credentials"]["category"] == "provenance_credentials_not_watermark"
    assert body["findings"]["watermark_evidence"]["invisible"]["status"] == "unsupported"


def test_parser_failure_is_inconclusive(monkeypatch):
    monkeypatch.setattr(analyzer, "_read_c2pa", lambda content, mime: {
        "status": "inconclusive", "reason_code": "C2PA_READ_FAILED"
    })
    response = client.post("/analyze", files={"file": ("sample.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    assert response.json()["findings"]["outcome"] == "inconclusive"
    assert response.json()["status"] == "partial"


def test_analysis_id_must_be_uuid(monkeypatch):
    monkeypatch.setattr(analyzer, "_read_c2pa", lambda content, mime: {
        "status": "not_detected", "reason_code": None
    })
    response = client.post(
        "/analyze",
        data={"analysis_id": "not-a-uuid"},
        files={"file": ("sample.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 422


def test_oversized_upload_rejected():
    response = client.post(
        "/analyze",
        files={"file": ("large.png", b"x" * (20 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413
