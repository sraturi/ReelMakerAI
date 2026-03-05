"""GET /api/thumbnail/{session_id}/{video_index}/{timestamp} — Thumbnail generation."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from session_store import store
from thumbnail_service import generate_thumbnail

router = APIRouter()


@router.get("/thumbnail/{session_id}/{video_index}/{timestamp}")
async def get_thumbnail(session_id: str, video_index: int, timestamp: float):
    """Generate and return a thumbnail frame. Cached after first request."""
    session = store.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if video_index < 0 or video_index >= len(session.video_paths):
        return JSONResponse({"error": "Invalid video index"}, status_code=400)

    video_path = session.video_paths[video_index]
    thumb_path = generate_thumbnail(video_path, session_id, video_index, timestamp)

    if not thumb_path:
        return JSONResponse({"error": "Failed to generate thumbnail"}, status_code=500)

    return FileResponse(str(thumb_path), media_type="image/jpeg")
