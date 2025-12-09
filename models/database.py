"""
models/database.py
SQLite persistence layer.
Thread-safe: uses check_same_thread=False + explicit connection-per-call pattern.
"""
import sqlite3
import json
import logging
from typing import Optional, Dict, Any
from core.config import config

logger = logging.getLogger(__name__)

# ── Schema ─────────────────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    dl_filename TEXT,
    ic_filename TEXT,
    result_json TEXT
);
"""


def _get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection (one-per-call, thread-safe)."""
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    with _get_conn() as conn:
        conn.execute(_DDL)
        conn.commit()
    logger.info("Database initialised at %s", config.DB_PATH)


# ── CRUD helpers ───────────────────────────────────────────────────────────────

def create_job(job_id: str, dl_filename: Optional[str], ic_filename: Optional[str]) -> None:
    """Insert a new job record with status=pending."""
    sql = "INSERT INTO jobs (id, status, dl_filename, ic_filename) VALUES (?, 'pending', ?, ?)"
    with _get_conn() as conn:
        conn.execute(sql, (job_id, dl_filename, ic_filename))
        conn.commit()
    logger.debug("Job created: %s", job_id)


def update_job_status(job_id: str, status: str) -> None:
    """Update just the status column."""
    sql = "UPDATE jobs SET status = ? WHERE id = ?"
    with _get_conn() as conn:
        conn.execute(sql, (status, job_id))
        conn.commit()


def save_job_result(job_id: str, result_json: str) -> None:
    """Persist the full result JSON and mark the job done."""
    sql = "UPDATE jobs SET status = 'done', result_json = ? WHERE id = ?"
    with _get_conn() as conn:
        conn.execute(sql, (result_json, job_id))
        conn.commit()
    logger.debug("Job result saved: %s", job_id)


def save_job_error(job_id: str, error: str) -> None:
    """Mark job as error and store the error message in result_json."""
    payload = json.dumps({"error": error})
    sql = "UPDATE jobs SET status = 'error', result_json = ? WHERE id = ?"
    with _get_conn() as conn:
        conn.execute(sql, (payload, job_id))
        conn.commit()
    logger.error("Job error saved: %s — %s", job_id, error)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return job row as a dict, or None if not found."""
    sql = "SELECT id, status, created_at, dl_filename, ic_filename, result_json FROM jobs WHERE id = ?"
    with _get_conn() as conn:
        row = conn.execute(sql, (job_id,)).fetchone()
    if row is None:
        return None
    return dict(row)
