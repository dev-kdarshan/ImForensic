import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.upload import router as upload_router
from app.routes.internal import router as internal_router
from app.services.repository import initialize
app=FastAPI(title="ImForensic API",version="1.1.0",
 description="Upload images and retrieve asynchronous six-engine analysis results.")
origins=os.getenv("CORS_ORIGINS","http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware,allow_origins=[o.strip() for o in origins if o.strip()],
 allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["*"])
@app.on_event("startup")
def startup(): initialize()
@app.get("/health")
def health(): return {"status":"ok","service":"api-gateway","version":"1.1.0"}
app.include_router(upload_router,prefix="/api/v1",tags=["Analysis"])
app.include_router(internal_router)
