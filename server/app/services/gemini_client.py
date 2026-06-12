"""Gemini API client: model rotation, transient-error retry, and scoring.

Uses the supported ``google-genai`` SDK. The SDK is imported lazily so the
rest of the app (and the test suite) does not depend on it being installed.
Scoring-domain helpers (prompt building, PII stripping, response parsing) live
in :mod:`gemini_scoring` to keep this module focused on I/O and retry logic.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.schemas.job import ScoreResult
from app.services.gemini_scoring import (
    SYSTEM_INSTRUCTION,
    build_scoring_prompt,
    parse_score_response,
    strip_pii,
)

logger = logging.getLogger(__name__)

# ── Stateful rotation state (process-level singletons) ───────────────────────
# Safe for single-worker deployments — FastAPI workers share one process.
current_model_index: int = 0
last_rotated_at: datetime | None = None


class GeminiUnavailableError(Exception):
    """Raised when every model in the rotation list is exhausted."""


class GeminiClient:
    """Thin async wrapper over the Gemini ``generate_content`` API."""

    def __init__(self, api_key: str, models: list[str], timeout_seconds: float) -> None:
        """Initialise the client.

        Args:
            api_key: Gemini API key (empty when unconfigured).
            models: Ordered list of model IDs to rotate through on errors.
            timeout_seconds: Per-request timeout.
        """
        self._api_key = api_key
        self._models = models
        self._timeout = timeout_seconds

    @property
    def is_configured(self) -> bool:
        """Whether an API key and at least one model are present."""
        return bool(self._api_key) and bool(self._models)

    def _generate(self, prompt: str, model: str) -> str:
        """Synchronously call Gemini with a specific model (run in a worker thread).

        Uses the supported ``google-genai`` SDK (the older ``google-generativeai``
        package is deprecated and no longer maintained).
        """
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=int(self._timeout * 1000)),
            ),
        )
        return response.text or ""

    def _generate_with_fallback(self, prompt: str) -> str:
        """Try each model with exponential back-off for transient errors.

        Error classification:

        * **Permanent** — non-429 ``ClientError`` (e.g. 400, 403): re-raised
          immediately, no retries, no rotation.
        * **Quota exhaustion** — ``429`` whose message contains ``"quota"`` or
          ``"exhausted"``: rotates to the next model immediately, bypassing the
          back-off loop to preserve retry budget.
        * **Transient** — soft ``429`` or *any* ``ServerError`` (5xx): retries
          the same model up to 3 times with exponential back-off (2 s → 4 s),
          then rotates.

        Mutates the module-level ``current_model_index`` and ``last_rotated_at``
        singletons. Raises :exc:`GeminiUnavailableError` when every model has
        been exhausted.
        """
        from google.genai.errors import ClientError, ServerError

        global current_model_index, last_rotated_at

        # Reset to primary after 1-hour cooldown from the last rotation.
        if last_rotated_at is not None:
            if datetime.now(timezone.utc) - last_rotated_at >= timedelta(hours=1):
                current_model_index = 0
                last_rotated_at = None
                logger.info("Gemini model index reset to primary.")

        _MAX_RETRIES = 3
        _BURST_BACKOFF = (2, 4)  # seconds to wait after 1st and 2nd transient failures

        num_models = len(self._models)
        for _ in range(num_models):
            model = self._models[current_model_index]
            should_rotate = False

            for attempt in range(_MAX_RETRIES):
                _transient = False
                _err_label = ""
                try:
                    return self._generate(prompt, model)
                except ClientError as exc:
                    if exc.code != 429:
                        raise  # Permanent 4xx — propagate immediately.
                    error_lower = str(exc).lower()
                    if "quota" in error_lower or "exhausted" in error_lower:
                        # Hard quota exhaustion: skip back-off, rotate now.
                        logger.warning("Gemini quota exhausted on %s — rotating.", model)
                        should_rotate = True
                    else:
                        _transient = True
                        _err_label = "soft 429"
                except ServerError as exc:
                    # All 5xx codes are treated as transient — no code inspection.
                    _transient = True
                    _err_label = f"HTTP {exc.code}"

                if should_rotate:
                    break

                if _transient:
                    if attempt < len(_BURST_BACKOFF):
                        delay = _BURST_BACKOFF[attempt]
                        logger.warning(
                            "Gemini %s on %s (attempt %d/%d) — retrying in %ds.",
                            _err_label, model, attempt + 1, _MAX_RETRIES, delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            "Gemini %s on %s persists after %d attempts — rotating.",
                            _err_label, model, _MAX_RETRIES,
                        )
                        should_rotate = True
                        break

            if should_rotate:
                next_index = (current_model_index + 1) % num_models
                logger.warning(
                    "Rotating Gemini model: %s → %s.", model, self._models[next_index]
                )
                current_model_index = next_index
                last_rotated_at = datetime.now(timezone.utc)

        raise GeminiUnavailableError(
            f"All {num_models} Gemini model(s) are unavailable. Retry later."
        )

    async def score(
        self,
        job_title: str | None,
        job_description: str | None,
        requirements: dict[str, Any] | None,
        resume_structured: dict[str, Any] | None,
    ) -> ScoreResult | None:
        """Score a job against a resume, returning ``None`` on any non-rate-limit failure.

        PII is stripped before the prompt is constructed. The synchronous SDK
        call is offloaded with ``asyncio.to_thread`` to keep the endpoint async.
        Raises :exc:`GeminiUnavailableError` when all models are exhausted.

        Args:
            job_title: The job title.
            job_description: The job description.
            requirements: The requirements JSONB.
            resume_structured: The active resume's structured data (with PII).

        Returns:
            A validated :class:`ScoreResult`, or ``None`` on API/parse failure.
        """
        clean_resume = strip_pii(resume_structured)
        prompt = build_scoring_prompt(
            job_title, job_description, requirements, clean_resume
        )
        try:
            text = await asyncio.to_thread(self._generate_with_fallback, prompt)
        except GeminiUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalise any SDK/network error.
            logger.error("Gemini scoring call failed", extra={"error": str(exc)})
            return None

        result = parse_score_response(text)
        if result is None:
            logger.warning("Gemini returned an unparseable score response")
        return result


def get_gemini_client() -> GeminiClient:
    """FastAPI dependency factory for a :class:`GeminiClient`.

    Aborts with a clear :exc:`ValueError` when ``GEMINI_MODELS`` is absent or
    empty — the server cannot score jobs without at least one model configured.
    """
    cfg = get_settings()
    models = cfg.gemini_models_list
    if not models:
        raise ValueError(
            "GEMINI_MODELS is not configured. "
            "Add a comma-separated list of model IDs to your .env file."
        )
    return GeminiClient(
        api_key=cfg.gemini_api_key,
        models=models,
        timeout_seconds=cfg.gemini_timeout_seconds,
    )
