from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (10, 10), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "metadata-provenance"


def test_analyze_upload():
    response = TestClient(app).post(
        "/analyze", files={"file": ("sample.png", png_bytes(), "image/png")}
    )
    assert response.status_code == 200
    assert response.json()["file"]["format"] == "PNG"


def test_rejects_oversized_upload():
    response = TestClient(app).post(
        "/analyze",
        files={"file": ("large.png", b"x" * (20 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413
