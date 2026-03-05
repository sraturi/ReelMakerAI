"""API route modules for the interactive editor."""

from fastapi import APIRouter

from .upload import router as upload_router
from .analyze import router as analyze_router
from .plan import router as plan_router
from .suggest import router as suggest_router
from .caption import router as caption_router
from .enhance import router as enhance_router
from .render import router as render_router
from .thumbnail import router as thumbnail_router
from .video import router as video_router
from .status import router as ws_status_router
from .session import router as session_router

api_router = APIRouter(prefix="/api")
api_router.include_router(upload_router)
api_router.include_router(analyze_router)
api_router.include_router(plan_router)
api_router.include_router(suggest_router)
api_router.include_router(caption_router)
api_router.include_router(enhance_router)
api_router.include_router(render_router)
api_router.include_router(thumbnail_router)
api_router.include_router(video_router)
api_router.include_router(session_router)

# WebSocket status route mounted separately (no /api prefix — lives at /ws/status/{job_id})
__all__ = ["api_router", "ws_status_router"]
