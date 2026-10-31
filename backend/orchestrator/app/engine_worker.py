"""One independently scalable worker per engine; Kafka carries references, never image bytes."""
from __future__ import annotations
import hashlib,json,os,time
from urllib.parse import quote
import httpx
from confluent_kafka import Consumer,Producer,KafkaException
from shared.kafka.topics import ENGINE_TASKS,ENGINE_RESULTS
from shared.schemas.engine_result import normalize_engine_result
ENGINE_URLS={
 "metadata-provenance":os.getenv("METADATA_SERVICE_URL","http://metadata-provenance:8001"),
 "model-fingerprint":os.getenv("MODEL_FINGERPRINT_SERVICE_URL","http://model-fingerprint:8002"),
 "pixel-forensics":os.getenv("PIXEL_FORENSICS_SERVICE_URL","http://pixel-forensics:8003"),
 "ai-content-detection":os.getenv("AI_CONTENT_DETECTION_SERVICE_URL","http://ai-content-detection:8004"),
 "watermark-detection":os.getenv("WATERMARK_DETECTION_SERVICE_URL","http://watermark-detection:8005"),
 "visual-consistency":os.getenv("VISUAL_CONSISTENCY_SERVICE_URL","http://visual-consistency:8006")}
GATEWAY_URL=os.getenv("GATEWAY_INTERNAL_URL","http://api-gateway:8000").rstrip("/")
TOKEN=os.getenv("IMFORENSIC_INTERNAL_TOKEN",""); BOOTSTRAP=os.getenv("KAFKA_BOOTSTRAP_SERVERS","kafka:9092")
TIMEOUT=float(os.getenv("ENGINE_HTTP_TIMEOUT_SECONDS","120"))
def _publish(producer,task,result):
    payload={"schema_version":"1.0.0","task_id":task["task_id"],"analysis_id":task["analysis_id"],
      "engine":task["engine"],"expected_engines":task["expected_engines"],"result":result}
    errors=[]
    producer.produce(ENGINE_RESULTS,key=task["task_id"],value=json.dumps(payload,separators=(",",":")).encode(),
      on_delivery=lambda error,message: errors.append(str(error)) if error else None)
    if producer.flush(20): raise TimeoutError("Engine result publish timed out")
    if errors: raise KafkaException(errors[0])
def _run_engine(task):
    engine=task["engine"]
    if task.get("image_ref") != f"storage://analysis/{task['analysis_id']}":
        raise ValueError("Unsupported storage reference")
    headers={"X-ImForensic-Internal-Token":TOKEN}
    with httpx.Client(timeout=TIMEOUT) as client:
        response=client.get(f"{GATEWAY_URL}/internal/images/{quote(task['analysis_id'])}",headers=headers)
        response.raise_for_status(); content=response.content
        if hashlib.sha256(content).hexdigest()!=task["sha256"]: raise ValueError("Stored image SHA-256 mismatch")
        media_type=response.headers.get("content-type","application/octet-stream").split(";")[0]
        data={"analysis_id":task["analysis_id"]}
        result=client.post(f"{ENGINE_URLS[engine].rstrip('/')}/analyze",params=data,data=data,
                           files={"file":("image",content,media_type)})
        result.raise_for_status(); raw=result.json()
    if not isinstance(raw,dict): raise ValueError("Engine response was not a JSON object")
    for key in ("file","image","input"):
        candidate=raw.get(key)
        if isinstance(candidate,dict) and candidate.get("sha256") and candidate["sha256"]!=task["sha256"]:
            raise ValueError("Engine-reported SHA-256 mismatch")
    raw.setdefault("analysis_id",task["analysis_id"]); raw.setdefault("engine",engine)
    raw.setdefault("engine_version","unknown"); raw.setdefault("status","completed")
    return normalize_engine_result(raw,expected_engine=engine).model_dump(mode="json")
def run():
    engine=os.getenv("ENGINE_NAME","").strip()
    if engine not in ENGINE_URLS: raise RuntimeError("ENGINE_NAME must be one of: "+", ".join(ENGINE_URLS))
    consumer=Consumer({"bootstrap.servers":BOOTSTRAP,"group.id":f"imforensic-{engine}-v1",
      "enable.auto.commit":False,"auto.offset.reset":"earliest"})
    producer=Producer({"bootstrap.servers":BOOTSTRAP,"enable.idempotence":True,"acks":"all","retries":5})
    consumer.subscribe([ENGINE_TASKS])
    while True:
        message=consumer.poll(1.0)
        if message is None: continue
        if message.error(): continue
        try:
            task=json.loads(message.value())
            if task.get("engine")!=engine:
                consumer.commit(message=message,asynchronous=False); continue
            if not TOKEN: raise RuntimeError("IMFORENSIC_INTERNAL_TOKEN is not configured")
            result=None; error=None
            for attempt in range(3):
                try: result=_run_engine(task); break
                except (httpx.HTTPError,ValueError,RuntimeError) as exc:
                    error=exc
                    if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code<500: break
                    time.sleep(0.5*(2**attempt))
            if result is None:
                result={"schema_version":"1.0.0","analysis_id":task["analysis_id"],"engine":engine,
                  "engine_version":"unknown","status":"failed","findings":[],"raw_result":{},"warnings":[],
                  "limitations":[],"error":{"code":"ENGINE_EXECUTION_FAILED",
                  "message":type(error).__name__ if error else "Unknown engine error","retryable":False}}
            _publish(producer,task,result); consumer.commit(message=message,asynchronous=False)
        except Exception: time.sleep(1)
if __name__=="__main__": run()
