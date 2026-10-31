from app.worker import _task_id


def test_task_id_is_deterministic_and_engine_scoped():
    assert _task_id("analysis-1", "pixel-forensics") == _task_id("analysis-1", "pixel-forensics")
    assert _task_id("analysis-1", "pixel-forensics") != _task_id("analysis-1", "watermark-detection")
