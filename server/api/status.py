"""GET /api/status/{job_id} — SSE stream for long-running operations."""

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from session_store import jobs

router = APIRouter()


@router.get("/status/{job_id}")
async def status_stream(job_id: str):
    """SSE endpoint streaming log lines and completion events."""
    job = jobs.get(job_id)
    if not job:
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
                result = job.get("result")
                yield {
                    "event": "done",
                    "data": json.dumps(result) if result else "",
                }
                break
            elif job["status"] == "error":
                yield {
                    "event": "error",
                    "data": job.get("error", "Unknown error"),
                }
                break

            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())
