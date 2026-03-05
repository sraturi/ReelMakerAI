"""POST /api/enhance-prompt — Use Gemini to improve a user's reel prompt."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
log = logging.getLogger(__name__)


class EnhanceRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    reel_style: str = "montage"
    reel_approach: str = "hook"
    target_duration: int = 30
    captions: bool = True
    audio_mode: str = "voice"
    transition_style: str = "auto"


@router.post("/enhance-prompt")
async def enhance_prompt(req: EnhanceRequest):
    """Enhance a user's reel prompt using Gemini."""
    if not req.prompt.strip():
        return JSONResponse({"error": "Prompt is empty"}, status_code=400)

    # Pull analysis context if session_id is provided
    video_context = ""
    if req.session_id:
        try:
            from session_store import store
            session = store.get(req.session_id)
            if session and session.analysis:
                video_context = _build_video_context(session.analysis)
        except Exception as e:
            log.warning("Could not load session analysis for enhance: %s", e)

    try:
        enhanced = await asyncio.to_thread(_enhance, req, video_context)
        return {"enhanced_prompt": enhanced}
    except Exception as e:
        log.error("Enhance prompt failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


def _build_video_context(analysis: dict) -> str:
    """Format analysis data into context for the enhancer."""
    lines = ["\n\nThe user's uploaded videos contain the following content:"]
    for video in analysis.get("videos", []):
        lines.append(f"\n**{video.get('filename', 'Video')}** ({video.get('duration', 0):.0f}s):")
        if video.get("summary"):
            lines.append(f"  Summary: {video['summary']}")
        for scene in video.get("scenes", []):
            peak = " [PEAK MOMENT]" if scene.get("is_peak_moment") else ""
            lines.append(
                f"  - {scene.get('start', 0):.1f}s–{scene.get('end', 0):.1f}s: "
                f"{scene.get('description', '')}{peak}"
            )
    return "\n".join(lines)


def _enhance(req: EnhanceRequest, video_context: str) -> str:
    """Call Gemini to enhance the prompt."""
    from gemini_service import _call_gemini

    system_prompt = f"""You are an expert social media video director. The user has configured these reel settings:
- Style: {req.reel_style}
- Approach: {req.reel_approach} (hook = attention-grabbing opening first, story = chronological)
- Duration: {req.target_duration} seconds
- Transitions: {req.transition_style}
- Audio: {req.audio_mode}
- Captions: {"yes" if req.captions else "no"}
{video_context}

Take their rough prompt and enhance it into a detailed, specific creative direction that will produce a compelling reel. Your enhanced prompt should:
- Keep the user's original intent and tone
- Factor in the settings above (e.g. for a 10s reel keep it punchy, for 45s allow more storytelling)
- Add specific visual directions (pacing, mood, shot types) that match the chosen style and approach
{"- Reference specific scenes, moments, or content from the uploaded videos when relevant" if video_context else ""}
- Be 2-4 sentences max, concise but vivid
- Do NOT add hashtags or emojis
- Do NOT mention the settings back — just write a better creative direction
- Do NOT explain what you changed — just return the enhanced prompt directly

User's prompt: {req.prompt}

Enhanced prompt:"""

    response = _call_gemini(system_prompt, temperature=0.8)
    return response.text.strip()
