#!/usr/bin/env python3
"""
Tests for engine/core/triage_utils.py — canonical triage-claim iteration helpers.
"""

from engine.core.triage_utils import iter_triage_claims, list_triage_claims


def test_iter_yields_pillar_then_questionable():
    pack = {
        "pillar_claims": [{"claim_id": "P1"}, {"claim_id": "P2"}],
        "questionable_claims": [{"claim_id": "Q1"}],
    }
    result = list(iter_triage_claims(pack))
    assert [c["claim_id"] for c in result] == ["P1", "P2", "Q1"]


def test_iter_empty_lists():
    pack = {"pillar_claims": [], "questionable_claims": []}
    assert list(iter_triage_claims(pack)) == []


def test_iter_missing_keys():
    assert list(iter_triage_claims({})) == []


def test_iter_skips_non_dict_items():
    pack = {
        "pillar_claims": [{"claim_id": "P1"}, "not_a_dict", None],
        "questionable_claims": [42, {"claim_id": "Q1"}],
    }
    result = list(iter_triage_claims(pack))
    assert [c["claim_id"] for c in result] == ["P1", "Q1"]


def test_list_triage_claims_returns_list():
    pack = {
        "pillar_claims": [{"claim_id": "P1"}],
        "questionable_claims": [{"claim_id": "Q1"}],
    }
    result = list_triage_claims(pack)
    assert isinstance(result, list)
    assert len(result) == 2


def test_list_triage_claims_on_empty_pack():
    assert list_triage_claims({}) == []


def test_iter_only_pillar():
    pack = {"pillar_claims": [{"claim_id": "P1"}]}
    assert [c["claim_id"] for c in iter_triage_claims(pack)] == ["P1"]


def test_iter_only_questionable():
    pack = {"questionable_claims": [{"claim_id": "Q1"}]}
    assert [c["claim_id"] for c in iter_triage_claims(pack)] == ["Q1"]


def test_iter_skips_missing_claim_id():
    pack = {
        "pillar_claims": [{"text": "no id"}, {"claim_id": "P1"}],
        "questionable_claims": [{"claim_id": "Q1"}],
    }
    assert [c["claim_id"] for c in iter_triage_claims(pack)] == ["P1", "Q1"]


def test_iter_skips_blank_claim_id():
    pack = {
        "pillar_claims": [{"claim_id": ""}, {"claim_id": "   "}, {"claim_id": "P1"}],
    }
    assert [c["claim_id"] for c in iter_triage_claims(pack)] == ["P1"]


def test_iter_skips_non_string_claim_id():
    pack = {
        "pillar_claims": [{"claim_id": 123}, {"claim_id": None}, {"claim_id": "P1"}],
    }
    assert [c["claim_id"] for c in iter_triage_claims(pack)] == ["P1"]
