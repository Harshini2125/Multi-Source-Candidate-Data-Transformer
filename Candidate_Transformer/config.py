"""Runtime output configuration.

The config is *data*, not code: it declares which canonical fields appear in the
output, how they are renamed/remapped, how they are normalized, and what to do
when a value is missing. The same engine serves the default schema and any
custom schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

OnMissing = Literal["null", "omit", "error"]


@dataclass
class FieldSpec:
    path: str                      # output key
    type: str                      # "string" | "string[]" | "number" | "object" | "boolean"
    frm: Optional[str] = None      # canonical source path ("from"); defaults to path
    required: bool = False
    normalize: Optional[str] = None  # "E164" | "canonical" | None

    @property
    def source_path(self) -> str:
        return self.frm or self.path


@dataclass
class OutputConfig:
    fields: list[FieldSpec]
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: OnMissing = "null"

    @staticmethod
    def from_dict(data: dict) -> "OutputConfig":
        fields = [
            FieldSpec(
                path=f["path"],
                type=f.get("type", "string"),
                frm=f.get("from"),
                required=bool(f.get("required", False)),
                normalize=f.get("normalize"),
            )
            for f in data.get("fields", [])
        ]
        return OutputConfig(
            fields=fields,
            include_confidence=bool(data.get("include_confidence", True)),
            include_provenance=bool(data.get("include_provenance", True)),
            on_missing=data.get("on_missing", "null"),
        )

    @staticmethod
    def load(path: Path) -> "OutputConfig":
        return OutputConfig.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# The default schema, expressed in the same config language as any custom one —
# proving the projection layer is the only thing that shapes output.
DEFAULT_CONFIG = OutputConfig(
    fields=[
        FieldSpec("candidate_id", "string", required=True),
        FieldSpec("full_name", "string"),
        FieldSpec("emails", "string[]"),
        FieldSpec("phones", "string[]"),
        FieldSpec("location", "object"),
        FieldSpec("links", "object"),
        FieldSpec("headline", "string"),
        FieldSpec("years_experience", "number"),
        FieldSpec("skills", "object[]"),
        FieldSpec("experience", "object[]"),
        FieldSpec("education", "object[]"),
    ],
    include_confidence=True,
    include_provenance=True,
    on_missing="null",
)
