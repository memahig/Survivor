#!/usr/bin/env python3
"""
FILE: tests/test_report_generator.py
PURPOSE:
Tests for engine/report/generator.py (Milestone R1).

Coverage:
  1. test_generator_deterministic_ordering         — identical inputs -> identical output
  2. test_generator_includes_all_groups_and_fields — all required fields present per group
  3. test_generator_embeds_evidence_snippets_exactly — snippets verbatim from EvidenceBank
  4. test_generator_omits_optional_meta_fields_when_absent — meta absent when not in run_state

Additional tests:
  - meta included when present
  - summary counts correct
  - overall_status priority logic
  - high_risk_flags_count
  - flags omitted from group when empty, present when non-empty
  - appendix evidence_index sorted and complete
  - appendix reviewer_index sorted, model_weight present
  - reviewer_notes included when configured
  - empty adjudicated_claims produces empty groups + overall_status=insufficient
  - multiple groups sorted by group_id

Run with: python -m pytest tests/ -v
"""

import copy

import pytest

from engine.report.generator import generate_report


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_EVIDENCE_ITEMS = [
    {
        "eid": "E1",
        "quote": "First sentence of the article.",
        "locator": {"char_start": 0, "char_end": 30},
        "source_id": "A1",
        "text": "First sentence of the article.",
        "char_len": 30,
    },
    {
        "eid": "E2",
        "quote": "Second sentence of the article.",
        "locator": {"char_start": 31, "char_end": 62},
        "source_id": "A1",
        "text": "Second sentence of the article.",
        "char_len": 31,
    },
]

assert len("First sentence of the article.") == 30
assert len("Second sentence of the article.") == 31

_ADJUDICATED_CLAIMS = [
    {
        "group_id": "openai-CL-01",
        "member_claim_ids": ["openai-CL-01"],
        "canonical_text": "A factual claim.",
        "status": "kept",
        "wscore": 0.75,
        "evidence_union": ["E1"],
        "contributing_reviewers": ["openai"],
    },
    {
        "group_id": "openai-CL-02",
        "member_claim_ids": ["openai-CL-02"],
        "canonical_text": "A second claim.",
        "status": "insufficient",
        "wscore": 0.0,
        "evidence_union": ["E2"],
        "contributing_reviewers": ["openai"],
    },
]

_RUN_STATE = {
    "evidence_bank": {"items": copy.deepcopy(_EVIDENCE_ITEMS)},
    "phase2": {
        "openai": {
            "reviewer": "openai",
            "pillar_claims": [],
            "questionable_claims": [
                {
                    "claim_id": "openai-CL-01",
                    "text": "A factual claim.",
                    "type": "factual",
                    "evidence_eids": ["E1"],
                    "centrality": 1,
                },
                {
                    "claim_id": "openai-CL-02",
                    "text": "A second claim.",
                    "type": "causal",
                    "evidence_eids": ["E2"],
                    "centrality": 2,
                },
            ],
            "background_claims_summary": {"total_claims_estimate": 2, "not_triaged_count": 0},
            "cross_claim_votes": [],
        }
    },
    "adjudicated_claims": copy.deepcopy(_ADJUDICATED_CLAIMS),
}

_CFG = {
    "reviewers_enabled": ["openai"],
    "model_weights": {"openai": 1.0},
    "confidence_weights": {"low": 0.5, "medium": 1.0, "high": 1.5},
    "max_claims_per_reviewer": 20,
    "max_near_duplicate_links": 3,
    "decision_margin": 0.2,
}

_REQUIRED_GROUP_FIELDS = {
    "group_id",
    "member_claim_ids",
    "canonical_text",
    "status",
    "wscore",
    "evidence_union",
    "evidence_snippets",
    "contributing_reviewers",
}

_REQUIRED_SNIPPET_FIELDS = {"eid", "quote", "locator", "source_id"}


# ---------------------------------------------------------------------------
# 1. Deterministic ordering
# ---------------------------------------------------------------------------


