"""Session management endpoints."""

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


@router.delete("/sessions")
async def clear_all_sessions():
    """Delete every session (DB rows + uploaded files)."""
    count = store.clear_all()
    return {"deleted": count}
