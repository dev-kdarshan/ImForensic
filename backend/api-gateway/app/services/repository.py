"""SQLite-backed analysis state. Engine result writes are idempotent by engine name."""
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
from typing import Any
DB_PATH = Path(os.getenv("IMFORENSIC_DB_PATH", "./data/imforensic.sqlite3"))
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15); db.row_factory = sqlite3.Row
    return db
def initialize():
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS analyses (
          analysis_id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at TEXT NOT NULL,filename TEXT NOT NULL,
          content_type TEXT NOT NULL,size_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,storage_ref TEXT NOT NULL,
          result_json TEXT,engine_results_json TEXT,error TEXT,expected_engines_json TEXT,correlation_json TEXT)""")
        columns = {r["name"] for r in db.execute("PRAGMA table_info(analyses)")}
        for name in ("engine_results_json","expected_engines_json","correlation_json"):
            if name not in columns: db.execute(f"ALTER TABLE analyses ADD COLUMN {name} TEXT")
def save_analysis(record: dict[str, Any]):
    initialize()
    with _connect() as db:
        db.execute("""INSERT INTO analyses (analysis_id,status,created_at,filename,content_type,size_bytes,
          sha256,storage_ref,result_json,engine_results_json,error,expected_engines_json,correlation_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(analysis_id) DO UPDATE SET status=excluded.status,
          result_json=excluded.result_json,engine_results_json=excluded.engine_results_json,error=excluded.error,
          expected_engines_json=excluded.expected_engines_json,correlation_json=excluded.correlation_json""",
          (record["analysis_id"],record["status"],record["created_at"],record["filename"],record["content_type"],
           record["size_bytes"],record["sha256"],record["storage_ref"],
           json.dumps(record.get("result"),ensure_ascii=False),json.dumps(record.get("engine_results") or {},ensure_ascii=False),
           record.get("error"),json.dumps(record.get("expected_engines") or [],ensure_ascii=False),
           json.dumps(record.get("correlation"),ensure_ascii=False) if record.get("correlation") is not None else None))
def record_engine_result(analysis_id: str, engine: str, result: dict[str, Any]):
    initialize()
    with _connect() as db:
        row=db.execute("SELECT * FROM analyses WHERE analysis_id=?",(analysis_id,)).fetchone()
        if row is None: raise KeyError("Analysis not found")
        results=json.loads(row["engine_results_json"] or "{}")
        results[engine]={"status":result["status"],"result":result}
        expected=json.loads(row["expected_engines_json"] or "[]")
        terminal=all(name in results for name in expected)
        status=("completed" if all(results[n]["status"]=="completed" for n in expected) else "partial") if terminal else "processing"
        error=None if status=="completed" else ("One or more engines returned partial/failed results." if terminal else None)
        db.execute("UPDATE analyses SET engine_results_json=?,status=?,error=? WHERE analysis_id=?",
                   (json.dumps(results,ensure_ascii=False),status,error,analysis_id))
        return {"analysis_id":analysis_id,"status":status,"expected_engines":expected,
                "received_engines":sorted(results),"engine_results":results}
def record_correlation(analysis_id: str, correlation: dict[str, Any]):
    initialize()
    with _connect() as db:
        db.execute("UPDATE analyses SET correlation_json=?,status=?,error=? WHERE analysis_id=?",
          (json.dumps(correlation,ensure_ascii=False),correlation.get("status","partial"),
           None if correlation.get("status")=="completed" else "Analysis completed with partial/failed engine results.",analysis_id))
def get_analysis(analysis_id: str):
    initialize()
    with _connect() as db: row=db.execute("SELECT * FROM analyses WHERE analysis_id=?",(analysis_id,)).fetchone()
    if row is None: return None
    item=dict(row)
    for col,key,default in (("result_json","result",None),("engine_results_json","engine_results",{}),
                            ("expected_engines_json","expected_engines",[]),("correlation_json","correlation",None)):
        raw=item.pop(col,None); item[key]=json.loads(raw) if raw else default
    return item
