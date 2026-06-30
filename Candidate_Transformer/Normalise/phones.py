"""Phone normalization to E.164.

Uses the ``phonenumbers`` library when available (correct, locale-aware), and
falls back to a conservative regex that only accepts clearly-valid input. An
unparseable number normalizes to ``None`` — it is never invented or padded.
"""

from __future__ import annotations

import re
from typing import Optional

try:  # pragma: no cover - exercised by environment, not unit tests
    import phonenumbers

    _HAVE_PHONENUMBERS = True
except ImportError:  # pragma: no cover
    _HAVE_PHONENUMBERS = False


# Default region used when a number has no country code. US is a reasonable
# default for this dataset; callers can override.
DEFAULT_REGION = "US"


def to_e164(raw: Optional[str], region: str = DEFAULT_REGION) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    if _HAVE_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(text, None if text.startswith("+") else region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
        except phonenumbers.NumberParseException:
            return None
        return None

    return _fallback_e164(text, region)


def _fallback_e164(text: str, region: str) -> Optional[str]:
    """Minimal E.164 best-effort without the phonenumbers dependency."""
    digits = re.sub(r"[^\d+]", "", text)
    if digits.startswith("+"):
        body = digits[1:]
        return "+" + body if 8 <= len(body) <= 15 else None
    if region == "US" and len(digits) == 10:
        return "+1" + digits
    if region == "US" and len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None
