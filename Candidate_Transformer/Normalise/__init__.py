"""Normalizers: turn source-specific value shapes into canonical formats.

Every normalizer returns ``None`` rather than guessing when the input cannot be
parsed — "honestly-empty beats wrong-but-confident".
"""

from .phones import to_e164
from .dates import to_year_month, to_year
from .location import to_country_alpha2
from .skills import canonicalize_skill

__all__ = [
    "to_e164",
    "to_year_month",
    "to_year",
    "to_country_alpha2",
    "canonicalize_skill",
]
