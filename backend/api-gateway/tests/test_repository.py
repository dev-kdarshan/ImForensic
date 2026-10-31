import json
import app.services.repository as repository


def test_engine_result_upsert_is_idempotent_and_completes_job(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PATH", tmp_path / "test.sqlite3")
    repository.save_analysis({
        "analysis_id": "analysis-1", "status": "queued", "created_at": "2026-01-01T00:00:00Z",
        "filename": "x.png", "content_type": "image/png", "size_bytes": 10, "sha256": "a" * 64,
        "storage_ref": "analysis-1.png", "expected_engines": ["metadata-provenance", "pixel-forensics"],
    })
    result = {"status": "completed", "engine": "metadata-provenance"}
    repository.record_engine_result("analysis-1", "metadata-provenance", result)
    repository.record_engine_result("analysis-1", "metadata-provenance", result)
    state = repository.record_engine_result("analysis-1", "pixel-forensics",
                                             {"status": "completed", "engine": "pixel-forensics"})
    assert state["status"] == "completed"
    assert len(state["engine_results"]) == 2
    assert repository.get_analysis("analysis-1")["status"] == "completed"
