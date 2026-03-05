"""In-memory session manager for the interactive editor."""

import shutil
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from config import THUMBNAIL_DIR, UPLOAD_DIR

SESSION_TTL = 3600  # 1 hour


class Session:
    """A user editing session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.videos: list[dict] = []       # VideoInfo dicts
        self.video_paths: list[str] = []   # Actual file paths
        self.analysis: dict | None = None  # Pass 1 SceneAnalysisResult
        self.scene_menu: str | None = None # Formatted scene menu text
        self.plan: dict | None = None      # Current EditingPlan
        self.settings: dict = {}           # User settings (prompt, style, etc.)
        self.upload_dir: Path = UPLOAD_DIR / session_id

    def touch(self):
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        return time.time() - self.last_accessed > SESSION_TTL


class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def create(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session = Session(session_id)
        session.upload_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
        if session and not session.is_expired():
            session.touch()
            return session
        if session and session.is_expired():
            self._cleanup_session(session)
            with self._lock:
                self._sessions.pop(session_id, None)
        return None

    def _cleanup_session(self, session: Session):
        """Remove uploaded files and thumbnails for a session."""
        upload_dir = UPLOAD_DIR / session.session_id
        thumb_dir = THUMBNAIL_DIR / session.session_id
        shutil.rmtree(str(upload_dir), ignore_errors=True)
        shutil.rmtree(str(thumb_dir), ignore_errors=True)

    def cleanup_expired(self):
        """Remove all expired sessions."""
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            session = self._sessions.get(sid)
            if session:
                self._cleanup_session(session)
            with self._lock:
                self._sessions.pop(sid, None)

    def to_dict(self, session: Session) -> dict:
        """Serialize session state for API response."""
        return {
            "session_id": session.session_id,
            "videos": session.videos,
            "analysis": session.analysis,
            "plan": session.plan,
            "settings": session.settings,
        }


# Global singleton
store = SessionStore()
