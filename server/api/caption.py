"""POST /api/rewrite-caption — AI generates caption alternatives."""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import RewriteCaptionRequest
from session_store import store

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/rewrite-caption")
async def rewrite_caption(req: RewriteCaptionRequest):
    """Ask AI to generate 3 alternative captions. Synchronous (1-3s)."""
    session = store.get(req.session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    context_info = ""
    if session.plan:
        context_info = f"Reel description: {session.plan.get('description', '')}"

    prompt = f"""You are an expert social media copywriter for Instagram Reels and TikTok.

CURRENT CAPTION: "{req.caption_text}"

REEL CONTEXT: {context_info}
{f"ADDITIONAL CONTEXT: {req.context}" if req.context else ""}
{f"USER DIRECTION: {req.direction}" if req.direction else ""}

Generate 3 alternative captions. Each should be:
- Short and punchy (max 8 words)
- Different tone/approach from each other
- Suitable for a text overlay on a vertical video

Return ONLY valid JSON:
{{
  "suggestions": [
    {{"text": "<caption text>", "style": "title|caption|highlight", "tone": "<brief tone description>"}},
    {{"text": "<caption text>", "style": "title|caption|highlight", "tone": "<brief tone description>"}},
    {{"text": "<caption text>", "style": "title|caption|highlight", "tone": "<brief tone description>"}}
  ]
}}"""

    try:
        from gemini_service import _call_gemini

        response = await asyncio.to_thread(
            _call_gemini, prompt, temperature=0.9, json_output=True,
            model=req.gemini_model or None,
            max_output_tokens=1024, thinking_budget=0,
        )
        return json.loads(response.text)

    except Exception as e:
        log.error("Rewrite caption failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
