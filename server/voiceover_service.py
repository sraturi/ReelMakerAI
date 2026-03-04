"""Voiceover service: Gemini writes the script, gTTS speaks it."""

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

from google import genai
from google.genai import types
from gtts import gTTS

from config import (
    AUDIO_SAMPLE_RATE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_RETRIES,
    RETRY_BACKOFF,
)

log = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_voiceover_script(prompt: str, total_duration: float) -> list[dict]:
    """
    Ask Gemini to write a voiceover script timed to the reel.
    Returns list of segments: [{text, start_time, end_time}, ...]
    """
    max_words = int(total_duration * 2.0)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=f"""Write a short voiceover script for a social media reel.

Prompt: "{prompt}"
Reel duration: {total_duration:.1f} seconds

RULES:
1. Write 3-5 short spoken segments that fit naturally over the video
2. Total word count must be under {max_words} words
3. Each segment should be 2-5 seconds when spoken
4. Leave gaps between segments (not wall-to-wall narration)
5. Start the first segment at 1.0 seconds (not 0)
6. Tone: confident, engaging, social-media style
7. End with a call to action

Return ONLY valid JSON array:
[
  {{"text": "<spoken text>", "start_time": <seconds>, "end_time": <seconds>}},
  ...
]""",
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * RETRY_BACKOFF
                log.info("  Rate limited, waiting %ds before retry...", wait)
                time.sleep(wait)
            else:
                raise

    segments = json.loads(response.text)
    log.info("  Script: %d segments", len(segments))
    for s in segments:
        log.info("    [%.1f-%.1fs] \"%s\"", s["start_time"], s["end_time"], s["text"])
    return segments


def synthesize_voiceover(segments: list[dict], total_duration: float) -> str:
    """
    Convert script segments to a single audio file using gTTS.
    Returns path to the voiceover WAV file.
    """
    import numpy as np
    import soundfile as sf

    sr = AUDIO_SAMPLE_RATE
    total_samples = int(total_duration * sr)
    mixed = np.zeros(total_samples)

    for seg in segments:
        tts = gTTS(text=seg["text"], lang="en", slow=False)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            tts.save(tmp_mp3.name)
            mp3_path = tmp_mp3.name

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name

        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", str(sr), "-ac", "1", wav_path],
            capture_output=True,
            check=True,
        )

        speech, _ = sf.read(wav_path)
        Path(mp3_path).unlink(missing_ok=True)
        Path(wav_path).unlink(missing_ok=True)

        # Place it at the right time
        start_sample = int(seg["start_time"] * sr)
        end_sample = start_sample + len(speech)

        if end_sample > total_samples:
            speech = speech[:total_samples - start_sample]

        if start_sample < total_samples:
            mixed[start_sample:start_sample + len(speech)] += speech

    # Normalize
    peak = np.max(np.abs(mixed))
    if peak > 0:
        mixed = mixed / peak * 0.9

    with tempfile.NamedTemporaryFile(suffix="_voiceover.wav", delete=False) as out_f:
        sf.write(out_f.name, mixed, sr)
        output_path = out_f.name

    log.info("  \u2713 Voiceover audio generated (%.1fs)", total_duration)
    return output_path
