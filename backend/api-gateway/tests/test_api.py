from io import BytesIO
import hashlib

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routes import upload
from app.services import repository, storage


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (12, 8), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_health():
    assert TestClient(app).get("/health").status_code == 200


def test_analysis_endpoint_persists_partial_when_engines_are_down(monkeypatch, tmp_path):
    monkeypatch.setattr(upload, "METADATA_SERVICE_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(upload, "MODEL_FINGERPRINT_SERVICE_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path / "uploads")
    storage.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    response = client.post(
        "/api/v1/analyses", files={"file": ("evidence.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "partial"
    assert body["sha256"]
    assert body["engine_results"]["metadata-provenance"]["status"] == "failed"
    assert body["engine_results"]["model-fingerprint"]["status"] == "failed"
    fetched = client.get("/api/v1/analyses/" + body["analysis_id"])
    assert fetched.status_code == 200
    assert fetched.json()["engine_results"] == body["engine_results"]


def test_analysis_endpoint_runs_both_engines(monkeypatch, tmp_path):
    digest = hashlib.sha256(png_bytes()).hexdigest()

    async def fake_call(service_url, filename, content, content_type, analysis_id):
        if "model-fingerprint" in service_url:
            return {
                "analysis_id": analysis_id,
                "image": {"sha256": digest},
                "findings": {"outcome": "inconclusive", "attribution_supported": False},
            }
        return {"analysis_id": analysis_id, "file": {"sha256": digest}, "metadata": {}, "observations": []}

    monkeypatch.setattr(upload, "METADATA_SERVICE_URL", "http://metadata-provenance:8001")
    monkeypatch.setattr(upload, "MODEL_FINGERPRINT_SERVICE_URL", "http://model-fingerprint:8002")
    monkeypatch.setattr(upload, "_call_engine", fake_call)
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path / "uploads")
    storage.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    response = TestClient(app).post(
        "/api/v1/analyses", files={"file": ("evidence.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["engine_results"]["metadata-provenance"]["status"] == "completed"
    fingerprint = body["engine_results"]["model-fingerprint"]["result"]
    assert fingerprint["findings"]["outcome"] == "inconclusive"
    assert fingerprint["findings"]["attribution_supported"] is False


def test_rejects_mismatched_content_type():
    response = TestClient(app).post(
        "/api/v1/analyses", files={"file": ("bad.png", b"not a png", "image/png")}
    )
    assert response.status_code in (415, 422)
