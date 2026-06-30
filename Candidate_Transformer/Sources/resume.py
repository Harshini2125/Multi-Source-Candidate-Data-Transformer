"""Resume adapter — unstructured prose (.txt / .pdf / .docx).

Resumes have no schema, so we extract with deterministic heuristics (regex +
labelled sections), never an LLM. PDF/DOCX text extraction uses ``pdfplumber`` /
``python-docx`` when installed; a plain ``.txt`` resume always works with no
dependencies, which keeps the default sample run dependency-light and
deterministic.

Only high-precision signals are emitted (emails, phones, an explicit Skills
section, education years). We deliberately do NOT try to parse free-form job
history out of prose — that is listed as descoped.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ..models import RawField, SourceRecord

log = logging.getLogger("candidate_transformer.sources.resume")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_SKILLS_HEADER_RE = re.compile(r"^\s*(skills|technologies|tech stack)\s*:?\s*$",
                               re.IGNORECASE)


class ResumeAdapter:
    name = "resume"

    def extract(self, inputs_dir: Path) -> list[SourceRecord]:
        out: list[SourceRecord] = []
        for path in sorted(inputs_dir.glob("resume*")):
            if path.suffix.lower() not in {".txt", ".pdf", ".docx", ".md"}:
                continue
            text = self._read(path)
            if not text:
                continue
            rec = self._extract_text(text)
            if rec.fields:
                out.append(rec)
        return out

    def _read(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md"}:
                return path.read_text(encoding="utf-8")
            if suffix == ".pdf":
                return _read_pdf(path)
            if suffix == ".docx":
                return _read_docx(path)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("could not read resume %s: %s", path, exc)
        return None

    def _extract_text(self, text: str) -> SourceRecord:
        fields: list[RawField] = []
        lines = text.splitlines()

        # Name heuristic: first non-empty line that has no email/digits.
        for line in lines:
            s = line.strip()
            if s and not _EMAIL_RE.search(s) and not re.search(r"\d", s) and len(s) < 60:
                fields.append(RawField("full_name", s, method="regex:first_line"))
                break

        for email in dict.fromkeys(_EMAIL_RE.findall(text)):
            fields.append(RawField("emails", email, method="regex:email"))

        for phone in dict.fromkeys(_PHONE_RE.findall(text)):
            if sum(c.isdigit() for c in phone) >= 10:
                fields.append(RawField("phones", phone.strip(), method="regex:phone"))

        for skill in self._extract_skills(lines):
            fields.append(RawField("skills", skill, method="section:skills"))

        for edu in self._extract_education(lines):
            fields.append(RawField("education", edu, method="section:education"))

        return SourceRecord(self.name, fields)

    def _extract_skills(self, lines: list[str]) -> list[str]:
        skills: list[str] = []
        capturing = False
        for line in lines:
            if _SKILLS_HEADER_RE.match(line):
                capturing = True
                continue
            if capturing:
                if not line.strip():
                    if skills:
                        break
                    continue
                # stop if we hit another section header (Title-case word + colon)
                if re.match(r"^[A-Z][A-Za-z ]+:\s*$", line.strip()):
                    break
                parts = re.split(r"[,;|••/]| - ", line)
                skills.extend(p.strip() for p in parts if p.strip())
        return [s for s in dict.fromkeys(skills) if len(s) <= 30]

    def _extract_education(self, lines: list[str]) -> list[dict]:
        edu: list[dict] = []
        capturing = False
        for line in lines:
            if re.match(r"^\s*education\s*:?\s*$", line, re.IGNORECASE):
                capturing = True
                continue
            if capturing:
                s = line.strip()
                if not s:
                    if edu:
                        break
                    continue
                if re.match(r"^[A-Z][A-Za-z ]+:\s*$", s):
                    break
                year = re.search(r"(19|20)\d{2}", s)
                edu.append({
                    "institution": re.split(r"[,–-]", s)[0].strip() or None,
                    "degree": None,
                    "field": None,
                    "end_year": int(year.group(0)) if year else None,
                })
        return edu


def _read_pdf(path: Path) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        log.warning("pdfplumber not installed; cannot read %s", path)
        return None
    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _read_docx(path: Path) -> str | None:
    try:
        import docx
    except ImportError:
        log.warning("python-docx not installed; cannot read %s", path)
        return None
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)
