"""SQLite-backed session manager for the interactive editor.

Replaces the previous in-memory dict.  Sessions survive server restarts.
Uses stdlib sqlite3 + json — no extra dependencies.
"""

import asyncio
import json
import logging
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from config import DATA_DIR, THUMBNAIL_DIR, UPLOAD_DIR

SESSION_TTL = 3600  # 1 hour
DB_PATH = DATA_DIR / "sessions.db"

log = logging.getLogger(__name__)

# Fields stored as JSON blobs in the DB
_JSON_FIELDS = {"videos", "video_paths", "analysis", "scene_menu", "plan", "settings"}


class Session:
    """Proxy object backed by a SQLite row.

    Attribute writes for data fields are intercepted and persisted to the DB
    automatically via ``__setattr__``.
    """

    def __init__(self, session_id: str, store: "SessionStore", row: dict):
        # Use object.__setattr__ to avoid triggering our override during init
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "created_at", row["created_at"])
        object.__setattr__(self, "last_accessed", row["last_accessed"])
        object.__setattr__(self, "upload_dir", UPLOAD_DIR / session_id)

        # Deserialize JSON fields
        object.__setattr__(self, "videos", json.loads(row["videos"]))
        object.__setattr__(self, "video_paths", json.loads(row["video_paths"]))
        object.__setattr__(self, "analysis", _json_or_none(row["analysis"]))
        object.__setattr__(self, "scene_menu", row["scene_menu"])  # plain text
        object.__setattr__(self, "plan", _json_or_none(row["plan"]))
        object.__setattr__(self, "settings", json.loads(row["settings"]))

    def __setattr__(self, name: str, value: Any):
        object.__setattr__(self, name, value)
        if name in _JSON_FIELDS:
            self._store._persist_field(self.session_id, name, value)

    def touch(self):
        now = time.time()
        object.__setattr__(self, "last_accessed", now)
        self._store._touch(self.session_id, now)


def _json_or_none(raw: str | None):
    """Deserialize a nullable JSON column."""
    if raw is None:
        return None
    return json.loads(raw)


def _serialize(name: str, value: Any) -> str | None:
    """Serialize a field value for storage."""
    if name == "scene_menu":
        return value  # plain text, may be None
    if value is None:
        return None
    return json.dumps(value)


