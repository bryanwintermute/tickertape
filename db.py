import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import os

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("TICKERTAPE_DB", "tickertape.db"))

def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT UNIQUE,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def enqueue_job(idempotency_key: str, job_type: str, payload: Dict[str, Any]) -> int:
    """
    Adds a print job to the queue. 
    Returns the job ID, or the existing job ID if the idempotency_key already exists.
    """
    payload_str = json.dumps(payload)
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO queue (idempotency_key, type, payload, status) VALUES (?, ?, ?, 'pending')",
                (idempotency_key, job_type, payload_str)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Idempotency key collision
            cursor = conn.execute(
                "SELECT id FROM queue WHERE idempotency_key = ?",
                (idempotency_key,)
            )
            return cursor.fetchone()['id']

def get_next_pending_job() -> Optional[Dict[str, Any]]:
    """Returns the oldest pending job, or None if the queue is empty."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, type, payload FROM queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            "id": row["id"],
            "type": row["type"],
            "payload": json.loads(row["payload"])
        }

def mark_job_status(job_id: int, status: str):
    """Updates the status of a job (e.g. 'printed' or 'failed')."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE queue SET status = ? WHERE id = ?",
            (status, job_id)
        )
        conn.commit()

def list_reminders() -> List[Dict[str, Any]]:
    """Returns a list of all active reminders (pending or otherwise)."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, payload, status, created_at FROM queue WHERE type = 'reminder' ORDER BY created_at DESC"
        )
        reminders = []
        for row in cursor:
            reminders.append({
                "id": row["id"],
                "payload": json.loads(row["payload"]),
                "status": row["status"],
                "created_at": row["created_at"]
            })
        return reminders

def list_history() -> List[Dict[str, Any]]:
    """Returns a list of all jobs marked as 'printed'."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, type, payload, created_at FROM queue WHERE status = 'printed' ORDER BY created_at DESC LIMIT 50"
        )
        history = []
        for row in cursor:
            history.append({
                "id": row["id"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"]
            })
        return history
