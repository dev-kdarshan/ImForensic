"""Kafka fan-out worker. Delivery is at-least-once, not end-to-end exactly-once."""
from __future__ import annotations
import hashlib
import json
import os
import time
from confluent_kafka import Consumer, KafkaException, Producer
from pydantic import ValidationError
from shared.schemas.analysis_request import AnalysisRequest
from shared.kafka.topics import ANALYSIS_JOBS, ANALYSIS_JOBS_DLQ, ENGINE_TASKS

def _task_id(analysis_id: str, engine: str) -> str:
    return hashlib.sha256(f"{analysis_id}:{engine}".encode()).hexdigest()

def _publish_task(producer: Producer, task: dict) -> None:
    delivery_errors: list[str] = []
    def delivered(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))
    producer.produce(ENGINE_TASKS, key=task["task_id"], value=json.dumps(task).encode(), on_delivery=delivered)
    if producer.flush(10):
        raise TimeoutError("Kafka engine-task delivery timeout")
    if delivery_errors:
        raise KafkaException(delivery_errors[0])

def run() -> None:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": "imforensic-orchestrator-v1",
                         "enable.auto.commit": False, "auto.offset.reset": "earliest"})
    producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True, "acks": "all", "retries": 5})
    consumer.subscribe([ANALYSIS_JOBS])
    while True:
        message = consumer.poll(1.0)
        if message is None:
            continue
        if message.error():
            continue
        try:
            request = AnalysisRequest.model_validate_json(message.value())
            for engine in request.requested_engines:
                task = {"schema_version": request.schema_version, "analysis_id": request.analysis_id,
                        "task_id": _task_id(request.analysis_id, engine),
                        "idempotency_key": request.idempotency_key or request.analysis_id,
                        "engine": engine, "image_ref": request.image_ref, "sha256": request.sha256,
                        "attempt": 0, "trace_id": request.trace_id}
                last_error = None
                for attempt in range(3):
                    try:
                        _publish_task(producer, task)
                        last_error = None
                        break
                    except (KafkaException, BufferError, TimeoutError) as exc:
                        last_error = exc
                        time.sleep(0.25 * (2 ** attempt))
                if last_error:
                    raise last_error
            consumer.commit(message=message, asynchronous=False)
        except (ValidationError, ValueError, TypeError):
            producer.produce(ANALYSIS_JOBS_DLQ, key=message.key(),
                             value=json.dumps({"reason": "INVALID_ANALYSIS_JOB",
                                               "payload_sha256": hashlib.sha256(message.value()).hexdigest()}).encode())
            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
        except Exception:
            # Leave offset uncommitted: redelivery is possible. Consumers must dedupe task_id.
            time.sleep(1)

if __name__ == "__main__":
    run()