class SessionStore:
    """SQLite-backed session store with the same public API as the old in-memory version."""

    def __init__(self):
        self._local = threading.local()
        self._init_db()

    # ---------- connection management ----------

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection (WAL mode, autocommit)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self):
        """Create sessions table if it doesn't exist."""
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id    TEXT PRIMARY KEY,
                created_at    REAL NOT NULL,
                last_accessed REAL NOT NULL,
                videos        TEXT NOT NULL DEFAULT '[]',
                video_paths   TEXT NOT NULL DEFAULT '[]',
                analysis      TEXT,
                scene_menu    TEXT,
                plan          TEXT,
                settings      TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.commit()

    # ---------- public API (unchanged signatures) ----------

    def create(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO sessions (session_id, created_at, last_accessed)
            VALUES (?, ?, ?)
            """,
            (session_id, now, now),
        )
        conn.commit()

        upload_dir = UPLOAD_DIR / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return Session(session_id, self, dict(row))

    def get(self, session_id: str) -> Session | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None

        # Check TTL
        if time.time() - row["last_accessed"] > SESSION_TTL:
            self._cleanup_session(session_id)
            return None

        # Touch and return proxy
        now = time.time()
        conn.execute(
            "UPDATE sessions SET last_accessed = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

        row_dict = dict(row)
        row_dict["last_accessed"] = now
        return Session(session_id, self, row_dict)

    def to_dict(self, session: Session) -> dict:
        """Serialize session state for API response."""
        return {
            "session_id": session.session_id,
            "videos": session.videos,
            "analysis": session.analysis,
            "plan": session.plan,
            "settings": session.settings,
        }

    def cleanup_expired(self):
        """Remove all expired sessions (rows + upload/thumbnail dirs)."""
        conn = self._get_conn()
        cutoff = time.time() - SESSION_TTL
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE last_accessed < ?", (cutoff,)
        ).fetchall()

        for row in rows:
            self._cleanup_session(row["session_id"])

    def clear_all(self) -> int:
        """Delete every session. Returns count of deleted rows."""
        conn = self._get_conn()
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
        for row in rows:
            sid = row["session_id"]
            shutil.rmtree(str(UPLOAD_DIR / sid), ignore_errors=True)
            shutil.rmtree(str(THUMBNAIL_DIR / sid), ignore_errors=True)
        count = len(rows)
        conn.execute("DELETE FROM sessions")
        conn.commit()
        log.info("Cleared all %d sessions", count)
        return count

    # ---------- internal helpers ----------

    def _persist_field(self, session_id: str, field: str, value: Any):
        """Write a single field back to the DB."""
        conn = self._get_conn()
        serialized = _serialize(field, value)
        conn.execute(
            f"UPDATE sessions SET {field} = ? WHERE session_id = ?",
            (serialized, session_id),
        )
        conn.commit()

    def _touch(self, session_id: str, now: float):
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET last_accessed = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    def _cleanup_session(self, session_id: str):
        """Delete DB row and remove upload/thumbnail dirs."""
        conn = self._get_conn()
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

        upload_dir = UPLOAD_DIR / session_id
        thumb_dir = THUMBNAIL_DIR / session_id
        shutil.rmtree(str(upload_dir), ignore_errors=True)
        shutil.rmtree(str(thumb_dir), ignore_errors=True)
        log.debug("Cleaned up session %s", session_id)


JOB_TTL = 600  # auto-prune completed/errored jobs after 10 minutes


class JobStore:
    """Unified in-memory job store with auto-pruning.

    Replaces the scattered per-module dicts (analyze_jobs, plan_jobs, render_jobs).
    Jobs are ephemeral — they live only while the server is up.
    """

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> dict:
        job = {
            "status": "running",
            "logs": [],
            "result": None,
            "error": None,
            "created_at": time.time(),
            "_task": None,
            "_cancel_event": threading.Event(),
        }
        with self._lock:
            self._jobs[job_id] = job
        self._prune()
        return job

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_task(self, job_id: str, task: asyncio.Task):
        """Store the asyncio.Task reference so it can be cancelled later."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job["_task"] = task

    def complete(self, job_id: str, result: Any) -> bool:
        """Atomically set a running job to done. Returns False if already cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return False
            job["result"] = result
            job["status"] = "done"
            return True

    def fail(self, job_id: str, error: str) -> bool:
        """Atomically set a running job to error. Returns False if already cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return False
            job["error"] = error
            job["status"] = "error"
            return True

    def cancel(self, job_id: str) -> bool:
        """Cancel a running job. Returns True if cancellation was initiated."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return False
            job["status"] = "cancelled"
            # Signal the cancel event (for thread-pool work like FFmpeg)
            cancel_event: threading.Event | None = job.get("_cancel_event")
            if cancel_event:
                cancel_event.set()
            # Cancel the asyncio task (raises CancelledError at next await)
            task: asyncio.Task | None = job.get("_task")
            if task and not task.done():
                task.cancel()
            return True

    def _prune(self):
        """Remove completed/errored/cancelled jobs older than JOB_TTL."""
        cutoff = time.time() - JOB_TTL
        with self._lock:
            expired = [
                jid for jid, j in self._jobs.items()
                if j["status"] in ("done", "error", "cancelled") and j.get("created_at", 0) < cutoff
            ]
            for jid in expired:
                del self._jobs[jid]
        if expired:
            log.debug("Pruned %d old jobs", len(expired))


# Global singletons
store = SessionStore()
jobs = JobStore()
