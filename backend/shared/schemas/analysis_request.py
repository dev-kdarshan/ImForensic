from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    analysis_id: str
    image_ref: str
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    requested_engines: list[str] = Field(default_factory=list)
