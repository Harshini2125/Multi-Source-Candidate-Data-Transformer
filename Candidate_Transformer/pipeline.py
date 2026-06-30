"""Pipeline orchestration: load -> extract -> normalize -> merge -> score ->
project -> validate.

``run`` is the single entry point. It is deterministic (same inputs -> same
output) and robust (a failing adapter is logged and skipped, never fatal).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import DEFAULT_CONFIG, OutputConfig
from .merge import merge_group, resolve
from .models import CanonicalProfile, SourceRecord
from .projection import project
from .sources import ALL_ADAPTERS
from .validation import validate_or_raise

log = logging.getLogger("candidate_transformer.pipeline")


def build_canonical_profiles(inputs_dir: Path) -> list[CanonicalProfile]:
    """Run load -> extract -> merge and return canonical profiles."""
    records: list[SourceRecord] = []
    for adapter in ALL_ADAPTERS:
        try:
            extracted = adapter.extract(inputs_dir)
            log.info("%s: %d record(s)", adapter.name, len(extracted))
            records.extend(extracted)
        except Exception as exc:  # robustness: one bad source never kills the run
            log.warning("adapter %s failed, skipping: %s", adapter.name, exc)

    profiles = [merge_group(group) for group in resolve(records)]
    # Deterministic ordering of the final list.
    profiles.sort(key=lambda p: p.candidate_id)
    return profiles


def run(
    inputs_dir: Path,
    config: Optional[OutputConfig] = None,
    validate: bool = True,
) -> list[dict]:
    """Full pipeline. Returns a list of projected, schema-valid profile dicts."""
    config = config or DEFAULT_CONFIG
    profiles = build_canonical_profiles(inputs_dir)

    results: list[dict] = []
    for profile in profiles:
        # model_dump gives the plain nested dict the projection layer reads.
        canonical = profile.model_dump()
        projected = project(canonical, config)
        if validate:
            validate_or_raise(projected, config)
        results.append(projected)
    return results
