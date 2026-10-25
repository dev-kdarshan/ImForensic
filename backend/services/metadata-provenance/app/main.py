
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.analyzer import analyze_image

app = FastAPI(
    title="ImForensic Metadata & Provenance Service",
    version="0.1.0",
)


class AnalyzeRequest(BaseModel):
    image_path: str = Field(min_length=1)


@app.get("/health")
def health():
    return {"status": "ok", "service": "metadata-provenance"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        return analyze_image(request.image_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Image file not found.",
        ) from None
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not analyze image: {type(exc).__name__}",
        ) from None
