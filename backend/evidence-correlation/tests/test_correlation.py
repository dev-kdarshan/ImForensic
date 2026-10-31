from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def result(engine, findings, status="completed"):
    return {"analysis_id": "analysis-1", "engine": engine, "engine_version": "1.0",
            "status": status, "findings": findings, "warnings": []}


def test_correlation_preserves_sources_and_does_not_aggregate_scores():
    response = client.post("/correlate", json={"analysis_id": "analysis-1",
        "expected_engines": ["pixel-forensics", "visual-consistency"],
        "results": [result("pixel-forensics", {"signal": {"value": 0.7}})]})
    assert response.status_code == 200
    body = response.json()
    assert body["missing_engines"] == ["visual-consistency"]
    assert body["summary"]["scores_aggregated"] is False
    assert body["engine_results"][0]["findings"][0]["source_engine"] == "pixel-forensics"


def test_correlation_flags_only_explicit_comparison_key_conflicts():
    response = client.post("/correlate", json={"analysis_id": "analysis-1",
        "expected_engines": ["pixel-forensics", "visual-consistency"],
        "results": [result("pixel-forensics", {"obs": {"comparison_key": "image.width", "value": 100}}),
                    result("visual-consistency", {"obs": {"comparison_key": "image.width", "value": 200}})]})
    assert response.status_code == 200
    assert response.json()["conflicts"][0]["comparison_key"] == "image.width"


def test_correlation_rejects_cross_analysis_results_and_duplicate_engines():
    mismatch = client.post("/correlate", json={"analysis_id": "analysis-1", "results": [result("pixel-forensics", {}, "completed") | {"analysis_id": "other"}]})
    duplicate = client.post("/correlate", json={"analysis_id": "analysis-1", "results": [result("pixel-forensics", {}), result("pixel-forensics", {})]})
    assert mismatch.status_code == 422
    assert duplicate.status_code == 422


def test_correlation_preserves_canonical_engine_result_envelope():
    canonical = {
        "schema_version": "1.0.0", "analysis_id": "analysis-1",
        "engine": "pixel-forensics", "engine_version": "0.1.0", "status": "completed",
        "findings": [{"finding_id": "stable-123", "finding_type": "noise",
                      "source_engine": "pixel-forensics", "source_path": "findings.noise",
                      "value": {"mean": 2}, "evidence": []}],
        "raw_result": {"engine": "pixel-forensics", "findings": {"noise": {"mean": 2}}},
        "warnings": [], "limitations": []
    }
    response = client.post("/correlate", json={"analysis_id": "analysis-1",
        "expected_engines": ["pixel-forensics"], "results": [canonical]})
    assert response.status_code == 200
    assert response.json()["engine_results"][0]["findings"][0]["finding_id"] == "stable-123"
