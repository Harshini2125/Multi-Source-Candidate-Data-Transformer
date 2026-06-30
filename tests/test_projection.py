"""Tests for the projection engine and path resolver."""

import pytest

from candidate_transformer.config import FieldSpec, OutputConfig
from candidate_transformer.projection import (
    MissingRequiredField,
    project,
    resolve,
)

PROFILE = {
    "candidate_id": "cand_x",
    "full_name": "Jane Doe",
    "emails": ["jane@example.com", "j.doe@work.com"],
    "phones": [],
    "location": {"city": "San Francisco", "country": "US"},
    "skills": [
        {"name": "Python", "confidence": 0.9, "sources": ["ats_json"]},
        {"name": "JavaScript", "confidence": 0.6, "sources": ["github"]},
    ],
    "overall_confidence": 0.8,
    "provenance": [{"field": "full_name", "source": "ats_json", "method": "x"}],
}


def test_resolve_index_nesting_and_wildcard():
    assert resolve(PROFILE, "emails[0]") == "jane@example.com"
    assert resolve(PROFILE, "location.city") == "San Francisco"
    assert resolve(PROFILE, "skills[].name") == ["Python", "JavaScript"]


def test_remap_and_field_selection():
    config = OutputConfig(
        fields=[
            FieldSpec("full_name", "string", required=True),
            FieldSpec("primary_email", "string", frm="emails[0]"),
            FieldSpec("skills", "string[]", frm="skills[].name"),
        ],
        include_confidence=False,
        include_provenance=False,
    )
    out = project(PROFILE, config)
    assert out == {
        "full_name": "Jane Doe",
        "primary_email": "jane@example.com",
        "skills": ["Python", "JavaScript"],
    }


def test_on_missing_null_omit_error():
    spec = [FieldSpec("phone", "string", frm="phones[0]")]

    null_cfg = OutputConfig(fields=spec, on_missing="null",
                            include_confidence=False, include_provenance=False)
    assert project(PROFILE, null_cfg) == {"phone": None}

    omit_cfg = OutputConfig(fields=spec, on_missing="omit",
                            include_confidence=False, include_provenance=False)
    assert project(PROFILE, omit_cfg) == {}

    err_cfg = OutputConfig(
        fields=[FieldSpec("phone", "string", frm="phones[0]", required=True)],
        on_missing="error", include_confidence=False, include_provenance=False,
    )
    with pytest.raises(MissingRequiredField):
        project(PROFILE, err_cfg)


def test_confidence_and_provenance_toggles():
    cfg = OutputConfig(
        fields=[FieldSpec("full_name", "string")],
        include_confidence=True, include_provenance=True,
    )
    out = project(PROFILE, cfg)
    assert out["overall_confidence"] == 0.8
    assert out["provenance"]
