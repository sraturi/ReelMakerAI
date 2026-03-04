"""Gemini API service for video analysis and editing plan generation."""

import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from models import EditingPlan, MusicTrack, SceneAnalysisResult, VideoInfo

log = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _call_gemini(contents, *, temperature: float = 0.7, json_output: bool = False):
    """Call Gemini with automatic retry on rate-limit (429) errors."""
    config = types.GenerateContentConfig(
        temperature=temperature,
        **({"response_mime_type": "application/json"} if json_output else {}),
    )
    for attempt in range(MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
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
        "Reel Length: 10-30 sec | Clip Count: 3-5\n\n"
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
        "Reel Length: 10-30 sec | Clip Count: 3-5\n\n"
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
        "Goal: Show a step or result clearly\n"
        "Reel Length: 10-30 sec | Clip Count: 3-5\n\n"
        "REEL STRUCTURE (follow this order):\n"
        "1. HOOK / PROBLEM (1-3 sec) \u2014 Show what you're solving or teaching\n"
        "2. STEP 1 (2-6 sec) \u2014 Visual of first step\n"
        "3. STEP 2 (2-6 sec) \u2014 Next key step\n"
        "4. RESULT / BEFORE-AFTER (2-5 sec) \u2014 Quick payoff or final tip\n\n"
        "TIP: Keep each step visually distinct. Add short captions for clarity.\n\n"
        "CAPTIONS (3-5, instructional):\n"
        "- Use 'title' for: what you're making/doing (e.g. 'Glass Skin in 3 Steps')\n"
        "- Use 'caption' for: step instructions (e.g. 'Step 1: Apply primer evenly')\n"
        "- Use 'highlight' for: pro tips (e.g. 'Game changer!', 'Don't skip this')"
    ),
    "montage": (
        "STYLE: Montage / Highlight\n"
        "Goal: Energize with fast, punchy edits\n"
        "Reel Length: 10-30 sec | Clip Count: 3-5 (can split into micro clips)\n\n"
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
        "Reel Length: 10-30 sec | Clip Count: 3-5\n\n"
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
        "Reel Length: 10-30 sec | Clip Count: 3-5\n\n"
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

    response = _call_gemini(content_parts, temperature=0.5, json_output=True)
    return SceneAnalysisResult(**json.loads(response.text))


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

    edit_prompt = f"""You are an expert short-form video editor (Instagram Reels / TikTok).

USER WANTS: {prompt}

{style_guide}

{approach_guide}

SCENE ANALYSIS (from video review):
{scene_menu}

TIMING:
- Target duration: {target_duration:.1f}s
- Beat timestamps (seconds): {beat_times_str}
- Summary: {beat_summary}
- Output: 1080x1920 portrait

YOUR JOB \u2014 use the scene analysis above to build the best possible reel:

1. SELECT SCENES \u2014 STRONGLY PREFER scenes rated 4-5. Avoid scenes rated 1-2.
   ALWAYS include scenes marked *** PEAK MOMENT *** \u2014 these are the highlights.
   If you skip a 5-rated scene, reconsider \u2014 it's probably worth including.

2. PICK YOUR OPENING \u2014 follow the APPROACH guide above:
   - If "Hook-first": the first clip must be the single most compelling moment (highest rated). Stop the scroll.
   - If "Story": the first clip should SET THE SCENE \u2014 an arrival, establishing shot, or starting point. Save the best moment for the climax later.

3. ARRANGE CLIPS following the REEL STRUCTURE from the style guide and APPROACH above.
   - CRITICAL: When including a peak moment, make sure the clip CONTAINS the peak \u2014 start 1-2s before the peak timestamp so the viewer sees the buildup AND the payoff.
   - Align clip transitions to the nearest beat timestamp when possible
   - Beats are a GUIDE, not a prison \u2014 shift up to 0.5s off-beat to capture a better moment
   - Content quality > beat precision
   - Use the clip lengths recommended in the style guide
   - Use different time ranges from each video \u2014 never repeat the same footage
   - Use multiple source videos \u2014 distribute clips across them
   - CHRONOLOGICAL RULE: if you use the same video twice, the second clip must be from LATER in the video than the first.

4. ADD CAPTIONS following the style guide's caption examples above.
   - Match the tone and style shown in the examples
   - Use the recommended overlay styles (title/caption/highlight) as described
   - Each overlay must have a "style" field: "title", "caption", or "highlight"
     - "title": big bold centered text \u2014 for hooks/headlines (position: center)
     - "caption": smaller text with dark background \u2014 for context (position: bottom)
     - "highlight": black text on yellow box \u2014 for callouts/CTAs (position: center or top)
   - Time overlays to appear/disappear near beat timestamps

5. SET AUDIO per clip: "keep_audio" if the scene has speech (marked [SPEECH]), "mute" otherwise.

6. REVIEW YOUR EDIT \u2014 before returning, check:
   - Did you include all *** PEAK MOMENT *** scenes? If not, reconsider.
   - Does every clip add something new? Replace duplicates with fresh moments.
   - Does it drag anywhere? Shorten or swap for higher-energy content.

CONSTRAINTS:
- Total duration must not exceed {target_duration:.1f}s
- Each clip must be at least 1.5s long
- Don't exceed any video's actual duration
- Use different segments \u2014 no repeated footage

CRITICAL \u2014 CLIP ORDERING:
The clips array is the PLAYBACK ORDER. clips[0] plays FIRST (the viewer sees it first).
The last clip in the array plays LAST. Order the array to match your intended reel structure.
Set timeline_start sequentially: 0.0 for the first clip, then previous clip's timeline_start + its duration, etc.

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
      "audio": "keep_audio|mute"
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

    response = _call_gemini(edit_prompt, temperature=0.7, json_output=True)
    return EditingPlan(**json.loads(response.text))


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
    log.info("  Pass 1: Analyzing video scenes (%s)...", GEMINI_MODEL)
    analysis = analyze_video_scenes(videos, uploaded_files)

    total_scenes = sum(len(v.scenes) for v in analysis.videos)
    peak_moments = sum(1 for v in analysis.videos for s in v.scenes if s.is_peak_moment)
    log.info("  Pass 1 complete: %d scenes, %d peak moments identified", total_scenes, peak_moments)
    for va in analysis.videos:
        high_interest = sum(1 for s in va.scenes if s.interest >= 4)
        log.info("    %s: %d scenes, %d high-interest (4-5)", va.filename, len(va.scenes), high_interest)

    # Delete uploaded files (Pass 2 doesn't need them)
    _delete_uploaded_files(uploaded_files)

    # --- Pass 2: Edit Planning (text-only) ---
    log.info("  Pass 2: Creating editing plan from scene analysis (%s)...", GEMINI_MODEL)
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
    )
    log.info("  Pass 2 complete: %d clips, %d overlays", len(plan.clips), len(plan.text_overlays))

    return plan
