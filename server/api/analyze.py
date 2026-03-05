"""POST /api/analyze — Gemini Pass 1 scene analysis."""

import asyncio
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from session_store import store

router = APIRouter()
log = logging.getLogger(__name__)

# Job store for long-running analyze operations
analyze_jobs: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    session_id: str
    gemini_model: str = "gemini-2.5-flash"


@router.post("/analyze")
async def analyze_videos(req: AnalyzeRequest):
    """Start Gemini Pass 1 analysis. Returns job_id for SSE progress."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.video_paths:
        return JSONResponse({"error": "No videos uploaded"}, status_code=400)

    job_id = uuid.uuid4().hex[:12]
    analyze_jobs[job_id] = {
        "status": "running",
        "logs": [],
        "result": None,
        "error": None,
    }

    asyncio.get_event_loop().create_task(
        _run_analyze(job_id, session, req.gemini_model)
    )

    return {"job_id": job_id}


async def _run_analyze(job_id: str, session, gemini_model: str):
    """Run Pass 1 analysis in a background thread."""
    from api.status import job_stores
    job_stores["analyze"] = analyze_jobs

    handler = _JobLogHandler(job_id, analyze_jobs)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        import config
        config.GEMINI_MODEL = gemini_model

        from models import VideoInfo
        from gemini_service import upload_video, analyze_video_scenes, _format_scene_menu

        videos = [VideoInfo(**v) for v in session.videos]

        analyze_jobs[job_id]["logs"].append("Uploading videos to Gemini...")

        uploaded_files = []
        for video in videos:
            uploaded_files.append(
                await asyncio.to_thread(upload_video, video.path)
            )

        analyze_jobs[job_id]["logs"].append("Analyzing video scenes (Pass 1)...")

        analysis = await asyncio.to_thread(
            analyze_video_scenes, videos, uploaded_files
        )

        # Clean up uploaded Gemini files
        from gemini_service import _delete_uploaded_files
        await asyncio.to_thread(_delete_uploaded_files, uploaded_files)

        # Store analysis in session
        analysis_dict = analysis.model_dump()
        session.analysis = analysis_dict
        session.scene_menu = _format_scene_menu(analysis)

        total_scenes = sum(len(v.scenes) for v in analysis.videos)
        peak_moments = sum(1 for v in analysis.videos for s in v.scenes if s.is_peak_moment)

        analyze_jobs[job_id]["status"] = "done"
        analyze_jobs[job_id]["result"] = {
            "total_scenes": total_scenes,
            "peak_moments": peak_moments,
            "analysis": analysis_dict,
        }
        analyze_jobs[job_id]["logs"].append(
            f"Analysis complete: {total_scenes} scenes, {peak_moments} peak moments"
        )

    except Exception as e:
        log.error("Analyze failed: %s", e, exc_info=True)
        analyze_jobs[job_id]["status"] = "error"
        analyze_jobs[job_id]["error"] = str(e)

    finally:
        root_logger.removeHandler(handler)


class _JobLogHandler(logging.Handler):
    def __init__(self, job_id: str, jobs: dict):
        super().__init__()
        self.job_id = job_id
        self.jobs = jobs

    def emit(self, record: logging.LogRecord):
        if self.job_id in self.jobs:
            self.jobs[self.job_id]["logs"].append(self.format(record))
