"""Generic JSON-skeleton generation from Pydantic models for AI prompts.

A skeleton mirrors a model's field structure with placeholder values so prompts
never hardcode the key set twice — the Pydantic model stays the single source of
truth. Scalars become ``"string"``, collections a single-element list, and
nested models a recursive dict.
"""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

# Placeholder emitted for every scalar field in a generated skeleton. Exported so
# the parser can recognise and discard values where a model echoed the
# placeholder back verbatim instead of extracting a real value.
PLACEHOLDER_SCALAR = "string"


def annotation_skeleton(annotation: Any) -> Any:
    """Build a JSON skeleton describing a single field annotation.

    Args:
        annotation: A type annotation from a Pydantic model field.

    Returns:
        A JSON-serialisable placeholder: ``"string"`` for scalars, a nested
        dict for sub-models, or a single-element list for collections.
    """
    origin = get_origin(annotation)

    # Optional[...] / Union[...] -> use the first non-None member.
    if origin is Union or origin is types.UnionType:
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        return annotation_skeleton(members[0]) if members else "string"

    if origin in (list, set, tuple):
        inner_args = get_args(annotation)
        inner = annotation_skeleton(inner_args[0]) if inner_args else PLACEHOLDER_SCALAR
        return [inner]

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {
            name: annotation_skeleton(field.annotation)
            for name, field in annotation.model_fields.items()
        }

    return PLACEHOLDER_SCALAR


def build_model_skeleton(model: type[BaseModel]) -> dict[str, Any]:
    """Return a JSON skeleton of a Pydantic model for embedding in an AI prompt.

    Args:
        model: The Pydantic model class to describe.

    Returns:
        A dict mirroring the model's schema with placeholder values, generated
        from the model so keys are never hardcoded twice.
    """
    skeleton = annotation_skeleton(model)
    return skeleton if isinstance(skeleton, dict) else {}
