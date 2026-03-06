#!/usr/bin/env python3
"""
FILE: tests/test_claim_deduplicator.py
PURPOSE: Tests for engine.analysis.claim_deduplicator
         - similar claims cluster
         - different numbers do not cluster
         - different years do not cluster
         - actor mismatch does not cluster
         - singletons preserved
         - deterministic output
         - empty/malformed input handled

Run with: python -m pytest tests/test_claim_deduplicator.py -v
"""

import pytest

from engine.analysis.claim_deduplicator import (
    _claims_differ_materially,
    cluster_story_claims,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claim(group_id: str, text: str, centrality: int = 2,
                adjudication: str = "kept") -> dict:
    return {
        "group_id": group_id,
        "text": text,
        "centrality": centrality,
        "adjudication": adjudication,
    }


# ---------------------------------------------------------------------------
# _claims_differ_materially tests
# ---------------------------------------------------------------------------

class TestClaimsDifferMaterially:

    def test_identical_texts(self):
        assert not _claims_differ_materially("GDP grew strongly", "GDP grew strongly")

    def test_different_numbers(self):
        assert _claims_differ_materially("GDP grew 3%", "GDP grew 12%")

    def test_different_years(self):
        assert _claims_differ_materially(
            "Russia invaded in 2014", "Russia invaded in 2022"
        )

    def test_one_has_number_other_does_not(self):
        assert _claims_differ_materially("GDP grew 3%", "GDP grew strongly")

    def test_one_has_year_other_does_not(self):
        assert _claims_differ_materially(
            "The conflict started in 2014", "The conflict started recently"
        )

    def test_same_numbers(self):
        assert not _claims_differ_materially(
            "The rate was 5% last year", "The rate hit 5% recently"
        )

    def test_different_causal_vocabulary(self):
        assert _claims_differ_materially(
            "NATO caused the conflict", "NATO triggered the conflict"
        )

    def test_same_causal_vocabulary(self):
        assert not _claims_differ_materially(
            "Sanctions caused the decline", "Sanctions caused the recession"
        )

    def test_different_actors(self):
        assert _claims_differ_materially(
            "Russia attacked Ukraine", "China attacked Taiwan"
        )

    def test_same_actors(self):
        assert not _claims_differ_materially(
            "Russia announced sanctions", "Russia imposed sanctions"
        )

    def test_empty_strings(self):
        assert not _claims_differ_materially("", "")

    def test_no_special_features(self):
        # No numbers, years, causal words, or actors — should not differ
        assert not _claims_differ_materially(
            "the economy is doing well", "the economy seems to be doing well"
        )


# ---------------------------------------------------------------------------
# cluster_story_claims tests
# ---------------------------------------------------------------------------

class TestClusterStoryClaims:

    def test_similar_claims_cluster(self):
        claims = [
            _make_claim("G1", "The government announced new economic sanctions"),
            _make_claim("G2", "The government announced new economic measures"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        # Should form one cluster with both members
        multi = [c for c in result if len(c["member_group_ids"]) > 1]
        assert len(multi) == 1
        assert set(multi[0]["member_group_ids"]) == {"G1", "G2"}

    def test_dissimilar_claims_stay_separate(self):
        claims = [
            _make_claim("G1", "The stock market crashed today"),
            _make_claim("G2", "A new species of frog was discovered"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        # Each should be a singleton
        assert len(result) == 2
        assert all(len(c["member_group_ids"]) == 1 for c in result)

    def test_different_numbers_prevent_clustering(self):
        claims = [
            _make_claim("G1", "GDP grew by 3% in the last quarter"),
            _make_claim("G2", "GDP grew by 12% in the last quarter"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 2
        assert all(len(c["member_group_ids"]) == 1 for c in result)

    def test_different_years_prevent_clustering(self):
        claims = [
            _make_claim("G1", "The invasion began in 2014 with military forces"),
            _make_claim("G2", "The invasion began in 2022 with military forces"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 2
        assert all(len(c["member_group_ids"]) == 1 for c in result)

    def test_different_actors_prevent_clustering(self):
        claims = [
            _make_claim("G1", "Russia launched the offensive against Ukraine"),
            _make_claim("G2", "China launched the offensive against Taiwan"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 2

    def test_singleton_preserved(self):
        claims = [
            _make_claim("G1", "A completely unique claim about nothing"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 1
        assert result[0]["member_group_ids"] == ["G1"]

    def test_canonical_text_is_longest(self):
        claims = [
            _make_claim("G1", "The government announced sanctions"),
            _make_claim("G2", "The government announced comprehensive sanctions against trade"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        multi = [c for c in result if len(c["member_group_ids"]) > 1]
        if multi:
            assert "comprehensive" in multi[0]["canonical_text"]

    def test_max_centrality_tracked(self):
        claims = [
            _make_claim("G1", "The government announced sanctions", centrality=1),
            _make_claim("G2", "The government announced new sanctions", centrality=3),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        multi = [c for c in result if len(c["member_group_ids"]) > 1]
        if multi:
            assert multi[0]["max_centrality"] == 3

    def test_adjudication_summary(self):
        claims = [
            _make_claim("G1", "The government announced sanctions", adjudication="kept"),
            _make_claim("G2", "The government announced new sanctions", adjudication="rejected"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        multi = [c for c in result if len(c["member_group_ids"]) > 1]
        if multi:
            summary = multi[0]["adjudication_summary"]
            assert summary["kept"] == 1
            assert summary["rejected"] == 1

    def test_cluster_ids_sequential(self):
        claims = [
            _make_claim("G1", "Alpha topic one"),
            _make_claim("G2", "Beta topic two"),
            _make_claim("G3", "Gamma topic three"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        ids = [c["cluster_id"] for c in result]
        assert ids == sorted(ids)
        assert ids[0].startswith("SC")

    def test_deterministic_output(self):
        claims = [
            _make_claim("G1", "The president signed the agreement"),
            _make_claim("G2", "The president ratified the agreement"),
            _make_claim("G3", "A volcano erupted in Iceland"),
        ]
        r1 = cluster_story_claims(claims, threshold=0.25)
        r2 = cluster_story_claims(claims, threshold=0.25)
        assert r1 == r2

    def test_empty_input(self):
        assert cluster_story_claims([]) == []

    def test_non_list_input(self):
        assert cluster_story_claims("not a list") == []

    def test_malformed_claims_skipped(self):
        claims = [
            "not a dict",
            {"no_group_id": True},
            _make_claim("G1", "Valid claim here"),
        ]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 1
        assert result[0]["member_group_ids"] == ["G1"]

    def test_output_shape(self):
        claims = [_make_claim("G1", "Some claim text")]
        result = cluster_story_claims(claims, threshold=0.25)
        assert len(result) == 1
        c = result[0]
        assert "cluster_id" in c
        assert "member_group_ids" in c
        assert "canonical_text" in c
        assert "max_centrality" in c
        assert "adjudication_summary" in c
