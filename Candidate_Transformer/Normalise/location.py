"""Location normalization — country names/codes to ISO-3166 alpha-2.

A small built-in lookup covers the common cases in the sample data. Unknown
countries normalize to ``None`` rather than a guessed code.
"""

from __future__ import annotations

from typing import Optional

# Common names / aliases -> ISO-3166 alpha-2. Lowercased keys.
_COUNTRY_ALPHA2 = {
    "us": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united states": "US", "united states of america": "US", "america": "US",
    "uk": "GB", "u.k.": "GB", "united kingdom": "GB", "great britain": "GB",
    "england": "GB",
    "india": "IN", "bharat": "IN",
    "canada": "CA", "ca": "CA",
    "germany": "DE", "deutschland": "DE", "de": "DE",
    "france": "FR", "fr": "FR",
    "australia": "AU", "au": "AU",
    "ireland": "IE", "netherlands": "NL", "nl": "NL",
    "singapore": "SG", "sg": "SG",
    "spain": "ES", "es": "ES",
    "brazil": "BR", "br": "BR",
    "japan": "JP", "jp": "JP",
    "china": "CN", "cn": "CN",
}


def to_country_alpha2(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip().lower().rstrip(".")
    if not text:
        return None
    # Already a 2-letter code we recognise.
    if len(text) == 2 and text.upper() in {v for v in _COUNTRY_ALPHA2.values()}:
        return text.upper()
    return _COUNTRY_ALPHA2.get(text)
