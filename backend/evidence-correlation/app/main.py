"""Source-preserving correlation; only explicit comparison keys are compared."""
from __future__ import annotations
import json
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from shared.schemas.engine_result import EngineResult, normalize_engine_result

app = FastAPI(title="ImForensic Evidence Correlation", version="1.0.0")

class CorrelationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: str
    expected_engines: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)

def _explicit_comparisons(value: Any, path: str = "findings") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("comparison_key"), str) and "value" in value:
            found.append({"comparison_key": value["comparison_key"], "value": value["value"], "source_path": path})
        for key, child in value.items():
            found.extend(_explicit_comparisons(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_explicit_comparisons(child, f"{path}[{index}]"))
    return found

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidence-correlation", "version": "1.0.0"}

@app.post("/correlate")
def correlate(request: CorrelationRequest) -> dict[str, Any]:
    normalized: list[EngineResult] = []
    seen: set[str] = set()
    for payload in request.results:
        try:
            result = normalize_engine_result(payload)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if result.analysis_id != request.analysis_id:
            raise HTTPException(status_code=422, detail="All engine results must match analysis_id")
        if result.engine in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate result for engine: {result.engine}")
        seen.add(result.engine)
        normalized.append(result)
    expected = set(request.expected_engines)
    missing = sorted(expected - seen)
    failed = sorted(result.engine for result in normalized if result.status == "failed")
    partial = sorted(result.engine for result in normalized if result.status == "partial")
    comparison_map: dict[str, list[dict[str, Any]]] = {}
    for result in normalized:
        for item in _explicit_comparisons(result.raw_result.get("findings", {})):
            comparison_map.setdefault(item["comparison_key"], []).append(
                {"engine": result.engine, "source_path": item["source_path"], "value": item["value"]})
    conflicts = []
    for key, observations in sorted(comparison_map.items()):
        distinct = {json.dumps(item["value"], sort_keys=True, default=str) for item in observations}
        if len(distinct) > 1:
            conflicts.append({"comparison_key": key, "observations": observations,
                              "interpretation": "Conflicting explicit observations; no winner selected."})
    return {
        "schema_version": "1.0.0", "analysis_id": request.analysis_id,
        "status": "partial" if missing or failed or partial else "completed",
        "engine_statuses": {result.engine: result.status for result in normalized},
        "missing_engines": missing, "failed_engines": failed, "partial_engines": partial,
        "engine_results": [result.model_dump(mode="json") for result in normalized],
        "conflicts": conflicts,
        "summary": {"received_engine_count": len(normalized), "expected_engine_count": len(expected),
                    "conflict_count": len(conflicts), "scores_aggregated": False, "independence_assumed": False},
        "limitations": ["Only explicitly keyed comparison observations are checked for disagreement.",
                        "No cross-engine score averaging, authenticity verdict, or calibrated combined probability is produced."],
    }
