"""
engine/eo/gsae_apply.py  v0.1 — GSAE Quarantine Application

Applies Tier C quarantine decisions to phase2 reviewer packs before
adjudication consumes them.

On QUARANTINE: removes the entire gsae_observation block from the
affected reviewer's pack (optional key deletion). This is the safest
fail-closed behavior without enum expansion.

Does NOT downweight entire ReviewerPack.
Does NOT mutate the original phase2_outputs dict (returns a shallow copy).
No I/O. Deterministic.

Trilateral session: 2026-03-01
Authorized by: ChatGPT (Coordinator), Gemini (Structural Critic), Claude (Code Author)
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional


def apply_gsae_quarantine(
    phase2_outputs: Dict[str, Dict[str, Any]],
    gsae_block: Optional[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Apply Tier C quarantine to phase2 reviewer packs.

    Returns a sanitized copy of phase2_outputs. Original is not mutated.

    For each GSAE artifact with symmetry_status == "QUARANTINE",
    removes "gsae_observation" from the corresponding reviewer's pack.

    If gsae_block is None or has no artifacts, returns phase2_outputs unchanged.
    """
    if gsae_block is None:
        return phase2_outputs

    artifacts = gsae_block.get("artifacts", [])
    pairs = gsae_block.get("packet_pairs", [])

    if not artifacts:
        return phase2_outputs

    # Build set of reviewers to quarantine.
    # Artifacts are ordered by extract_gsae_observations (sorted reviewer keys).
    # We need to map artifact index → reviewer name.
    # The gsae_block doesn't store reviewer names directly, so we re-derive
    # the mapping from phase2_outputs in the same sorted order used by
    # extract_gsae_observations.
    sorted_reviewers_with_obs = []
    for name in sorted(phase2_outputs.keys()):
        pack = phase2_outputs[name]
        if isinstance(pack, dict) and "gsae_observation" in pack:
            sorted_reviewers_with_obs.append(name)

    quarantine_reviewers: set[str] = set()
    for i, art in enumerate(artifacts):
        if art.get("symmetry_status") == "QUARANTINE":
            if i < len(sorted_reviewers_with_obs):
                quarantine_reviewers.add(sorted_reviewers_with_obs[i])

    if not quarantine_reviewers:
        return phase2_outputs

    # Shallow copy of outer dict; deep copy only quarantined packs.
    sanitized = dict(phase2_outputs)
    for reviewer in quarantine_reviewers:
        if reviewer in sanitized:
            sanitized[reviewer] = copy.copy(sanitized[reviewer])
            sanitized[reviewer].pop("gsae_observation", None)

    return sanitized
