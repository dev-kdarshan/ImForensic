"""Canonical engine-result envelope and compatibility normalizer."""
from __future__ import annotations
import hashlib
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    evidence_id: str
    source_engine: str
    source_path: str
    observation: Any = None

class EngineFinding(BaseModel):
    model_config = ConfigDict(extra="allow")
    finding_id: str
    finding_type: str
    source_engine: str
    source_path: str
    value: Any = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    score: float | None = None
    score_semantics: str | dict[str, Any] | None = None
    confidence_semantics: str | dict[str, Any] | None = None

class EngineError(BaseModel):
    code: str
    message: str
    retryable: bool = False

class EngineResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: str = "1.0.0"
    analysis_id: str
    engine: str
    engine_version: str
    status: Literal["completed", "partial", "failed"]
    findings: list[EngineFinding] = Field(default_factory=list)
    raw_result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    score_semantics: str | dict[str, Any] | None = None
    confidence_semantics: str | dict[str, Any] | None = None
    error: EngineError | None = None
    processing_time_ms: float | None = Field(default=None, ge=0)

def _stable_id(analysis_id: str, engine: str, source_path: str) -> str:
    return hashlib.sha256(f"{analysis_id}:{engine}:{source_path}".encode("utf-8")).hexdigest()[:24]

def normalize_engine_result(payload: dict[str, Any], expected_engine: str | None = None) -> EngineResult:
    """Wrap a legacy engine payload while retaining its original findings verbatim."""
    if not isinstance(payload, dict):
        raise ValueError("Engine result must be a JSON object")
    analysis_id = str(payload.get("analysis_id") or "")
    engine = str(payload.get("engine") or expected_engine or "unknown")
    if not analysis_id or not engine:
        raise ValueError("Engine result must contain analysis_id and engine")
    if expected_engine and engine != expected_engine:
        raise ValueError(f"Engine identity mismatch: expected {expected_engine}, received {engine}")
    status = payload.get("status", "partial")
    if status not in {"completed", "partial", "failed"}:
        status = "partial"
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, dict):
        raw_findings = {"result": raw_findings} if raw_findings is not None else {}
    findings = []
    for key, value in sorted(raw_findings.items(), key=lambda item: str(item[0])):
        source_path = f"findings.{key}"
        stable_id = _stable_id(analysis_id, engine, source_path)
        evidence = [EvidenceItem(evidence_id=stable_id, source_engine=engine, source_path=source_path, observation=value)]
        findings.append(EngineFinding(finding_id=stable_id, finding_type=str(key), source_engine=engine,
                                      source_path=source_path, value=value, evidence=evidence))
    return EngineResult(
        analysis_id=analysis_id, engine=engine,
        engine_version=str(payload.get("engine_version") or payload.get("model_version") or "unknown"),
        status=status, findings=findings, raw_result=payload,
        warnings=list(payload.get("warnings") or []), limitations=list(payload.get("limitations") or []),
        score_semantics=raw_findings.get("score_semantics"),
        processing_time_ms=payload.get("processing_time_ms"),
    )
