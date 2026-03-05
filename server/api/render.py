"""POST /api/render — FFmpeg assembly from user's edited plan."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import RenderRequest
from session_store import store

router = APIRouter()
log = logging.getLogger(__name__)

# Job store for render operations
render_jobs: dict[str, dict] = {}


@router.post("/render")
async def render_reel(req: RenderRequest):
    """Render the reel from user's edited plan. Returns job_id for SSE progress."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.video_paths:
        return JSONResponse({"error": "No videos in session"}, status_code=400)

    job_id = uuid.uuid4().hex[:12]
    render_jobs[job_id] = {
        "status": "running",
        "logs": [],
        "result": None,
        "error": None,
    }

    asyncio.get_event_loop().create_task(
        _run_render(job_id, session, req)
    )

    return {"job_id": job_id}


async def _run_render(job_id: str, session, req: RenderRequest):
    """Run FFmpeg render in background."""
    from api.status import job_stores
    job_stores["render"] = render_jobs

    handler = _JobLogHandler(job_id, render_jobs)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

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

        render_jobs[job_id]["logs"].append(
            f"Rendering {len(plan.clips)} clips, {len(plan.text_overlays)} overlays..."
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        output_path = str(OUTPUT_DIR / f"reel_{timestamp}.mp4")

        result_path = await asyncio.to_thread(
            assemble_reel, plan, videos, output_path,
            audio_mode=req.audio_mode, transition_style=req.transition_style,
        )

        output_file = f"reel_{timestamp}.mp4"
        render_jobs[job_id]["status"] = "done"
        render_jobs[job_id]["result"] = {
            "output": output_file,
            "output_url": f"/api/output/{output_file}",
        }
        render_jobs[job_id]["logs"].append(f"Render complete: {output_file}")

    except Exception as e:
        log.error("Render failed: %s", e, exc_info=True)
        render_jobs[job_id]["status"] = "error"
        render_jobs[job_id]["error"] = str(e)

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
