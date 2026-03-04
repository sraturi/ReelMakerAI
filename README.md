# AiReelMaker

AI-powered tool that automatically creates beat-synced Instagram Reels and TikTok videos from raw footage. It uses Google Gemini to analyze your videos, pick the best moments, and assemble a polished reel with music, text overlays, and smart audio mixing — all via a simple CLI.

## How It Works

1. **Probe videos** — FFmpeg extracts metadata (duration, resolution, FPS)
2. **Pick music** — Gemini selects the best track from a built-in catalog based on your prompt
3. **Detect beats** — librosa analyzes the music to find beat timestamps for cut-syncing
4. **AI editing (2-pass)**
   - *Pass 1:* Gemini watches your videos and catalogs every scene (interest rating, speech detection, peak moments)
   - *Pass 2:* Gemini builds an editing plan — clip selection, ordering, text overlays — all synced to beats
5. **Assemble** — FFmpeg cuts, scales, concatenates, mixes audio, and burns in text overlays

## Features

- **6 reel styles** — Travel, Vlog, Tutorial, Montage, Aesthetic, Promo
- **2 editing approaches** — Hook-first (best shot opens) or Story (chronological build)
- **4 audio modes** — Voice + Music, Music only, Voice only (smart mute), Original audio
- **Beat-synced cuts** — Clip transitions align with music beats
- **Smart audio** — Keeps speech, mutes ambient noise, mixes background music
- **Text overlays** — AI-generated captions in 3 styles (title, caption, highlight)
- **BPM mode** — Skip music selection and sync to a custom BPM (for adding your own song later on Instagram)
- **Built-in music catalog** — 14 tracks across 7 genres (pop, lofi, cinematic, trap, romantic, EDM, acoustic)

## Prerequisites

- **Python 3.10+**
- **FFmpeg** installed and available in PATH
- **Google Gemini API key**

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd AiReelMaker

# Create virtual environment
cd server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Usage

```bash
cd server

# Pass a folder of videos
python cli.py --videos test-videos/ --prompt "Promote my eyelashes course"

# Pass individual video files
python cli.py --videos video1.mp4 video2.mp4 --prompt "Summer vibes montage"
```

The CLI will walk you through interactive menus to select:
- Reel style (Travel, Vlog, Tutorial, etc.)
- Editing approach (Hook-first or Story)
- Reel length (10, 15, 20, or 30 seconds)
- Captions (Yes / No)
- Audio mode (Voice + Music, Music only, etc.)
- BPM (if using Voice only or Original audio mode)

Output reels are saved to `server/output/`.

## Project Structure

```
server/
  cli.py               # CLI entry point with interactive menus
  pipeline.py           # Main pipeline orchestrator (5-step flow)
  gemini_service.py     # Gemini API — video analysis + edit planning
  ffmpeg_service.py     # FFmpeg — video probing + reel assembly
  beat_detection.py     # Beat detection with librosa
  voiceover_service.py  # Voiceover generation (Gemini script + gTTS)
  models.py             # Pydantic data models
  config.py             # Centralized configuration
  requirements.txt      # Python dependencies
  music/                # Built-in music catalog (14 tracks + catalog.json)
  output/               # Generated reels
```

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `OUTPUT_WIDTH` | 1080 | Output video width (portrait) |
| `OUTPUT_HEIGHT` | 1920 | Output video height (portrait) |
| `MUSIC_VOLUME` | 0.15 | Background music volume level |
| `MIN_BEAT_INTERVAL` | 1.5s | Minimum seconds between cuts |
| `GEMINI_MODEL` | gemini-2.5-flash | Gemini model for AI analysis |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Override the default Gemini model |
