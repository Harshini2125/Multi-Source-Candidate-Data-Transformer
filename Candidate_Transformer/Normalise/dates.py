"""Date normalization.

Canonical date shape is ``YYYY-MM``. Partial inputs are handled honestly:

* a bare year (``"2021"``) yields ``"2021"`` — we keep what we know and do not
  invent a month;
* "present"/"current"/blank yields ``None`` (open-ended).

Uses ``dateutil`` when available for flexible parsing, with a regex fallback.
"""

from __future__ import annotations

import re
from typing import Optional

try:  # pragma: no cover
    from dateutil import parser as _dateparser

    _HAVE_DATEUTIL = True
except ImportError:  # pragma: no cover
    _HAVE_DATEUTIL = False

_PRESENT = {"present", "current", "now", "ongoing", ""}
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def to_year_month(raw: Optional[str]) -> Optional[str]:
    """Return ``YYYY-MM``, or ``YYYY`` for year-only input, or ``None``."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in _PRESENT:
        return None

    # Year only — keep the year, do not fabricate a month.
    if re.fullmatch(r"(19|20)\d{2}", text):
        return text

    # "YYYY-MM" / "YYYY/MM" already close to canonical.
    m = re.fullmatch(r"((?:19|20)\d{2})[-/](\d{1,2})", text)
    if m:
        year, month = m.group(1), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year}-{month:02d}"

    # "Jan 2020" / "January 2020"
    m = re.fullmatch(r"([a-z]+)\.?\s+((?:19|20)\d{2})", text)
    if m and m.group(1)[:3] in _MONTHS:
        return f"{m.group(2)}-{_MONTHS[m.group(1)[:3]]:02d}"

    if _HAVE_DATEUTIL:
        try:
            dt = _dateparser.parse(text, default=None)
            if dt is not None:
                return f"{dt.year:04d}-{dt.month:02d}"
        except (ValueError, OverflowError):
            return None
    return None


def to_year(raw: Optional[str]) -> Optional[int]:
    """Extract a 4-digit year as an int, or ``None``."""
    if raw is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(raw))
    return int(m.group(0)) if m else None
