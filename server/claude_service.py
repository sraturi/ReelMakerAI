"""Claude API service for music selection and editing plan creation."""

import json
import os

import anthropic
from dotenv import load_dotenv

from models import EditingPlan, MusicTrack, VideoInfo

load_dotenv()

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")


def pick_music_track(prompt: str, catalog: list[MusicTrack]) -> MusicTrack:
    """Use Claude to pick the best music track based on the prompt vibe."""
    tracks_desc = "\n".join(
        f'- {t.filename}: "{t.name}" (vibe: {t.vibe}, BPM: {t.bpm}, duration: {t.duration}s)'
        for t in catalog
    )

    response = claude.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Pick the best music track for this short-form reel.

User prompt: "{prompt}"

Available tracks:
{tracks_desc}

Return ONLY the filename of the best matching track (e.g., "energetic_01.mp3"). Nothing else.""",
        }],
    )

    chosen_filename = response.content[0].text.strip().strip('"').strip("'")

    for track in catalog:
        if track.filename == chosen_filename:
            return track

    # Fallback
    print(f"  Warning: Claude picked '{chosen_filename}' which wasn't found, using first track")
    return catalog[0]


def create_editing_plan(
    video_analyses: list[dict],
    videos: list[VideoInfo],
    prompt: str,
    beat_times: list[float],
    music_track: MusicTrack,
) -> EditingPlan:
    """
    Claude creates the editing plan from Gemini's video analysis.
    Uses Claude's superior structured reasoning for beat-synced JSON.
    """
    # Build video context from Gemini's analysis
    video_context = []
    for i, (v, analysis) in enumerate(zip(videos, video_analyses)):
        video_context.append(
            f"Video {i} ({v.filename}): {v.duration:.1f}s, {v.width}x{v.height}\n"
            f"  Content: {analysis['description']}\n"
            f"  Key moments: {analysis.get('key_moments', 'N/A')}"
        )
    videos_str = "\n\n".join(video_context)

    beat_times_str = ", ".join(f"{t:.2f}" for t in beat_times)

    max_duration = min(60.0, music_track.duration)
    target_duration = max(15.0, min(max_duration, sum(v.duration for v in videos)))

    usable_beats = [t for t in beat_times if t <= target_duration]
    if not usable_beats:
        usable_beats = [i * 2.0 for i in range(int(target_duration / 2))]

    response = claude.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""You are an expert video editor creating a short-form reel (Instagram/TikTok style).

TASK: Create a beat-synced editing plan for a reel.

USER PROMPT: {prompt}

AVAILABLE VIDEOS (analyzed by AI):
{videos_str}

MUSIC: {music_track.name} ({music_track.vibe} vibe, {music_track.bpm} BPM)
BEAT TIMESTAMPS for cuts (seconds): {beat_times_str}

TARGET DURATION: {target_duration:.1f} seconds (must be between 15-60 seconds)
OUTPUT FORMAT: 1080x1920 (portrait/vertical)

RULES:
1. Cut clips ON the beat timestamps - each clip transition should align with a beat
2. Use segments from the provided videos (don't exceed their durations)
3. Each clip should be at least 1.5 seconds long
4. Add 3-5 engaging text overlays that support the prompt message
5. Text overlays should appear/disappear on beats too
6. Vary which source videos you use - don't just use one
7. The total timeline must not exceed {target_duration:.1f} seconds
8. Pick the most visually interesting moments from each video based on the AI analysis

Return ONLY valid JSON matching this exact schema:
{{
  "music_track": "{music_track.filename}",
  "total_duration": <number>,
  "description": "<brief description of your editing approach>",
  "clips": [
    {{
      "source_video": "<filename>",
      "source_index": <int>,
      "start_time": <number>,
      "end_time": <number>,
      "timeline_start": <number>
    }}
  ],
  "text_overlays": [
    {{
      "text": "<text>",
      "start_time": <number>,
      "end_time": <number>,
      "position": "top|center|bottom",
      "font_size": <int>,
      "color": "white"
    }}
  ]
}}""",
        }],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if Claude wraps it
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    plan_json = json.loads(raw)
    return EditingPlan(**plan_json)