def test_generator_deterministic_ordering():
    """Same inputs called twice must produce identical output."""
    r1 = generate_report(copy.deepcopy(_RUN_STATE), copy.deepcopy(_CFG))
    r2 = generate_report(copy.deepcopy(_RUN_STATE), copy.deepcopy(_CFG))
    assert r1 == r2


# ---------------------------------------------------------------------------
# 2. All groups and required fields present
# ---------------------------------------------------------------------------


def test_generator_includes_all_groups_and_fields():
    """Every adjudicated group must appear with all required fields."""
    report = generate_report(_RUN_STATE, _CFG)
    groups = report["groups"]
    assert len(groups) == len(_ADJUDICATED_CLAIMS)

    for g in groups:
        for field in _REQUIRED_GROUP_FIELDS:
            assert field in g, f"missing field {field!r} in group {g.get('group_id')!r}"


def test_generator_groups_sorted_by_group_id():
    """groups must be sorted ascending by group_id."""
    run = copy.deepcopy(_RUN_STATE)
    # Reverse the input ordering to confirm sorting is applied
    run["adjudicated_claims"] = list(reversed(copy.deepcopy(_ADJUDICATED_CLAIMS)))
    report = generate_report(run, _CFG)
    ids = [g["group_id"] for g in report["groups"]]
    assert ids == sorted(ids)


def test_generator_member_claim_ids_sorted():
    """member_claim_ids in each group must be sorted."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["member_claim_ids"] = ["zz-claim", "aa-claim"]
    report = generate_report(run, _CFG)
    g = report["groups"][0]
    assert g["member_claim_ids"] == sorted(g["member_claim_ids"])


def test_generator_evidence_union_sorted():
    """evidence_union in each group must be sorted."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["evidence_union"] = ["E2", "E1"]
    run["evidence_bank"]["items"] = copy.deepcopy(_EVIDENCE_ITEMS)
    report = generate_report(run, _CFG)
    g = report["groups"][0]
    assert g["evidence_union"] == sorted(g["evidence_union"])


def test_generator_contributing_reviewers_sorted():
    """contributing_reviewers in each group must be sorted."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["contributing_reviewers"] = ["openai", "gemini"]
    report = generate_report(run, _CFG)
    g = report["groups"][0]
    assert g["contributing_reviewers"] == sorted(g["contributing_reviewers"])


# ---------------------------------------------------------------------------
# 3. Evidence snippets verbatim from EvidenceBank
# ---------------------------------------------------------------------------


def test_generator_embeds_evidence_snippets_exactly():
    """
    Evidence snippets must exactly match the EvidenceBank:
    verbatim quote, exact locator, exact source_id.
    Snippet dicts must have exactly the 4 canonical fields.
    """
    report = generate_report(_RUN_STATE, _CFG)

    # Build eid -> item lookup from fixture
    eid_lookup = {it["eid"]: it for it in _EVIDENCE_ITEMS}

    for g in report["groups"]:
        for snippet in g["evidence_snippets"]:
            eid = snippet["eid"]
            original = eid_lookup.get(eid)
            assert original is not None, f"snippet eid {eid!r} not in fixture evidence items"
            assert snippet["quote"] == original["quote"], f"quote mismatch for {eid!r}"
            assert snippet["locator"] == original["locator"], f"locator mismatch for {eid!r}"
            assert snippet["source_id"] == original["source_id"], f"source_id mismatch for {eid!r}"
            # Exactly these 4 fields — no extras (no text alias, no char_len)
            assert set(snippet.keys()) == _REQUIRED_SNIPPET_FIELDS, (
                f"snippet for {eid!r} has unexpected fields: {set(snippet.keys())}"
            )


def test_generator_evidence_snippets_ordered_by_evidence_union():
    """evidence_snippets must appear in the same order as evidence_union (sorted)."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["evidence_union"] = ["E2", "E1"]
    run["evidence_bank"]["items"] = copy.deepcopy(_EVIDENCE_ITEMS)
    report = generate_report(run, _CFG)
    g = report["groups"][0]
    snippet_eids = [s["eid"] for s in g["evidence_snippets"]]
    assert snippet_eids == g["evidence_union"]  # both should be sorted


