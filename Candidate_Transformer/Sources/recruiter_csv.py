"""Recruiter CSV adapter — structured rows.

Columns: name, email, phone, current_company, title. One person per row.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from ..models import RawField, SourceRecord

log = logging.getLogger("candidate_transformer.sources.recruiter_csv")

# Map the source's column names -> canonical paths. Tolerant of common variants.
_COLUMN_MAP = {
    "name": "full_name",
    "full_name": "full_name",
    "email": "emails",
    "emails": "emails",
    "phone": "phones",
    "phones": "phones",
    "current_company": "experience.company",
    "company": "experience.company",
    "title": "experience.title",
}


class RecruiterCsvAdapter:
    name = "recruiter_csv"

    def extract(self, inputs_dir: Path) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for path in sorted(inputs_dir.glob("*.csv")):
            records.extend(self._extract_file(path))
        return records

    def _extract_file(self, path: Path) -> list[SourceRecord]:
        out: list[SourceRecord] = []
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for i, row in enumerate(reader):
                    fields: list[RawField] = []
                    company = (row.get("current_company") or row.get("company") or "").strip()
                    title = (row.get("title") or "").strip()
                    for col, value in row.items():
                        if col is None or value is None:
                            continue
                        canonical = _COLUMN_MAP.get((col or "").strip().lower())
                        value = value.strip()
                        if not canonical or not value:
                            continue
                        # company/title are folded into a single experience row below
                        if canonical.startswith("experience."):
                            continue
                        fields.append(
                            RawField(canonical, value, method=f"csv_column:{col}")
                        )
                    if company or title:
                        fields.append(
                            RawField(
                                "experience",
                                {"company": company or None, "title": title or None},
                                method="csv_column:current_company+title",
                            )
                        )
                    if fields:
                        out.append(SourceRecord(self.name, fields))
        except (OSError, csv.Error) as exc:
            log.warning("skipping malformed CSV %s: %s", path, exc)
            return []
        return out
