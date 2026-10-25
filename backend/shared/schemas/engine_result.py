from typing import Any, Literal
from pydantic import BaseModel

class EngineResult(BaseModel):
    analysis_id: str
    engine: str
    status: Literal["completed", "partial", "failed"]
    findings: dict[str, Any] = {}
    warnings: list[str] = []
    model_version: str | None = None
