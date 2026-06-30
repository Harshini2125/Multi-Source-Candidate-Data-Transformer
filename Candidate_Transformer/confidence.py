"""Confidence scoring — principled and explainable, not a magic number.

Each source has a base reliability weight. When several sources independently
assert the same value, our confidence in it should rise. We combine agreeing
sources with a *noisy-OR*:

    confidence = 1 - Π (1 - weight_i)   over the sources that agree

So two medium sources beat one, but no single value ever reaches 1.0 (we cap at
0.99 — nothing is ever certain). The same rule scores both ordinary fields and
individual skills, and the overall profile confidence is the mean of its
populated core fields.
"""

from __future__ import annotations

from typing import Iterable

# Source reliability. Structured ATS/CSV rank above scraped/parsed sources.
# This ordering is also the deterministic conflict-resolution priority.
SOURCE_WEIGHTS: dict[str, float] = {
    "ats_json": 0.90,
    "recruiter_csv": 0.85,
    "resume": 0.70,
    "github": 0.60,
}

# Priority order for picking a winner on conflicting scalar values.
SOURCE_PRIORITY: list[str] = ["ats_json", "recruiter_csv", "resume", "github"]

_DEFAULT_WEIGHT = 0.5
_CAP = 0.99

# Core fields averaged into overall_confidence.
_CORE_FIELDS = ["full_name", "emails", "phones", "location", "skills", "experience"]


def source_weight(source: str) -> float:
    return SOURCE_WEIGHTS.get(source, _DEFAULT_WEIGHT)


def priority_rank(source: str) -> int:
    """Lower is better. Unknown sources sort last but deterministically."""
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


def combine(sources: Iterable[str]) -> float:
    """Noisy-OR over the weights of the given (agreeing) sources."""
    product = 1.0
    seen = False
    for src in sources:
        seen = True
        product *= 1.0 - source_weight(src)
    if not seen:
        return 0.0
    return round(min(1.0 - product, _CAP), 4)


def overall(field_confidences: dict[str, float]) -> float:
    populated = [field_confidences[f] for f in _CORE_FIELDS if field_confidences.get(f)]
    if not populated:
        return 0.0
    return round(sum(populated) / len(populated), 4)
