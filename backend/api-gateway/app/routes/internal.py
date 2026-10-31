"""Private worker callbacks and image retrieval protected by a shared internal token."""
import hmac, os
from uuid import UUID
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from app.services.repository import get_analysis, record_engine_result, record_correlation
from app.services.storage import image_path
router=APIRouter(prefix="/internal",include_in_schema=False)
TOKEN=os.getenv("IMFORENSIC_INTERNAL_TOKEN","")
def _authorize(value):
    if not TOKEN or not value or not hmac.compare_digest(TOKEN,value):
        raise HTTPException(status_code=401,detail="Unauthorized internal service request")
class EngineResultCallback(BaseModel):
    model_config=ConfigDict(extra="forbid")
    analysis_id:str; engine:str; result:dict
class CorrelationCallback(BaseModel):
    model_config=ConfigDict(extra="forbid")
    analysis_id:str; correlation:dict
@router.get("/images/{analysis_id}")
def read_stored_image(analysis_id:str,x_imforensic_internal_token:str|None=Header(default=None)):
    _authorize(x_imforensic_internal_token)
    try: safe_id=str(UUID(analysis_id))
    except ValueError: raise HTTPException(status_code=404,detail="Image not found") from None
    record=get_analysis(safe_id)
    if record is None: raise HTTPException(status_code=404,detail="Image not found")
    try: path=image_path(record["storage_ref"])
    except ValueError: raise HTTPException(status_code=404,detail="Image not found") from None
    if not path.is_file(): raise HTTPException(status_code=404,detail="Image not found")
    return FileResponse(path,media_type=record["content_type"],filename=record["filename"])
@router.post("/results")
def receive_engine_result(payload:EngineResultCallback,x_imforensic_internal_token:str|None=Header(default=None)):
    _authorize(x_imforensic_internal_token)
    try: return record_engine_result(payload.analysis_id,payload.engine,payload.result)
    except KeyError: raise HTTPException(status_code=404,detail="Analysis not found") from None
@router.post("/correlation")
def receive_correlation(payload:CorrelationCallback,x_imforensic_internal_token:str|None=Header(default=None)):
    _authorize(x_imforensic_internal_token); record_correlation(payload.analysis_id,payload.correlation)
    return {"accepted":True,"analysis_id":payload.analysis_id}
