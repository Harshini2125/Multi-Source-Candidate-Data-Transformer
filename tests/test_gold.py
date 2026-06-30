"""Gold-profile comparison.

Pins the full default-schema output for the sample inputs against a reviewed
snapshot (``tests/gold/default_profiles.json``). Because the pipeline is
deterministic, any change to extraction, merge, normalization, confidence, or
projection that alters the canonical result will fail this test loudly — which
is exactly what we want for a transformer where "wrong-but-confident" is the
expensive failure mode.

The snapshot covers both an edge-case profile (John Smith: invalid phone -> null,
no skills/education) and a fully-merged profile (Jane Doe: four sources, deduped
phone, agreement-boosted skill confidence, complete provenance).

To regenerate intentionally after a deliberate change:
    python -m candidate_transformer.cli samples/inputs \
        --config samples/configs/default.json --out tests/gold/default_profiles.json
"""

import json
from pathlib import Path

from candidate_transformer.config import DEFAULT_CONFIG
from candidate_transformer.pipeline import run

GOLD = Path(__file__).parent / "gold" / "default_profiles.json"


def test_default_output_matches_gold(samples_inputs):
    expected = json.loads(GOLD.read_text(encoding="utf-8"))
    actual = run(samples_inputs, DEFAULT_CONFIG, validate=True)
    assert actual == expected
