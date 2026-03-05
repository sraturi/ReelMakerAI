"""POST /api/render — FFmpeg assembly from user's edited plan."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import RenderRequest
from session_store import store, jobs

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/render")
async def render_reel(req: RenderRequest):
    """Render the reel from user's edited plan. Returns job_id for WebSocket progress."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.video_paths:
        return JSONResponse({"error": "No videos in session"}, status_code=400)

    job_id = uuid.uuid4().hex[:12]
    jobs.create(job_id)

    task = asyncio.create_task(_run_render(job_id, session, req))
    jobs.set_task(job_id, task)

    return {"job_id": job_id}


async def _run_render(job_id: str, session, req: RenderRequest):
    """Run FFmpeg render in background."""
    job = jobs.get(job_id)

    try:
        from config import (
            ALLOWED_KENBURNS, ALLOWED_LAYOUTS, ALLOWED_TRANSITIONS,
            LAYOUT_SOURCE_COUNT, OUTPUT_DIR, TRANSITION_DURATION,
            TRANSITION_STYLES,
        )
        from ffmpeg_service import assemble_reel
        from models import ClipPlan, EditingPlan, SubSource, TextOverlay, VideoInfo

        videos = [VideoInfo(**v) for v in session.videos]

        # Reconstruct EditingPlan from user's edited dict
        plan_data = req.plan.copy()

        # Strip frontend-only fields from clips
        raw_clips = plan_data.get("clips", [])
        clean_clips = []
        for c in raw_clips:
            c.pop("clip_id", None)
            c.pop("thumbnail_url", None)
            c.pop("video_url", None)
            # Strip frontend-only fields from sub_sources
            for sub in c.get("sub_sources", []):
                sub.pop("thumbnail_url", None)
                sub.pop("video_url", None)
            clean_clips.append(ClipPlan(**c))

        # Strip frontend-only fields from overlays
        raw_overlays = plan_data.get("text_overlays", [])
        clean_overlays = []
        for o in raw_overlays:
            o.pop("overlay_id", None)
            clean_overlays.append(TextOverlay(**o))

        plan = EditingPlan(
            music_track=plan_data.get("music_track", ""),
            total_duration=plan_data.get("total_duration", 30.0),
            clips=clean_clips,
            text_overlays=clean_overlays,
            description=plan_data.get("description", ""),
        )

        # Recalculate timeline_start sequentially
        use_transitions = req.transition_style != "cut"
        t = 0.0
        for i, clip in enumerate(plan.clips):
            clip.timeline_start = round(t, 3)
            if clip.layout != "single" and clip.sub_sources:
                t += min(s.end_time - s.start_time for s in clip.sub_sources)
            else:
                t += clip.end_time - clip.start_time
            if use_transitions and i < len(plan.clips) - 1:
                t -= TRANSITION_DURATION
        plan.total_duration = round(t, 3)

        # Validate clips
        valid_clips = []
        for clip in plan.clips:
            if clip.source_index < 0 or clip.source_index >= len(videos):
                continue
            vid_dur = videos[clip.source_index].duration
            clip.start_time = max(0.0, min(clip.start_time, vid_dur - 0.1))
            clip.end_time = max(clip.start_time + 0.5, min(clip.end_time, vid_dur))
            if clip.end_time - clip.start_time < 0.5:
                continue
            if clip.ken_burns not in ALLOWED_KENBURNS:
                clip.ken_burns = "none"
            allowed_tr = TRANSITION_STYLES.get(req.transition_style, ALLOWED_TRANSITIONS)
            if not allowed_tr:
                clip.transition = "fade"
            elif clip.transition not in allowed_tr:
                clip.transition = allowed_tr[0]

            # Composite layout validation
            if clip.layout not in ALLOWED_LAYOUTS:
                clip.layout = "single"
            expected = LAYOUT_SOURCE_COUNT.get(clip.layout, 0)
            if expected > 0 and len(clip.sub_sources) != expected:
                clip.layout = "single"
                clip.sub_sources = []
            if clip.layout != "single" and clip.sub_sources:
                clip.ken_burns = "none"
                valid_subs = True
                for sub in clip.sub_sources:
                    if sub.source_index < 0 or sub.source_index >= len(videos):
                        valid_subs = False
                        break
                    sub_dur = videos[sub.source_index].duration
                    sub.start_time = max(0.0, min(sub.start_time, sub_dur - 0.1))
                    sub.end_time = max(sub.start_time + 0.5, min(sub.end_time, sub_dur))
                    if sub.end_time - sub.start_time < 0.5:
                        valid_subs = False
                        break
                if not valid_subs:
                    clip.layout = "single"
                    clip.sub_sources = []

            valid_clips.append(clip)
        plan.clips = valid_clips

        # Check cancellation before FFmpeg
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        job["logs"].append(
            f"Rendering {len(plan.clips)} clips, {len(plan.text_overlays)} overlays..."
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        output_path = str(OUTPUT_DIR / f"reel_{timestamp}.mp4")

        cancel_event = job.get("_cancel_event")
        result_path = await asyncio.to_thread(
            assemble_reel, plan, videos, output_path,
            audio_mode=req.audio_mode, transition_style=req.transition_style,
            cancel_event=cancel_event,
        )

        # Check cancellation after render
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        output_file = f"reel_{timestamp}.mp4"
        result = {
            "output": output_file,
            "output_url": f"/api/output/{output_file}",
        }
        if jobs.complete(job_id, result):
            job["logs"].append(f"Render complete: {output_file}")

    except asyncio.CancelledError:
        job["status"] = "cancelled"
        job["logs"].append("Cancelled by user.")

    except Exception as e:
        log.error("Render failed: %s", e, exc_info=True)
        jobs.fail(job_id, str(e))
