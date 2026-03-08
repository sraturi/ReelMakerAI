"""POST /api/render — FFmpeg assembly from user's edited plan."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import RenderRequest
from session_store import store, jobs, project_store

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
        job["logs"].append(
            f"Validating {len(plan.clips)} clips, {len(plan.text_overlays)} overlays..."
        )
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

        composites = sum(1 for c in plan.clips if c.layout != "single")
        transitions_desc = req.transition_style if req.transition_style != "cut" else "none"
        job["logs"].append(
            f"Prepared {len(plan.clips)} clips ({composites} composite), "
            f"{len(plan.text_overlays)} overlays, "
            f"transitions: {transitions_desc}"
        )
        job["logs"].append("Building FFmpeg filter graph...")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        output_path = str(OUTPUT_DIR / f"reel_{timestamp}.mp4")

        job["logs"].append(
            f"Starting FFmpeg encode ({plan.total_duration:.1f}s, "
            f"{req.audio_mode} audio)..."
        )

        cancel_event = job.get("_cancel_event")

        def _on_progress(pct: int, message: str):
            job["logs"].append(message)

        result_path = await asyncio.to_thread(
            assemble_reel, plan, videos, output_path,
            audio_mode=req.audio_mode, transition_style=req.transition_style,
            cancel_event=cancel_event,
            progress_callback=_on_progress,
        )

        # Check cancellation after render
        if job["status"] == "cancelled":
            job["logs"].append("Cancelled by user.")
            return

        job["logs"].append("Encoding complete, finalizing...")

        output_file = f"reel_{timestamp}.mp4"

        # Auto-save as completed project
        job["logs"].append("Saving project...")
        project_id = None
        try:
            from datetime import datetime
            from thumbnail_service import generate_project_thumbnail

            # Name from prompt or fallback
            settings = session.settings if isinstance(session.settings, dict) else {}
            prompt = settings.get("prompt", "")
            name = prompt[:60].strip() if prompt else f"Reel - {datetime.now().strftime('%b %d, %Y %H:%M')}"
            description = plan_data.get("description", "")

            thumb_file = generate_project_thumbnail(output_path, "tmp_" + str(timestamp))
            project_id = project_store.create(
                session_id=session.session_id,
                output_file=output_file,
                duration=plan.total_duration,
                name=name,
                description=description,
                settings=settings,
                thumbnail_file=None,
            )
            # Re-generate thumbnail with actual project_id
            thumb_file = generate_project_thumbnail(output_path, project_id)
            if thumb_file:
                conn = project_store._get_conn()
                conn.execute(
                    "UPDATE projects SET thumbnail_file = ? WHERE project_id = ?",
                    (thumb_file, project_id),
                )
                conn.commit()
        except Exception as e:
            log.warning("Failed to auto-save project: %s", e)

        result = {
            "output": output_file,
            "output_url": f"/api/output/{output_file}",
        }
        if project_id:
            result["project_id"] = project_id
        if jobs.complete(job_id, result):
            job["logs"].append(f"Render complete: {output_file}")

    except asyncio.CancelledError:
        job["status"] = "cancelled"
        job["logs"].append("Cancelled by user.")

    except Exception as e:
        log.error("Render failed: %s", e, exc_info=True)
        jobs.fail(job_id, str(e))
