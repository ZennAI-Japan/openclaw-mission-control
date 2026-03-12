"""SQLite persistence for FIFO queue task state."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

TASK_STATUSES = frozenset({"queued", "processing", "succeeded", "failed", "dead_letter"})


@dataclass(frozen=True)
class FifoTaskRecord:
    task_id: str
    group_id: str
    payload: dict[str, Any]
    status: str
    retry_count: int
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _db_path() -> Path:
    return Path(settings.fifo_sqlite_path)


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fifo_tasks (
            task_id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL,
            retry_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
    conn.commit()
    return conn


def upsert_task(
    *, task_id: str, group_id: str, payload: dict[str, Any], status: str, retry_count: int
) -> None:
    if status not in TASK_STATUSES:
        raise ValueError(f"Unsupported task status: {status}")
    ts = _now_iso()
    conn = _conn()
    conn.execute(
        """
        INSERT INTO fifo_tasks(task_id, group_id, payload, status, retry_count, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(task_id)
        DO UPDATE SET
            group_id=excluded.group_id,
            payload=excluded.payload,
            status=excluded.status,
            retry_count=excluded.retry_count,
            updated_at=excluded.updated_at
        """,
        (task_id, group_id, json.dumps(payload, ensure_ascii=False), status, retry_count, ts, ts),
    )
    conn.commit()
    conn.close()


def get_task(task_id: str) -> FifoTaskRecord | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM fifo_tasks WHERE task_id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return FifoTaskRecord(
        task_id=str(row["task_id"]),
        group_id=str(row["group_id"]),
        payload=json.loads(str(row["payload"])),
        status=str(row["status"]),
        retry_count=int(row["retry_count"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def list_tasks(
    *, status: str | None = None, limit: int = 100, offset: int = 0
) -> list[FifoTaskRecord]:
    conn = _conn()
    if status is None:
        rows = conn.execute(
            "SELECT * FROM fifo_tasks ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM fifo_tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    conn.close()
    return [
        FifoTaskRecord(
            task_id=str(row["task_id"]),
            group_id=str(row["group_id"]),
            payload=json.loads(str(row["payload"])),
            status=str(row["status"]),
            retry_count=int(row["retry_count"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in rows
    ]
