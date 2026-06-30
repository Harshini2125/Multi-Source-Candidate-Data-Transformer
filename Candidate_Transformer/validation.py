"""Validate a projected output against the schema implied by its config.

This is the final gate before a profile is returned: types must match the
declared ``type`` and required fields must be present and non-null. Validating
the *projected* object (not just the canonical one) means custom configs are
held to the same standard as the default schema.
"""

from __future__ import annotations

from .config import OutputConfig


class SchemaValidationError(ValueError):
    pass


def _type_ok(value, declared: str) -> bool:
    if value is None:
        return True  # null handled by the required check, not the type check
    if declared == "string":
        return isinstance(value, str)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "object":
        return isinstance(value, dict)
    if declared == "string[]":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if declared == "object[]":
        return isinstance(value, list) and all(isinstance(v, dict) for v in value)
    if declared.endswith("[]"):
        return isinstance(value, list)
    return True  # unknown declared type: don't block


def validate(projected: dict, config: OutputConfig) -> list[str]:
    """Return a list of problems (empty == valid)."""
    problems: list[str] = []
    for spec in config.fields:
        if spec.path not in projected:
            if spec.required and config.on_missing != "omit":
                problems.append(f"missing required field '{spec.path}'")
            continue
        value = projected[spec.path]
        if spec.required and value is None:
            problems.append(f"required field '{spec.path}' is null")
        if not _type_ok(value, spec.type):
            problems.append(
                f"field '{spec.path}' expected {spec.type}, got {type(value).__name__}"
            )
    return problems


def validate_or_raise(projected: dict, config: OutputConfig) -> dict:
    problems = validate(projected, config)
    if problems:
        raise SchemaValidationError("; ".join(problems))
    return projected
