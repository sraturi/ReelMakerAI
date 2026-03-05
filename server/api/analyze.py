"""POST /api/analyze — Gemini Pass 1 scene analysis."""

import asyncio
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from session_store import store, jobs

router = APIRouter()
log = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    session_id: str
    gemini_model: str = "gemini-2.5-flash"


@router.post("/analyze")
async def analyze_videos(req: AnalyzeRequest):
    """Start Gemini Pass 1 analysis. Returns job_id for WebSocket progress."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.video_paths:
        return JSONResponse({"error": "No videos uploaded"}, status_code=400)

    job_id = uuid.uuid4().hex[:12]
    job = jobs.create(job_id)

    task = asyncio.create_task(_run_analyze(job_id, session, req.gemini_model))
    jobs.set_task(job_id, task)

    return {"job_id": job_id}


async def _run_analyze(job_id: str, session, gemini_model: str):
    """Run Pass 1 analysis in a background thread."""
    job = jobs.get(job_id)
    uploaded_files = []

    try:
        from models import VideoInfo
        from gemini_service import upload_video, analyze_video_scenes, _format_scene_menu

        videos = [VideoInfo(**v) for v in session.videos]

        total = len(videos)
        for i, video in enumerate(videos, 1):
            # Check cancellation between uploads
            if job["status"] == "cancelled":
                job["logs"].append("Cancelled by user.")
                return

            job["logs"].append(
                f"Uploading video {i}/{total}: {video.filename}"
            )
            uploaded_files.append(
                await asyncio.to_thread(upload_video, video.path)
            )
            job["logs"].append(
                f"Uploaded {i}/{total}: {video.filename}"
            )

        # Check cancellation before analysis
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        job["logs"].append("Analyzing video scenes (Pass 1)...")

        analysis = await asyncio.to_thread(
            analyze_video_scenes, videos, uploaded_files, model=gemini_model
        )

        # Check cancellation after analysis
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        # Store analysis in session
        analysis_dict = analysis.model_dump()
        session.analysis = analysis_dict
        session.scene_menu = _format_scene_menu(analysis)

        total_scenes = sum(len(v.scenes) for v in analysis.videos)
        peak_moments = sum(1 for v in analysis.videos for s in v.scenes if s.is_peak_moment)

        result = {
            "total_scenes": total_scenes,
            "peak_moments": peak_moments,
            "analysis": analysis_dict,
        }
        if jobs.complete(job_id, result):
            job["logs"].append(
                f"Analysis complete: {total_scenes} scenes, {peak_moments} peak moments"
            )

    except asyncio.CancelledError:
        job["status"] = "cancelled"
        job["logs"].append("Cancelled by user.")

    except Exception as e:
        log.error("Analyze failed: %s", e, exc_info=True)
        jobs.fail(job_id, str(e))

    finally:
        # Always clean up Gemini uploaded files, even on cancel/error
        if uploaded_files:
            try:
                from gemini_service import _delete_uploaded_files
                await asyncio.to_thread(_delete_uploaded_files, uploaded_files)
            except Exception:
                log.debug("Failed to clean up Gemini files for job %s", job_id)
