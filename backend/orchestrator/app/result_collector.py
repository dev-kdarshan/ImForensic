"""Durably deduplicate engine results, correlate complete jobs, and update the Gateway."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

import httpx
from confluent_kafka import Consumer
from shared.kafka.topics import ENGINE_RESULTS
from shared.schemas.engine_result import EngineResult

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("imforensic.result_collector")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DB_PATH = Path(os.getenv("RESULT_DB_PATH", "/var/lib/imforensic/results.sqlite3"))
GATEWAY_URL = os.getenv("GATEWAY_INTERNAL_URL", "http://api-gateway:8000").rstrip("/")
CORRELATION_URL = os.getenv("EVIDENCE_CORRELATION_URL", "http://evidence-correlation:8008").rstrip("/")
TOKEN = os.getenv("IMFORENSIC_INTERNAL_TOKEN", "")
TIMEOUT = float(os.getenv("INTERNAL_HTTP_TIMEOUT_SECONDS", "30"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS engine_results (
            analysis_id TEXT NOT NULL,
            engine TEXT NOT NULL,
            task_id TEXT NOT NULL,
            expected_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            PRIMARY KEY (analysis_id, engine)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS completed_analyses (
            analysis_id TEXT PRIMARY KEY,
            correlation_json TEXT NOT NULL
        )
    """)
    return db


def persist(message: dict):
    result = EngineResult.model_validate(message["result"])
    expected = sorted(set(message["expected_engines"]))
    if message.get("engine") != result.engine or result.engine not in expected:
        raise ValueError("Result engine identity does not match the task")
    if message.get("analysis_id") != result.analysis_id:
        raise ValueError("Result analysis_id does not match the task")

    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO engine_results VALUES (?, ?, ?, ?, ?)",
            (
                result.analysis_id,
                result.engine,
                message["task_id"],
                json.dumps(expected),
                result.model_dump_json(),
            ),
        )
        rows = db.execute(
            "SELECT engine, result_json FROM engine_results WHERE analysis_id=?",
            (result.analysis_id,),
        ).fetchall()
        stored = {row[0]: json.loads(row[1]) for row in rows}
        received = set(stored)
        done = db.execute(
            "SELECT 1 FROM completed_analyses WHERE analysis_id=?",
            (result.analysis_id,),
        ).fetchone()

        # Correlate once. A duplicate Kafka result must not repeatedly invoke
        # the correlation service after the analysis has been marked complete.
        should_correlate = not done and set(expected).issubset(received)
        return expected, list(stored.values()), should_correlate, stored[result.engine]


def deliver(message: dict, stored_result: dict) -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        client.post(
            f"{GATEWAY_URL}/internal/results",
            headers={"X-ImForensic-Internal-Token": TOKEN},
            json={
                "analysis_id": message["analysis_id"],
                "engine": message["engine"],
                "result": stored_result,
            },
        ).raise_for_status()


def correlate(analysis_id: str, expected: list[str], results: list[dict]) -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(
            f"{CORRELATION_URL}/correlate",
            json={"analysis_id": analysis_id, "expected_engines": expected, "results": results},
        )
        response.raise_for_status()
        value = response.json()
        client.post(
            f"{GATEWAY_URL}/internal/correlation",
            headers={"X-ImForensic-Internal-Token": TOKEN},
            json={"analysis_id": analysis_id, "correlation": value},
        ).raise_for_status()

    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO completed_analyses VALUES (?, ?)",
            (analysis_id, json.dumps(value, ensure_ascii=False)),
        )


def run() -> None:
    if not TOKEN:
        raise RuntimeError("IMFORENSIC_INTERNAL_TOKEN is required")

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": "imforensic-result-collector-v1",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([ENGINE_RESULTS])
    logger.info("Result collector started")

    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                logger.error("Kafka consumer error: %s", message.error())
                continue

            try:
                payload = json.loads(message.value())
                expected, results, should_correlate, stored = persist(payload)
                deliver(payload, stored)
                if should_correlate:
                    correlate(payload["analysis_id"], expected, results)
                consumer.commit(message=message, asynchronous=False)
            except (ValueError, KeyError, TypeError) as exc:
                # Poison messages should be logged and skipped rather than
                # blocking this partition forever. The invalid payload is not
                # safe to deliver or correlate.
                logger.exception("Discarding invalid engine result message: %s", exc)
                consumer.commit(message=message, asynchronous=False)
            except (httpx.HTTPError, sqlite3.Error):
                # Do not commit: Kafka will redeliver this result so delivery
                # or persistence can be retried.
                logger.exception("Transient result processing failure; leaving message uncommitted")
                time.sleep(2)
                raise
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
