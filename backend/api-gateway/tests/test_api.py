from io import BytesIO

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


def test_analysis_endpoint_persists_partial_when_metadata_service_is_down(monkeypatch, tmp_path):
    monkeypatch.setattr(upload, "METADATA_SERVICE_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path / "uploads")
    response = TestClient(app).post(
        "/api/v1/analyses", files={"file": ("evidence.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "partial"
    assert body["sha256"]
    assert body["error"].startswith("Metadata analysis unavailable")
    fetched = TestClient(app).get("/api/v1/analyses/" + body["analysis_id"])
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == body["analysis_id"]


def test_rejects_mismatched_content_type():
    response = TestClient(app).post(
        "/api/v1/analyses", files={"file": ("bad.png", b"not a png", "image/png")}
    )
    assert response.status_code in (415, 422)
