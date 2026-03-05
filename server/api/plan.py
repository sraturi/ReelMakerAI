"""POST /api/plan and /api/replan — Gemini Pass 2 editing plan."""

import asyncio
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import PlanRequest, ReplanRequest
from session_store import store, jobs

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/plan")
async def create_plan(req: PlanRequest):
    """Generate an editing plan from stored analysis (Pass 2). Returns job_id for SSE."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.analysis:
        return JSONResponse({"error": "No analysis found. Run /api/analyze first."}, status_code=400)

    # Store settings
    session.settings = req.model_dump(exclude={"session_id"})

    job_id = uuid.uuid4().hex[:12]
    jobs.create(job_id)

    asyncio.get_event_loop().create_task(
        _run_plan(job_id, session, req)
    )

    return {"job_id": job_id}


@router.post("/replan")
async def replan(req: ReplanRequest):
    """Re-run Pass 2 with a new direction, reusing stored Pass 1 analysis."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.analysis:
        return JSONResponse({"error": "No analysis found. Run /api/analyze first."}, status_code=400)

    # Merge direction into prompt
    original_prompt = session.settings.get("prompt", "")
    combined_prompt = f"{original_prompt}\n\nADDITIONAL DIRECTION: {req.direction}" if req.direction else original_prompt

    plan_req = PlanRequest(
        session_id=req.session_id,
        prompt=combined_prompt,
        reel_style=req.reel_style,
        reel_approach=req.reel_approach,
        target_duration=req.target_duration,
        bpm=req.bpm,
        captions=req.captions,
        audio_mode=req.audio_mode,
        transition_style=req.transition_style,
        gemini_model=req.gemini_model,
        composite_layouts=req.composite_layouts,
    )

    job_id = uuid.uuid4().hex[:12]
    jobs.create(job_id)

    asyncio.get_event_loop().create_task(
        _run_plan(job_id, session, plan_req)
    )

    return {"job_id": job_id}


async def _run_plan(job_id: str, session, req: PlanRequest):
    """Run Pass 2 plan generation in background."""
    job = jobs.get(job_id)

    try:
        from beat_detection import beats_from_bpm
        from gemini_service import create_editing_plan_from_scenes
        from models import MusicTrack, VideoInfo

        videos = [VideoInfo(**v) for v in session.videos]
        target_duration = float(req.target_duration)

        job["logs"].append("Generating beats...")
        track = MusicTrack(
            filename="", name=f"Custom {req.bpm} BPM", genre="",
            vibe="custom", bpm=req.bpm, duration=target_duration,
        )
        beat_times = beats_from_bpm(req.bpm, target_duration)

        job["logs"].append("Creating editing plan (Pass 2)...")

        plan = await asyncio.to_thread(
            create_editing_plan_from_scenes,
            scene_menu=session.scene_menu,
            prompt=req.prompt,
            beat_times=beat_times,
            music_track=track,
            videos=videos,
            target_duration=target_duration,
            reel_style=req.reel_style,
            reel_approach=req.reel_approach,
            composite_layouts=req.composite_layouts,
            model=req.gemini_model,
        )

        # Post-process plan (same validation as pipeline.py)
        from config import (
            ALLOWED_KENBURNS, ALLOWED_LAYOUTS, ALLOWED_TRANSITIONS,
            LAYOUT_SOURCE_COUNT, TRANSITION_DURATION, TRANSITION_STYLES,
        )
        plan.clips.sort(key=lambda c: c.timeline_start)

        valid_clips = []
        for clip in plan.clips:
            if clip.source_index < 0 or clip.source_index >= len(videos):
                continue
            vid_dur = videos[clip.source_index].duration
            if clip.start_time > clip.end_time:
                clip.start_time, clip.end_time = clip.end_time, clip.start_time
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

        # Recalculate timeline
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

        if not req.captions:
            plan.text_overlays = []

        # Add IDs for frontend tracking + thumbnail URLs
        plan_dict = plan.model_dump()
        for i, clip in enumerate(plan_dict["clips"]):
            clip["clip_id"] = f"clip-{i}"
            mid_time = (clip["start_time"] + clip["end_time"]) / 2
            clip["thumbnail_url"] = (
                f"/api/thumbnail/{session.session_id}/{clip['source_index']}/{mid_time:.2f}"
            )
            clip["video_url"] = (
                f"/api/video/{session.session_id}/{clip['source_index']}"
            )
            # Add thumbnail/video URLs to sub-sources
            for sub in clip.get("sub_sources", []):
                sub_mid = (sub["start_time"] + sub["end_time"]) / 2
                sub["thumbnail_url"] = (
                    f"/api/thumbnail/{session.session_id}/{sub['source_index']}/{sub_mid:.2f}"
                )
                sub["video_url"] = (
                    f"/api/video/{session.session_id}/{sub['source_index']}"
                )

        for i, overlay in enumerate(plan_dict["text_overlays"]):
            overlay["overlay_id"] = f"overlay-{i}"

        session.plan = plan_dict

        job["status"] = "done"
        job["result"] = plan_dict
        job["logs"].append(
            f"Plan complete: {len(plan.clips)} clips, {len(plan.text_overlays)} overlays"
        )

    except Exception as e:
        log.error("Plan failed: %s", e, exc_info=True)
        job["status"] = "error"
        job["error"] = str(e)
