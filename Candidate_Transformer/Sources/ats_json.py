"""ATS JSON adapter — semi-structured, with its own field names.

This is the source that most exercises field remapping: the ATS uses names that
do NOT match ours (``candidate_name``, ``contact.mail``, ``location_str`` ...).
The remap table below is the single place that knowledge lives.

Accepts either a single object or a list of objects. A file that is not the ATS
shape (e.g. the GitHub fixture) is skipped.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import RawField, SourceRecord

log = logging.getLogger("candidate_transformer.sources.ats_json")

# Marker keys that identify a blob as ATS data (vs the github fixture etc.).
_ATS_MARKERS = {"candidate_name", "applicant", "ats_id", "work_history"}


def _get(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


class AtsJsonAdapter:
    name = "ats_json"

    def extract(self, inputs_dir: Path) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for path in sorted(inputs_dir.glob("*.json")):
            records.extend(self._extract_file(path))
        return records

    def _extract_file(self, path: Path) -> list[SourceRecord]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("skipping malformed JSON %s: %s", path, exc)
            return []

        blobs = data if isinstance(data, list) else [data]
        out: list[SourceRecord] = []
        for blob in blobs:
            if not isinstance(blob, dict) or not (_ATS_MARKERS & blob.keys()):
                continue  # not ATS-shaped; another adapter may own it
            rec = self._extract_blob(blob)
            if rec.fields:
                out.append(rec)
        return out

    def _extract_blob(self, blob: dict) -> SourceRecord:
        fields: list[RawField] = []

        def add(canonical: str, value: Any, ats_key: str) -> None:
            if value in (None, "", []):
                return
            fields.append(RawField(canonical, value, method=f"json_field:{ats_key}"))

        # --- scalar remaps: ATS key -> canonical path -----------------------
        add("full_name", blob.get("candidate_name"), "candidate_name")
        add("headline", blob.get("current_title") or blob.get("headline"),
            "current_title")
        add("location.city", _get(blob, "location.city"), "location.city")
        add("location.region", _get(blob, "location.state")
            or _get(blob, "location.region"), "location.state")
        add("location.country", _get(blob, "location.country"), "location.country")
        add("links.linkedin", _get(blob, "social.linkedin"), "social.linkedin")
        add("links.github", _get(blob, "social.github"), "social.github")
        yrs = blob.get("years_of_experience")
        if isinstance(yrs, (int, float)):
            add("years_experience", float(yrs), "years_of_experience")

        # --- contact: may be string or list --------------------------------
        for mail in _as_list(_get(blob, "contact.mail") or blob.get("email")):
            add("emails", mail, "contact.mail")
        for tel in _as_list(_get(blob, "contact.tel") or blob.get("phone")):
            add("phones", tel, "contact.tel")

        # --- skills --------------------------------------------------------
        for sk in _as_list(blob.get("skill_tags") or blob.get("skills")):
            add("skills", sk, "skill_tags")

        # --- work history --------------------------------------------------
        for job in _as_list(blob.get("work_history") or blob.get("experience")):
            if not isinstance(job, dict):
                continue
            exp = {
                "company": job.get("org") or job.get("company"),
                "title": job.get("role") or job.get("title"),
                "start": job.get("from") or job.get("start"),
                "end": job.get("to") or job.get("end"),
                "summary": job.get("notes") or job.get("summary"),
            }
            add("experience", exp, "work_history[]")

        # --- education -----------------------------------------------------
        for ed in _as_list(blob.get("education")):
            if not isinstance(ed, dict):
                continue
            edu = {
                "institution": ed.get("school") or ed.get("institution"),
                "degree": ed.get("degree"),
                "field": ed.get("major") or ed.get("field"),
                "end_year": ed.get("grad_year") or ed.get("end_year"),
            }
            add("education", edu, "education[]")

        return SourceRecord(self.name, fields)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
