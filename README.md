# Reelvo

AI-powered tool that creates beat-synced Instagram Reels and TikTok videos from raw footage. Upload your videos, let Gemini analyze them, set your creative direction, and get a fully editable reel with transitions, effects, and text overlays.

## How It Works

1. **Upload** — Drop in your video files
2. **Analyze** — Gemini watches every video, cataloging scenes, speech, action, and peak moments
3. **Prompt & Settings** — Write your creative direction (with AI enhancement), choose style/duration/transitions
4. **Plan** — Gemini builds an editing plan — clip selection, ordering, text overlays — synced to beats
5. **Edit** — Drag-and-drop editor to reorder clips, adjust timings, edit captions, swap clips
6. **Render** — FFmpeg assembles the final reel with transitions, Ken Burns effects, and text overlays
7. **Preview** — Watch and download your finished reel

## Features

### AI
- **2-pass pipeline** — Pass 1 analyzes scenes (with video), Pass 2 plans edits (text-only, fast re-plans)
- **Prompt enhancement** — AI improves your prompt using actual scene descriptions from your footage
- **Clip suggestions** — AI recommends alternative clips for any position
- **Caption rewriting** — Generate alternative captions with different tones
- **Gemini 2.5 Flash or Pro** — Choose per step

### Editing
- **6 reel styles** — Montage, Travel, Vlog, Tutorial, Aesthetic, Promo
- **2 approaches** — Hook-first (best shot opens) or Story (chronological)
- **Drag-and-drop reordering** with undo/redo (30 levels)
- **Per-clip controls** — Trim, transitions, Ken Burns, audio mode
- **Composite layouts** — Split screen (vertical/horizontal), picture-in-picture, 2x2 grid
- **Text overlays** — Title, caption, and highlight styles with timing control
- **Re-plan without re-analyzing** — Give new direction, keep cached analysis

### Video & Audio
- **Beat-synced cuts** — Transitions align with BPM
- **Audio modes** — Keep voice or mute per clip
- **Ken Burns effects** — Zoom in/out, pan left/right
- **5 transition styles** — Auto, Smooth, Dynamic, Dramatic, Hard Cut
- **1080x1920 portrait** output

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **FFmpeg** in PATH
- **Google Gemini API key** — [Google AI Studio](https://aistudio.google.com/apikey)

## Setup

```bash
# Backend
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Frontend
cd ../frontend
npm install
npm run build
```

## Running

### Production

```bash
cd frontend && npm run build
cd ../server
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

### Development

```bash
# Terminal 1 — Backend (hot reload)
cd server && source venv/bin/activate
uvicorn app:app --reload --port 8000

# Terminal 2 — Frontend (proxies /api to :8000)
cd frontend && npm run dev
```

Open http://localhost:3000

## Project Structure

```
server/
  app.py                # FastAPI main — serves React build, CORS
  config.py             # Centralized configuration
  models.py             # Pydantic data models
  session_store.py      # SQLite-backed session manager (1hr TTL)
  gemini_service.py     # Gemini API — scene analysis + edit planning
  ffmpeg_service.py     # FFmpeg — probing + reel assembly + composites
  thumbnail_service.py  # Thumbnail extraction + caching
  beat_detection.py     # Beat generation from BPM
  voiceover_service.py  # Voiceover generation (Gemini + gTTS)
  pipeline.py           # Monolithic pipeline (CLI)
  cli.py                # CLI entry point
  api/
    upload.py           # POST /api/upload
    analyze.py          # POST /api/analyze (Pass 1)
    plan.py             # POST /api/plan, /api/replan (Pass 2)
    enhance.py          # POST /api/enhance-prompt
    render.py           # POST /api/render
    suggest.py          # POST /api/suggest-clip
    caption.py          # POST /api/rewrite-caption
    session.py          # GET /api/session/:id, DELETE /api/sessions
    status.py           # GET /api/status/:job_id (SSE)
    thumbnail.py        # GET /api/thumbnail/:session/:index/:time
    video.py            # GET /api/video/:session/:index, /api/output/:file
  data/                 # SQLite sessions.db (auto-created, gitignored)

frontend/
  src/
    App.tsx             # Step-based routing
    api/                # apiFetch client, SSE helper, per-feature modules
    store/              # Zustand: session, editor (undo/redo), UI
    types/              # TypeScript interfaces
    components/
      upload/           # Dropzone + file list
      prompt/           # Prompt input + AI enhancement
      settings/         # Style, duration, BPM, transitions, layouts
      editor/           # Clip cards, detail panel, overlays, composites
      render/           # Progress + video preview
      layout/           # App shell, step indicator
      shared/           # Loading overlay, thumbnails, clip player
```

## Configuration

`server/config.py`:

| Setting | Default | Description |
|---|---|---|
| `OUTPUT_WIDTH` | 1080 | Portrait width |
| `OUTPUT_HEIGHT` | 1920 | Portrait height |
| `GEMINI_MODEL` | gemini-2.5-flash | Default Gemini model |
| `TRANSITION_DURATION` | 0.3s | Crossfade duration |
| `KENBURNS_SCALE` | 1.2 | Zoom/pan overscan |
| `MIN_BEAT_INTERVAL` | 1.5s | Min seconds between cuts |
| `SESSION_TTL` | 3600s | Session expiry (in session_store.py) |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Override default model |
