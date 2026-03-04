"""Beat detection using librosa."""

import logging
from pathlib import Path

import librosa

from config import MIN_BEAT_INTERVAL

log = logging.getLogger(__name__)


def _thin_beats(all_beats: list[float], min_interval: float) -> list[float]:
    """Keep only beats that are at least *min_interval* apart."""
    if not all_beats or min_interval <= 0:
        return all_beats
    thinned = [all_beats[0]]
    for b in all_beats[1:]:
        if b - thinned[-1] >= min_interval:
            thinned.append(b)
    return thinned


def detect_beats(music_path: str, min_interval: float = MIN_BEAT_INTERVAL) -> list[float]:
    """
    Detect beat timestamps in a music file using librosa.

    min_interval: minimum seconds between cuts. At 128 BPM raw beats
    are ~0.47s apart which is way too fast. Default 1.5s means cuts
    land on every 3rd-4th beat, giving a natural rhythm without
    overwhelming the viewer.
    """
    music_path = str(Path(music_path).resolve())
    y, sr = librosa.load(music_path, sr=22050, mono=True)

    _tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    all_beats = [round(float(t), 3) for t in beat_times]

    beats = _thin_beats(all_beats, min_interval)

    log.info(
        "  Detected %d raw beats, using %d cut points (min %.1fs apart)",
        len(all_beats), len(beats), min_interval,
    )
    return beats


def beats_from_bpm(bpm: int, duration: float, min_interval: float = MIN_BEAT_INTERVAL) -> list[float]:
    """
    Generate evenly-spaced beat timestamps from a BPM value.
    Use this when the user wants to sync cuts to a song they'll
    add later (e.g., on Instagram) by matching its BPM.
    """
    beat_interval = 60.0 / bpm
    all_beats = []
    t = 0.0
    while t <= duration:
        all_beats.append(round(t, 3))
        t += beat_interval

    beats = _thin_beats(all_beats, min_interval)

    log.info(
        "  Generated %d beats at %d BPM, using %d cut points (min %.1fs apart)",
        len(all_beats), bpm, len(beats), min_interval,
    )
    return beats
