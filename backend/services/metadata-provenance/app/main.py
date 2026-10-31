from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import UnidentifiedImageError

from app.analyzer import analyze_image

app = FastAPI(
    title="ImForensic Metadata & Provenance Engine",
    version="1.0.0",
    description="Extracts image metadata and provenance indicators without trusting client paths.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "metadata-provenance", "version": "1.0.0"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB.")
    try:
        return analyze_image(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except (OSError, UnidentifiedImageError):
        raise HTTPException(status_code=422, detail="Image could not be analyzed.") from None
    finally:
        await file.close()