# ---------------------------------------------------------------------------
# 4. Meta section omitted when absent
# ---------------------------------------------------------------------------


def test_generator_omits_optional_meta_fields_when_absent():
    """
    meta must be omitted entirely when run_id, created_at, and version
    are all absent from run_state.
    """
    run = copy.deepcopy(_RUN_STATE)
    # Ensure none of the meta keys are present
    for k in ("run_id", "created_at", "version"):
        run.pop(k, None)
    report = generate_report(run, _CFG)
    assert "meta" not in report, "meta must be absent when no meta fields are in run_state"


def test_generator_includes_meta_when_run_id_present():
    """meta must appear when run_id is in run_state."""
    run = copy.deepcopy(_RUN_STATE)
    run["run_id"] = "test-run-001"
    report = generate_report(run, _CFG)
    assert "meta" in report
    assert report["meta"]["run_id"] == "test-run-001"
    assert "created_at" not in report["meta"]
    assert "version" not in report["meta"]


def test_generator_includes_meta_partial_fields():
    """meta includes only the fields actually present in run_state."""
    run = copy.deepcopy(_RUN_STATE)
    run["version"] = "1.0"
    run["created_at"] = "2026-02-24T00:00:00Z"
    report = generate_report(run, _CFG)
    assert report["meta"]["version"] == "1.0"
    assert report["meta"]["created_at"] == "2026-02-24T00:00:00Z"
    assert "run_id" not in report["meta"]


# ---------------------------------------------------------------------------
# Summary invariants
# ---------------------------------------------------------------------------


def test_generator_summary_counts_correct():
    """counts_by_status must correctly count groups by status."""
    report = generate_report(_RUN_STATE, _CFG)
    counts = report["summary"]["counts_by_status"]
    assert counts.get("kept", 0) == 1
    assert counts.get("insufficient", 0) == 1


def test_generator_summary_counts_sorted_keys():
    """counts_by_status keys must be sorted."""
    report = generate_report(_RUN_STATE, _CFG)
    keys = list(report["summary"]["counts_by_status"].keys())
    assert keys == sorted(keys)


def test_generator_overall_status_worst_case():
    """overall_status reflects worst-case: rejected > downgraded > kept > insufficient."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["status"] = "rejected"
    run["adjudicated_claims"][1]["status"] = "kept"
    report = generate_report(run, _CFG)
    assert report["summary"]["overall_status"] == "rejected"


def test_generator_overall_status_downgraded_beats_kept():
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["status"] = "downgraded"
    run["adjudicated_claims"][1]["status"] = "kept"
    report = generate_report(run, _CFG)
    assert report["summary"]["overall_status"] == "downgraded"


def test_generator_overall_status_all_kept():
    run = copy.deepcopy(_RUN_STATE)
    for g in run["adjudicated_claims"]:
        g["status"] = "kept"
    report = generate_report(run, _CFG)
    assert report["summary"]["overall_status"] == "kept"


def test_generator_overall_status_empty_claims():
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"] = []
    report = generate_report(run, _CFG)
    assert report["summary"]["overall_status"] == "insufficient"
    assert report["summary"]["counts_by_status"] == {}
    assert report["groups"] == []


def test_generator_high_risk_flags_count():
    """high_risk_flags_count must reflect groups with high_structural_risk."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["flags"] = ["high_structural_risk"]
    report = generate_report(run, _CFG)
    assert report["summary"]["high_risk_flags_count"] == 1


# ---------------------------------------------------------------------------
# Flags in groups
# ---------------------------------------------------------------------------


def test_generator_flags_key_absent_when_empty():
    """flags key must not appear in group dict when flags list is empty."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0].pop("flags", None)
    report = generate_report(run, _CFG)
    g = report["groups"][0]
    assert "flags" not in g


def test_generator_flags_key_present_when_nonempty():
    """flags key must appear when group has flags."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["flags"] = ["high_structural_risk"]
    report = generate_report(run, _CFG)
    g = next(x for x in report["groups"] if x["group_id"] == "openai-CL-01")
    assert g["flags"] == ["high_structural_risk"]


# ---------------------------------------------------------------------------
# Appendix invariants
# ---------------------------------------------------------------------------


