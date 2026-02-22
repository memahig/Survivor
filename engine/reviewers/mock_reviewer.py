#!/usr/bin/env python3
"""
FILE: engine/reviewers/mock_reviewer.py
VERSION: 0.2
PURPOSE:
Deterministic mock reviewer for pipeline wiring and validator testing.

v0.2 CHANGE:
- In Phase 2, adds near_duplicate_of links deterministically based on claim text similarity.
"""

from __future__ import annotations

from typing import Any, Dict, List

from engine.reviewers.base import ReviewerInputs
from engine.core.near_duplicates import build_edges_from_claim_texts


class MockReviewer:
    def __init__(self, name: str) -> None:
        self.name = name  # "openai" | "gemini" | "claude"

    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        claims = [
            {
                "claim_id": f"{self.name}-CL-01",
                "text": "The article makes a central claim.",
                "type": "factual",
                "evidence_eids": ["E1"],
                "centrality": 3,
            },
            {
                "claim_id": f"{self.name}-CL-02",
                "text": "The article implies a causal relationship.",
                "type": "causal",
                "evidence_eids": ["E2"],
                "centrality": 2,
            },
        ]

        pack: Dict[str, Any] = {
            "reviewer": self.name,
            "whole_article_judgment": {
                "classification": "analysis",
                "confidence": "medium",
                "evidence_eids": ["E1", "E2"],
            },
            "main_conclusion": {
                "text": "Main conclusion placeholder.",
                "evidence_eids": ["E1"],
                "confidence": "medium",
            },
            "claims": claims,
            "scope_markers": [
                {"text": "greatest", "marker_type": "greatest", "evidence_eids": ["E1"]}
            ],
            "causal_links": [
                {
                    "from_claim_id": claims[0]["claim_id"],
                    "to_claim_id": claims[1]["claim_id"],
                    "evidence_eids": ["E2"],
                }
            ],
            "article_patterns": [
                {"pattern_type": "conclusion_exceeds_premises", "evidence_eids": ["E1", "E2"]}
            ],
            "omission_candidates": [
                {
                    "missing_frame": "Relevant comparative data",
                    "reason_expected": "Would test the conclusion",
                    "confidence": "low",
                }
            ],
            "counterfactual_requirements": [
                {
                    "target_claim_id": claims[0]["claim_id"],
                    "counterfactual_type": "weakening",
                    "measurable_type": "dataset",
                    "description": "A dataset that compares outcomes across relevant groups/time periods.",
                    "why_it_changes_confidence": "Would test whether the generalization holds.",
                    "confidence": "medium",
                }
            ],
            "evidence_density": {
                "claims_count": len(claims),
                "claims_with_internal_support": 2,
                "external_sources_count": 0,
            },
            "cross_claim_votes": [],
            "claim_tickets": [],
            "article_tickets": [],
        }
        return pack

    def run_phase2(self, inp: ReviewerInputs, cross_review_payload: Dict[str, Any]) -> Dict[str, Any]:
        phase1 = cross_review_payload["phase1_outputs"]
        my_phase1 = phase1[self.name]

        # Build master claim index from ALL reviewers
        claim_index: Dict[str, Dict[str, Any]] = {}
        for m, pack in phase1.items():
            for c in pack["claims"]:
                claim_index[c["claim_id"]] = c

        # Deterministic near-duplicate edges by text similarity
        cfg = cross_review_payload.get("config", {})
        threshold = float(cfg.get("near_duplicate_similarity_threshold", 0.92))
        max_links = int(cfg.get("max_near_duplicate_links", 3))
        edges = build_edges_from_claim_texts(claim_index, threshold=threshold, max_links_per_claim=max_links)

        # Convert edges into near_duplicate_of lists
        nd_map: Dict[str, List[str]] = {cid: [] for cid in claim_index.keys()}
        for a, b in edges:
            if b not in nd_map[a]:
                nd_map[a].append(b)
            if a not in nd_map[b]:
                nd_map[b].append(a)

        # Cross-claim votes over all claims, with near-duplicate links when present
        all_claim_ids = sorted(claim_index.keys())
        cross_votes = []
        for cid in all_claim_ids:
            v: Dict[str, Any] = {
                "claim_id": cid,
                "exists_as_real_claim": True,
                "is_material_to_argument": True,
                "vote": "supported",
                "confidence": "medium",
                "centrality": 2 if cid.endswith("02") else 3,
            }
            if nd_map.get(cid):
                v["near_duplicate_of"] = sorted(nd_map[cid])[:max_links]
            cross_votes.append(v)

        out = dict(my_phase1)
        out["cross_claim_votes"] = cross_votes
        return out