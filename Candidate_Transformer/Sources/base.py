"""Shared adapter protocol and helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from ..models import SourceRecord

log = logging.getLogger("candidate_transformer.sources")


class SourceAdapter(Protocol):
    """Every adapter implements ``name`` and ``extract``.

    ``extract`` is given the inputs directory, discovers the files it owns, and
    returns one ``SourceRecord`` per person. It must not raise: on a
    missing/empty/malformed file it logs and returns ``[]``.
    """

    name: str

    def extract(self, inputs_dir: Path) -> list[SourceRecord]:
        ...


def safe_read_text(path: Path) -> str | None:
    """Read text defensively; return ``None`` on any error."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        log.warning("could not read %s: %s", path, exc)
        return None