def test_generator_appendix_evidence_index_complete():
    """appendix.evidence_index must include all EvidenceBank items."""
    report = generate_report(_RUN_STATE, _CFG)
    index = report["appendix"]["evidence_index"]
    assert len(index) == len(_EVIDENCE_ITEMS)
    index_eids = {e["eid"] for e in index}
    fixture_eids = {e["eid"] for e in _EVIDENCE_ITEMS}
    assert index_eids == fixture_eids


def test_generator_appendix_evidence_index_sorted_by_eid():
    """appendix.evidence_index must be sorted by eid."""
    report = generate_report(_RUN_STATE, _CFG)
    eids = [e["eid"] for e in report["appendix"]["evidence_index"]]
    assert eids == sorted(eids)


def test_generator_appendix_evidence_index_fields_only():
    """appendix.evidence_index entries must have exactly the 4 canonical fields."""
    report = generate_report(_RUN_STATE, _CFG)
    for entry in report["appendix"]["evidence_index"]:
        assert set(entry.keys()) == _REQUIRED_SNIPPET_FIELDS


def test_generator_appendix_reviewer_index_sorted():
    """appendix.reviewer_index must be sorted by reviewer name."""
    cfg = copy.deepcopy(_CFG)
    cfg["reviewers_enabled"] = ["openai", "gemini", "claude"]
    cfg["model_weights"]["gemini"] = 0.8
    cfg["model_weights"]["claude"] = 1.2
    report = generate_report(_RUN_STATE, cfg)
    names = [r["reviewer"] for r in report["appendix"]["reviewer_index"]]
    assert names == sorted(names)


def test_generator_appendix_reviewer_index_model_weight():
    """appendix.reviewer_index entries must include correct model_weight."""
    report = generate_report(_RUN_STATE, _CFG)
    idx = {e["reviewer"]: e for e in report["appendix"]["reviewer_index"]}
    assert idx["openai"]["model_weight"] == 1.0


def test_generator_appendix_reviewer_notes_included_when_configured():
    """notes must appear in reviewer_index entry when reviewer_notes is in config."""
    cfg = copy.deepcopy(_CFG)
    cfg["reviewer_notes"] = {"openai": "GPT-4o snapshot 2026-01"}
    report = generate_report(_RUN_STATE, cfg)
    idx = {e["reviewer"]: e for e in report["appendix"]["reviewer_index"]}
    assert idx["openai"].get("notes") == "GPT-4o snapshot 2026-01"


def test_generator_appendix_reviewer_notes_absent_when_not_configured():
    """notes must not appear when reviewer_notes absent from config."""
    report = generate_report(_RUN_STATE, _CFG)
    for entry in report["appendix"]["reviewer_index"]:
        assert "notes" not in entry


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_generator_missing_eid_in_evidence_bank_skips_gracefully():
    """
    If evidence_union references an eid not in EvidenceBank, the generator
    skips that eid silently (does not raise).
    """
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["evidence_union"] = ["E1", "E999"]
    report = generate_report(run, _CFG)
    g = next(x for x in report["groups"] if x["group_id"] == "openai-CL-01")
    snippet_eids = {s["eid"] for s in g["evidence_snippets"]}
    assert "E1" in snippet_eids
    assert "E999" not in snippet_eids


def test_generator_canonical_text_none_preserved():
    """canonical_text=None must be preserved as None in output (no substitution)."""
    run = copy.deepcopy(_RUN_STATE)
    run["adjudicated_claims"][0]["canonical_text"] = None
    report = generate_report(run, _CFG)
    g = next(x for x in report["groups"] if x["group_id"] == "openai-CL-01")
    assert g["canonical_text"] is None


def test_generator_raises_on_non_dict_run_state():
    with pytest.raises(RuntimeError):
        generate_report("not-a-dict", _CFG)


def test_generator_top_level_keys():
    """Report must have summary, groups, appendix. meta absent when not in run_state."""
    report = generate_report(_RUN_STATE, _CFG)
    assert "summary" in report
    assert "groups" in report
    assert "appendix" in report
    assert "meta" not in report
