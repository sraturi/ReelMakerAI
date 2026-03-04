"""Pipeline orchestrator for ReelMaker AI."""

import logging
import time
from collections import defaultdict

from beat_detection import beats_from_bpm, detect_beats
from config import MUSIC_DIR, OUTPUT_DIR
from ffmpeg_service import assemble_reel, probe_video
from gemini_service import (
    analyze_videos_and_create_plan,
    load_music_catalog,
    pick_music_track,
)
from models import ClipPlan, EditingPlan, MusicTrack, VideoInfo

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _deduplicate_clips(plan: EditingPlan, videos: list[VideoInfo]) -> int:
    """
    Fix duplicate/overlapping clips by reassigning to unused video segments.
    Modifies plan.clips in place. Returns the number of clips fixed.
    """
    used: dict[int, list[tuple[float, float]]] = {}
    fixed = 0

    def overlaps(s: float, e: float, ranges: list[tuple[float, float]]) -> bool:
        return any(s < ue - 0.1 and e > us + 0.1 for us, ue in ranges)

    for clip in plan.clips:
        si = clip.source_index
        if si not in used:
            used[si] = []

        if not overlaps(clip.start_time, clip.end_time, used[si]):
            used[si].append((clip.start_time, clip.end_time))
            continue

        # This clip overlaps — find an unused segment
        clip_dur = clip.end_time - clip.start_time
        placed = False

        # Try unused segment in same video first
        vid_dur = videos[si].duration
        t = 0.0
        while t + clip_dur <= vid_dur:
            if not overlaps(t, t + clip_dur, used[si]):
                clip.start_time = round(t, 3)
                clip.end_time = round(t + clip_dur, 3)
                placed = True
                break
            t += 0.5

        # Try other videos
        if not placed:
            for alt_si, v in enumerate(videos):
                if alt_si == si:
                    continue
                alt_used = used.get(alt_si, [])
                t = 0.0
                while t + clip_dur <= v.duration:
                    if not overlaps(t, t + clip_dur, alt_used):
                        clip.source_index = alt_si
                        clip.source_video = v.filename
                        clip.start_time = round(t, 3)
                        clip.end_time = round(t + clip_dur, 3)
                        si = alt_si
                        if si not in used:
                            used[si] = []
                        placed = True
                        break
                    t += 0.5
                if placed:
                    break

        if placed:
            fixed += 1
        used[si].append((clip.start_time, clip.end_time))

    return fixed


def _fix_chronological_order(plan: EditingPlan) -> int:
    """
    For clips from the same source video, ensure they appear in chronological
    order in the reel. Prevents showing the end of a video before its beginning.
    Swaps source time ranges while keeping reel positions fixed.
    """
    source_positions: dict[int, list[int]] = defaultdict(list)
    for i, clip in enumerate(plan.clips):
        source_positions[clip.source_index].append(i)

    fixed = 0
    for positions in source_positions.values():
        if len(positions) < 2:
            continue

        ranges = [(plan.clips[i].start_time, plan.clips[i].end_time) for i in positions]
        sorted_ranges = sorted(ranges, key=lambda r: r[0])

        if ranges == sorted_ranges:
            continue

        for pos, (new_start, new_end) in zip(positions, sorted_ranges):
            clip = plan.clips[pos]
            if clip.start_time != new_start or clip.end_time != new_end:
                clip.start_time = new_start
                clip.end_time = new_end
                fixed += 1

    return fixed


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    video_paths: list[str],
    prompt: str,
    target_duration: int | None = None,
    captions: bool = True,
    audio_mode: str = "both",
    bpm: int | None = None,
    reel_style: str = "montage",
    reel_approach: str = "hook",
) -> str:
    """
    Run the full reel-making pipeline:
    1. Probe videos with FFmpeg
    2. Pick music track via Gemini (or use BPM)
    3. Detect beats in the music (or generate from BPM)
    4. Analyze videos + create editing plan via Gemini (2-pass)
    5. Assemble: original audio (voices) + light background music + text overlays
    """
    start_time = time.time()

    # --- Step 1: Probe videos ---
    log.info("\n[1/5] Probing videos...")
    videos: list[VideoInfo] = []
    for vpath in video_paths:
        info = probe_video(vpath)
        videos.append(info)
        log.info("  %s: %.1fs, %dx%d", info.filename, info.duration, info.width, info.height)

    if bpm:
        # BPM mode: generate beats from BPM, skip music selection
        duration = float(target_duration) if target_duration else 30.0

        log.info("\n[2/5] Using %d BPM for beat timing (skipping music selection)...", bpm)
        track = MusicTrack(
            filename="", name=f"Custom {bpm} BPM", genre="",
            vibe="custom", bpm=bpm, duration=duration,
        )
        music_path = ""

        log.info("\n[3/5] Generating beats at %d BPM...", bpm)
        beat_times = beats_from_bpm(bpm, duration)
    else:
        # Normal mode: pick music track + detect beats from audio
        log.info("\n[2/5] Selecting music track...")
        catalog = load_music_catalog()
        track = pick_music_track(prompt, catalog)
        music_path = str(MUSIC_DIR / track.filename)
        log.info("  Selected: %s (%s, %d BPM)", track.name, track.vibe, track.bpm)

        log.info("\n[3/5] Detecting beats in music...")
        beat_times = detect_beats(music_path)

    # --- Step 4: Analyze videos + create editing plan (Gemini 2-pass) ---
    log.info("\n[4/5] Analyzing videos and creating editing plan (2-pass)...")
    plan: EditingPlan = analyze_videos_and_create_plan(
        videos=videos,
        prompt=prompt,
        beat_times=beat_times,
        music_track=track,
        target_duration=target_duration,
        reel_style=reel_style,
        reel_approach=reel_approach,
    )

    # Sort clips by timeline_start and recalculate sequential timing
    plan.clips.sort(key=lambda c: c.timeline_start)

    chrono_count = _fix_chronological_order(plan)
    if chrono_count:
        log.info("  Fixed %d clip(s) \u2014 reordered to chronological within source videos", chrono_count)

    # Recalculate timeline_start after reordering
    t = 0.0
    for clip in plan.clips:
        clip.timeline_start = round(t, 3)
        t += clip.end_time - clip.start_time

    dedup_count = _deduplicate_clips(plan, videos)
    if dedup_count:
        log.info("  Fixed %d overlapping clip(s) \u2014 reassigned to unused footage", dedup_count)

    if not captions:
        plan.text_overlays = []
        log.info("  Captions disabled \u2014 skipping text overlays")

    kept_audio = sum(1 for c in plan.clips if c.audio == "keep_audio")
    muted_audio = len(plan.clips) - kept_audio
    log.info("  Plan: %d clips, %d text overlays", len(plan.clips), len(plan.text_overlays))
    log.info("  Audio: %d clips with speech (keep_audio), %d muted", kept_audio, muted_audio)
    log.info("  Duration: %.1fs", plan.total_duration)
    log.info("  Approach: %s", plan.description)

    # --- Step 5: Assemble with FFmpeg ---
    log.info("\n[5/5] Assembling reel (original audio + background music)...")
    timestamp = int(time.time())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / f"reel_{timestamp}.mp4")
    result_path = assemble_reel(plan, videos, music_path, output_path, audio_mode=audio_mode)

    elapsed = time.time() - start_time
    log.info("\n\u2713 Done in %.1fs \u2192 %s", elapsed, result_path)

    return result_path
