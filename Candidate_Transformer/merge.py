"""Entity resolution + conflict resolution.

Two jobs:

1. **Resolve** which ``SourceRecord`` objects describe the same person, using
   match keys (normalized email primary; normalized name+company fallback). No
   fuzzy ML — the rule is simple and explainable.
2. **Merge** each group into one ``CanonicalProfile``: normalize every value,
   pick deterministic winners for scalar conflicts (by source priority), union +
   dedupe list fields, and populate provenance + confidence throughout.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Optional

from . import confidence as conf
from .models import (
    CanonicalProfile,
    Education,
    Experience,
    Links,
    Location,
    Provenance,
    Skill,
    SourceRecord,
)
from .normalize import (
    canonicalize_skill,
    to_country_alpha2,
    to_e164,
    to_year,
    to_year_month,
)

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


# --------------------------------------------------------------------------- #
# Step 1 — entity resolution
# --------------------------------------------------------------------------- #
def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _norm_url(value: Any) -> Optional[str]:
    """Reduce a profile URL to a host+path key so the same profile matches
    across sources regardless of scheme / www / trailing slash."""
    u = _norm_text(value)
    if not u:
        return None
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/") or None


def _match_keys(record: SourceRecord) -> set[str]:
    keys: set[str] = set()
    for email in record.values("emails"):
        e = _norm_text(email)
        if _EMAIL_RE.match(e):
            keys.add(f"email:{e}")
    # Profile links are strong identity signals (a GitHub record may carry no
    # email, but its URL matches the one the ATS recorded).
    for path in ("links.github", "links.linkedin"):
        for url in record.values(path):
            key = _norm_url(url)
            if key:
                keys.add(f"url:{key}")
    name = record.first("full_name")
    company = None
    for exp in record.values("experience"):
        if isinstance(exp, dict) and exp.get("company"):
            company = exp["company"]
            break
    if name and company:
        keys.add(f"nameco:{_norm_text(name)}|{_norm_text(company)}")
    return keys


def resolve(records: list[SourceRecord]) -> list[list[SourceRecord]]:
    """Group records that share at least one match key (union-find)."""
    parent: dict[int, int] = {i: i for i in range(len(records))}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    key_to_idx: dict[str, int] = {}
    for i, rec in enumerate(records):
        for key in _match_keys(rec):
            if key in key_to_idx:
                union(i, key_to_idx[key])
            else:
                key_to_idx[key] = i

    groups: dict[int, list[SourceRecord]] = defaultdict(list)
    for i, rec in enumerate(records):
        groups[find(i)].append(rec)
    # Deterministic group ordering by their smallest match key.
    return [g for _, g in sorted(
        ((min(_match_keys(g[0]) | {f"idx:{id(g)}"}), g) for g in groups.values()),
        key=lambda t: t[0],
    )]


# --------------------------------------------------------------------------- #
# Step 2 — merge a group into one CanonicalProfile
# --------------------------------------------------------------------------- #
class _ProvenanceLog:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str, str]] = set()
        self.entries: list[Provenance] = []

    def add(self, field: str, source: str, method: str) -> None:
        key = (field, source, method)
        if key not in self._seen:
            self._seen.add(key)
            self.entries.append(Provenance(field=field, source=source, method=method))


def merge_group(records: list[SourceRecord]) -> CanonicalProfile:
    prov = _ProvenanceLog()
    field_conf: dict[str, float] = {}

    # Gather (source, method, value) per canonical path.
    by_path: dict[str, list[tuple[str, str, Any]]] = defaultdict(list)
    for rec in records:
        for f in rec.fields:
            by_path[f.path].append((rec.source, f.method, f.value))

    # ---- scalar fields: deterministic winner by source priority ----------
    full_name = _scalar(by_path, "full_name", prov, field_conf)
    headline = _scalar(by_path, "headline", prov, field_conf)
    years_experience = _scalar(by_path, "years_experience", prov, field_conf)

    # ---- location (per-subfield) -----------------------------------------
    location = Location(
        city=_scalar(by_path, "location.city", prov, field_conf, fld="location"),
        region=_scalar(by_path, "location.region", prov, field_conf, fld="location"),
        country=_scalar(by_path, "location.country", prov, field_conf,
                        fld="location", normalizer=to_country_alpha2),
    )

    # ---- links (per-subfield) --------------------------------------------
    links = Links(
        linkedin=_scalar(by_path, "links.linkedin", prov, field_conf, fld="links"),
        github=_scalar(by_path, "links.github", prov, field_conf, fld="links"),
        portfolio=_scalar(by_path, "links.portfolio", prov, field_conf, fld="links"),
        other=[],
    )

    # ---- multi-valued: emails, phones ------------------------------------
    emails = _string_list(by_path, "emails", prov, field_conf,
                          normalizer=_norm_email)
    phones = _string_list(by_path, "phones", prov, field_conf, normalizer=to_e164)

    # ---- skills (canonicalized, aggregated confidence) -------------------
    skills = _merge_skills(by_path.get("skills", []), prov, field_conf)

    # ---- experience / education ------------------------------------------
    experience = _merge_experience(by_path.get("experience", []), prov, field_conf)
    education = _merge_education(by_path.get("education", []), prov)

    candidate_id = _candidate_id(emails, full_name)
    overall = conf.overall(field_conf)

    return CanonicalProfile(
        candidate_id=candidate_id,
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=prov.entries,
        overall_confidence=overall,
    )


# --------------------------------------------------------------------------- #
# Field-level helpers
# --------------------------------------------------------------------------- #
def _scalar(
    by_path: dict[str, list[tuple[str, str, Any]]],
    path: str,
    prov: _ProvenanceLog,
    field_conf: dict[str, float],
    fld: Optional[str] = None,
    normalizer=None,
) -> Optional[Any]:
    """Pick the winning value for a scalar path and record provenance/confidence.

    Winner = value asserted by the highest-priority source. Ties break toward
    more agreeing sources, then lexically — fully deterministic.
    """
    fld = fld or path
    candidates = by_path.get(path, [])
    norm: list[tuple[str, str, Any]] = []
    for source, method, value in candidates:
        v = normalizer(value) if normalizer else value
        if isinstance(v, str):
            v = v.strip()
        if v in (None, ""):
            continue
        norm.append((source, method, v))
    if not norm:
        return None

    # Group sources by value.
    by_value: dict[Any, list[tuple[str, str]]] = defaultdict(list)
    for source, method, v in norm:
        by_value[v].append((source, method))

    def rank(item) -> tuple:
        value, srcs = item
        best = min(conf.priority_rank(s) for s, _ in srcs)
        return (best, -len(srcs), str(value))

    winner_value, winner_srcs = min(by_value.items(), key=rank)
    # Provenance from the highest-priority asserting source.
    top_source, top_method = min(winner_srcs, key=lambda sm: conf.priority_rank(sm[0]))
    prov.add(fld, top_source, top_method)
    field_conf[fld] = max(field_conf.get(fld, 0.0),
                          conf.combine(s for s, _ in winner_srcs))
    return winner_value


def _string_list(
    by_path: dict[str, list[tuple[str, str, Any]]],
    path: str,
    prov: _ProvenanceLog,
    field_conf: dict[str, float],
    normalizer=None,
) -> list[str]:
    """Union + dedupe a multi-valued string field, ordered by source priority.

    All sources that assert the same normalized value are kept so that agreement
    still boosts confidence and every contributor is recorded in provenance.
    """
    by_value: dict[str, set[str]] = defaultdict(set)
    methods: dict[tuple[str, str], str] = {}
    for source, method, value in by_path.get(path, []):
        v = normalizer(value) if normalizer else value
        if not v:
            continue
        by_value[v].add(source)
        methods.setdefault((v, source), method)
    if not by_value:
        return []

    # Distinct values ordered by their best (highest-priority) source, then text.
    ordered = sorted(
        by_value, key=lambda v: (min(conf.priority_rank(s) for s in by_value[v]), v)
    )
    sources_for_field: set[str] = set()
    for value in ordered:
        for source in sorted(by_value[value], key=conf.priority_rank):
            prov.add(path, source, methods[(value, source)])
            sources_for_field.add(source)
    field_conf[path] = conf.combine(sources_for_field)
    return ordered


def _merge_skills(
    candidates: list[tuple[str, str, Any]],
    prov: _ProvenanceLog,
    field_conf: dict[str, float],
) -> list[Skill]:
    by_name: dict[str, set[str]] = defaultdict(set)
    method_by_source: dict[str, str] = {}
    for source, method, value in candidates:
        name = canonicalize_skill(value)
        if not name:
            continue
        by_name[name].add(source)
        method_by_source[source] = method
    skills: list[Skill] = []
    all_sources: set[str] = set()
    for name in sorted(by_name):
        srcs = sorted(by_name[name], key=conf.priority_rank)
        skills.append(Skill(name=name, confidence=conf.combine(srcs), sources=srcs))
        for s in srcs:
            prov.add("skills", s, method_by_source.get(s, "merge"))
            all_sources.add(s)
    if skills:
        field_conf["skills"] = conf.combine(all_sources)
    return skills


def _merge_experience(
    candidates: list[tuple[str, str, Any]],
    prov: _ProvenanceLog,
    field_conf: dict[str, float],
) -> list[Experience]:
    by_key: dict[tuple, dict] = {}
    sources: set[str] = set()
    for source, method, value in candidates:
        if not isinstance(value, dict):
            continue
        company = (value.get("company") or "").strip() or None
        title = (value.get("title") or "").strip() or None
        if not company and not title:
            continue
        key = (_norm_text(company), _norm_text(title))
        entry = by_key.setdefault(key, {
            "company": company, "title": title,
            "start": None, "end": None, "summary": None,
        })
        # Fill missing subfields preferring higher-priority sources (first wins).
        start = to_year_month(value.get("start"))
        end = to_year_month(value.get("end"))
        entry["start"] = entry["start"] or start
        entry["end"] = entry["end"] or end
        entry["summary"] = entry["summary"] or (value.get("summary") or None)
        prov.add("experience", source, method)
        sources.add(source)
    result = [Experience(**v) for v in by_key.values()]
    result.sort(key=lambda e: (e.start or "", e.company or ""))
    if result:
        field_conf["experience"] = conf.combine(sources)
    return result


def _merge_education(
    candidates: list[tuple[str, str, Any]],
    prov: _ProvenanceLog,
) -> list[Education]:
    by_key: dict[tuple, dict] = {}
    for source, method, value in candidates:
        if not isinstance(value, dict):
            continue
        institution = (value.get("institution") or "").strip() or None
        if not institution:
            continue
        end_year = value.get("end_year")
        end_year = int(end_year) if isinstance(end_year, int) else to_year(end_year)
        key = (_norm_text(institution), end_year)
        entry = by_key.setdefault(key, {
            "institution": institution,
            "degree": value.get("degree") or None,
            "field": value.get("field") or None,
            "end_year": end_year,
        })
        entry["degree"] = entry["degree"] or (value.get("degree") or None)
        entry["field"] = entry["field"] or (value.get("field") or None)
        prov.add("education", source, method)
    return [Education(**v) for v in by_key.values()]


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def _norm_email(value: Any) -> Optional[str]:
    e = _norm_text(value)
    return e if _EMAIL_RE.match(e) else None


def _candidate_id(emails: list[str], full_name: Optional[str]) -> str:
    """Deterministic id from the strongest available key."""
    basis = emails[0] if emails else _norm_text(full_name) or "unknown"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"cand_{digest}"
