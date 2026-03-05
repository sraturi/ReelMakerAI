# AiReelMaker

AI-powered tool that automatically creates beat-synced Instagram Reels and TikTok videos from raw footage. Upload your videos, let Google Gemini analyze them, set your creative direction with an AI-enhanced prompt, and get a fully editable reel with text overlays and smart audio mixing.

## How It Works

1. **Upload** — Drop in your video files
2. **Analyze** — Gemini watches every video, cataloging scenes, speech, action, and peak moments
3. **Prompt & Settings** — See what AI found, write your creative direction (with AI prompt enhancement that references your actual footage), and choose style/duration/transitions
4. **Plan** — Gemini builds an editing plan — clip selection, ordering, text overlays — all synced to beats
5. **Edit** — Drag-and-drop editor to reorder clips, adjust timings, edit captions, add/remove clips
6. **Render** — FFmpeg assembles the final reel with transitions, Ken Burns effects, and text overlays
7. **Preview** — Watch and download your finished reel

## Features

### AI-Powered
- **2-pass AI pipeline** — Pass 1 analyzes video content, Pass 2 generates an editing plan informed by analysis
- **Smart prompt enhancement** — AI improves your prompt using actual scene descriptions and peak moments from your footage
- **AI clip suggestions** — Get AI-recommended clips to add to your reel
- **AI caption rewriting** — Generate alternative captions with different tones

### Editing
- **6 reel styles** — Montage, Travel, Vlog, Tutorial, Aesthetic, Promo
- **2 editing approaches** — Hook-first (best shot opens) or Story (chronological)
- **Drag-and-drop clip reordering** — Rearrange clips visually
- **Per-clip editing** — Adjust start/end times, transitions, Ken Burns effects
- **Text overlays** — AI-generated captions in multiple styles (title, caption, highlight)
- **Re-plan on the fly** — Give new direction and regenerate the plan without re-analyzing

### Video & Audio
- **Beat-synced cuts** — Clip transitions align with BPM so you can add music later on Instagram/TikTok
- **2 audio modes** — Voice only (smart mute of ambient noise) or Original audio
- **Ken Burns effects** — Zoom in/out and pan for cinematic motion on static shots
- **5 transition styles** — Auto, Smooth, Dynamic, Dramatic, Hard Cut
- **Portrait output** — 1080x1920 optimized for Reels/TikTok

### Models
- **Gemini 2.5 Flash** — Fast and cheap, good for most reels
- **Gemini 2.5 Pro** — Higher quality analysis and planning

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **FFmpeg** installed and available in PATH
- **Google Gemini API key** — get one at [Google AI Studio](https://aistudio.google.com/apikey)

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd AiReelMaker

# --- Backend ---
cd server
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install fastapi uvicorn sse-starlette python-dotenv google-genai pydantic jinja2 python-multipart

# Configure API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# --- Frontend ---
cd ../frontend
npm install
npm run build
```

## Running

### Production (recommended)

Build the frontend once, then just run the backend — it serves everything:

```bash
# Build frontend (only needed once, or after frontend changes)
cd frontend
npm run build

# Run the server
cd ../server
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

### Development (hot reload)

Run backend and frontend separately for live reloading:

```bash
# Terminal 1 — Backend
cd server
source venv/bin/activate
uvicorn app:app --reload --port 8000

# Terminal 2 — Frontend (proxies /api to backend)
cd frontend
npm run dev
```

Open http://localhost:3000

## CLI Usage

You can also use the CLI directly without the web UI:

```bash
cd server
source venv/bin/activate

# Pass a folder of videos
python cli.py --videos test-videos/ --prompt "Promote my eyelashes course"

# Pass individual video files
python cli.py --videos video1.mp4 video2.mp4 --prompt "Summer vibes montage"
```

Output reels are saved to `server/output/`.

## Project Structure

```
server/
  app.py                # FastAPI main — serves React build + legacy UI, CORS
  config.py             # Centralized configuration
  models.py             # Pydantic data models
  session_store.py      # In-memory session manager (1hr TTL)
  gemini_service.py     # Gemini API — video analysis + edit planning
  ffmpeg_service.py     # FFmpeg — video probing + reel assembly
  thumbnail_service.py  # FFmpeg thumbnail extraction + caching
  beat_detection.py     # Beat generation from BPM
  voiceover_service.py  # Voiceover generation (Gemini script + gTTS)
  pipeline.py           # Monolithic pipeline (used by CLI)
  cli.py                # CLI entry point with interactive menus
  api/
    upload.py           # POST /api/upload
    analyze.py          # POST /api/analyze (Pass 1)
    plan.py             # POST /api/plan (Pass 2)
    enhance.py          # POST /api/enhance-prompt
    render.py           # POST /api/render
    suggest.py          # POST /api/suggest-clip
    caption.py          # POST /api/rewrite-caption
    session.py          # GET /api/session/:id
    status.py           # GET /api/status/:job_id (SSE)
    thumbnail.py        # GET /api/thumbnail/:session/:index/:time

frontend/
  src/
    App.tsx             # Main app — step-based routing
    api/                # API client + SSE helper
    store/              # Zustand stores (session, editor, UI)
    components/
      upload/           # Upload dropzone + file list
      prompt/           # Prompt & settings page
      settings/         # Settings panel (style, duration, etc.)
      editor/           # Clip cards, drag-and-drop, overlay editor
      render/           # Render progress + video preview
      layout/           # App shell, step indicator
      shared/           # Loading overlay
```

## Configuration

Key settings in `server/config.py`:

| Setting | Default | Description |
|---|---|---|
| `OUTPUT_WIDTH` | 1080 | Output video width (portrait) |
| `OUTPUT_HEIGHT` | 1920 | Output video height (portrait) |
| `MIN_BEAT_INTERVAL` | 1.5s | Minimum seconds between cuts |
| `GEMINI_MODEL` | gemini-2.5-flash | Default Gemini model |
| `TRANSITION_DURATION` | 0.3s | Crossfade duration between clips |
| `KENBURNS_SCALE` | 1.2 | Overscan factor for zoom/pan |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Override default Gemini model |
