"""FFmpeg thumbnail extraction and caching service."""

import subprocess
from pathlib import Path

from config import THUMBNAIL_DIR


def get_thumbnail_path(session_id: str, video_index: int, timestamp: float) -> Path:
    """Get the cache path for a thumbnail."""
    cache_dir = THUMBNAIL_DIR / session_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts_str = f"{timestamp:.2f}".replace(".", "_")
    return cache_dir / f"{video_index}_{ts_str}.jpg"


def generate_thumbnail(
    video_path: str,
    session_id: str,
    video_index: int,
    timestamp: float,
) -> Path | None:
    """Generate a thumbnail frame at the given timestamp. Returns cached path if exists."""
    cache_path = get_thumbnail_path(session_id, video_index, timestamp)

    if cache_path.exists():
        return cache_path

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", f"{timestamp:.3f}",
                "-i", video_path,
                "-vframes", "1",
                "-s", "270x480",
                "-q:v", "3",
                str(cache_path),
            ],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return cache_path if cache_path.exists() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
