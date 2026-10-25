
from fastapi import FastAPI

from app.routes.upload import router as upload_router

app = FastAPI(title="ImForensic API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-gateway"}


app.include_router(upload_router, prefix="/api/v1", tags=["Analysis"])
