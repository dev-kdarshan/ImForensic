from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    analysis_id: str
    image_ref: str
    sha256: str = Field(min_length=64, max_length=64)
    requested_engines: list[str]
