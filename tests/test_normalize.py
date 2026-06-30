"""Unit tests for the normalizers, including the edge cases from the design."""

from candidate_transformer.normalize import (
    canonicalize_skill,
    to_country_alpha2,
    to_e164,
    to_year_month,
)


def test_phone_e164_variants_normalize_equal():
    assert to_e164("(415) 555-0132") == "+14155550132"
    assert to_e164("+1 415 555 0132") == "+14155550132"


def test_unparseable_phone_is_none_not_invented():
    assert to_e164("not-a-phone") is None
    assert to_e164("") is None
    assert to_e164(None) is None


def test_partial_date_keeps_year_only():
    assert to_year_month("2021") == "2021"
    assert to_year_month("Jan 2017") == "2017-01"
    assert to_year_month("2020-03") == "2020-03"
    assert to_year_month("present") is None


def test_skill_synonyms_canonicalize():
    assert canonicalize_skill("js") == "JavaScript"
    assert canonicalize_skill("react.js") == "React"
    assert canonicalize_skill("postgres") == "PostgreSQL"


def test_unknown_skill_is_kept_not_dropped():
    assert canonicalize_skill("Rust") == "Rust"


def test_country_to_alpha2():
    assert to_country_alpha2("United States") == "US"
    assert to_country_alpha2("india") == "IN"
    assert to_country_alpha2("Atlantis") is None
