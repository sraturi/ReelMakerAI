"""POST /api/suggest-clip — AI suggests alternative clips for a position."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import SuggestClipRequest
from session_store import store

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/suggest-clip")
async def suggest_clip(req: SuggestClipRequest):
    """Ask AI to suggest 3 alternative clips for a given position. Synchronous (2-5s)."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    if not session.analysis or not session.scene_menu:
        return JSONResponse({"error": "No analysis found"}, status_code=400)

    current_clip = None
    clips = req.current_plan.get("clips", [])
    if 0 <= req.clip_index < len(clips):
        current_clip = clips[req.clip_index]

    prompt = f"""You are an expert video editor. Given a scene analysis and the current editing plan, suggest 3 alternative clips that could replace clip #{req.clip_index}.

SCENE ANALYSIS:
{session.scene_menu}

CURRENT CLIP AT POSITION {req.clip_index}:
{json.dumps(current_clip, indent=2) if current_clip else "None"}

CURRENT PLAN CONTEXT:
{json.dumps(req.current_plan.get("description", ""), indent=2)}

{f"USER DIRECTION: {req.direction}" if req.direction else ""}

Suggest 3 different clips from the available scenes that would work well in this position.
Each suggestion should be from a different scene or time range.

Return ONLY valid JSON:
{{
  "suggestions": [
    {{
      "source_video": "<filename>",
      "source_index": <int>,
      "start_time": <float>,
      "end_time": <float>,
      "reason": "<why this clip works here>"
    }}
  ]
}}"""

    try:
        from gemini_service import _call_gemini

        response = await asyncio.to_thread(
            _call_gemini, prompt, temperature=0.8, json_output=True
        )
        suggestions = json.loads(response.text)

        # Add thumbnail + video URLs
        for s in suggestions.get("suggestions", []):
            mid_time = (s["start_time"] + s["end_time"]) / 2
            s["thumbnail_url"] = (
                f"/api/thumbnail/{session.session_id}/{s['source_index']}/{mid_time:.2f}"
            )
            s["video_url"] = (
                f"/api/video/{session.session_id}/{s['source_index']}"
            )

        return suggestions

    except Exception as e:
        log.error("Suggest clip failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
