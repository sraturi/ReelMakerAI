"""FastAPI web frontend for Reelvo."""

import asyncio
import logging
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from config import OUTPUT_DIR, UPLOAD_DIR, THUMBNAIL_DIR, VIDEO_EXTENSIONS

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Reelvo")

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

STATIC_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- Mount API routes ---
from api import api_router
app.include_router(api_router)

# --- Background cleanup ---
from session_store import store as session_store

@app.on_event("startup")
async def start_cleanup_loop():
    async def cleanup_loop():
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            session_store.cleanup_expired()
            # Clean output files older than 2 hours
            cutoff = time.time() - 7200
            for f in OUTPUT_DIR.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
    asyncio.create_task(cleanup_loop())

# --- Static file mounts ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# In-memory job store (legacy one-shot pipeline)
# ---------------------------------------------------------------------------

jobs: dict[str, dict] = {}


class JobLogHandler(logging.Handler):
    """Captures log records into a job's log list."""

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def emit(self, record: logging.LogRecord):
        if self.job_id in jobs:
            jobs[self.job_id]["logs"].append(self.format(record))


# ---------------------------------------------------------------------------
# Legacy routes (original one-shot pipeline)
# ---------------------------------------------------------------------------

@app.get("/legacy", response_class=HTMLResponse)
async def legacy_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate(
    request: Request,
    videos: list[UploadFile] = File(...),
    prompt: str = Form(...),
    reel_style: str = Form("montage"),
    reel_approach: str = Form("hook"),
    duration: int = Form(30),
    captions: str = Form("yes"),
    audio_mode: str = Form("voice"),
    bpm: int = Form(120),
    transition_style: str = Form("auto"),
    gemini_model: str = Form("gemini-2.5-flash"),
):
    """Accept form + uploaded videos, start pipeline in background, return job_id."""
    tmp_dir = tempfile.mkdtemp(prefix="reelvo_")
    video_paths: list[str] = []

    for upload in videos:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            continue
        dest = Path(tmp_dir) / upload.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        video_paths.append(str(dest))

    if not video_paths:
        return JSONResponse(
            {"error": "No valid video files uploaded."},
            status_code=400,
        )

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "running",
        "logs": [],
        "output": None,
        "error": None,
    }

    asyncio.get_event_loop().create_task(
        _run_pipeline_bg(
            job_id,
            video_paths,
            prompt,
            target_duration=duration,
            captions=captions == "yes",
            audio_mode=audio_mode,
            bpm=bpm,
            reel_style=reel_style,
            reel_approach=reel_approach,
            transition_style=transition_style,
            gemini_model=gemini_model,
            tmp_dir=tmp_dir,
        )
    )

    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
async def status_stream(job_id: str):
    """SSE endpoint streaming log lines in real-time."""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    async def event_generator():
        last_idx = 0
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            logs = job["logs"]
            while last_idx < len(logs):
                yield {"event": "log", "data": logs[last_idx]}
                last_idx += 1

            if job["status"] == "done":
                yield {
                    "event": "done",
                    "data": job["output"] or "",
                }
                break
            elif job["status"] == "error":
                yield {
                    "event": "error",
                    "data": job["error"] or "Unknown error",
                }
                break

            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@app.get("/result/{job_id}")
async def result(job_id: str):
    """Return JSON with output video path (or error)."""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    job = jobs[job_id]
    if job["status"] == "running":
        return JSONResponse({"status": "running"})
    elif job["status"] == "error":
        return JSONResponse({"status": "error", "error": job["error"]}, status_code=500)
    else:
        return JSONResponse({"status": "done", "output": job["output"]})


# ---------------------------------------------------------------------------
# Background pipeline runner (legacy)
# ---------------------------------------------------------------------------

async def _run_pipeline_bg(
    job_id: str,
    video_paths: list[str],
    prompt: str,
    *,
    target_duration: int,
    captions: bool,
    audio_mode: str,
    bpm: int,
    reel_style: str,
    reel_approach: str,
    transition_style: str,
    gemini_model: str,
    tmp_dir: str,
):
    """Run the blocking pipeline in a thread, capturing logs."""
    handler = JobLogHandler(job_id)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    try:
        import config
        config.GEMINI_MODEL = gemini_model

        from pipeline import run_pipeline

        output_path = await asyncio.to_thread(
            run_pipeline,
            video_paths,
            prompt,
            target_duration=target_duration,
            captions=captions,
            audio_mode=audio_mode,
            bpm=bpm,
            reel_style=reel_style,
            reel_approach=reel_approach,
            transition_style=transition_style,
        )

        output_file = Path(output_path).name
        jobs[job_id]["status"] = "done"
        jobs[job_id]["output"] = output_file

    except Exception as e:
        logging.getLogger(__name__).error("Pipeline failed: %s", e, exc_info=True)
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

    finally:
        root_logger.removeHandler(handler)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Serve React frontend (production build) or fallback to legacy
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_root():
    """Serve React app index.html if built, else redirect to legacy."""
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse(
        '<h2>Frontend not built yet</h2>'
        '<p>Run <code>cd frontend && npm run build</code> or use '
        '<code>npm run dev</code> on port 3000/5173.</p>'
        '<p><a href="/legacy">Use legacy UI</a></p>'
    )


# Serve React static assets
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")


# Catch-all for React client-side routing (must be last)
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """Serve React app for any unmatched route (client-side routing)."""
    # Don't catch API or static routes
    if full_path.startswith(("api/", "static/", "assets/")):
        return JSONResponse({"error": "Not found"}, status_code=404)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"error": "Not found"}, status_code=404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
