"""POST /api/upload — Upload videos, probe with FFmpeg, create or extend session."""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from config import VIDEO_EXTENSIONS
from ffmpeg_service import probe_video
from session_store import store

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/upload")
async def upload_videos(
    videos: list[UploadFile] = File(...),
    session_id: str = Form(""),
):
    """Upload video files, probe them, and create or extend a session."""
    # Reuse existing session or create a new one
    session = None
    if session_id:
        session = store.get(session_id)
    if not session:
        session = store.create()

    existing_count = len(session.video_paths)
    new_paths: list[str] = []

    for upload in videos:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            continue
        dest = session.upload_dir / upload.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        new_paths.append(str(dest))

    if not new_paths:
        return JSONResponse(
            {"error": "No valid video files uploaded."},
            status_code=400,
        )

    # Probe each new video, indexing continues from existing count
    new_videos_info = []
    for i, vpath in enumerate(new_paths):
        idx = existing_count + i
        info = probe_video(vpath)
        info_dict = info.model_dump()
        info_dict["index"] = idx

        # Thumbnail generated lazily on first request via /api/thumbnail
        info_dict["thumbnail_url"] = f"/api/thumbnail/{session.session_id}/{idx}/0.00"

        new_videos_info.append(info_dict)

    session.video_paths.extend(new_paths)
    session.videos.extend(new_videos_info)

    log.info(
        "Session %s: added %d videos (total %d)",
        session.session_id, len(new_paths), len(session.video_paths),
    )

    return {
        "session_id": session.session_id,
        "videos": session.videos,
    }
