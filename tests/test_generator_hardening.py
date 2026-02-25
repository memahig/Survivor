#!/usr/bin/env python3
"""
tests/test_generator_hardening.py
Adversarial hardening tests for engine/report/generator.py v0.1.1

GH1  — missing evidence_bank raises RuntimeError
GH2  — missing adjudicated_claims raises RuntimeError
GH2b — missing phase2 raises RuntimeError
GH3  — evidence_bank not dict raises RuntimeError
GH4  — evidence_bank.items not list raises RuntimeError
GH5  — adjudicated_claims not list raises RuntimeError
GH6a — group_id missing raises RuntimeError
GH6b — group_id empty string raises RuntimeError
GH6c — group_id non-str raises RuntimeError
GH7  — member_claim_ids not list raises RuntimeError (pins sorted("str") fix)
GH8  — evidence_union not list raises RuntimeError
GH9  — contributing_reviewers not list raises RuntimeError
GH10a — ev item missing quote raises RuntimeError
GH10b — ev item missing locator raises RuntimeError
GH10c — ev item locator not dict raises RuntimeError
GH10d — ev item missing source_id raises RuntimeError
GH11a — malformed ev item (empty eid) raises RuntimeError in pre-pass
GH11b — unknown eid in evidence_union skips gracefully (no RuntimeError)
Extra — duplicate eid in ev_items raises RuntimeError
Extra — status missing from group raises RuntimeError
Extra — wscore non-numeric raises RuntimeError
"""

import pytest

from engine.report.generator import generate_report


