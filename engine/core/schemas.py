#!/usr/bin/env python3
"""
FILE: engine/core/schemas.py
VERSION: 0.1
PURPOSE:
Schema contracts for Survivor pipeline artifacts.

CONTRACT:
- These are *data-shape contracts* (dict schemas), not runtime business logic.
- Reviewers MUST conform. Validator fails closed if they don't.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


# ----------------------------
# Enums
# ----------------------------

Vote = Literal["supported", "unsupported", "undetermined"]
Confidence = Literal["low", "medium", "high"]

ArticleClassification = Literal[
    "analysis",
    "advocacy",
    "propaganda-patterned advocacy",
    "mixed",
    "uncertain",
]

ClaimType = Literal["factual", "causal", "normative", "predictive"]

MeasurableType = Literal[
    "dataset",
    "archival_document",
    "statistical_study",
    "legal_record",
    "historical_record",
]

CounterfactualType = Literal["falsifying", "weakening"]


# ----------------------------
# Core objects
# ----------------------------

class WholeArticleJudgment(TypedDict):
    classification: ArticleClassification
    confidence: Confidence
    evidence_eids: List[str]  # may be [] ONLY if classification == "uncertain"


class Claim(TypedDict):
    claim_id: str             # e.g., "openai-CL-01"
    text: str
    type: ClaimType
    evidence_eids: List[str]  # internal support in article (can be [])
    centrality: int           # 1|2|3


class ScopeMarker(TypedDict):
    text: str
    marker_type: str          # keep open in v0 (we can lock enum later)
    evidence_eids: List[str]


class CausalLink(TypedDict):
    from_claim_id: str
    to_claim_id: str
    evidence_eids: List[str]


class ArticlePattern(TypedDict):
    pattern_type: str         # keep open in v0 (we can lock enum later)
    evidence_eids: List[str]


class OmissionCandidate(TypedDict):
    missing_frame: str
    reason_expected: str
    confidence: Confidence


class CounterfactualRequirement(TypedDict):
    target_claim_id: str
    counterfactual_type: CounterfactualType
    measurable_type: MeasurableType
    description: str
    why_it_changes_confidence: str
    confidence: Confidence


class EvidenceDensity(TypedDict):
    claims_count: int
    claims_with_internal_support: int
    external_sources_count: int


# ----------------------------
# Voting on foreign claims
# ----------------------------

class CrossClaimVote(TypedDict, total=False):
    claim_id: str
    exists_as_real_claim: bool
    is_material_to_argument: bool
    vote: Vote
    confidence: Confidence
    centrality: int           # 1|2|3
    near_duplicate_of: List[str]  # optional, max length enforced by validator


# ----------------------------
# Tickets
# ----------------------------

class Ticket(TypedDict, total=False):
    ticket_id: str
    level: Literal["claim", "article"]
    category: str
    target_claim_id: Optional[str]     # for claim-linked tickets
    description: str
    evidence_eids: List[str]           # may be [] for absence-type tickets only
    reviewer_votes: Dict[str, Dict[str, str]]  # model -> {vote, confidence}
    adjudication: Literal["kept", "rejected", "downgraded"]


# ----------------------------
# ReviewerPack (Phase 1/2)
# ----------------------------

class ReviewerPack(TypedDict):
    reviewer: str  # "openai" | "gemini" | "claude"

    whole_article_judgment: WholeArticleJudgment

    # Structure extraction:
    main_conclusion: Dict[str, Any]            # keep open in v0; validator checks required keys
    claims: List[Claim]
    scope_markers: List[ScopeMarker]
    causal_links: List[CausalLink]
    article_patterns: List[ArticlePattern]
    omission_candidates: List[OmissionCandidate]
    counterfactual_requirements: List[CounterfactualRequirement]
    evidence_density: EvidenceDensity

    # Claim arena voting (Phase 2 must include; Phase 1 can omit or be empty):
    cross_claim_votes: List[CrossClaimVote]

    # Tickets:
    claim_tickets: List[Ticket]
    article_tickets: List[Ticket]