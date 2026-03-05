"""Centralized configuration for Reelvo."""

import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = BASE_DIR / "uploads"
THUMBNAIL_DIR = BASE_DIR / "thumbnails"
DATA_DIR = BASE_DIR / "data"

# Font path (platform-aware, with fallback chain)
_FONT_CANDIDATES = {
    "Darwin": [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "Windows": [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ],
}
_LINUX_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

def _find_font() -> str:
    """Find the first existing font from the candidate list."""
    candidates = _FONT_CANDIDATES.get(platform.system(), _LINUX_FALLBACKS)
    for path in candidates:
        if Path(path).exists():
            return path
    # Last resort: return the first candidate (FFmpeg will error with a clear message)
    return candidates[0] if candidates else "sans-serif"

FONT_PATH = _find_font()

# --- Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_RETRIES = 3
RETRY_BACKOFF = 15  # seconds multiplier per attempt

# --- Video output ---
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# --- Audio ---
AUDIO_SAMPLE_RATE = 44100

# --- Transitions ---
TRANSITION_DURATION = 0.3  # seconds of crossfade between clips
ALLOWED_TRANSITIONS = [
    "fade", "fadeblack", "dissolve",
    "wipeleft", "wiperight",
    "slideup", "slideleft",
    "circleopen", "radial",
]
TRANSITION_STYLES = {
    "auto": ALLOWED_TRANSITIONS,
    "smooth": ["fade", "fadeblack", "dissolve"],
    "dynamic": ["wipeleft", "wiperight", "slideup", "slideleft"],
    "dramatic": ["circleopen", "radial", "fadeblack"],
    "cut": [],  # empty = no xfade transitions
}

# --- Ken Burns ---
KENBURNS_SCALE = 1.2  # overscan factor for zoom/pan room
ALLOWED_KENBURNS = ["none", "zoom_in", "zoom_out", "pan_left", "pan_right"]

# --- Beat detection ---
MIN_BEAT_INTERVAL = 1.5  # minimum seconds between cuts

# --- File types ---
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

# --- Composite layouts ---
ALLOWED_LAYOUTS = ["single", "split_v", "split_h", "pip", "grid"]
LAYOUT_SOURCE_COUNT = {"single": 0, "split_v": 2, "split_h": 2, "pip": 2, "grid": 4}
LAYOUT_DIMS = {
    "split_v": (1080, 960),       # each half (top/bottom)
    "split_h": (540, 1920),       # each half (left/right)
    "pip_main": (1080, 1920),     # main video
    "pip_overlay": (300, 533),    # small overlay
    "grid": (540, 960),           # each quadrant
}
PIP_X, PIP_Y = 750, 1357  # overlay position (bottom-right)
COMPOSITE_BORDER_PX = 3   # thin white divider between panels
COMPOSITE_BORDER_COLOR = "white"
