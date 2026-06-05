"""Shared TF-IDF cosine similarity over short text corpora.

Both duplicate detection and score caching reduce a job to a
single ``job_title + " " + job_description`` string and find the most similar
prior job. This module owns that comparison so the concatenation rule and the
vectorisation live in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class SimilarityMatch:
    """The best match found within a corpus for a candidate string."""

    index: int
    score: float


def comparison_string(title: str | None, description: str | None) -> str:
    """Concatenate title and description into one comparison string.

    Args:
        title: Job title (may be ``None``).
        description: Job description (may be ``None``).

    Returns:
        The trimmed ``"title description"`` string.
    """
    return f"{(title or '').strip()} {(description or '').strip()}".strip()


def best_match(candidate: str, corpus: list[str]) -> SimilarityMatch | None:
    """Return the corpus entry most similar to ``candidate``.

    Args:
        candidate: The query string.
        corpus: Existing strings to compare against.

    Returns:
        The best :class:`SimilarityMatch`, or ``None`` when the candidate or
        corpus is empty or the TF-IDF vocabulary is empty (e.g. only
        stop-words).
    """
    if not candidate or not corpus:
        return None

    documents = [candidate] + corpus
    try:
        matrix = TfidfVectorizer().fit_transform(documents)
    except ValueError:
        return None

    similarities = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    index = int(similarities.argmax())
    return SimilarityMatch(index=index, score=float(similarities[index]))
