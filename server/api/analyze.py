"""POST /api/analyze — Gemini Pass 1 scene analysis (batched)."""

import asyncio
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import GEMINI_ANALYSIS_BATCH_SIZE
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
    """Run Pass 1 analysis in batches to handle large video sets."""
    job = jobs.get(job_id)

    try:
        from models import VideoInfo
        from gemini_service import (
            upload_video,
            analyze_video_scenes,
            _format_scene_menu,
            _delete_uploaded_files,
        )
        from models import SceneAnalysisResult

        videos = [VideoInfo(**v) for v in session.videos]
        total = len(videos)
        batch_size = GEMINI_ANALYSIS_BATCH_SIZE
        num_batches = (total + batch_size - 1) // batch_size
        all_video_results = []

        for batch_idx in range(num_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, total)
            batch_videos = videos[start:end]
            batch_num = batch_idx + 1

            # Check cancellation between batches
            if job["status"] == "cancelled":
                job["logs"].append("Cancelled by user.")
                return

            # --- Upload batch (parallel) ---
            uploaded_files = []
            try:
                if job["status"] == "cancelled":
                    job["logs"].append("Cancelled by user.")
                    return

                filenames = ", ".join(v.filename for v in batch_videos)
                job["logs"].append(
                    f"Uploading {len(batch_videos)} video(s) in parallel: {filenames}"
                    + (f" (batch {batch_num}/{num_batches})" if num_batches > 1 else "")
                )

                upload_tasks = [
                    asyncio.to_thread(upload_video, video.path)
                    for video in batch_videos
                ]
                uploaded_files = list(await asyncio.gather(*upload_tasks))

                job["logs"].append(
                    f"All {len(uploaded_files)} upload(s) complete"
                    + (f" (batch {batch_num}/{num_batches})" if num_batches > 1 else "")
                )

                # Check cancellation before analysis
                if job["status"] == "cancelled":
                    job["logs"].append("Cancelled by user.")
                    return

                # --- Analyze batch ---
                if num_batches > 1:
                    job["logs"].append(
                        f"Analyzing batch {batch_num}/{num_batches} "
                        f"({len(batch_videos)} videos, index {start}-{end - 1})..."
                    )
                else:
                    job["logs"].append("Analyzing video scenes (Pass 1)...")

                batch_result = await asyncio.to_thread(
                    analyze_video_scenes,
                    batch_videos,
                    uploaded_files,
                    model=gemini_model,
                    start_index=start,
                )

                all_video_results.extend(batch_result.videos)

                if num_batches > 1:
                    analyzed_so_far = end
                    job["logs"].append(
                        f"Batch {batch_num}/{num_batches} complete "
                        f"({analyzed_so_far}/{total} videos analyzed)"
                    )

            finally:
                # Clean up this batch's uploaded files immediately
                if uploaded_files:
                    try:
                        await asyncio.to_thread(_delete_uploaded_files, uploaded_files)
                    except Exception:
                        log.debug(
                            "Failed to clean up Gemini files for batch %d of job %s",
                            batch_num, job_id,
                        )

        # Check cancellation after all batches
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        # --- Merge results ---
        analysis = SceneAnalysisResult(videos=all_video_results)

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
