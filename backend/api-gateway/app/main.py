import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.upload import router as upload_router
from app.services.repository import initialize

app = FastAPI(
    title="ImForensic API",
    version="1.0.0",
    description="Upload images and retrieve Metadata & Provenance analysis results.",
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    initialize()


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-gateway", "version": "1.0.0"}


app.include_router(upload_router, prefix="/api/v1", tags=["Analysis"])
