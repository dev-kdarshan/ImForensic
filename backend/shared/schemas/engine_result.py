from typing import Any, Literal

from pydantic import BaseModel, Field


class EngineResult(BaseModel):
    analysis_id: str
    engine: str
    status: Literal["completed", "partial", "failed"]
    findings: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    model_version: str | None = None
