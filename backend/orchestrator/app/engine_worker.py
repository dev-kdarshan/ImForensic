"""One independently scalable worker per engine; Kafka carries references, never image bytes."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from urllib.parse import quote

import httpx
from confluent_kafka import Consumer, Producer, KafkaException
from shared.kafka.topics import ENGINE_TASKS, ENGINE_RESULTS
from shared.schemas.engine_result import normalize_engine_result

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("imforensic.engine_worker")

ENGINE_URLS = {
    "metadata-provenance": os.getenv("METADATA_SERVICE_URL", "http://metadata-provenance:8001"),
    "model-fingerprint": os.getenv("MODEL_FINGERPRINT_SERVICE_URL", "http://model-fingerprint:8002"),
    "pixel-forensics": os.getenv("PIXEL_FORENSICS_SERVICE_URL", "http://pixel-forensics:8003"),
    "ai-content-detection": os.getenv("AI_CONTENT_DETECTION_SERVICE_URL", "http://ai-content-detection:8004"),
    "watermark-detection": os.getenv("WATERMARK_DETECTION_SERVICE_URL", "http://watermark-detection:8005"),
    "visual-consistency": os.getenv("VISUAL_CONSISTENCY_SERVICE_URL", "http://visual-consistency:8006"),
}

GATEWAY_URL = os.getenv("GATEWAY_INTERNAL_URL", "http://api-gateway:8000").rstrip("/")
TOKEN = os.getenv("IMFORENSIC_INTERNAL_TOKEN", "")
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DEFAULT_TIMEOUT = float(os.getenv("ENGINE_HTTP_TIMEOUT_SECONDS", "120"))
DDA_TIMEOUT = float(os.getenv("DDA_ENGINE_HTTP_TIMEOUT_SECONDS", "900"))
MAX_ATTEMPTS = int(os.getenv("ENGINE_MAX_ATTEMPTS", "3"))
MAX_POLL_INTERVAL_MS = int(os.getenv("ENGINE_MAX_POLL_INTERVAL_MS", "2400000"))


def _publish(producer: Producer, task: dict, result: dict) -> None:
    payload = {
        "schema_version": "1.0.0",
        "task_id": task["task_id"],
        "analysis_id": task["analysis_id"],
        "engine": task["engine"],
        "expected_engines": task["expected_engines"],
        "result": result,
    }
    errors: list[str] = []
    producer.produce(
        ENGINE_RESULTS,
        key=task["task_id"],
        value=json.dumps(payload, separators=(",", ":")).encode(),
        on_delivery=lambda error, message: errors.append(str(error)) if error else None,
    )
    remaining = producer.flush(30)
    if remaining:
        raise TimeoutError(f"Timed out publishing engine result; {remaining} message(s) remain")
    if errors:
        raise KafkaException(errors[0])


def _run_engine(task: dict) -> dict:
    engine = task["engine"]
    analysis_id = task["analysis_id"]

    if task.get("image_ref") != f"storage://analysis/{analysis_id}":
        raise ValueError("Unsupported storage reference")

    headers = {"X-ImForensic-Internal-Token": TOKEN}
    timeout_seconds = DDA_TIMEOUT if engine == "ai-content-detection" else DEFAULT_TIMEOUT
    timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{GATEWAY_URL}/internal/images/{quote(analysis_id)}",
            headers=headers,
        )
        response.raise_for_status()
        content = response.content

        if hashlib.sha256(content).hexdigest() != task["sha256"]:
            raise ValueError("Stored image SHA-256 mismatch")

        media_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
        form_data = {"analysis_id": analysis_id}
        result_response = client.post(
            f"{ENGINE_URLS[engine].rstrip('/')}/analyze",
            params=form_data,
            data=form_data,
            files={"file": ("image", content, media_type)},
        )
        result_response.raise_for_status()
        raw = result_response.json()

    if not isinstance(raw, dict):
        raise ValueError("Engine response was not a JSON object")

    for key in ("file", "image", "input"):
        candidate = raw.get(key)
        if (
            isinstance(candidate, dict)
            and candidate.get("sha256")
            and candidate["sha256"] != task["sha256"]
        ):
            raise ValueError("Engine-reported SHA-256 mismatch")

    raw.setdefault("analysis_id", analysis_id)
    raw.setdefault("engine", engine)
    raw.setdefault("engine_version", "unknown")
    raw.setdefault("status", "completed")
    return normalize_engine_result(raw, expected_engine=engine).model_dump(mode="json")


def _failed_result(task: dict, engine: str, error: Exception) -> dict:
    return {
        "schema_version": "1.0.0",
        "analysis_id": task["analysis_id"],
        "engine": engine,
        "engine_version": "unknown",
        "status": "failed",
        "findings": [],
        "raw_result": {},
        "warnings": [],
        "limitations": [],
        "error": {
            "code": "ENGINE_EXECUTION_FAILED",
            "message": type(error).__name__,
            "retryable": False,
        },
    }


def run() -> None:
    engine = os.getenv("ENGINE_NAME", "").strip()
    if engine not in ENGINE_URLS:
        raise RuntimeError("ENGINE_NAME must be one of: " + ", ".join(ENGINE_URLS))
    if not TOKEN:
        raise RuntimeError("IMFORENSIC_INTERNAL_TOKEN is not configured")

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"imforensic-{engine}-v1",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        # This must exceed the longest expected processing/retry window because
        # this worker currently processes one task synchronously at a time.
        "max.poll.interval.ms": MAX_POLL_INTERVAL_MS,
    })
    producer = Producer({
        "bootstrap.servers": BOOTSTRAP,
        "enable.idempotence": True,
        "acks": "all",
        "retries": 5,
    })

    consumer.subscribe([ENGINE_TASKS])
    logger.info(
        "Started worker engine=%s timeout=%ss max_poll_interval_ms=%s",
        engine,
        DDA_TIMEOUT if engine == "ai-content-detection" else DEFAULT_TIMEOUT,
        MAX_POLL_INTERVAL_MS,
    )

    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                logger.error("Kafka consumer error: %s", message.error())
                continue

            task = json.loads(message.value())
            if task.get("engine") != engine:
                # All engine workers subscribe to the shared topic. Each group
                # has its own offset, so a nonmatching task is not expected.
                consumer.commit(message=message, asynchronous=False)
                continue

            result = None
            last_error: Exception | None = None

            for attempt in range(MAX_ATTEMPTS):
                try:
                    logger.info(
                        "Starting task analysis_id=%s engine=%s attempt=%s/%s",
                        task.get("analysis_id"),
                        engine,
                        attempt + 1,
                        MAX_ATTEMPTS,
                    )
                    result = _run_engine(task)
                    break
                except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                    last_error = exc
                    logger.warning(
                        "Engine attempt failed analysis_id=%s engine=%s attempt=%s error=%s",
                        task.get("analysis_id"),
                        engine,
                        attempt + 1,
                        type(exc).__name__,
                    )

                    # A read timeout does not prove the server stopped working.
                    # The AI service's persistent idempotency layer makes a
                    # repeated request safe: it waits for/reuses the first run.
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                        break
                    if attempt + 1 < MAX_ATTEMPTS:
                        time.sleep(min(2 ** attempt, 8))

            if result is None:
                if last_error is None:
                    last_error = RuntimeError("Unknown engine execution failure")
                result = _failed_result(task, engine, last_error)

            # Do not commit the task until its result is durably acknowledged by Kafka.
            _publish(producer, task, result)
            consumer.commit(message=message, asynchronous=False)
            logger.info(
                "Finished task analysis_id=%s engine=%s status=%s",
                task.get("analysis_id"),
                engine,
                result.get("status"),
            )
    except Exception:
        logger.exception("Worker stopping; current message will be replayed if uncommitted")
        raise
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
