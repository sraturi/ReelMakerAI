"""GET /api/status/{job_id} — SSE stream for long-running operations."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

# Registries of job stores from other modules
# Each module registers its job store here so we can find any job_id
job_stores: dict[str, dict] = {}


def _find_job(job_id: str) -> dict | None:
    """Search all registered job stores for a job."""
    # Check each registered store
    for store_dict in job_stores.values():
        if job_id in store_dict:
            return store_dict[job_id]

    # Also check the legacy app.py jobs and individual module stores
    from api.analyze import analyze_jobs
    from api.plan import plan_jobs
    from api.render import render_jobs

    for store_dict in [analyze_jobs, plan_jobs, render_jobs]:
        if job_id in store_dict:
            return store_dict[job_id]

    return None


@router.get("/status/{job_id}")
async def status_stream(job_id: str):
    """SSE endpoint streaming log lines and completion events."""
    job = _find_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    async def event_generator():
        last_idx = 0
        while True:
            job = _find_job(job_id)
            if not job:
                break

            logs = job["logs"]
            while last_idx < len(logs):
                yield {"event": "log", "data": logs[last_idx]}
                last_idx += 1

            if job["status"] == "done":
                import json
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
