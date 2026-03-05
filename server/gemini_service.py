"""Gemini API service for video analysis and editing plan generation."""

import json
import logging
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

from config import (
    ALLOWED_KENBURNS,
    ALLOWED_TRANSITIONS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from models import EditingPlan, MusicTrack, SceneAnalysisResult, VideoInfo


def _parse_gemini_json(text: str) -> dict:
    """Parse JSON from Gemini, tolerating trailing commas and truncation."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = cleaned

        # Strip a dangling key with no value  ("key":  at end or before } / ])
        repaired = re.sub(r',\s*"[^"]*"\s*:\s*$', "", repaired)

        # Close any unterminated string
        if repaired.count('"') % 2 == 1:
            repaired += '"'

        # Insert null for "key": } or "key": ] (missing value)
        repaired = re.sub(r':\s*([}\]])', r": null\1", repaired)

        # Remove trailing commas again
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        # Close open brackets/braces from inside out
        for _ in range(10):
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                stack = []
                in_str = False
                prev = ""
                for ch in repaired:
                    if ch == '"' and prev != '\\':
                        in_str = not in_str
                    if not in_str:
                        if ch in '{[':
                            stack.append(ch)
                        elif ch in '}]':
                            if stack:
                                stack.pop()
                    prev = ch
                if not stack:
                    break
                closer = '}' if stack[-1] == '{' else ']'
                repaired += closer

        # Final cleanup pass
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        return json.loads(repaired)

def _truncate_to_last_complete(text: str) -> dict | None:
    """Try to salvage truncated JSON by finding the last complete array element.

    Looks for the last '},' which marks a finished object in an array,
    truncates there, and closes all open brackets.  Returns the parsed
    dict on success, or None.
    """
    # Strip markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Find last complete array element boundary
    last_obj_end = cleaned.rfind("},")
    if last_obj_end == -1:
        return None

    truncated = cleaned[: last_obj_end + 1]  # include the closing }

    # Remove trailing commas
    truncated = re.sub(r",\s*$", "", truncated)

    # Close any remaining open brackets/braces
    for _ in range(20):
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            stack = []
            in_str = False
            prev = ""
            for ch in truncated:
                if ch == '"' and prev != '\\':
                    in_str = not in_str
                if not in_str:
                    if ch in '{[':
                        stack.append(ch)
                    elif ch in '}]':
                        if stack:
                            stack.pop()
                prev = ch
            if not stack:
                return None
            closer = '}' if stack[-1] == '{' else ']'
            truncated += closer

    return None


log = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _call_gemini(
    contents,
    *,
    temperature: float = 0.7,
    json_output: bool = False,
    model: str | None = None,
    max_output_tokens: int = 65536,
    thinking_budget: int | None = None,
):
    """Call Gemini with automatic retry on rate-limit (429) errors."""
    model = model or GEMINI_MODEL
    gen_config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        **({"response_mime_type": "application/json"} if json_output else {}),
        **({"thinking_config": types.ThinkingConfig(thinking_budget=thinking_budget)} if thinking_budget is not None else {}),
    )
    for attempt in range(MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=gen_config,
            )
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * RETRY_BACKOFF
                log.info("  Rate limited, waiting %ds before retry...", wait)
                time.sleep(wait)
            else:
                raise


def upload_video(video_path: str) -> types.File:
    """Upload a video file to Gemini for analysis."""
    name = Path(video_path).name
    log.info("  Uploading %s to Gemini...", name)

    video_file = client.files.upload(file=video_path)
    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state == "FAILED":
        raise RuntimeError(f"Gemini failed to process video: {video_path}")

    log.info("  \u2713 %s uploaded and processed", name)
    return video_file


def _delete_uploaded_files(files: list[types.File]) -> None:
    """Best-effort cleanup of uploaded Gemini files."""
    for f in files:
        try:
            client.files.delete(name=f.name)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Style & approach guides (used by Pass 2)
# ---------------------------------------------------------------------------

STYLE_GUIDES = {
    "travel": (
        "STYLE: Travel / Adventure\n"
        "Goal: Excite and inspire wanderlust\n"
        "Reel Length: 10-30 sec | Clip Count: 4-10 (use more clips for longer reels)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK (1-3 sec) \u2014 Best scenery or action shot\n"
        "2. JOURNEY / BUILD (2-7 sec) \u2014 POV, walking, drone, or travel transitions\n"
        "3. HIGHLIGHT / PAYOFF (2-5 sec) \u2014 Iconic location or final action (jump, sunset, etc.)\n"
        "4. OPTIONAL LOOP / ENDING (1-2 sec) \u2014 Repeat motion, subtle zoom out\n\n"
        "TIP: Mix wide + medium + close shots for variety.\n\n"
        "CAPTIONS (3-4 max, keep them dreamy and short):\n"
        "- Use 'title' for: location name or one powerful phrase (e.g. 'Lost in Bali', 'Chasing Sunsets')\n"
        "- Use 'caption' for: context (e.g. 'Day 3 exploring the coast', 'Morning hike')\n"
        "- Use 'highlight' for: the payoff (e.g. 'Worth every step', 'This view though')"
    ),
    "vlog": (
        "STYLE: Mini Vlog\n"
        "Goal: Tell a quick story or daily moment\n"
        "Reel Length: 10-30 sec | Clip Count: 4-10 (use more clips for longer reels)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK (1-3 sec) \u2014 Funny, relatable, or intriguing moment\n"
        "2. CONTEXT / BUILD (2-8 sec) \u2014 Short clips showing environment or setup\n"
        "3. MAIN MOMENT / CLIMAX (2-5 sec) \u2014 Key action or punchline\n"
        "4. ENDING / CTA (1-3 sec) \u2014 Smile, reaction, or text overlay\n\n"
        "TIP: Slightly longer clips (2-4 sec) feel authentic; don't over-cut talking head moments.\n\n"
        "CAPTIONS (3-5, conversational tone):\n"
        "- Use 'title' for: the hook line (e.g. 'POV: trying street food in Tokyo')\n"
        "- Use 'caption' for: narration (e.g. 'We had no idea what to expect', 'Best day ever')\n"
        "- Use 'highlight' for: punchlines or reactions (e.g. 'SO GOOD', 'Wait for it')"
    ),
    "tutorial": (
        "STYLE: Tutorial / How-To\n"
        "Goal: Show the process AND the final result clearly\n"
        "Reel Length: 10-45 sec | Clip Count: 4-10 (use more clips for longer reels)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK / PROBLEM (1-3 sec) \u2014 Show what you're solving or teaching\n"
        "2. STEP 1 (2-6 sec) \u2014 Visual of first step\n"
        "3. STEP 2+ (2-6 sec each) \u2014 Continue through the process steps\n"
        "4. FINAL RESULT / REVEAL (3-8 sec) \u2014 MUST show the finished product!\n"
        "   The last videos (highest numbered) usually contain the final result \u2014 ALWAYS use them.\n"
        "   Give the reveal enough screen time (3-8 sec) so the viewer sees the payoff.\n\n"
        "TIP: Keep each step visually distinct. The final reveal is the most important part \u2014 never skip it.\n\n"
        "CAPTIONS (3-5, instructional):\n"
        "- Use 'title' for: what you're making/doing (e.g. 'Glass Skin in 3 Steps')\n"
        "- Use 'caption' for: step instructions (e.g. 'Step 1: Apply primer evenly')\n"
        "- Use 'highlight' for: pro tips or the reveal (e.g. 'Game changer!', 'The final look')"
    ),
    "montage": (
        "STYLE: Montage / Highlight\n"
        "Goal: Energize with fast, punchy edits\n"
        "Reel Length: 10-30 sec | Clip Count: 4-10 (use more clips for longer reels, can split into micro clips)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK / IMPACT (1-2 sec) \u2014 Most visually striking moment\n"
        "2. RAPID HIGHLIGHTS (5-15 sec) \u2014 Cut shots in 1-2 sec increments, synced with beat\n"
        "3. CLIMAX / SIGNATURE MOMENT (2-5 sec) \u2014 The final impressive action\n"
        "4. LOOP / REPLAY (optional) \u2014 End mid-action for replayability\n\n"
        "TIP: You can turn each video into 2-3 micro clips for rhythm.\n\n"
        "CAPTIONS (2-4, punchy and hype):\n"
        "- Use 'title' for: one big phrase (e.g. 'SUMMER 2024', 'Best Night Ever')\n"
        "- Use 'highlight' for: energy words (e.g. 'LET'S GO', 'VIBES', 'Unreal')\n"
        "- Use 'caption' sparingly for: context if needed"
    ),
    "aesthetic": (
        "STYLE: Aesthetic / Cinematic\n"
        "Goal: Slow, emotional, visually pleasing\n"
        "Reel Length: 10-30 sec | Clip Count: 4-10 (use more clips for longer reels)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. OPENING / MOOD (2-4 sec) \u2014 Wide or establishing shot\n"
        "2. MIDDLE / FLOW (3-8 sec) \u2014 Medium shots with movement, subtle zooms, or transitions\n"
        "3. ENDING / HIGHLIGHT (3-8 sec) \u2014 Close-up, sunset, or dramatic moment\n"
        "4. OPTIONAL LOOP / FADE (1-2 sec) \u2014 Smooth fade or looping visual\n\n"
        "TIP: Longer clip durations work; motion inside the shot keeps attention without rapid cuts.\n\n"
        "CAPTIONS (1-2 MAX \u2014 less is more):\n"
        "- Use 'title' for: one poetic line (e.g. 'Quiet mornings', 'In between moments')\n"
        "- Avoid 'highlight' style \u2014 it's too loud for this aesthetic\n"
        "- If a second overlay is needed, use 'caption' (e.g. a date or location)"
    ),
    "promo": (
        "STYLE: Promo / Business\n"
        "Goal: Clear, persuasive message\n"
        "Reel Length: 10-30 sec | Clip Count: 4-10 (use more clips for longer reels)\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK (1-3 sec) \u2014 Eye-catching statement or benefit\n"
        "2. FEATURE / VALUE (2-8 sec) \u2014 Show product/service in action\n"
        "3. BENEFIT / RESULT (2-5 sec) \u2014 Before/after or testimonial\n"
        "4. CTA / ENDING (2-5 sec) \u2014 Text or voice directing action\n\n"
        "TIP: Keep clips purposeful; no filler. Each clip should push toward the goal.\n\n"
        "CAPTIONS (3-5, benefit-focused):\n"
        "- Use 'title' for: the hook (e.g. 'Your skin will thank you', 'Stop scrolling')\n"
        "- Use 'caption' for: features/benefits (e.g. '100% organic ingredients')\n"
        "- Use 'highlight' for: CTA (e.g. 'Link in bio', 'Book now', 'Limited spots')"
    ),
}


APPROACH_GUIDES = {
    "hook": (
        "APPROACH: Hook-first\n"
        "Open with the single most compelling, scroll-stopping moment across all videos.\n"
        "Then build context and end with a satisfying close.\n"
        "Structure: BEST SHOT \u2192 context/journey \u2192 payoff \u2192 close"
    ),
    "story": (
        "APPROACH: Story / Chronological Narrative\n"
        "Tell the story in natural order \u2014 beginning, middle, climax.\n"
        "Build anticipation and let the viewer experience the journey.\n"
        "Save the most impressive moment for the CLIMAX, not the opening.\n"
        "The first clip should SET THE SCENE (arrival, starting point, establishing shot),\n"
        "NOT the best moment. Build toward it.\n"
        "Structure: SCENE-SETTER \u2192 journey/build \u2192 CLIMAX (best moment) \u2192 close/resolution"
    ),
}


# ---------------------------------------------------------------------------
# Pass 1 — Scene analysis (with video files)
# ---------------------------------------------------------------------------

def analyze_video_scenes(
    videos: list[VideoInfo],
    uploaded_files: list[types.File],
    model: str | None = None,
) -> SceneAnalysisResult:
    """
    Pass 1: Watch videos and describe scenes in ~2-second windows.
    Purely analytical — no editing decisions.
    """
    videos_context = "\n".join(
        f"Video {i} ({v.filename}): {v.duration:.1f}s, {v.width}x{v.height}"
        for i, v in enumerate(videos)
    )

    analysis_prompt = f"""You are an expert video analyst. Your ONLY job is to watch these videos carefully and describe what happens.

VIDEOS:
{videos_context}

INSTRUCTIONS:
Watch each video and break it into ~2-second windows. For each window, describe:
1. What visually happens (be specific \u2014 "woman applies lipstick to upper lip" not "makeup application")
2. Rate visual interest 1-5:
   - 1: Static/boring (blank wall, nothing happening)
   - 2: Low interest (repetitive motion, unclear framing)
   - 3: Average (decent content, standard shot)
   - 4: High interest (great composition, interesting action, beautiful scenery)
   - 5: Exceptional (stunning visuals, dramatic moment, perfect timing, emotional peak)
   NOTE: Most content is 2-3. Reserve 4-5 for truly standout moments.
3. Tag each scene: scenery, action, closeup, wide_shot, medium_shot, transition, peak_moment, reaction, detail
4. Flag if there is speech/dialogue (has_speech)
5. Flag if there is significant movement/action (has_action)
6. Flag peak moments \u2014 the climax, payoff, or most visually striking instant (is_peak_moment)
   A peak moment is where anticipation pays off: the sunset bursts with color, the reveal happens, the reaction lands.

IMPORTANT: Do NOT suggest edits, clips, or transitions. Just watch and describe.

Return ONLY valid JSON:
{{
  "videos": [
    {{
      "filename": "<filename>",
      "source_index": <int>,
      "duration": <float>,
      "summary": "<one sentence overview of the video>",
      "scenes": [
        {{
          "start": <float>,
          "end": <float>,
          "description": "<what visually happens>",
          "interest": <1-5>,
          "tags": ["<tag1>", "<tag2>"],
          "has_speech": <bool>,
          "has_action": <bool>,
          "is_peak_moment": <bool>
        }}
      ]
    }}
  ]
}}"""

    content_parts = [
        types.Part.from_uri(file_uri=uf.uri, mime_type=uf.mime_type)
        for uf in uploaded_files
    ]
    content_parts.append(types.Part.from_text(text=analysis_prompt))

    for attempt in range(2):
        response = _call_gemini(
            content_parts, temperature=0.5, json_output=True, model=model,
            max_output_tokens=16384,
        )
        try:
            return SceneAnalysisResult(**_parse_gemini_json(response.text))
        except (json.JSONDecodeError, Exception) as e:
            if attempt == 0:
                log.warning("Pass 1 JSON parse failed (%s), trying truncation repair...", e)
                repaired = _truncate_to_last_complete(response.text)
                if repaired is not None:
                    try:
                        return SceneAnalysisResult(**repaired)
                    except Exception:
                        log.warning("Truncation repair failed, re-calling Gemini...")
            else:
                raise


# ---------------------------------------------------------------------------
# Scene menu formatter (bridge between Pass 1 and Pass 2)
# ---------------------------------------------------------------------------

def _format_scene_menu(analysis: SceneAnalysisResult) -> str:
    """Convert Pass 1 scene analysis into a readable text menu for Pass 2."""
    lines = []
    for video in analysis.videos:
        lines.append(f"VIDEO {video.source_index}: {video.filename} ({video.duration:.1f}s)")
        lines.append(f"  Summary: {video.summary}")
        lines.append("  Scenes:")
        for scene in video.scenes:
            peak = " *** PEAK MOMENT ***" if scene.is_peak_moment else ""
            speech = " [SPEECH]" if scene.has_speech else ""
            tags = ", ".join(scene.tags)
            lines.append(
                f"    [{scene.start:.1f}s - {scene.end:.1f}s] Interest: {scene.interest}/5{peak}{speech} "
                f"\u2014 {scene.description} ({tags})"
            )
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pass 2 — Edit planning (text-only, no video files)
# ---------------------------------------------------------------------------

def create_editing_plan_from_scenes(
    scene_menu: str,
    prompt: str,
    beat_times: list[float],
    music_track: MusicTrack,
    videos: list[VideoInfo],
    target_duration: float,
    reel_style: str = "montage",
    reel_approach: str = "hook",
    composite_layouts: list[str] | None = None,
    model: str | None = None,
) -> EditingPlan:
    """Pass 2: Create an editing plan from scene descriptions (text-only)."""
    beat_times_str = ", ".join(f"{t:.2f}" for t in beat_times)

    usable_beats = [t for t in beat_times if t <= target_duration]
    if not usable_beats:
        usable_beats = [i * 2.0 for i in range(int(target_duration / 2))]

    style_guide = STYLE_GUIDES.get(reel_style, STYLE_GUIDES["montage"])
    approach_guide = APPROACH_GUIDES.get(reel_approach, APPROACH_GUIDES["hook"])

    beat_count = len(usable_beats)
    if beat_count >= 2:
        avg_interval = round((usable_beats[-1] - usable_beats[0]) / (beat_count - 1), 2)
        beat_summary = f"{beat_count} beats, ~{avg_interval}s apart"
    else:
        beat_summary = f"{beat_count} beats"

    # Build per-video duration limits for the prompt
    total_footage = sum(v.duration for v in videos)
    video_limits = "\n".join(
        f"  Video {i} ({v.filename}): max {v.duration:.1f}s \u2014 start_time must be < {v.duration:.1f}, end_time must be \u2264 {v.duration:.1f}"
        for i, v in enumerate(videos)
    )

    # Composite layout prompt section (only when 2+ videos AND user checked at least one layout)
    allowed = [l for l in (composite_layouts or []) if l in ("split_v", "split_h", "pip", "grid")]
    if len(videos) >= 2 and allowed:
        layout_descriptions = {
            "split_v": '   - "split_v": top/bottom \u2014 comparisons, before/after',
            "split_h": '   - "split_h": left/right \u2014 side-by-side',
            "pip": '   - "pip": picture-in-picture \u2014 reaction/commentary over main',
            "grid": '   - "grid": 2x2 \u2014 montage of 4 quick moments (needs 4+ source videos)',
        }
        layout_lines = "\n".join(layout_descriptions[l] for l in allowed)
        # Build a concrete example for the first allowed layout
        example_layout = allowed[0]
        if example_layout in ("split_v", "split_h", "pip"):
            example_positions = {"split_v": ("top", "bottom"), "split_h": ("left", "right"), "pip": ("main", "overlay")}
            p0, p1 = example_positions[example_layout]
            composite_example = (
                f'      "layout": "{example_layout}",\n'
                f'      "sub_sources": [\n'
                f'        {{"source_video": "<file1>", "source_index": 0, "start_time": 2.0, "end_time": 5.0, "position": "{p0}"}},\n'
                f'        {{"source_video": "<file2>", "source_index": 1, "start_time": 1.0, "end_time": 4.0, "position": "{p1}"}}\n'
                f'      ]'
            )
        else:  # grid
            composite_example = (
                f'      "layout": "grid",\n'
                f'      "sub_sources": [\n'
                f'        {{"source_video": "<file1>", "source_index": 0, "start_time": 0.0, "end_time": 3.0, "position": "tl"}},\n'
                f'        {{"source_video": "<file2>", "source_index": 1, "start_time": 0.0, "end_time": 3.0, "position": "tr"}},\n'
                f'        {{"source_video": "<file1>", "source_index": 0, "start_time": 5.0, "end_time": 8.0, "position": "bl"}},\n'
                f'        {{"source_video": "<file2>", "source_index": 1, "start_time": 3.0, "end_time": 6.0, "position": "br"}}\n'
                f'      ]'
            )

        composite_section = f"""8. COMPOSITE LAYOUTS \u2014 REQUIRED: You MUST include at least 1 composite clip using the layouts below:
   The user has specifically requested these multi-video layouts:
{layout_lines}

   ONLY use the layout types listed above. Do NOT use any other layout types.
   You MUST include at least {min(len(allowed), 3)} composite clip(s) — use a DIFFERENT layout for each.
   Try to use each of the listed layouts at least once.
   Pick moments where the effect makes sense (comparisons, reactions, simultaneous moments).

   For composite clips, set clip.layout and clip.sub_sources (array of objects).
   Each sub_source: {{"source_video": "<filename>", "source_index": <int>, "start_time": <float>, "end_time": <float>, "position": "<pos>"}}
   Positions: split_v \u2192 top/bottom, split_h \u2192 left/right, pip \u2192 main/overlay, grid \u2192 tl/tr/bl/br
   Sub-sources MUST have the same duration (trim to match). Use different source videos for each sub-source.
   Don't use composites for the opening clip (clip 0).
   For composite clips, source_video/source_index/start_time/end_time refer to the first sub-source.

   Example composite clip:
   {{
      "source_video": "<file1>", "source_index": 0, "start_time": 2.0, "end_time": 5.0,
      "timeline_start": 6.0, "audio": "mute", "transition": "fade", "ken_burns": "none",
{composite_example}
   }}

"""
    else:
        composite_section = ""

    edit_prompt = f"""You are an expert short-form video editor (Instagram Reels / TikTok).

PRIMARY GOAL \u2014 this is your #1 priority, every clip must serve this:
{prompt}

Every clip you choose MUST clearly relate to the goal above. If a clip doesn't help
tell the story the user asked for, do NOT include it \u2014 no matter how "interesting" it looks.

{style_guide}

{approach_guide}

VIDEO ORDERING:
Videos are listed in recording order (filenames are sequential). Video 0 was recorded FIRST,
the last video was recorded LAST. This is the real-world chronological order \u2014 use it to
build a natural narrative (e.g. setup \u2192 process \u2192 result).

HARD LIMITS \u2014 do NOT use timestamps beyond these:
{video_limits}
Total available footage: {total_footage:.1f}s

SCENE ANALYSIS (from video review):
{scene_menu}

TIMING:
- Target duration: {target_duration:.1f}s (aim to fill this, but never exceed a video's actual duration)
- Beat timestamps (seconds): {beat_times_str}
- Summary: {beat_summary}
- Output: 1080x1920 portrait

YOUR JOB \u2014 build a reel that fulfills the PRIMARY GOAL above:

1. SELECT SCENES \u2014 Choose scenes that best serve the PRIMARY GOAL.
   - Prefer scenes rated 4-5, but INCLUDE lower-rated scenes if they show key content
     (e.g. a process step, a technique, a person speaking) that the goal requires.
   - ALWAYS include scenes marked *** PEAK MOMENT ***.
   - A 3-rated scene showing the main subject IS better than a 5-rated scene of something unrelated.

2. PICK YOUR OPENING \u2014 follow the APPROACH guide above:
   - If "Hook-first": open with the most compelling moment that matches the PRIMARY GOAL.
   - If "Story": open with a scene-setter that introduces the subject/topic.

3. ARRANGE CLIPS following the REEL STRUCTURE from the style guide.
   - The reel should feel like a coherent story about the PRIMARY GOAL, not a random highlight reel.
   - FOLLOW THE RECORDING ORDER: videos are sequential, so prefer Video 0 \u2192 Video 1 \u2192 Video 2 etc.
     This naturally builds a narrative (e.g. start of makeup \u2192 mid-process \u2192 final look).
     Exception: "Hook-first" approach may pull the best moment to the front, then resume sequential order.
   - When including a peak moment, start 1-2s before so the viewer sees buildup AND payoff.
   - Align clip transitions to beat timestamps when possible (but content > beat precision).
   - Use different time ranges \u2014 never repeat the same footage.
   - Spread across source videos when possible, but don't force it \u2014 if the best content for the goal is in one video, use that video more.

4. ADD CAPTIONS following the style guide's examples.
   - Each overlay needs a "style": "title", "caption", or "highlight"
     - "title": big bold centered text \u2014 hooks/headlines (position: center)
     - "caption": smaller text with dark background \u2014 context (position: bottom)
     - "highlight": black text on yellow box \u2014 callouts/CTAs (position: center or top)
   - Time overlays to appear/disappear near beat timestamps.

5. SET AUDIO per clip: "keep_audio" if [SPEECH] is present, "mute" otherwise.

6. PER-CLIP EFFECTS (secondary \u2014 pick quickly, don't overthink):
   - "transition": visual transition INTO this clip. Values: {', '.join(ALLOWED_TRANSITIONS)}
     Fast cuts \u2192 wipeleft/slideup. Smooth \u2192 fade/dissolve. Reveals \u2192 circleopen/radial. First clip: "fade".
   - "ken_burns": subtle zoom/pan. Values: {', '.join(ALLOWED_KENBURNS)}
     Static/wide shots \u2192 zoom_in/pan_right. Reveals \u2192 zoom_out. Action/speech \u2192 none.

7. REVIEW \u2014 before returning, check:
   - Does every clip serve the PRIMARY GOAL? Remove any that don't and replace with on-topic content.
   - Did you include *** PEAK MOMENT *** scenes?
   - Does the reel tell a coherent story or does it feel like random clips?

{composite_section}CONSTRAINTS:
- DURATION: {target_duration:.1f}s is the MINIMUM. You may go up to {target_duration * 1.25:.1f}s.
  Aim for {target_duration:.1f}s\u2013{target_duration * 1.25:.1f}s total. Use as much good footage as possible.
  If your clips add up to less than {target_duration:.1f}s, add more clips or use longer clips.
  BUT never invent timestamps \u2014 only use times within each video's actual duration (see HARD LIMITS above).
  If there isn't enough footage, use what's available \u2014 a shorter reel is better than invalid timestamps.
- Each clip must be at least 1.5s long
- Don't exceed any video's actual duration
- Use different segments \u2014 no repeated footage

CLIP ORDERING:
clips[0] plays FIRST. Last clip plays LAST. Set timeline_start sequentially:
0.0 for first clip, then previous clip's timeline_start + its duration, etc.

Return ONLY valid JSON:
{{
  "music_track": "{music_track.filename}",
  "total_duration": <number>,
  "description": "<1 sentence: what moments you chose and why>",
  "clips": [
    {{
      "source_video": "<filename>",
      "source_index": <int>,
      "start_time": <number>,
      "end_time": <number>,
      "timeline_start": <number>,
      "audio": "keep_audio|mute",
      "transition": "fade|fadeblack|dissolve|wipeleft|wiperight|slideup|slideleft|circleopen|radial",
      "ken_burns": "none|zoom_in|zoom_out|pan_left|pan_right",
      "layout": "single|split_v|split_h|pip|grid",
      "sub_sources": ["... array of sub_source objects, empty for single layout"]
    }}
  ],
  "text_overlays": [
    {{
      "text": "<text>",
      "start_time": <number>,
      "end_time": <number>,
      "position": "top|center|bottom",
      "font_size": <int>,
      "color": "white",
      "style": "title|caption|highlight"
    }}
  ]
}}"""

    for attempt in range(2):
        response = _call_gemini(
            edit_prompt, temperature=0.7 if attempt == 0 else 0.3,
            json_output=True, model=model,
            max_output_tokens=16384,
        )
        try:
            return EditingPlan(**_parse_gemini_json(response.text))
        except (json.JSONDecodeError, Exception) as e:
            if attempt == 0:
                log.warning("Pass 2 JSON parse failed (%s), trying truncation repair...", e)
                repaired = _truncate_to_last_complete(response.text)
                if repaired is not None:
                    try:
                        return EditingPlan(**repaired)
                    except Exception:
                        log.warning("Truncation repair failed, re-calling Gemini with lower temperature...")
            else:
                raise


# ---------------------------------------------------------------------------
# Orchestrator (public API — called by pipeline)
# ---------------------------------------------------------------------------

def analyze_videos_and_create_plan(
    videos: list[VideoInfo],
    prompt: str,
    beat_times: list[float],
    music_track: MusicTrack,
    target_duration: int | None = None,
    reel_style: str = "montage",
    reel_approach: str = "hook",
    model: str | None = None,
) -> EditingPlan:
    """
    Two-pass Gemini pipeline:
      Pass 1 — Upload videos, analyze scenes (with video files)
      Pass 2 — Create editing plan from scene descriptions (text-only)
    Returns a beat-synced editing plan with text overlays.
    """
    # Calculate target duration
    if target_duration is not None:
        target_dur = float(target_duration)
    else:
        max_duration = min(60.0, music_track.duration)
        target_dur = max(15.0, min(max_duration, sum(v.duration for v in videos)))

    # Upload videos
    uploaded_files = []
    for video in videos:
        uploaded_files.append(upload_video(video.path))

    # --- Pass 1: Scene Analysis (with video files) ---
    log.info("  Pass 1: Analyzing video scenes (%s)...", model or GEMINI_MODEL)
    analysis = analyze_video_scenes(videos, uploaded_files, model=model)

    total_scenes = sum(len(v.scenes) for v in analysis.videos)
    peak_moments = sum(1 for v in analysis.videos for s in v.scenes if s.is_peak_moment)
    log.info("  Pass 1 complete: %d scenes, %d peak moments identified", total_scenes, peak_moments)
    for va in analysis.videos:
        high_interest = sum(1 for s in va.scenes if s.interest >= 4)
        log.info("    %s: %d scenes, %d high-interest (4-5)", va.filename, len(va.scenes), high_interest)

    # Delete uploaded files (Pass 2 doesn't need them)
    _delete_uploaded_files(uploaded_files)

    # --- Pass 2: Edit Planning (text-only) ---
    log.info("  Pass 2: Creating editing plan from scene analysis (%s)...", model or GEMINI_MODEL)
    scene_menu = _format_scene_menu(analysis)
    plan = create_editing_plan_from_scenes(
        scene_menu=scene_menu,
        prompt=prompt,
        beat_times=beat_times,
        music_track=music_track,
        videos=videos,
        target_duration=target_dur,
        reel_style=reel_style,
        reel_approach=reel_approach,
        model=model,
    )
    log.info("  Pass 2 complete: %d clips, %d overlays", len(plan.clips), len(plan.text_overlays))

    return plan
