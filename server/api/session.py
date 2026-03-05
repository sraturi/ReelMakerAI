"""GET /api/session/{session_id} — Recover session state on page refresh."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from session_store import store

router = APIRouter()


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Return full session state for recovery."""
    session = store.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found or expired"}, status_code=404)

    return store.to_dict(session)
