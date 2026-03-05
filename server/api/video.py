"""GET /api/video/... — Serve uploaded and output video files."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from config import OUTPUT_DIR
from session_store import store

router = APIRouter()

MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".m4v": "video/x-m4v",
}


@router.get("/video/{session_id}/{video_index}")
async def get_video(session_id: str, video_index: int):
    """Serve an uploaded video file for in-browser playback."""
    session = store.get(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if video_index < 0 or video_index >= len(session.video_paths):
        return JSONResponse({"error": "Invalid video index"}, status_code=400)

    video_path = session.video_paths[video_index]
    ext = Path(video_path).suffix.lower()
    media_type = MIME_TYPES.get(ext, "video/mp4")

    return FileResponse(
        video_path, media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/output/{filename}")
async def get_output_video(filename: str):
    """Serve a rendered output video with range-request support."""
    # Prevent path traversal
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name
    if not file_path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    ext = file_path.suffix.lower()
    media_type = MIME_TYPES.get(ext, "video/mp4")

    return FileResponse(
        str(file_path), media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
