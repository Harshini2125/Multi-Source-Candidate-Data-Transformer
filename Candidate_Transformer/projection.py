"""Projection engine — the required "configurable output" twist.

Takes a fully-merged ``CanonicalProfile`` (as a dict) plus an ``OutputConfig``
and produces the requested shape. The engine reads the config as data; there are
no per-field branches. It supports:

* field selection (only configured fields appear),
* ``from``-path remapping with indexing (``emails[0]``), nesting
  (``location.city``) and wildcard projection (``skills[].name``),
* per-field re-normalization (``E164``, ``canonical``),
* ``on_missing`` semantics: ``null`` / ``omit`` / ``error``,
* optional provenance and confidence blocks.

The canonical record is never mutated — projection only reads from it.
"""

from __future__ import annotations

import re
from typing import Any

from .config import FieldSpec, OutputConfig
from .normalize import canonicalize_skill, to_e164

_MISSING = object()  # sentinel distinct from a legitimate None


class MissingRequiredField(ValueError):
    """Raised when on_missing='error' and a value is absent."""


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(r"([^.\[\]]+)(\[(\d+|)\])?")


def resolve_path(data: Any, path: str) -> Any:
    """Resolve a canonical path against the profile dict.

    Returns ``_MISSING`` if any segment is absent. Supports:
      ``a.b``         nested dict access
      ``a[0]``        list index
      ``a[].b``       wildcard: map ``b`` over every element of list ``a``
    """
    cur: Any = data
    for name, _bracket, index in _TOKEN_RE.findall(path):
        if isinstance(cur, dict):
            if name not in cur:
                return _MISSING
            cur = cur[name]
        else:
            return _MISSING

        if _bracket == "":
            continue
        if index == "":  # wildcard "[]": the tail is applied per element by resolve()
            if not isinstance(cur, list):
                return _MISSING
            return _Wildcard(cur)
        else:  # explicit index
            i = int(index)
            if not isinstance(cur, list) or i >= len(cur):
                return _MISSING
            cur = cur[i]
    return cur


class _Wildcard:
    """Marks 'the rest of the path applies to each element of this list'."""

    def __init__(self, items: list):
        self.items = items


def resolve(data: Any, path: str) -> Any:
    """Full resolution including wildcard tails like ``skills[].name``."""
    if "[]" not in path:
        return resolve_path(data, path)
    head, tail = path.split("[]", 1)
    tail = tail.lstrip(".")
    base = resolve_path(data, head + "[]")  # returns a _Wildcard or _MISSING
    if base is _MISSING:
        return _MISSING
    items = base.items if isinstance(base, _Wildcard) else base
    out = []
    for item in items:
        v = resolve_path(item, tail) if tail else item
        if v is not _MISSING and v is not None:
            out.append(v)
    return out


# --------------------------------------------------------------------------- #
# Normalization hook
# --------------------------------------------------------------------------- #
_NORMALIZERS = {
    "E164": to_e164,
    "canonical": canonicalize_skill,
}


def _apply_normalize(value: Any, kind: str | None) -> Any:
    if not kind or value is None:
        return value
    fn = _NORMALIZERS.get(kind)
    if fn is None:
        return value
    if isinstance(value, list):
        return [fn(v) for v in value if fn(v) is not None]
    return fn(value)


# --------------------------------------------------------------------------- #
# Projection
# --------------------------------------------------------------------------- #
def project(profile: dict, config: OutputConfig) -> dict:
    out: dict[str, Any] = {}
    for spec in config.fields:
        value = _project_field(profile, spec, config)
        if value is _OMIT:
            continue
        out[spec.path] = value

    if config.include_confidence and "overall_confidence" in profile:
        out["overall_confidence"] = profile["overall_confidence"]
    if config.include_provenance and "provenance" in profile:
        out["provenance"] = profile["provenance"]
    return out


_OMIT = object()


def _project_field(profile: dict, spec: FieldSpec, config: OutputConfig) -> Any:
    raw = resolve(profile, spec.source_path)
    present = raw is not _MISSING and raw not in (None, [], "")

    if not present:
        if spec.required and config.on_missing == "error":
            raise MissingRequiredField(
                f"required field '{spec.path}' (from '{spec.source_path}') is missing"
            )
        if config.on_missing == "omit":
            return _OMIT
        if spec.required:  # null mode but required and absent -> still an error
            raise MissingRequiredField(
                f"required field '{spec.path}' is missing and on_missing='null'"
            )
        return None

    return _apply_normalize(raw, spec.normalize)
