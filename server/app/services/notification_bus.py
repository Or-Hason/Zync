"""In-memory SSE notification bus.

Maintains a list of per-client asyncio queues. The background scraper calls
:func:`emit_job_match` to broadcast an event; each SSE client drains its own
queue. The bus is intentionally simple (no persistence, no durable queue) —
if the client is not connected at emission time, the event is dropped. This
matches the "real-time desktop notification" model: a missed ping when the app
is closed is acceptable.

Thread safety: all access is from the asyncio event loop, so a plain list
suffices without locks.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

_PING_INTERVAL_SECONDS = 30

# Module-level registry of connected SSE client queues.
_clients: list[asyncio.Queue[str | None]] = []


def add_client() -> asyncio.Queue[str | None]:
    """Register a new SSE client and return its dedicated queue.

    Returns:
        A fresh :class:`asyncio.Queue` that will receive formatted SSE data
        strings as events are emitted.
    """
    q: asyncio.Queue[str | None] = asyncio.Queue()
    _clients.append(q)
    logger.debug("SSE client connected. Active clients: %d", len(_clients))
    return q


def remove_client(q: asyncio.Queue[str | None]) -> None:
    """Deregister a client queue after its connection closes.

    Args:
        q: The queue previously returned by :func:`add_client`.
    """
    try:
        _clients.remove(q)
        logger.debug("SSE client disconnected. Active clients: %d", len(_clients))
    except ValueError:
        pass  # already removed — idempotent


def is_dnd_active(dnd_start: str | None, dnd_end: str | None) -> bool:
    """Return whether the current local time falls inside the DND window.

    Handles windows that span midnight (e.g. 23:00→07:00).  If either
    boundary is ``None`` the window is considered inactive.

    Args:
        dnd_start: DND window start in ``HH:MM`` format, or ``None``.
        dnd_end: DND window end in ``HH:MM`` format, or ``None``.

    Returns:
        ``True`` when the current local time is within the DND window.
    """
    if not dnd_start or not dnd_end:
        return False
    now_t = int(datetime.now().strftime("%H%M"))
    s = int(dnd_start.replace(":", ""))
    e = int(dnd_end.replace(":", ""))
    if s <= e:
        return s <= now_t < e
    # Midnight-spanning window (e.g. 23:00→07:00).
    return now_t >= s or now_t < e


async def emit_job_match(
    job_id: str,
    job_title: str,
    match_score: int,
    job_count: int = 1,
    *,
    silent: bool = False,
) -> None:
    """Push a ``job_match`` SSE event to every connected client.

    No-op when no clients are connected (event is silently dropped).

    Args:
        job_id: UUID string of the matched job.
        job_title: Title shown in the notification body.
        match_score: Computed match score (0–100).
        job_count: Total number of matching jobs found in this scan batch.
            Used by the frontend to decide between a detail-view link
            (exactly 1 job) and the general Explorer view.
        silent: When ``True``, instructs the frontend to create a native
            Windows notification that goes directly to the Action Center
            without popping up or making a sound (DND mode).
    """
    if not _clients:
        return
    payload = json.dumps(
        {
            "job_id": job_id,
            "job_title": job_title,
            "match_score": match_score,
            "job_count": job_count,
            "silent": silent,
        }
    )
    data = f"event: job_match\ndata: {payload}\n\n"
    for q in list(_clients):
        await q.put(data)
    logger.info(
        "Emitted job_match notification",
        extra={
            "job_id": job_id,
            "match_score": match_score,
            "job_count": job_count,
            "silent": silent,
            "clients": len(_clients),
        },
    )


async def stream_events(q: asyncio.Queue[str | None]) -> AsyncGenerator[str, None]:
    """Yield SSE data strings from *q*, sending keep-alive pings every 30 s.

    The generator handles its own cleanup via a ``try/finally`` block — the
    caller must ensure it is consumed inside a ``try`` so that ``remove_client``
    always runs on disconnect.

    Args:
        q: The client queue returned by :func:`add_client`.

    Yields:
        Formatted SSE strings (``event: …\\ndata: …\\n\\n`` or ``: ping\\n\\n``).
    """
    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=_PING_INTERVAL_SECONDS)
                yield data
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        remove_client(q)
