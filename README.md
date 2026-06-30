# Multi-Source Candidate Data Transformer

Turns messy candidate data from several heterogeneous sources into **one clean,
canonical profile per candidate** — normalized formats, deduplicated across
sources, with a record of **where each value came from** (provenance) and **how
confident** we are in it.

Guiding principle: *wrong-but-confident is worse than honestly-empty.* Nothing is
invented; unknown values become `null`; every surviving value is traceable.

## Sources handled

| Group | Source | Adapter |
|---|---|---|
| Structured | Recruiter CSV (`*.csv`) | `sources/recruiter_csv.py` |
| Structured | ATS JSON (`*.json`, own field names) | `sources/ats_json.py` |
| Unstructured | Resume prose (`resume.*` — `.txt`/`.pdf`/`.docx`) | `sources/resume.py` |
| Unstructured | GitHub profile (`github*.json` fixture) | `sources/github.py` |

GitHub is read from a cached fixture by default so runs are **deterministic** and
tests run offline. `sources/github.py:fetch_and_cache` shows how the fixture is
produced from the live REST API.

## Pipeline

```
load → extract → normalize → merge (resolve) → score → project → validate
```

- **extract** — each adapter maps its own field names onto canonical paths,
  tagging every value with `{source, method}`.
- **normalize** — phones → E.164, dates → `YYYY-MM`, country → ISO-3166 alpha-2,
  skills → canonical names. Unparseable input → `None`, never a guess.
- **merge** — records are grouped into one person by match keys (email, profile
  URL, or name+company), then merged. Scalar conflicts are resolved by a fixed
  **source priority** (`ats_json > recruiter_csv > resume > github`);
  multi-valued fields are unioned and deduped.
- **score** — confidence via *noisy-OR* over agreeing sources (below).
- **project** — a config-driven layer reshapes the canonical record (the
  required "configurable output" twist).
- **validate** — the projected output is checked against the requested schema
  before it is returned.

## Install

**With [uv](https://docs.astral.sh/uv/) (recommended):**

```bash
uv sync --extra full          # creates .venv + installs runtime extras and dev (pytest)
```

**With pip:**

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[full,test]"                       # or: pip install -r requirements.txt
```

The only hard dependency is `pydantic`. `phonenumbers` and `python-dateutil` are
recommended (the code falls back to regex/heuristics without them);
`pdfplumber` / `python-docx` are only needed for non-`.txt` resumes. The `--extra
full` / `[full]` extra installs all of them.

## Run

Prefix the commands with `uv run` (no manual venv activation needed), or drop the
prefix if you installed with pip into an active venv.

Default canonical schema:

```bash
uv run python -m candidate_transformer.cli samples/inputs \
  --config samples/configs/default.json \
  --out samples/outputs/default.json -v
```

Custom config (field selection + remapping + normalization + toggles — the
example from the brief, extended):

```bash
uv run python -m candidate_transformer.cli samples/inputs \
  --config samples/configs/custom.json \
  --out samples/outputs/custom.json
```

A console entry point is also installed: `uv run candidate-transformer samples/inputs ...`.
Omit `--config` to use the built-in default schema, and omit `--out` to print to
stdout.

## The configurable output (the twist)

The config is **data, not code** — the same engine serves the default and any
custom schema. A field spec:

```json
{ "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164" }
```

- `from` resolves canonical paths with indexing (`emails[0]`), nesting
  (`location.city`) and wildcard projection (`skills[].name`).
- `normalize` re-applies a normalizer (`E164`, `canonical`).
- `include_confidence` / `include_provenance` toggle those blocks.
- `on_missing` ∈ `null | omit | error` decides what happens when a value is
  absent.

See `projection.py` (engine) and `config.py` (schema). The result is validated by
`validation.py`.

## Confidence model

Each source has a base reliability weight (ATS 0.90, CSV 0.85, resume 0.70,
GitHub 0.60). When N sources independently assert the same value we combine them
with noisy-OR:

```
confidence = 1 − Π (1 − weight_i)        (capped at 0.99)
```

So agreement raises confidence, but nothing is ever certain. `overall_confidence`
is the mean of the populated core fields. Definition lives in `confidence.py`.

## Edge cases handled

1. **Garbage/empty source** → logged and skipped; the run still succeeds.
2. **Format-divergent duplicates** → CSV `(415) 555-0132` and ATS
   `+1 415 555 0132` normalize to one E.164 value and dedupe.
3. **Unparseable phone** (`not-a-phone`) → dropped to empty, never invented.
4. **Partial dates** (`2021`, `Jan 2017`) → best-effort `YYYY-MM`; year-only kept
   as `YYYY`.
5. **Skill synonyms/casing** (`js`, `react.js`, `postgres`) → canonicalized;
   unknown skills kept as-is.
6. **`on_missing: error`** with a required field absent → clear validation error.

## Tests

```bash
uv run pytest          # or just: pytest  (inside an activated venv)
```

Covers the normalizers, the projection engine (`from`-remap, all three
`on_missing` modes), an end-to-end merge across all four sample sources,
determinism, a deliberately-malformed-source robustness test, and a
**gold-profile comparison** (`tests/test_gold.py` vs `tests/gold/default_profiles.json`)
that pins the full default output against a reviewed snapshot.

## Assumptions & deliberately descoped

- **Assumptions:** a US default region for phones without a country code; one
  recruiter CSV row = one person; profile URLs are reliable identity signals.
- **Descoped under time pressure:** LinkedIn source; ML/NLP resume parsing (we
  use high-precision heuristics and intentionally do not parse free-form job
  history out of prose); live GitHub (fixture-cached); fuzzy-name matching; any
  UI beyond the CLI.

## Layout

```
candidate_transformer/   engine (sources/, normalize/, merge, confidence,
                         projection, config, validation, pipeline, cli)
samples/inputs/          sample CSV, ATS JSON, resume, GitHub fixture
samples/configs/         default.json, custom.json
samples/outputs/         produced output (generated by the run commands above)
tests/                   unit + end-to-end tests
docs/DESIGN.md           Stage 1 one-page design
```
