"""FFmpeg service for probing videos and assembling the final reel."""

import json
import logging
import re
import subprocess
from pathlib import Path

from config import (
    ALLOWED_KENBURNS,
    ALLOWED_LAYOUTS,
    ALLOWED_TRANSITIONS,
    AUDIO_SAMPLE_RATE,
    COMPOSITE_BORDER_COLOR,
    COMPOSITE_BORDER_PX,
    FONT_PATH,
    KENBURNS_SCALE,
    LAYOUT_DIMS,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    PIP_X,
    PIP_Y,
    TRANSITION_DURATION,
)
from models import ClipPlan, EditingPlan, SubSource, VideoInfo

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

    # Detect audio stream
    has_audio = any(
        s["codec_type"] == "audio" for s in data.get("streams", [])
    )

    # Extract rotation from side_data_list or tags
    rotation = 0
    for sd in video_stream.get("side_data_list", []):
        if "rotation" in sd:
            rotation = int(sd["rotation"])
            break
    if rotation == 0:
        rotation = int(video_stream.get("tags", {}).get("rotate", 0))

    # Detect HDR from color transfer characteristics
    color_transfer = video_stream.get("color_transfer", "")
    is_hdr = color_transfer in ("arib-std-b67", "smpte2084")  # HLG or PQ/HDR10

    if rotation != 0:
        log.info("  Rotation detected: %d\u00b0 (FFmpeg auto-rotates)", rotation)
    if is_hdr:
        log.info("  HDR detected (%s) in %s", color_transfer, Path(video_path).name)
    if not has_audio:
        log.info("  No audio stream detected in %s", Path(video_path).name)

    return VideoInfo(
        path=str(Path(video_path).resolve()),
        filename=Path(video_path).name,
        duration=duration,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        rotation=rotation,
        has_audio=has_audio,
        is_hdr=is_hdr,
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

    # Only include fontfile if the configured font actually exists
    font_param = f"fontfile={FONT_PATH}:" if Path(FONT_PATH).exists() else ""

    if style == "caption":
        y_expr = f"{OUTPUT_HEIGHT * 0.85}"
        return (
            f"[{current_label}]drawtext="
            f"text='{escaped}':"
            f"{font_param}"
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
            f"{font_param}"
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
        f"{font_param}"
        f"fontsize={fs}:"
        f"fontcolor=white:"
        f"borderw=4:bordercolor=black:"
        f"shadowx=3:shadowy=3:shadowcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"{enable}"
        f"[{next_label}]"
    )


def _color_filter(is_hdr: bool) -> str:
    """Return filter snippet to normalize color to SDR BT.709.

    For HDR sources: tone-map to SDR via zscale + hable tone-mapping.
    For SDR sources: returns empty string (no-op).
    """
    if is_hdr:
        return (
            "zscale=tin=arib-std-b67:min=2020_ncl:pin=bt2020:"
            "t=linear:npl=100,format=gbrpf32le,"
            "zscale=p=bt709,tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:p=bt709:r=limited,"
            "format=yuv420p,"
        )
    return ""


def _build_kenburns_filter(
    clip: ClipPlan,
    input_label: str,
    output_label: str,
    is_hdr: bool = False,
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
        color_prefix = _color_filter(is_hdr)
        return [
            f"[{input_label}]{color_prefix}scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:"
            f"force_original_aspect_ratio=increase:flags=lanczos,"
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

    color_prefix = _color_filter(is_hdr)
    return [
        f"[{input_label}]{color_prefix}scale={os_w}:{os_h}:"
        f"force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={os_w}:{os_h},"
        f"setsar=1,"
        f"fps=30,"
        f"{zp}[{output_label}]"
    ]


def _build_composite_filter(
    clip: ClipPlan,
    clip_index: int,
    input_indices: dict[int, int],
    audio_mode: str,
    videos: list[VideoInfo] | None = None,
) -> tuple[list[str], str, str]:
    """
    Build filter chain for a composite layout clip.

    Returns (filter_lines, video_label, audio_label).
    """
    layout = clip.layout
    subs = clip.sub_sources
    filters: list[str] = []
    sr = AUDIO_SAMPLE_RATE
    prefix = f"comp{clip_index}"

    # All sub-sources must have the exact same duration to avoid
    # overlay disappearing early or xfade glitches at the seam
    min_dur = min(sub.end_time - sub.start_time for sub in subs)

    # Trim and scale each sub-source (clamped to min_dur)
    sub_labels: list[str] = []
    for j, sub in enumerate(subs):
        src_idx = input_indices[sub.source_index]
        vl = f"{prefix}_v{j}"
        sl = f"{prefix}_s{j}"
        sub_end = sub.start_time + min_dur  # clamp to shared duration

        # Determine target size for this sub
        if layout == "split_v":
            w, h = LAYOUT_DIMS["split_v"]
        elif layout == "split_h":
            w, h = LAYOUT_DIMS["split_h"]
        elif layout == "pip":
            if j == 0:  # main
                w, h = LAYOUT_DIMS["pip_main"]
            else:  # overlay
                w, h = LAYOUT_DIMS["pip_overlay"]
        elif layout == "grid":
            w, h = LAYOUT_DIMS["grid"]
        else:
            w, h = OUTPUT_WIDTH, OUTPUT_HEIGHT

        filters.append(
            f"[{src_idx}:v]trim=start={sub.start_time:.3f}:end={sub_end:.3f},"
            f"setpts=PTS-STARTPTS[{vl}]"
        )
        sub_is_hdr = videos[sub.source_index].is_hdr if videos else False
        color_prefix = _color_filter(sub_is_hdr)
        filters.append(
            f"[{vl}]{color_prefix}scale={w}:{h}:"
            f"force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h},setsar=1,fps=30[{sl}]"
        )
        sub_labels.append(sl)

    # Compose based on layout, then draw thin border lines at seams
    bw = COMPOSITE_BORDER_PX
    bc = COMPOSITE_BORDER_COLOR
    out_v = f"{prefix}_out"
    raw_v = f"{prefix}_raw"

    if layout == "split_v":
        # Horizontal seam at y = 960 (midpoint)
        seam_y = LAYOUT_DIMS["split_v"][1] - bw // 2
        filters.append(
            f"[{sub_labels[0]}][{sub_labels[1]}]vstack=inputs=2[{raw_v}]"
        )
        filters.append(
            f"[{raw_v}]drawbox=x=0:y={seam_y}:w={OUTPUT_WIDTH}:h={bw}:"
            f"color={bc}:t=fill[{out_v}]"
        )
    elif layout == "split_h":
        # Vertical seam at x = 540 (midpoint)
        seam_x = LAYOUT_DIMS["split_h"][0] - bw // 2
        filters.append(
            f"[{sub_labels[0]}][{sub_labels[1]}]hstack=inputs=2[{raw_v}]"
        )
        filters.append(
            f"[{raw_v}]drawbox=x={seam_x}:y=0:w={bw}:h={OUTPUT_HEIGHT}:"
            f"color={bc}:t=fill[{out_v}]"
        )
    elif layout == "pip":
        # Border outline around the overlay window
        ow, oh = LAYOUT_DIMS["pip_overlay"]
        filters.append(
            f"[{sub_labels[0]}][{sub_labels[1]}]overlay=x={PIP_X}:y={PIP_Y}[{raw_v}]"
        )
        filters.append(
            f"[{raw_v}]drawbox=x={PIP_X}:y={PIP_Y}:w={ow}:h={oh}:"
            f"color={bc}:t={bw}[{out_v}]"
        )
    elif layout == "grid":
        # Cross: vertical line at x=540, horizontal at y=960
        gw, gh = LAYOUT_DIMS["grid"]
        seam_x = gw - bw // 2
        seam_y = gh - bw // 2
        mid_v = f"{prefix}_gmid"
        filters.append(
            f"[{sub_labels[0]}][{sub_labels[1]}][{sub_labels[2]}][{sub_labels[3]}]"
            f"xstack=inputs=4:layout=0_0|{gw}_0|0_{gh}|{gw}_{gh}[{raw_v}]"
        )
        filters.append(
            f"[{raw_v}]drawbox=x={seam_x}:y=0:w={bw}:h={OUTPUT_HEIGHT}:"
            f"color={bc}:t=fill[{mid_v}]"
        )
        filters.append(
            f"[{mid_v}]drawbox=x=0:y={seam_y}:w={OUTPUT_WIDTH}:h={bw}:"
            f"color={bc}:t=fill[{out_v}]"
        )

    # Audio: use first sub-source's audio, clamped to min_dur
    # Falls back to silence if the source has no audio stream
    a_label = f"{prefix}_a"
    first_sub = subs[0]
    audio_end = first_sub.start_time + min_dur
    src_idx = input_indices[first_sub.source_index]
    source_has_audio = videos[first_sub.source_index].has_audio if videos else True

    if not source_has_audio or (clip.audio == "mute" and audio_mode != "original"):
        filters.append(
            f"aevalsrc=0:d={min_dur:.3f},"
            f"aformat=sample_rates={sr}:channel_layouts=stereo[{a_label}]"
        )
    else:
        # Pad + trim to exact duration for A/V sync with xfade
        filters.append(
            f"[{src_idx}:a]atrim=start={first_sub.start_time:.3f}:end={audio_end:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={min_dur:.3f},"
            f"atrim=end={min_dur:.3f},asetpts=PTS-STARTPTS[{a_label}]"
        )

    return filters, out_v, a_label


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
        # Main source
        if clip.source_index not in input_indices:
            cmd.extend(["-i", videos[clip.source_index].path])
            input_indices[clip.source_index] = ffmpeg_idx
            ffmpeg_idx += 1
        # Sub-sources for composite layouts
        for sub in clip.sub_sources:
            if sub.source_index not in input_indices:
                cmd.extend(["-i", videos[sub.source_index].path])
                input_indices[sub.source_index] = ffmpeg_idx
                ffmpeg_idx += 1

    # --- Build filter_complex ---
    filters = []
    video_concat_inputs = []
    audio_concat_inputs = []
    sr = AUDIO_SAMPLE_RATE

    for i, clip in enumerate(plan.clips):
        v_scaled = f"vscaled{i}"
        a_clip = f"aclip{i}"

        is_composite = (
            clip.layout in ALLOWED_LAYOUTS
            and clip.layout != "single"
            and len(clip.sub_sources) >= 2
        )

        if is_composite:
            # Composite layout: build multi-source filter
            comp_filters, comp_v, comp_a = _build_composite_filter(
                clip, i, input_indices, audio_mode, videos=videos
            )
            filters.extend(comp_filters)
            # Ensure consistent fps + reset PTS for xfade compatibility
            filters.append(f"[{comp_v}]fps=30,setpts=PTS-STARTPTS[{v_scaled}]")
            filters.append(f"[{comp_a}]asetpts=PTS-STARTPTS[{a_clip}]")
        else:
            # Standard single-source clip
            src_idx = input_indices[clip.source_index]
            v_clip = f"vclip{i}"

            # Trim video
            filters.append(
                f"[{src_idx}:v]trim=start={clip.start_time:.3f}:end={clip.end_time:.3f},"
                f"setpts=PTS-STARTPTS[{v_clip}]"
            )

            # Scale/crop with optional Ken Burns effect
            clip_is_hdr = videos[clip.source_index].is_hdr
            filters.extend(_build_kenburns_filter(clip, v_clip, v_scaled, is_hdr=clip_is_hdr))

            # Per-clip audio (silence fallback if source has no audio stream)
            # Pad + trim to exact clip duration for A/V sync with xfade
            clip_dur = clip.end_time - clip.start_time
            source_has_audio = videos[clip.source_index].has_audio
            if not source_has_audio or (clip.audio == "mute" and audio_mode != "original"):
                filters.append(
                    f"aevalsrc=0:d={clip_dur:.3f},"
                    f"aformat=sample_rates={sr}:channel_layouts=stereo[{a_clip}]"
                )
            else:
                filters.append(
                    f"[{src_idx}:a]atrim=start={clip.start_time:.3f}:end={clip.end_time:.3f},"
                    f"asetpts=PTS-STARTPTS,"
                    f"apad=whole_dur={clip_dur:.3f},"
                    f"atrim=end={clip_dur:.3f},asetpts=PTS-STARTPTS[{a_clip}]"
                )

        audio_concat_inputs.append(f"[{a_clip}]")
        video_concat_inputs.append(f"[{v_scaled}]")

    # Join video clips (xfade transitions or hard concat)
    n_clips = len(plan.clips)
    T = TRANSITION_DURATION
    use_xfade = transition_style != "cut" and n_clips > 1

    def _clip_duration(c: ClipPlan) -> float:
        if c.layout != "single" and c.sub_sources:
            return min(s.end_time - s.start_time for s in c.sub_sources)
        return c.end_time - c.start_time

    clip_durations = [round(_clip_duration(c), 3) for c in plan.clips]

    # Pre-compute xfade offsets using incremental accumulation (not re-summing)
    # to avoid O(n²) work and floating-point drift on long reels.
    xfade_offsets: list[float] = []
    if use_xfade:
        cumulative = 0.0
        for k in range(1, n_clips):
            cumulative = round(cumulative + clip_durations[k - 1], 3)
            offset = round(cumulative - k * T, 3)
            # Clip must be longer than transition duration on both sides
            prev_ok = clip_durations[k - 1] > T * 2
            curr_ok = clip_durations[k] > T * 2
            if offset < 0.05 or not prev_ok or not curr_ok:
                # Too short for transition — fall back to hard cut for whole reel
                log.warning(
                    "Clip %d too short for xfade (offset=%.3f), falling back to concat",
                    k, offset,
                )
                use_xfade = False
                xfade_offsets.clear()
                break
            xfade_offsets.append(offset)

    if n_clips == 1:
        lbl = video_concat_inputs[0].strip("[]")
        filters.append(f"[{lbl}]null[concatv]")
    elif use_xfade:
        prev = video_concat_inputs[0].strip("[]")
        for k in range(1, n_clips):
            cur = video_concat_inputs[k].strip("[]")
            out_label = "concatv" if k == n_clips - 1 else f"xf{k}"
            offset = xfade_offsets[k - 1]
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

    # Join audio clips — acrossfade with same duration as video xfade
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
    # When xfade is active, the output timeline is compressed: each transition
    # removes T seconds.  Build a mapping from raw cumulative time to xfade time
    # so overlay timestamps land at the correct position in the output.
    def _adjust_time(t: float) -> float:
        """Map a raw-timeline time to the xfade-compressed output timeline."""
        if not use_xfade:
            return t
        # Cumulative raw boundaries (before compression)
        # Round at each step to prevent drift on long reels (10+ clips)
        raw_boundary = 0.0
        compressed = 0.0
        for k, dur in enumerate(clip_durations):
            next_raw = round(raw_boundary + dur, 3)
            if t <= next_raw:
                # t falls inside clip k
                return round(compressed + (t - raw_boundary), 3)
            # After this clip, subtract transition overlap (except last clip)
            compressed = round(compressed + dur - (T if k < n_clips - 1 else 0), 3)
            raw_boundary = next_raw
        # Past the end — clamp to total
        return compressed

    current_video = "concatv"
    for j, overlay in enumerate(plan.text_overlays):
        next_label = f"txt{j}"
        adj_start = _adjust_time(overlay.start_time)
        adj_end = _adjust_time(overlay.end_time)
        if adj_end <= adj_start:
            continue  # overlay collapsed to nothing after adjustment
        filters.append(_build_drawtext_filter(
            current_label=current_video,
            next_label=next_label,
            text=overlay.text,
            style=getattr(overlay, "style", "title"),
            position=overlay.position,
            font_size=overlay.font_size,
            start_time=adj_start,
            end_time=adj_end,
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
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",        # BT.709 color matrix
        "-color_primaries", "bt709",   # BT.709 primaries
        "-color_trc", "bt709",         # BT.709 transfer curve
        "-preset", "fast",
        "-crf", "18",                  # near visually lossless
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
    cancel_event: "threading.Event | None" = None,
    progress_callback: "callable | None" = None,
) -> str:
    """Assemble the final reel using FFmpeg.

    If *cancel_event* is provided and gets set while FFmpeg is running,
    the subprocess is terminated early and a RuntimeError is raised.

    If *progress_callback(pct, message)* is provided, it is called with
    encoding progress updates parsed from FFmpeg's stderr output.
    """
    import threading

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_command(plan, videos, output_path, audio_mode=audio_mode,
                               transition_style=transition_style)

    kept = sum(1 for c in plan.clips if c.audio == "keep_audio")
    muted = len(plan.clips) - kept
    audio_desc = {"voice": "voice only", "original": "original audio"}
    log.info("  Running FFmpeg (%d clips, %d overlays)...", len(plan.clips), len(plan.text_overlays))
    log.info("  Audio: %s (%d keep, %d muted)", audio_desc.get(audio_mode, audio_mode), kept, muted)
    log.info("  Video: crop-to-fill %dx%d (no black bars)", OUTPUT_WIDTH, OUTPUT_HEIGHT)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # --- Read stderr in a background thread to parse FFmpeg progress ---
    stderr_lines: list[str] = []
    total_dur = plan.total_duration
    last_reported_pct = -1

    def _read_stderr():
        nonlocal last_reported_pct
        buf = ""
        for ch in iter(lambda: proc.stderr.read(1), ""):
            if ch in ("\r", "\n"):
                line = buf.strip()
                buf = ""
                if not line:
                    continue
                stderr_lines.append(line)
                if progress_callback and total_dur > 0 and "time=" in line:
                    m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
                    if m:
                        secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        pct = min(int(secs / total_dur * 100), 99)
                        if pct >= last_reported_pct + 10:
                            last_reported_pct = pct
                            speed_m = re.search(r"speed=\s*([\d.]+)x", line)
                            speed_str = f" ({speed_m.group(1)}x)" if speed_m else ""
                            progress_callback(pct, f"Encoding: {pct}%{speed_str}")
            else:
                buf += ch

    reader = threading.Thread(target=_read_stderr, daemon=True)
    reader.start()

    if cancel_event is not None:
        # Poll until process finishes or cancel is requested
        while proc.poll() is None:
            if cancel_event.wait(timeout=0.5):
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                reader.join(timeout=2)
                # Clean up partial output
                out = Path(output_path)
                if out.exists():
                    out.unlink(missing_ok=True)
                raise RuntimeError("Render cancelled by user")

    proc.wait()
    reader.join(timeout=5)
    stderr = "\n".join(stderr_lines)

    if proc.returncode != 0:
        log.error("  FFmpeg stderr:\n%s", stderr)
        raise RuntimeError(f"FFmpeg failed with code {proc.returncode}")

    out = Path(output_path)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg produced no output at {output_path}")

    size_mb = out.stat().st_size / (1024 * 1024)
    log.info("  \u2713 Reel assembled: %s (%.1f MB)", output_path, size_mb)
    return output_path
