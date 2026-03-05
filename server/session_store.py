"""SQLite-backed session manager for the interactive editor.

Replaces the previous in-memory dict.  Sessions survive server restarts.
Uses stdlib sqlite3 + json — no extra dependencies.
"""

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


# Global singleton
store = SessionStore()
