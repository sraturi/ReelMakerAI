"""Beat generation from BPM."""

import logging

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
