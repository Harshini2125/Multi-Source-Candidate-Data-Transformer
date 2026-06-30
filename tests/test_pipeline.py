"""End-to-end pipeline tests against the sample inputs, plus robustness."""

from candidate_transformer.config import DEFAULT_CONFIG, OutputConfig
from candidate_transformer.pipeline import build_canonical_profiles, run


def _jane(profiles):
    return next(p for p in profiles if p.full_name == "Jane Doe")


def test_jane_is_merged_across_all_four_sources(samples_inputs):
    profiles = build_canonical_profiles(samples_inputs)
    jane = _jane(profiles)
    # Every source contributed to provenance.
    sources = {p.source for p in jane.provenance}
    assert sources == {"recruiter_csv", "ats_json", "resume", "github"}


def test_phone_normalized_and_deduped(samples_inputs):
    jane = _jane(build_canonical_profiles(samples_inputs))
    # CSV "(415) 555-0132" and ATS "+1 415 555 0132" collapse to one E.164 value.
    assert jane.phones == ["+14155550132"]


def test_skills_canonicalized_with_sources(samples_inputs):
    jane = _jane(build_canonical_profiles(samples_inputs))
    names = {s.name for s in jane.skills}
    assert {"Python", "JavaScript", "React", "PostgreSQL"} <= names
    python = next(s for s in jane.skills if s.name == "Python")
    # Asserted by multiple sources -> confidence above any single source weight.
    assert python.confidence > 0.9
    assert len(python.sources) >= 2


def test_invalid_phone_is_honestly_empty(samples_inputs):
    profiles = build_canonical_profiles(samples_inputs)
    john = next(p for p in profiles if p.full_name == "John Smith")
    assert john.phones == []  # "not-a-phone" -> dropped, never invented


def test_deterministic_output(samples_inputs):
    a = run(samples_inputs, DEFAULT_CONFIG)
    b = run(samples_inputs, DEFAULT_CONFIG)
    assert a == b


def test_default_output_is_schema_valid(samples_inputs):
    results = run(samples_inputs, DEFAULT_CONFIG, validate=True)
    assert len(results) == 2
    for r in results:
        assert "candidate_id" in r and r["candidate_id"]


def test_custom_config_projection(samples_inputs):
    config = OutputConfig.load(
        samples_inputs.parent / "configs" / "custom.json"
    )
    results = run(samples_inputs, config, validate=True)
    jane = next(r for r in results if r["full_name"] == "Jane Doe")
    assert jane["primary_email"] == "jane.doe@example.com"
    assert jane["phone"] == "+14155550132"
    assert "provenance" not in jane  # toggled off in custom.json


def test_garbage_source_does_not_crash(tmp_path):
    # A directory of malformed files must still produce a (possibly empty) run.
    (tmp_path / "broken.json").write_text("{ not valid json ", encoding="utf-8")
    (tmp_path / "broken.csv").write_text("\x00\x01 garbage", encoding="utf-8")
    results = run(tmp_path, DEFAULT_CONFIG, validate=True)
    assert isinstance(results, list)
