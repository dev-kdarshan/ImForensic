from app.worker import _task_id


def test_task_id_is_deterministic_and_engine_scoped():
    assert _task_id("analysis-1", "pixel-forensics") == _task_id("analysis-1", "pixel-forensics")
    assert _task_id("analysis-1", "pixel-forensics") != _task_id("analysis-1", "watermark-detection")


def test_task_identity_is_stable_for_retries():
    first = {"analysis_id": "a-1", "engine": "metadata-provenance"}
    replay = {"analysis_id": "a-1", "engine": "metadata-provenance"}
    assert _task_id(first["analysis_id"], first["engine"]) == _task_id(replay["analysis_id"], replay["engine"])
