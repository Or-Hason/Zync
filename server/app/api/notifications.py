"""Server-Sent Events endpoint for real-time job-match notifications.

The frontend connects once on app mount and keeps the connection open. When
the background scraper scores a job above the user's threshold, it calls
:func:`~app.services.notification_bus.emit_job_match`, which pushes the event
to every connected client via their per-client :class:`asyncio.Queue`.

No authentication beyond the existing app trust model is required — the app
runs locally and all endpoints share the same trust boundary.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services import notification_bus

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get(
    "/stream",
    summary="SSE stream for real-time job-match notifications",
)
async def notification_stream() -> StreamingResponse:
    """Open a Server-Sent Events stream for job-match notifications.

    Each connected client receives ``job_match`` events immediately after the
    background scraper scores a job that meets or exceeds the user's configured
    threshold. The stream sends comment-line pings every 30 s to prevent proxy
    and idle-connection timeouts.

    The ``EventSource`` browser API reconnects automatically on drop, so no
    manual retry logic is needed on the client.

    Returns:
        A long-lived ``text/event-stream`` response. The connection stays open
        until the client disconnects or the server shuts down.
    """
    q = notification_bus.add_client()
    logger.info("SSE client connected to notification stream.")

    return StreamingResponse(
        notification_bus.stream_events(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering for SSE
        },
    )
