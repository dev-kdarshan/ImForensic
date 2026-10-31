"""HTTP ingress for asynchronous analysis jobs; Kafka receives references, never image bytes."""
from __future__ import annotations
import json
import os
from typing import Any
from confluent_kafka import KafkaException, Producer
from fastapi import FastAPI, HTTPException
from shared.schemas.analysis_request import AnalysisRequest
from shared.kafka.topics import ANALYSIS_JOBS

app = FastAPI(title="ImForensic Orchestrator", version="1.0.0")
_producer: Producer | None = None

def _get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer({"bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
                              "enable.idempotence": True, "acks": "all", "retries": 5, "message.timeout.ms": 10000})
    return _producer

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator", "version": "1.0.0"}

@app.get("/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready", "service": "orchestrator", "messaging": "producer_lazy_initialized"}

@app.post("/jobs", status_code=202)
def submit_job(request: AnalysisRequest) -> dict[str, Any]:
    event = request.model_dump(mode="json")
    try:
        producer = _get_producer()
        producer.produce(ANALYSIS_JOBS, key=request.analysis_id,
                         value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
                         headers={"schema_version": request.schema_version,
                                  "idempotency_key": request.idempotency_key or request.analysis_id})
        if producer.flush(10):
            raise TimeoutError("Kafka delivery did not complete before the timeout")
    except (KafkaException, TimeoutError, BufferError) as exc:
        raise HTTPException(status_code=503, detail={"code": "JOB_PUBLISH_FAILED", "message": type(exc).__name__}) from None
    return {"analysis_id": request.analysis_id, "status": "accepted", "topic": ANALYSIS_JOBS,
            "delivery_semantics": "at_least_once; downstream consumers must deduplicate by idempotency_key"}