BASE_CFG = {
    "reviewers_enabled": [],
    "model_weights": {},
    "reviewer_notes": {},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ev(eid="e1", quote="verbatim quote text", locator=None, source_id="s1"):
    """Build a minimal valid evidence item."""
    return {
        "eid": eid,
        "quote": quote,
        "locator": locator if locator is not None else {"page": 1},
        "source_id": source_id,
    }


def _grp(group_id="g1", status="kept", **kwargs):
    """Build a minimal valid adjudicated group dict."""
    g = {
        "group_id": group_id,
        "member_claim_ids": ["c1"],
        "canonical_text": None,
        "status": status,
        "wscore": 0.8,
        "evidence_union": ["e1"],
        "contributing_reviewers": ["r1"],
    }
    g.update(kwargs)
    return g


def _run(**overrides):
    """Build a minimal valid run_state; apply overrides."""
    base = {
        "evidence_bank": {"items": [_ev()]},
        "phase2": {},
        "adjudicated_claims": [_grp()],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# GH1: missing evidence_bank
# ---------------------------------------------------------------------------


def test_gh1_missing_evidence_bank_raises():
    run = {"phase2": {}, "adjudicated_claims": []}
    with pytest.raises(RuntimeError, match="evidence_bank"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH2: missing adjudicated_claims
# ---------------------------------------------------------------------------


def test_gh2_missing_adjudicated_claims_raises():
    run = {"evidence_bank": {"items": []}, "phase2": {}}
    with pytest.raises(RuntimeError, match="adjudicated_claims"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH2b: missing phase2
# ---------------------------------------------------------------------------


def test_gh2b_missing_phase2_raises():
    run = {"evidence_bank": {"items": []}, "adjudicated_claims": []}
    with pytest.raises(RuntimeError, match="phase2"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH3: evidence_bank not dict
# ---------------------------------------------------------------------------


def test_gh3_evidence_bank_not_dict_raises():
    run = _run(evidence_bank="oops")
    with pytest.raises(RuntimeError, match="evidence_bank"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH4: evidence_bank.items not list
# ---------------------------------------------------------------------------


def test_gh4_evidence_bank_items_not_list_raises():
    run = _run(evidence_bank={"items": 42})
    with pytest.raises(RuntimeError, match="items"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH5: adjudicated_claims not list
# ---------------------------------------------------------------------------


def test_gh5_adjudicated_claims_not_list_raises():
    run = _run(adjudicated_claims="bad")
    with pytest.raises(RuntimeError, match="adjudicated_claims"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH6: group_id variants
# ---------------------------------------------------------------------------


def test_gh6a_group_id_missing_raises():
    grp = _grp()
    del grp["group_id"]
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="group_id"):
        generate_report(run, BASE_CFG)


def test_gh6b_group_id_empty_string_raises():
    run = _run(adjudicated_claims=[_grp(group_id="")])
    with pytest.raises(RuntimeError, match="group_id"):
        generate_report(run, BASE_CFG)


def test_gh6c_group_id_non_str_raises():
    run = _run(adjudicated_claims=[_grp(group_id=42)])
    with pytest.raises(RuntimeError):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH7: member_claim_ids must be a list (pins sorted("string") fix)
# ---------------------------------------------------------------------------


def test_gh7_member_claim_ids_string_raises():
    grp = _grp()
    grp["member_claim_ids"] = "not-a-list"
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="member_claim_ids"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH8: evidence_union must be a list
# ---------------------------------------------------------------------------


def test_gh8_evidence_union_string_raises():
    grp = _grp()
    grp["evidence_union"] = "not-a-list"
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="evidence_union"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH9: contributing_reviewers must be a list
# ---------------------------------------------------------------------------


def test_gh9_contributing_reviewers_string_raises():
    grp = _grp()
    grp["contributing_reviewers"] = "not-a-list"
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="contributing_reviewers"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH10: EvidenceBank item field validation
# ---------------------------------------------------------------------------


def test_gh10a_ev_item_missing_quote_raises():
    item = _ev()
    del item["quote"]
    run = _run(evidence_bank={"items": [item]}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="quote"):
        generate_report(run, BASE_CFG)


def test_gh10b_ev_item_missing_locator_raises():
    item = _ev()
    del item["locator"]
    run = _run(evidence_bank={"items": [item]}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="locator"):
        generate_report(run, BASE_CFG)


def test_gh10c_ev_item_locator_not_dict_raises():
    item = _ev(locator="page:1")
    run = _run(evidence_bank={"items": [item]}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="locator"):
        generate_report(run, BASE_CFG)


def test_gh10d_ev_item_missing_source_id_raises():
    item = _ev()
    del item["source_id"]
    run = _run(evidence_bank={"items": [item]}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="source_id"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# GH11: malformed eid and unknown eid
# ---------------------------------------------------------------------------


def test_gh11a_empty_eid_in_ev_items_raises():
    """Empty eid fails upfront validation in the pre-pass -> RuntimeError."""
    item = {"eid": "", "quote": "q", "locator": {"page": 1}, "source_id": "s1"}
    run = _run(evidence_bank={"items": [item]}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="eid"):
        generate_report(run, BASE_CFG)


def test_gh11b_unknown_eid_in_evidence_union_skips_gracefully():
    """eid referenced by evidence_union but absent from ev_items -> skipped silently."""
    grp = _grp(evidence_union=["e_unknown"])
    run = _run(
        evidence_bank={"items": [_ev(eid="e1")]},
        adjudicated_claims=[grp],
    )
    report = generate_report(run, BASE_CFG)
    snippets = report["groups"][0]["evidence_snippets"]
    assert snippets == []


# ---------------------------------------------------------------------------
# Extra: duplicate eid in ev_items
# ---------------------------------------------------------------------------


def test_extra_duplicate_eid_in_ev_items_raises():
    """Duplicate eid values in evidence_bank.items -> RuntimeError (fail-closed)."""
    items = [_ev(eid="dup"), _ev(eid="dup", quote="different quote")]
    run = _run(evidence_bank={"items": items}, adjudicated_claims=[])
    with pytest.raises(RuntimeError, match="duplicate"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# Extra: status missing from group
# ---------------------------------------------------------------------------


def test_extra_status_missing_from_group_raises():
    """status is required; absent -> RuntimeError."""
    grp = _grp()
    del grp["status"]
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="status"):
        generate_report(run, BASE_CFG)


# ---------------------------------------------------------------------------
# Extra: wscore non-numeric
# ---------------------------------------------------------------------------


def test_extra_wscore_non_numeric_raises():
    """Non-numeric wscore -> RuntimeError (fail-closed)."""
    grp = _grp(wscore="not-a-number")
    run = _run(adjudicated_claims=[grp])
    with pytest.raises(RuntimeError, match="wscore"):
        generate_report(run, BASE_CFG)
