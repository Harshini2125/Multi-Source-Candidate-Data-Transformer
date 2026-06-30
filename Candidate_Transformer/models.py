"""Canonical data model.

Two layers live here:

* The *raw* extraction layer (`RawField`, `SourceRecord`) — what each adapter
  emits before any merging. Every value is tagged with the source it came from
  and the method used to extract it, so provenance is never bolted on later.
* The *canonical* layer (`CanonicalProfile` and friends) — the one fixed schema
  the merge step produces. This is validated with pydantic so an internally
  malformed profile fails loudly before it can reach the projection layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Raw extraction layer (pre-merge)
# --------------------------------------------------------------------------- #
@dataclass
class RawField:
    """A single value extracted from one source, with how it was obtained.

    `path` is a canonical dotted path (e.g. ``full_name``, ``location.city``,
    ``links.github``). List-valued canonical fields (``emails``, ``phones``,
    ``skills`` ...) use the bare field name and carry one item per RawField.
    """

    path: str
    value: Any
    method: str  # e.g. "csv_column:email", "json_field:contact.mail", "regex:phone"


@dataclass
class SourceRecord:
    """All fields belonging to one person, from one source."""

    source: str  # "recruiter_csv" | "ats_json" | "resume" | "github"
    fields: list[RawField] = field(default_factory=list)

    def values(self, path: str) -> list[Any]:
        return [f.value for f in self.fields if f.path == path and f.value not in (None, "")]

    def first(self, path: str) -> Optional[Any]:
        vals = self.values(path)
        return vals[0] if vals else None


# --------------------------------------------------------------------------- #
# Canonical layer (post-merge) — the default output schema
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    confidence: float
    sources: list[str]


class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM
    end: Optional[str] = None    # YYYY-MM or None (current)
    summary: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class Provenance(BaseModel):
    field: str
    source: str
    method: str


class CanonicalProfile(BaseModel):
    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: float = 0.0
