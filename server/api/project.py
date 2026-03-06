"""Project history endpoints — list completed reels, manage drafts."""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from config import OUTPUT_DIR, THUMBNAIL_DIR
from session_store import store, project_store

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/projects")
async def list_projects():
    """Return completed projects + current draft info for the home screen."""
    projects = project_store.list_all()

    # Build response with URLs
    project_list = []
    for p in projects:
        project_list.append({
            "project_id": p["project_id"],
            "name": p["name"],
            "description": p["description"],
            "output_url": f"/api/projects/{p['project_id']}/video",
            "thumbnail_url": f"/api/projects/{p['project_id']}/thumbnail",
            "duration": p["duration"],
            "created_at": p["created_at"],
        })

    # Draft info — most recent session
    draft = None
    session = store.get_draft()
    if session:
        video_count = len(session.videos)
        has_analysis = session.analysis is not None
        has_plan = session.plan is not None
        prompt = ""
        settings = session.settings
        if isinstance(settings, dict):
            prompt = settings.get("prompt", "")
        draft = {
            "session_id": session.session_id,
            "video_count": video_count,
            "has_analysis": has_analysis,
            "has_plan": has_plan,
            "prompt": prompt,
            "created_at": session.created_at,
        }

    return {"projects": project_list, "draft": draft}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a completed reel (output file + thumbnail + DB row)."""
    if project_store.delete(project_id):
        return {"ok": True}
    return JSONResponse({"error": "Project not found"}, status_code=404)


@router.post("/projects/new")
async def new_project():
    """Delete current draft session (files + data) and return OK."""
    session = store.get_draft()
    if session:
        store._cleanup_session(session.session_id)
    return {"ok": True}


@router.get("/projects/{project_id}/thumbnail")
async def project_thumbnail(project_id: str):
    """Serve project thumbnail JPEG."""
    proj = project_store.get(project_id)
    if not proj or not proj.get("thumbnail_file"):
        return JSONResponse({"error": "Thumbnail not found"}, status_code=404)
    thumb_path = THUMBNAIL_DIR / "projects" / proj["thumbnail_file"]
    if not thumb_path.exists():
        return JSONResponse({"error": "Thumbnail file missing"}, status_code=404)
    return FileResponse(str(thumb_path), media_type="image/jpeg")


@router.get("/projects/{project_id}/video")
async def project_video(project_id: str):
    """Serve completed reel video file."""
    proj = project_store.get(project_id)
    if not proj:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    video_path = OUTPUT_DIR / proj["output_file"]
    if not video_path.exists():
        return JSONResponse({"error": "Video file missing"}, status_code=404)
    return FileResponse(str(video_path), media_type="video/mp4")
