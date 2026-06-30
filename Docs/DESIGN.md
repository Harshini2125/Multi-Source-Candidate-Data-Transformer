# Multi-Source Candidate Data Transformer — Stage 1 Design

**Problem.** Ingest candidate data from many heterogeneous sources and emit one
canonical profile per candidate: fixed fields, normalized formats, deduplicated
across sources, with provenance and confidence per value. Guiding rule:
*wrong-but-confident is worse than honestly-empty* — never invent, prefer `null`,
make every choice deterministic and explainable.

## Pipeline

```
load → extract → normalize → merge(resolve) → score → project → validate
```

- **load / extract** — one adapter per source discovers its files and emits
  `(canonical_path, value, source, method)` candidates. Adapters never raise: a
  missing/garbage source is logged and skipped. The ATS adapter holds the
  source→canonical remap table (its field names do not match ours).
- **normalize** — phones→E.164, dates→`YYYY-MM`, country→ISO-3166 α2,
  skills→canonical names. Unparseable input → `None`.
- **merge** — entity resolution + conflict resolution (below).
- **score** — confidence per value/skill + overall.
- **project** — config-driven reshaping into the requested output.
- **validate** — projected output checked against the requested schema.

## Canonical schema & normalized formats

Canonical record = the default schema (candidate_id, full_name, emails[],
phones[], location{city,region,country}, links{linkedin,github,portfolio,other[]},
headline, years_experience, skills[{name,confidence,sources[]}],
experience[{company,title,start,end,summary}], education[{institution,degree,
field,end_year}], provenance[{field,source,method}], overall_confidence).

Formats: **phones** E.164 (`+14155550132`); **dates** `YYYY-MM`, year-only kept as
`YYYY`; **country** ISO-3166 alpha-2; **skills** a canonical dictionary with a
synonym map (`js`→`JavaScript`), unknown skills retained as-is.

## Merge / conflict resolution

- **Match keys** (union-find grouping): normalized email; normalized profile URL
  (GitHub/LinkedIn); fallback name+company. Simple and explainable — no fuzzy ML.
- **Scalar winner**: fixed **source priority** `ats_json > recruiter_csv > resume
  > github`; ties break toward more agreeing sources, then lexically → fully
  deterministic.
- **Multi-valued** (emails, phones, links, skills): union + dedupe after
  normalization; "primary" = highest-priority source's value.

## Confidence

Source base weights (ATS .90, CSV .85, resume .70, GitHub .60). Agreeing sources
combine by **noisy-OR**: `conf = 1 − Π(1 − wᵢ)`, capped at 0.99 — agreement
raises confidence, certainty is never reached. `overall_confidence` = mean of
populated core fields.

## Configurable output (the twist)

A runtime config (data, not code) drives a **projection layer** that is fully
separate from the canonical record. It can select a subset of fields, remap from
a canonical path (`from: emails[0]`, `skills[].name`), set per-field
normalization, toggle provenance/confidence, and choose `on_missing` =
`null|omit|error`. A path resolver handles nesting, indexing, and wildcard
projection; the projected object is then validated against the schema implied by
the config. Same engine serves default and custom schemas.

## Edge cases

1. **Garbage/empty source** → skip + warn, run succeeds.
2. **Format-divergent duplicate phone** (`(415) 555-0132` vs `+1 415 555 0132`)
   → one E.164 value, deduped, confidence boosted by agreement.
3. **Unparseable phone** → `null`, never invented.
4. **Partial date** (`2021`, `Jan 2017`) → `YYYY` / `YYYY-MM`, no fabricated month.
5. **Skill synonyms/casing** → canonicalized; unknown skills kept.
6. **`on_missing: error`** on an absent required field → explicit validation error.

## Deliberately left out (time pressure)

LinkedIn source; ML/NLP resume parsing (use high-precision heuristics; no
free-form job-history parsing); live GitHub (fixture-cached for determinism);
fuzzy-name matching; any UI beyond a CLI.
