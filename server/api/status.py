"""WebSocket /ws/status/{job_id} — bidirectional job progress + cancellation.

Replaces the old SSE endpoint for the interactive editor pipeline.
Server streams: log, done, error, cancelled events.
Client can send: {"action": "cancel"} to abort a running job.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from session_store import jobs

router = APIRouter()
log = logging.getLogger(__name__)


@router.websocket("/ws/status/{job_id}")
async def status_ws(ws: WebSocket, job_id: str):
    """WebSocket endpoint streaming job progress and accepting cancel commands."""
    job = jobs.get(job_id)
    if not job:
        await ws.close(code=4004, reason="Job not found")
        return

    await ws.accept()

    last_idx = 0

    async def _listen_for_cancel():
        """Listen for incoming cancel messages from the client."""
        try:
            while True:
                data = await ws.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("action") == "cancel":
                        jobs.cancel(job_id)
                except (json.JSONDecodeError, AttributeError):
                    pass
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    listen_task = asyncio.create_task(_listen_for_cancel())

    try:
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            # Flush new log lines
            logs = job["logs"]
            while last_idx < len(logs):
                await ws.send_json({"event": "log", "data": logs[last_idx]})
                last_idx += 1

            status = job["status"]

            if status == "done":
                result = job.get("result")
                await ws.send_json({
                    "event": "done",
                    "data": result if result else {},
                })
                break
            elif status == "error":
                await ws.send_json({
                    "event": "error",
                    "data": job.get("error", "Unknown error"),
                })
                break
            elif status == "cancelled":
                await ws.send_json({
                    "event": "cancelled",
                    "data": "Job cancelled by user",
                })
                break

            await asyncio.sleep(0.3)

    except WebSocketDisconnect:
        log.debug("Client disconnected from job %s", job_id)
    except Exception as e:
        log.error("WebSocket error for job %s: %s", job_id, e)
    finally:
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        try:
            await ws.close()
        except Exception:
            pass
