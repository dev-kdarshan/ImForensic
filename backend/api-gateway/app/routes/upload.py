from __future__ import annotations
import hashlib, os
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import APIRouter,File,HTTPException,UploadFile
from PIL import Image,UnidentifiedImageError
from app.services.repository import get_analysis,save_analysis
from app.services.storage import save_image
router=APIRouter()
MAX_FILE_SIZE=int(os.getenv("MAX_UPLOAD_MB","20"))*1024*1024
ALLOWED_TYPES={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}
ORCHESTRATOR_URL=os.getenv("ORCHESTRATOR_URL","http://127.0.0.1:8007").rstrip("/")
ENGINE_TIMEOUT=float(os.getenv("ENGINE_TIMEOUT_SECONDS","15"))
ALL_ENGINES=["metadata-provenance","model-fingerprint","pixel-forensics","ai-content-detection","watermark-detection","visual-consistency"]
def _validate_image(content:bytes,extension:str):
    signatures={".jpg":content.startswith(b"\xff\xd8\xff"),".png":content.startswith(b"\x89PNG\r\n\x1a\n"),
                ".webp":len(content)>=12 and content.startswith(b"RIFF") and content[8:12]==b"WEBP"}
    if not signatures[extension]: raise HTTPException(status_code=415,detail="Image content does not match its declared type.")
    try:
        with Image.open(__import__("io").BytesIO(content)) as image:
            if image.format not in {"JPEG","PNG","WEBP"}: raise HTTPException(status_code=415,detail="Unsupported image format.")
            if image.width*image.height>40_000_000: raise HTTPException(status_code=413,detail="Image dimensions exceed the 40-megapixel limit.")
            image.verify()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise HTTPException(status_code=422,detail="Uploaded file is not a valid safe image.") from None
@router.post("/analyses",status_code=202)
async def create_analysis(file:UploadFile=File(...)):
    extension=ALLOWED_TYPES.get(file.content_type or "")
    if not extension: raise HTTPException(status_code=415,detail="Only JPEG, PNG and WebP images are supported.")
    content=await file.read(MAX_FILE_SIZE+1)
    if not content: raise HTTPException(status_code=400,detail="Empty file.")
    if len(content)>MAX_FILE_SIZE: raise HTTPException(status_code=413,detail=f"Image exceeds {MAX_FILE_SIZE//(1024*1024)} MB.")
    _validate_image(content,extension)
    analysis_id=str(uuid4()); filename=Path(file.filename or "image").name.replace("\\","_")
    sha256=hashlib.sha256(content).hexdigest()
    try: stored_path=save_image(analysis_id,content,extension)
    except OSError: raise HTTPException(status_code=500,detail="Could not store the uploaded image.") from None
    created_at=datetime.now(timezone.utc).isoformat()
    record={"analysis_id":analysis_id,"status":"queued","created_at":created_at,"filename":filename,
      "content_type":file.content_type,"size_bytes":len(content),"sha256":sha256,
      "storage_ref":Path(stored_path).name,"result":None,"engine_results":{},
      "expected_engines":ALL_ENGINES,"error":None}
    save_analysis(record); await file.close()
    event={"schema_version":"1.0.0","analysis_id":analysis_id,"image_ref":f"storage://analysis/{analysis_id}",
      "sha256":sha256,"requested_engines":ALL_ENGINES,"idempotency_key":analysis_id,
      "created_at":created_at,"trace_id":analysis_id}
    try:
        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT) as client:
            response=await client.post(f"{ORCHESTRATOR_URL}/jobs",json=event); response.raise_for_status()
    except (httpx.HTTPError,ValueError):
        record["status"]="failed"; record["error"]="The analysis could not be queued. The uploaded image is retained for retry or cleanup."
        save_analysis(record)
        raise HTTPException(status_code=503,detail={"code":"ORCHESTRATOR_UNAVAILABLE","analysis_id":analysis_id,
                            "message":record["error"]}) from None
    return {"analysis_id":analysis_id,"status":"queued","created_at":created_at,"filename":filename,
      "content_type":file.content_type,"size_bytes":len(content),"sha256":sha256,
      "expected_engines":ALL_ENGINES,"engine_results":{},"poll_url":f"/api/v1/analyses/{analysis_id}"}
@router.get("/analyses/{analysis_id}")
def read_analysis(analysis_id:str):
    record=get_analysis(analysis_id)
    if record is None: raise HTTPException(status_code=404,detail="Analysis not found.")
    return record
