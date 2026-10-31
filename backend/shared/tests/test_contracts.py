import pytest
from pydantic import ValidationError
from shared.schemas.analysis_request import AnalysisRequest
from shared.schemas.engine_result import normalize_engine_result


def test_analysis_request_accepts_secure_storage_reference():
    request = AnalysisRequest(analysis_id="12345678-1234-5678-1234-567812345678",
        image_ref="storage://uploads/123/image.jpg", sha256="a" * 64,
        requested_engines=["metadata-provenance", "pixel-forensics"])
    assert request.schema_version == "1.0.0"


@pytest.mark.parametrize("reference", ["/etc/passwd", "file:///etc/passwd", "storage://bucket/../secret"])
def test_analysis_request_rejects_unsafe_reference(reference):
    with pytest.raises(ValidationError):
        AnalysisRequest(analysis_id="12345678-1234-5678-1234-567812345678",
            image_ref=reference, sha256="a" * 64, requested_engines=["pixel-forensics"])


def test_normalizer_is_stable_and_preserves_raw_result():
    payload = {"analysis_id": "a-1", "engine": "pixel-forensics", "engine_version": "1",
               "status": "completed", "findings": {"noise": {"mean": 2}}, "processing_time_ms": 4.2}
    first = normalize_engine_result(payload)
    second = normalize_engine_result(payload)
    assert first.findings[0].finding_id == second.findings[0].finding_id
    assert first.raw_result == payload
    assert first.findings[0].source_engine == "pixel-forensics"
