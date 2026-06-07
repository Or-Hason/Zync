"""Best-effort recovery of a JSON object from messy LLM output.

Both the Ollama and Gemini clients ask their models for a bare JSON object but
must tolerate stray markdown fences or surrounding prose. This never raises: an
unparseable response yields an empty dict so callers fall back to defaults.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_json_object(content: str) -> dict[str, Any]:
    """Parse a JSON object from raw model output.

    Tolerates stray markdown fences or surrounding prose by isolating the
    outermost ``{...}`` span.

    Args:
        content: Raw text returned by the model.

    Returns:
        The parsed JSON object, or ``{}`` if none could be recovered.
    """
    if not content:
        return {}

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        parsed = json.loads(content[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        logger.warning("Model response was not valid JSON; using empty fallback")
        return {}
