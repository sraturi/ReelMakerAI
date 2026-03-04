"""Centralized configuration for ReelMaker AI."""

import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# Font path (platform-aware)
_FONT_PATHS = {
    "Darwin": "/System/Library/Fonts/HelveticaNeue.ttc",
    "Windows": "C:/Windows/Fonts/arial.ttf",
}
FONT_PATH = _FONT_PATHS.get(
    platform.system(),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

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

# --- Beat detection ---
MIN_BEAT_INTERVAL = 1.5  # minimum seconds between cuts

# --- File types ---
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
