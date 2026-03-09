"""
FILE: tests/test_mode_classifier.py
VERSION: 0.1.0
PURPOSE:
Tests for deterministic presented-mode classification.

BUILD MANIFEST: Stage 1 — Mode Spine.
"""

import pytest

from engine.analysis.mode_classifier import classify_mode


# ── canonical fixture: witness ────────────────────────────────────────

class TestWitnessMode:
    def test_classify_witness_breaking_news(self):
        text = """
        Police said the fire began at 2 a.m. According to witnesses,
        officials reported no injuries and confirmed the building was
        evacuated. A spokesperson told reporters the cause is under
        investigation.
        """
        result = classify_mode(text=text, title="Officials report overnight fire")
        assert result.presented_mode == "witness"

    def test_classify_witness_wire_report(self):
        text = """
        The president said Thursday that negotiations would continue.
        Officials confirmed the meeting took place at the White House.
        Sources say both sides reported progress but declined to give details.
        """
        result = classify_mode(text=text, title="Negotiations to continue")
        assert result.presented_mode == "witness"
        assert result.requires_reviewer_confirm is not None  # field exists


# ── canonical fixture: argument ───────────────────────────────────────

class TestArgumentMode:
    def test_classify_argument_editorial(self):
        text = """
        We must recognize that this policy clearly fails the people it
        claims to protect. Therefore lawmakers should reject it immediately.
        It is essential that we act now, without question.
        """
        result = classify_mode(text=text, title="Why this policy must end")
        assert result.presented_mode == "argument"

    def test_classify_argument_advocacy(self):
        text = """
        This proves that the current approach is undeniably flawed.
        We need to fundamentally rethink our strategy. The only way
        forward is to embrace reform. We must act decisively.
        """
        result = classify_mode(text=text)
        assert result.presented_mode == "argument"


# ── canonical fixture: proof ──────────────────────────────────────────

class TestProofMode:
    def test_classify_proof_research_paper(self):
        text = """
        In this study, we analyzed data from 500 participants using
        standard methods. The results show a statistically significant
        correlation. Our findings suggest the hypothesis is supported
        by the dataset.
        """
        result = classify_mode(text=text, title="A study of correlation effects")
        assert result.presented_mode == "proof"


# ── canonical fixture: rule ───────────────────────────────────────────

class TestRuleMode:
    def test_classify_rule_legal_text(self):
        text = """
        Pursuant to the statute, the court ruled that the regulation
        requires compliance with the amended procedure. The burden
        of proof falls on the defendant under this jurisdiction.
        """
        result = classify_mode(text=text, title="Court ruling on procedure")
        assert result.presented_mode == "rule"


# ── canonical fixture: explanation ────────────────────────────────────

class TestExplanationMode:
    def test_classify_explanation_causal(self):
        text = """
        The collapse occurred because the foundation was weakened by
        decades of erosion. As a result, the supporting beams failed.
        This explains why the structure gave way so suddenly. The reason
        is a contributing factor of poor maintenance driven by budget cuts.
        """
        result = classify_mode(text=text, title="Why the bridge collapsed")
        assert result.presented_mode == "explanation"


# ── canonical fixture: experience ─────────────────────────────────────

class TestExperienceMode:
    def test_classify_experience_memoir(self):
        text = """
        I was twelve when my family fled the country. I remember the
        sound of the trucks. I felt terror unlike anything I had known.
        I saw my father cry for the first time. I realized then that
        our lives had changed forever.
        """
        result = classify_mode(text=text, title="The night we left")
        assert result.presented_mode == "experience"


# ── canonical fixture: record ─────────────────────────────────────────

class TestRecordMode:
    def test_classify_record_reference(self):
        text = """
        Entry: Photosynthesis. Definition: the process by which plants
        convert light into energy. See also: chlorophyll, carbon fixation.
        Reference: Biology Catalog, Appendix D. Archived: 2024-01-15.
        """
        result = classify_mode(text=text, title="Photosynthesis")
        assert result.presented_mode == "record"


# ── canonical fixture: voice ──────────────────────────────────────────

class TestVoiceMode:
    def test_classify_voice_press_release(self):
        text = """
        Official statement from the organization: We believe in transparency.
        Our mission is to serve the public interest. We are committed to
        accountability in all operations.
        """
        result = classify_mode(text=text, title="Statement from the board")
        assert result.presented_mode == "voice"


# ── canonical fixture: formal ─────────────────────────────────────────

class TestFormalMode:
    def test_classify_formal_math(self):
        text = """
        Theorem. Let p be a prime integer. Proof. By definition, suppose
        p divides ab. Then by the lemma, p divides a or p divides b.
        Corollary: the sequence is bounded.
        """
        result = classify_mode(text=text, title="A theorem about primes")
        assert result.presented_mode == "formal"
        assert result.formal_submode == "mathematics"

    def test_classify_formal_logic(self):
        text = """
        Premise 1: All men are mortal. Premise 2: Socrates is a man.
        Conclusion: Socrates is mortal. This is a valid syllogism
        following modus ponens. The deduction is sound.
        """
        result = classify_mode(text=text, title="A logical argument")
        assert result.presented_mode == "formal"
        assert result.formal_submode == "logic"


# ── fail-closed behavior ─────────────────────────────────────────────

class TestUncertainMode:
    def test_classify_uncertain_short_text(self):
        text = "This is a short paragraph with no clear structure."
        result = classify_mode(text=text, title="")
        assert result.presented_mode == "uncertain"
        assert result.requires_reviewer_confirm is True
        assert result.notes is not None

    def test_classify_uncertain_empty_text(self):
        result = classify_mode(text="", title="")
        assert result.presented_mode == "uncertain"

    def test_classify_uncertain_ambiguous(self):
        text = "Something happened. People were involved. Things changed."
        result = classify_mode(text=text)
        assert result.presented_mode == "uncertain"


# ── confidence and signal behavior ────────────────────────────────────

class TestConfidenceAndSignals:
    def test_confidence_within_range(self):
        text = """
        Police said the suspect was arrested. Officials confirmed the
        identity. According to sources, the investigation is ongoing.
        """
        result = classify_mode(text=text)
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_label_valid(self):
        text = """
        We must act now. Therefore this policy should be rejected.
        It is essential that we change course immediately.
        """
        result = classify_mode(text=text)
        assert result.confidence_label in {"low", "medium", "high"}

    def test_signals_non_empty_for_classified(self):
        text = """
        Police said the fire started at dawn. Officials reported no
        injuries. According to witnesses, the building was evacuated.
        """
        result = classify_mode(text=text)
        if result.presented_mode != "uncertain":
            assert len(result.signals) > 0

    def test_formal_submode_none_for_non_formal(self):
        text = """
        Police said something happened. Officials confirmed the report.
        According to sources, the situation is under control.
        """
        result = classify_mode(text=text)
        if result.presented_mode != "formal":
            assert result.formal_submode == "none"
