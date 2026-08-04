"""Job ingestion + scoring pipeline: scrape, filter, score, detect duplicates.

Pipeline order: extract -> classification gate -> duplicate detection ->
score cache (early return on hit) -> blacklist filter -> active-resume guard ->
Gemini score -> persist -> auto-reject -> advice.

PII / privacy rule (CLAUDE.md, DESIGN.md): logs reference only ``job_id`` and
``source_type`` — never raw job text, resume PII, or the Gemini API key.

Facade: the endpoints live in ``app/api/_jobs_scrape.py`` (``POST /scrape``),
``app/api/_jobs_query.py`` (list + skills autocomplete), and
``app/api/_jobs_detail.py`` (read/unread mutations + single-job lookups).
Assembled into one ``router`` here so ``app.api.jobs.router``
keeps exposing the exact same routes.

Inclusion order matters: sub-routers are merged in the same relative order
the routes were originally declared in, so fixed paths that could otherwise be
shadowed by a ``{job_id}`` path parameter (``/skills``, ``/read-all``) are
still registered before it.
"""

from fastapi import APIRouter

from app.api._jobs_detail import router as _detail_router
from app.api._jobs_query import router as _query_router
from app.api._jobs_scrape import router as _scrape_router

router = APIRouter()
router.include_router(_scrape_router)
router.include_router(_query_router)
router.include_router(_detail_router)

__all__ = ["router"]
