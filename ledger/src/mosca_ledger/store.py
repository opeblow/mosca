"""Event store on SQLite.

Every write is an immutable event. Current state (latest assessment, owner answers,
history) is derived by reading events, so the full audit trail is never lost: who
said payments data must stay secret for 10 years, and when, is always answerable.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    repo       TEXT    NOT NULL,
    type       TEXT    NOT NULL CHECK (type IN ('assessment', 'answer')),
    payload    TEXT    NOT NULL,
    actor      TEXT,
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS events_repo_type ON events (repo, type, seq);
"""


@dataclass(frozen=True)
class Event:
    seq: int
    repo: str
    type: str
    payload: dict[str, Any]
    actor: str | None
    created_at: str


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def append(self, repo: str, type_: str, payload: dict[str, Any], actor: str | None = None) -> Event:
        created = _now()
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO events (repo, type, payload, actor, created_at) VALUES (?, ?, ?, ?, ?)",
                (repo, type_, body, actor, created),
            )
            seq = cur.lastrowid
        return Event(seq, repo, type_, payload, actor, created)

    def events(self, repo: str, type_: str, limit: int | None = None, desc: bool = False) -> list[Event]:
        order = "DESC" if desc else "ASC"
        sql = f"SELECT * FROM events WHERE repo = ? AND type = ? ORDER BY seq {order}"
        params: tuple[Any, ...] = (repo, type_)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def repos(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT repo FROM events ORDER BY repo").fetchall()
        return [r["repo"] for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row(r: sqlite3.Row) -> Event:
        return Event(r["seq"], r["repo"], r["type"], json.loads(r["payload"]), r["actor"], r["created_at"])

    # ---- projections ----------------------------------------------------------------
    def latest_assessment(self, repo: str) -> Event | None:
        rows = self.events(repo, "assessment", limit=1, desc=True)
        return rows[0] if rows else None

    def answers(self, repo: str) -> dict[str, dict[str, Any]]:
        """Fold answer events into the shape `mosca --answers` expects. Later answers win."""
        state: dict[str, dict[str, Any]] = {}
        for e in self.events(repo, "answer"):
            p = e.payload
            entry = state.setdefault(p["system"], {})
            entry[p["kind"]] = p["years"]
            entry["answered_by"] = e.actor or p.get("answered_by")
            entry["answered_at"] = e.created_at
        return state

    def history(self, repo: str) -> list[dict[str, Any]]:
        out = []
        for e in self.events(repo, "assessment"):
            p = e.payload
            out.append({
                "seq": e.seq,
                "at": e.created_at,
                "ref": p.get("ref"),
                "readiness": p.get("readiness"),
                **p.get("summary", {}),
            })
        return out
