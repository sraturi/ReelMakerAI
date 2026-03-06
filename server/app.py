"""FastAPI web frontend for Reelvo."""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import OUTPUT_DIR, UPLOAD_DIR, THUMBNAIL_DIR

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
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

STATIC_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# --- Mount API routes ---
from api import api_router, ws_status_router
app.include_router(api_router)
app.include_router(ws_status_router)  # WebSocket at /ws/status/{job_id}

# --- Background cleanup ---
from session_store import store as session_store, project_store

@app.on_event("startup")
async def start_cleanup_loop():
    async def cleanup_loop():
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            session_store.cleanup_expired()
            # Clean output files older than 2 hours, but protect project files
            protected = project_store.protected_files()
            cutoff = time.time() - 7200
            for f in OUTPUT_DIR.iterdir():
                if f.is_file() and f.name not in protected and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
    asyncio.create_task(cleanup_loop())

# --- Static file mounts ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Serve React frontend (production build)
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_root():
    """Serve React app index.html if built, else show instructions."""
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse(
        '<h2>Frontend not built yet</h2>'
        '<p>Run <code>cd frontend && npm run build</code> or use '
        '<code>npm run dev</code> on port 3000/5173.</p>'
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
