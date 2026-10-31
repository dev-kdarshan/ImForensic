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

def _publish(producer: Producer, topic: str, key: str, value: bytes, headers: list[tuple[str, str]]) -> None:
    delivery_errors: list[str] = []
    def delivered(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))
    producer.produce(topic, key=key, value=value, headers=headers, on_delivery=delivered)
    if producer.flush(10):
        raise TimeoutError("Kafka delivery did not complete before the timeout")
    if delivery_errors:
        raise KafkaException(delivery_errors[0])

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
        _publish(_get_producer(), ANALYSIS_JOBS, request.analysis_id,
                 json.dumps(event, separators=(",", ":")).encode("utf-8"),
                 [("schema_version", request.schema_version),
                  ("idempotency_key", request.idempotency_key or request.analysis_id)])
    except (KafkaException, TimeoutError, BufferError) as exc:
        raise HTTPException(status_code=503, detail={"code": "JOB_PUBLISH_FAILED", "message": type(exc).__name__}) from None
    return {"analysis_id": request.analysis_id, "status": "accepted", "topic": ANALYSIS_JOBS,
            "delivery_semantics": "at_least_once; downstream consumers must deduplicate by idempotency_key"}
