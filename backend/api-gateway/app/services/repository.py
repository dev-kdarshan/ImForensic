"""Small durable analysis repository using SQLite (stdlib; no external DB required)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("IMFORENSIC_DB_PATH", "./data/imforensic.sqlite3"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with _connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                analysis_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                storage_ref TEXT NOT NULL,
                result_json TEXT,
                engine_results_json TEXT,
                error TEXT
            )
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(analyses)")}
        if "engine_results_json" not in columns:
            db.execute("ALTER TABLE analyses ADD COLUMN engine_results_json TEXT")


def save_analysis(record: dict[str, Any]) -> None:
    initialize()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO analyses (
                analysis_id, status, created_at, filename, content_type, size_bytes,
                sha256, storage_ref, result_json, engine_results_json, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                status=excluded.status, result_json=excluded.result_json,
                engine_results_json=excluded.engine_results_json, error=excluded.error
            """,
            (
                record["analysis_id"], record["status"], record["created_at"],
                record["filename"], record["content_type"], record["size_bytes"],
                record["sha256"], record["storage_ref"],
                json.dumps(record.get("result"), ensure_ascii=False),
                json.dumps(record.get("engine_results"), ensure_ascii=False),
                record.get("error"),
            ),
        )


def get_analysis(analysis_id: str) -> dict[str, Any] | None:
    initialize()
    with _connect() as db:
        row = db.execute(
            "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
    item["engine_results"] = json.loads(item.pop("engine_results_json")) if item.get("engine_results_json") else {}
    return item
