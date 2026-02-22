#!/usr/bin/env python3
"""
FILE: engine/core/pipeline.py
VERSION: 0.1
PURPOSE:
Primary execution spine for Survivor.

FLOW:
Ingest → Normalize → EvidenceBank → Phase1 Reviewers →
Cross-Review Payload → Phase2 Reviewers →
Adjudication → Validation → Render Outputs
"""

from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any

from engine.core.config_loader import load_config
from engine.core.ingest import ingest_input
from engine.core.normalize import normalize_text
from engine.core.evidence_bank import build_evidence_bank
from engine.core.adjudicator import adjudicate
from engine.core.validators import validate_run
from engine.render.report import render_report
from engine.render.debug_report import render_debug

from engine.reviewers.mock_reviewer import MockReviewer
from engine.reviewers.base import ReviewerInputs


def run_pipeline(url: Optional[str], textfile: Optional[str], outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)

    config = load_config()

    article = ingest_input(url=url, textfile=textfile)
    normalized = normalize_text(article["text"])
    evidence_bank = build_evidence_bank(normalized, config)

    reviewers = [
        MockReviewer("openai"),
        MockReviewer("gemini"),
        MockReviewer("claude"),
    ]

    # ---------------------------
    # Phase 1
    # ---------------------------
    phase1_outputs = {}

    for reviewer in reviewers:
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        phase1_outputs[reviewer.name] = reviewer.run_phase1(inp)

    # ---------------------------
    # Cross-review payload
    # ---------------------------
    cross_payload = {
        "phase1_outputs": phase1_outputs,
        "config": config,
    }

    # ---------------------------
    # Phase 2
    # ---------------------------
    phase2_outputs = {}

    for reviewer in reviewers:
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        phase2_outputs[reviewer.name] = reviewer.run_phase2(
            inp,
            cross_payload,
        )

    # ---------------------------
    # Adjudication
    # ---------------------------
    adjudicated = adjudicate(phase2_outputs, config)

    run_state = {
        "article": article,
        "evidence_bank": evidence_bank,
        "phase1": phase1_outputs,
        "phase2": phase2_outputs,
        "adjudicated": adjudicated,
    }

    validate_run(run_state, config)

    # ---------------------------
    # Outputs
    # ---------------------------
    with open(os.path.join(outdir, "run.json"), "w") as f:
        json.dump(run_state, f, indent=2)

    # tickets.json (auditable artifact)
    with open(os.path.join(outdir, config["outputs"]["tickets_json"]), "w") as f:
        json.dump(adjudicated.get("final_tickets", []), f, indent=2)
        
    with open(os.path.join(outdir, "report.md"), "w") as f:
        f.write(render_report(run_state, config))

    with open(os.path.join(outdir, "debug.md"), "w") as f:
        f.write(render_debug(run_state, config))