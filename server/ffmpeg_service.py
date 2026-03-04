"""FFmpeg service for probing videos and assembling the final reel."""

import json
import logging
import subprocess
from pathlib import Path

from config import (
    ALLOWED_KENBURNS,
    ALLOWED_TRANSITIONS,
    AUDIO_SAMPLE_RATE,
    FONT_PATH,
    KENBURNS_SCALE,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    TRANSITION_DURATION,
)
from models import ClipPlan, EditingPlan, VideoInfo

log = logging.getLogger(__name__)


def probe_video(video_path: str) -> VideoInfo:
    """Probe a video file with FFmpeg to get metadata."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    video_stream = None
    for stream in data.get("streams", []):
        if stream["codec_type"] == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError(f"No video stream found in {video_path}")

    fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

    duration = float(data["format"]["duration"])

    # Extract rotation from side_data_list or tags
    rotation = 0
    for sd in video_stream.get("side_data_list", []):
        if "rotation" in sd:
            rotation = int(sd["rotation"])
            break
    if rotation == 0:
        rotation = int(video_stream.get("tags", {}).get("rotate", 0))

    if rotation != 0:
        log.info("  Rotation detected: %d\u00b0 (FFmpeg auto-rotates)", rotation)

    return VideoInfo(
        path=str(Path(video_path).resolve()),
        filename=Path(video_path).name,
        duration=duration,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        rotation=rotation,
    )


def _escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    return (
        text
        .replace("\\", "\\\\")
        .replace("'", "'\\''")
        .replace(":", "\\:")
        .replace("%", "%%")
    )


def _build_drawtext_filter(
    current_label: str,
    next_label: str,
    text: str,
    style: str,
    position: str,
    font_size: int,
    start_time: float,
    end_time: float,
) -> str:
    """Build a single drawtext filter string for a text overlay."""
    escaped = _escape_drawtext(text)
    enable = f"enable='between(t,{start_time:.3f},{end_time:.3f})'"

    if style == "caption":
        y_expr = f"{OUTPUT_HEIGHT * 0.85}"
        return (
            f"[{current_label}]drawtext="
            f"text='{escaped}':"
            f"fontfile={FONT_PATH}:"
            f"fontsize=48:"
            f"fontcolor=white:"
            f"box=1:boxcolor=black@0.5:boxborderw=20:"
            f"x=(w-text_w)/2:y={y_expr}:"
            f"{enable}"
            f"[{next_label}]"
        )

    if style == "highlight":
        y_map = {"top": f"{OUTPUT_HEIGHT * 0.08}", "bottom": f"{OUTPUT_HEIGHT * 0.85}"}
        y_expr = y_map.get(position, "(h-text_h)/2")
        return (
            f"[{current_label}]drawtext="
            f"text='{escaped}':"
            f"fontfile={FONT_PATH}:"
            f"fontsize=56:"
            f"fontcolor=black:"
            f"box=1:boxcolor=yellow@0.9:boxborderw=16:"
            f"x=(w-text_w)/2:y={y_expr}:"
            f"{enable}"
            f"[{next_label}]"
        )

    # title (default): big bold hero text, centered, with shadow
    fs = font_size if font_size else 72
    return (
        f"[{current_label}]drawtext="
        f"text='{escaped}':"
        f"fontfile={FONT_PATH}:"
        f"fontsize={fs}:"
        f"fontcolor=white:"
        f"borderw=4:bordercolor=black:"
        f"shadowx=3:shadowy=3:shadowcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"{enable}"
        f"[{next_label}]"
    )


def _build_kenburns_filter(
    clip: ClipPlan,
    input_label: str,
    output_label: str,
) -> list[str]:
    """
    Build filter chain for Ken Burns zoom/pan effect on a single clip.

    Returns a list of filter strings that transform [input_label] -> [output_label].
    For 'none', returns a simple scale/crop chain (same as default).
    For zoom/pan effects, scales to overscan size then applies zoompan.
    """
    kb = clip.ken_burns
    if kb not in ALLOWED_KENBURNS or kb == "none":
        # Standard scale + crop (no Ken Burns)
        # fps=30 ensures consistent timebase across all clips for xfade
        return [
            f"[{input_label}]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
            f"setsar=1,fps=30[{output_label}]"
        ]

    # Overscan dimensions for zoompan room
    os_w = int(OUTPUT_WIDTH * KENBURNS_SCALE)
    os_h = int(OUTPUT_HEIGHT * KENBURNS_SCALE)

    clip_dur = clip.end_time - clip.start_time
    n_frames = max(int(clip_dur * 30), 1)

    # Build zoompan expression based on effect type
    if kb == "zoom_in":
        zp = (
            f"zoompan=z='min(1+0.15*on/{n_frames},1.15)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps=30"
        )
    elif kb == "zoom_out":
        zp = (
            f"zoompan=z='if(eq(on,0),1.15,max(1.15-0.15*on/{n_frames},1.0))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps=30"
        )
    elif kb == "pan_right":
        zp = (
            f"zoompan=z=1.1:"
            f"x='iw*(1-1/1.1)*on/{n_frames}':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps=30"
        )
    else:  # pan_left
        zp = (
            f"zoompan=z=1.1:"
            f"x='iw*(1-1/1.1)*(1-on/{n_frames})':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps=30"
        )

    return [
        f"[{input_label}]scale={os_w}:{os_h}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={os_w}:{os_h},"
        f"setsar=1,"
        f"fps=30,"
        f"{zp}[{output_label}]"
    ]


def build_ffmpeg_command(
    plan: EditingPlan,
    videos: list[VideoInfo],
    output_path: str,
    audio_mode: str = "voice",
    transition_style: str = "auto",
) -> list[str]:
    """
    Build an FFmpeg command that:
    1. Cuts clips according to the editing plan (video + audio)
    2. Scales/crops each clip to OUTPUT_WIDTH x OUTPUT_HEIGHT
    3. Concatenates clips with their original audio
    4. Burns in text overlays
    """
    cmd = ["ffmpeg", "-y"]

    # --- Input files ---
    input_indices: dict[int, int] = {}
    ffmpeg_idx = 0
    for clip in plan.clips:
        if clip.source_index not in input_indices:
            cmd.extend(["-i", videos[clip.source_index].path])
            input_indices[clip.source_index] = ffmpeg_idx
            ffmpeg_idx += 1

    # --- Build filter_complex ---
    filters = []
    video_concat_inputs = []
    audio_concat_inputs = []
    sr = AUDIO_SAMPLE_RATE

    for i, clip in enumerate(plan.clips):
        src_idx = input_indices[clip.source_index]
        v_clip = f"vclip{i}"
        v_scaled = f"vscaled{i}"
        a_clip = f"aclip{i}"

        # Trim video
        filters.append(
            f"[{src_idx}:v]trim=start={clip.start_time:.3f}:end={clip.end_time:.3f},"
            f"setpts=PTS-STARTPTS[{v_clip}]"
        )

        # Scale/crop with optional Ken Burns effect
        filters.extend(_build_kenburns_filter(clip, v_clip, v_scaled))

        # Per-clip audio
        # "original" keeps all audio; "voice" respects Gemini mute flags
        clip_dur = clip.end_time - clip.start_time
        if clip.audio == "mute" and audio_mode != "original":
            filters.append(
                f"aevalsrc=0:d={clip_dur:.3f},"
                f"aformat=sample_rates={sr}:channel_layouts=stereo[{a_clip}]"
            )
        else:
            filters.append(
                f"[{src_idx}:a]atrim=start={clip.start_time:.3f}:end={clip.end_time:.3f},"
                f"asetpts=PTS-STARTPTS[{a_clip}]"
            )
        audio_concat_inputs.append(f"[{a_clip}]")

        video_concat_inputs.append(f"[{v_scaled}]")

    # Join video clips (xfade transitions or hard concat)
    n_clips = len(plan.clips)
    T = TRANSITION_DURATION
    use_xfade = transition_style != "cut" and n_clips > 1
    clip_durations = [c.end_time - c.start_time for c in plan.clips]

    if n_clips == 1:
        lbl = video_concat_inputs[0].strip("[]")
        filters.append(f"[{lbl}]null[concatv]")
    elif use_xfade:
        prev = video_concat_inputs[0].strip("[]")
        for k in range(1, n_clips):
            cur = video_concat_inputs[k].strip("[]")
            out_label = "concatv" if k == n_clips - 1 else f"xf{k}"
            offset = sum(clip_durations[:k]) - k * T
            # Use per-clip transition type (validated against allowed list)
            tr = getattr(plan.clips[k], "transition", "fade")
            if tr not in ALLOWED_TRANSITIONS:
                tr = "fade"
            filters.append(
                f"[{prev}][{cur}]xfade=transition={tr}:duration={T}:offset={offset:.3f}[{out_label}]"
            )
            prev = out_label
    else:
        # Hard cut — simple concat, no crossfade
        all_v = "".join(video_concat_inputs)
        filters.append(f"{all_v}concat=n={n_clips}:v=1:a=0[concatv]")

    # Join audio clips
    if n_clips == 1:
        filters.append(f"{audio_concat_inputs[0]}anull[concata]")
    elif use_xfade:
        prev = audio_concat_inputs[0].strip("[]")
        for k in range(1, n_clips):
            cur = audio_concat_inputs[k].strip("[]")
            out_label = "concata" if k == n_clips - 1 else f"axf{k}"
            filters.append(
                f"[{prev}][{cur}]acrossfade=d={T}:c1=tri:c2=tri[{out_label}]"
            )
            prev = out_label
    else:
        # Hard cut — simple concat audio
        all_a = "".join(audio_concat_inputs)
        filters.append(f"{all_a}concat=n={n_clips}:v=0:a=1[concata]")

    # Text overlays
    current_video = "concatv"
    for j, overlay in enumerate(plan.text_overlays):
        next_label = f"txt{j}"
        filters.append(_build_drawtext_filter(
            current_label=current_video,
            next_label=next_label,
            text=overlay.text,
            style=getattr(overlay, "style", "title"),
            position=overlay.position,
            font_size=overlay.font_size,
            start_time=overlay.start_time,
            end_time=overlay.end_time,
        ))
        current_video = next_label

    # --- Audio output ---
    filters.append(
        f"[concata]aformat=sample_rates={sr}:channel_layouts=stereo,"
        "loudnorm=I=-14:TP=-1:LRA=11[outa]"
    )

    filter_complex = ";\n".join(filters)

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{current_video}]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", "30",
        "-t", f"{plan.total_duration:.3f}",
        "-movflags", "+faststart",
        output_path,
    ])

    return cmd


def assemble_reel(
    plan: EditingPlan,
    videos: list[VideoInfo],
    output_path: str,
    audio_mode: str = "voice",
    transition_style: str = "auto",
) -> str:
    """Assemble the final reel using FFmpeg."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_command(plan, videos, output_path, audio_mode=audio_mode,
                               transition_style=transition_style)

    kept = sum(1 for c in plan.clips if c.audio == "keep_audio")
    muted = len(plan.clips) - kept
    audio_desc = {"voice": "voice only", "original": "original audio"}
    log.info("  Running FFmpeg (%d clips, %d overlays)...", len(plan.clips), len(plan.text_overlays))
    log.info("  Audio: %s (%d keep, %d muted)", audio_desc.get(audio_mode, audio_mode), kept, muted)
    log.info("  Video: crop-to-fill %dx%d (no black bars)", OUTPUT_WIDTH, OUTPUT_HEIGHT)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("  FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")

    out = Path(output_path)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg produced no output at {output_path}")

    size_mb = out.stat().st_size / (1024 * 1024)
    log.info("  \u2713 Reel assembled: %s (%.1f MB)", output_path, size_mb)
    return output_path
