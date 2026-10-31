from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.analyzer import MAX_IMAGE_BYTES, analyze_image
from app.main import app


def make_image(fmt="PNG", size=(96, 80), pattern="solid"):
    image = Image.new("RGB", size, (100, 100, 100))
    draw = ImageDraw.Draw(image)
    if pattern == "gradient":
        for x in range(size[0]):
            shade = int(255 * x / max(1, size[0] - 1))
            draw.line((x, 0, x, size[1]), fill=(shade, shade, shade))
    elif pattern == "checker":
        block = 8
        for y in range(0, size[1], block):
            for x in range(0, size[0], block):
                shade = 240 if (x // block + y // block) % 2 else 15
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(shade, shade, shade))
    elif pattern == "split":
        draw.rectangle((size[0] // 2, 0, size[0], size[1]), fill=(220, 40, 40))
    stream = BytesIO()
    image.save(stream, format=fmt, quality=90)
    return stream.getvalue()


def test_uniform_image_is_completed_but_inconclusive():
    result = analyze_image(make_image())
    assert result["engine"] == "visual-consistency"
    assert result["status"] == "completed"
    assert result["findings"]["outcome"] == "inconclusive"
    assert result["findings"]["manipulation_supported"] is False
    assert result["findings"]["summary"]["region_count"] == 16
    assert result["findings"]["score_semantics"]["global_manipulation_score"] is None


def test_gradient_and_checkerboard_produce_bounded_measurements():
    for pattern in ("gradient", "checker"):
        result = analyze_image(make_image(pattern=pattern))
        regions = result["findings"]["regions"]
        assert len(regions) <= 16
        assert all("mean_luminance_0_255" in region["measurements"] for region in regions)
        assert all("source_bounds_px" in region for region in regions)


def test_region_coordinates_map_to_source_dimensions():
    result = analyze_image(make_image(size=(128, 64)))
    regions = result["findings"]["regions"]
    assert regions[0]["source_bounds_px"] == {"left": 0, "top": 0, "right": 32, "bottom": 16}
    assert regions[-1]["source_bounds_px"]["right"] == 128
    assert regions[-1]["source_bounds_px"]["bottom"] == 64


def test_split_colour_image_reports_variation_not_manipulation():
    result = analyze_image(make_image(pattern="split"))
    assert result["findings"]["outcome"] == "inconclusive"
    assert result["findings"]["manipulation_supported"] is False
    assert "not evidence of manipulation" in result["findings"]["summary"]["interpretation"]


def test_repeat_analysis_is_deterministic_except_timing_and_id():
    content = make_image(pattern="checker")
    first = analyze_image(content)
    second = analyze_image(content)
    assert first["image"]["sha256"] == second["image"]["sha256"]
    assert first["findings"] == second["findings"]
    assert first["methods"] == second["methods"]


def test_empty_malformed_and_unsupported_inputs_are_rejected():
    with pytest.raises(ValueError, match="empty"):
        analyze_image(b"")
    with pytest.raises(ValueError, match="invalid or could not be decoded"):
        analyze_image(b"not an image")
    with pytest.raises(ValueError, match="Only JPEG"):
        analyze_image(make_image("GIF"))


def test_oversized_input_is_rejected(monkeypatch):
    monkeypatch.setattr("app.analyzer.MAX_IMAGE_BYTES", 4)
    with pytest.raises(ValueError, match="20 MB"):
        analyze_image(b"12345")


def test_invalid_analysis_id_is_rejected():
    with pytest.raises(ValueError, match="UUID"):
        analyze_image(make_image(), "not-a-uuid")


def test_small_image_has_single_region_without_outlier_claims():
    result = analyze_image(make_image(size=(8, 8)))
    assert len(result["findings"]["regions"]) == 1
    comparison = result["findings"]["regions"][0]["within_image_comparison"]
    assert all(value["robust_z"] is None for value in comparison.values())


def test_api_health_readiness_and_analysis():
    client = TestClient(app)
    assert client.get("/health").json()["service"] == "visual-consistency"
    assert client.get("/ready").json()["status"] == "ready"
    response = client.post(
        "/analyze",
        data={"analysis_id": "123e4567-e89b-12d3-a456-426614174000"},
        files={"file": ("sample.png", make_image(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["analysis_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert response.json()["findings"]["outcome"] == "inconclusive"


def test_api_rejects_invalid_uuid_and_oversized_upload():
    client = TestClient(app)
    invalid = client.post(
        "/analyze",
        data={"analysis_id": "bad"},
        files={"file": ("sample.png", make_image(), "image/png")},
    )
    assert invalid.status_code == 422
    oversized = client.post(
        "/analyze",
        files={"file": ("large.png", b"x" * (MAX_IMAGE_BYTES + 1), "image/png")},
    )
    assert oversized.status_code == 413
