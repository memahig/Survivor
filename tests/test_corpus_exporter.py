"""Tests for engine.io.corpus_exporter — BiasLens corpus case export."""

import json
import os

import pytest

from engine.io.corpus_exporter import (
    export_corpus_case,
    _resolve_genre,
    _slugify,
    _fingerprint,
    _derive_case_folder_name,
    _derive_year_month,
    _build_article_json,
    _load_manifest,
    _save_manifest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_state(
    article=None,
    adjudicated=None,
):
    """Build minimal run_state for corpus exporter testing."""
    return {
        "article": article or {
            "id": "test-001",
            "source_url": "https://example.com/article",
            "source": "Example News",
            "date": "2026-03-07",
            "title": "Test Article Title",
            "text": "This is the full article text for testing purposes.",
        },
        "adjudicated": adjudicated or {},
    }


# ---------------------------------------------------------------------------
# Genre routing
# ---------------------------------------------------------------------------

class TestGenreRouting:
    def test_journalism(self):
        rs = _run_state(article={"genre": "journalism", "text": "x"})
        assert _resolve_genre(rs) == "news_reporting"

    def test_reporting(self):
        rs = _run_state(article={"genre": "reporting", "text": "x"})
        assert _resolve_genre(rs) == "news_reporting"

    def test_advocacy(self):
        rs = _run_state(article={"genre": "advocacy", "text": "x"})
        assert _resolve_genre(rs) == "opinion_analysis"

    def test_opinion(self):
        rs = _run_state(article={"genre": "opinion", "text": "x"})
        assert _resolve_genre(rs) == "opinion_analysis"

    def test_scientific(self):
        rs = _run_state(article={"genre": "scientific", "text": "x"})
        assert _resolve_genre(rs) == "scholarly_research"

    def test_legal(self):
        rs = _run_state(article={"genre": "legal", "text": "x"})
        assert _resolve_genre(rs) == "legal_material"

    def test_unknown_genre(self):
        rs = _run_state(article={"genre": "mystery", "text": "x"})
        assert _resolve_genre(rs) == "uncategorized"

    def test_empty_genre(self):
        rs = _run_state(article={"text": "x"})
        assert _resolve_genre(rs) == "uncategorized"

    def test_fallback_to_waj_classification(self):
        rs = _run_state(
            article={"text": "x"},
            adjudicated={"whole_article_judgment": {"classification": "journalism"}},
        )
        assert _resolve_genre(rs) == "news_reporting"


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        assert _slugify("Al Jazeera: U.S. Iran Attack!") == "al_jazeera_us_iran_attack"

    def test_max_len(self):
        result = _slugify("a" * 100, max_len=20)
        assert len(result) <= 20

    def test_empty(self):
        assert _slugify("") == ""


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_deterministic(self):
        assert _fingerprint("hello") == _fingerprint("hello")

    def test_different_texts(self):
        assert _fingerprint("hello") != _fingerprint("world")

    def test_is_sha256(self):
        fp = _fingerprint("test")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# Case folder naming
# ---------------------------------------------------------------------------

class TestCaseFolderName:
    def test_basic(self):
        article = {
            "date": "2026-03-07",
            "source": "Al Jazeera",
            "title": "U.S. Iran Attack",
        }
        name = _derive_case_folder_name(article)
        assert name.startswith("2026-03-07_")
        assert "al_jazeera" in name
        assert "iran" in name

    def test_missing_date(self):
        article = {"source": "BBC", "title": "Test"}
        name = _derive_case_folder_name(article)
        # Falls back to today's date
        assert len(name) > 10

    def test_missing_source(self):
        article = {"date": "2026-01-01", "title": "Test"}
        name = _derive_case_folder_name(article)
        assert "unknown_source" in name


# ---------------------------------------------------------------------------
# Year/month derivation
# ---------------------------------------------------------------------------

class TestDeriveYearMonth:
    def test_basic(self):
        assert _derive_year_month({"date": "2026-03-07"}) == ("2026", "03")

    def test_iso_with_time(self):
        assert _derive_year_month({"date": "2026-03-07T12:00:00Z"}) == ("2026", "03")

    def test_missing_date(self):
        year, month = _derive_year_month({})
        assert len(year) == 4
        assert len(month) == 2


# ---------------------------------------------------------------------------
# Article JSON builder
# ---------------------------------------------------------------------------

class TestBuildArticleJson:
    def test_required_keys(self):
        article = {
            "id": "a1",
            "source_url": "https://example.com",
            "source": "Test",
            "date": "2026-03-07",
            "title": "Test Title",
            "text": "Article body text.",
        }
        result = _build_article_json(article, "v1.0", "2026-03-07T00:00:00+00:00")
        assert result["id"] == "a1"
        assert result["url"] == "https://example.com"
        assert result["fingerprint"] is not None
        assert result["captured_at"] == "2026-03-07T00:00:00+00:00"
        assert result["engine_version"] == "v1.0"
        assert result["user_tags"] == []

    def test_empty_text(self):
        result = _build_article_json({"text": ""}, "v1", "now")
        assert result["fingerprint"] is None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_load_missing_file(self, tmp_path):
        path = str(tmp_path / "missing.json")
        assert _load_manifest(path) == []

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "manifest.json")
        entries = [{"case_id": "c1", "fingerprint": "abc"}]
        _save_manifest(path, entries)
        loaded = _load_manifest(path)
        assert loaded == entries

    def test_load_corrupt_json(self, tmp_path):
        path = str(tmp_path / "manifest.json")
        with open(path, "w") as f:
            f.write("not json")
        assert _load_manifest(path) == []


# ---------------------------------------------------------------------------
# Full export
# ---------------------------------------------------------------------------

class TestExportCorpusCase:
    def test_creates_four_artifacts(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(
            rs,
            corpus_root=corpus_root,
            reader_report_md="# Reader Report\nTest content.",
            debug_report_md="# Debug Report\nTest content.",
            config={},
        )
        assert case_dir is not None
        assert os.path.isfile(os.path.join(case_dir, "article.json"))
        assert os.path.isfile(os.path.join(case_dir, "run.json"))
        assert os.path.isfile(os.path.join(case_dir, "reader_review.md"))
        assert os.path.isfile(os.path.join(case_dir, "scholar_debug.md"))

    def test_article_json_has_metadata(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(rs, corpus_root=corpus_root, config={})
        with open(os.path.join(case_dir, "article.json")) as f:
            article = json.load(f)
        assert "captured_at" in article
        assert "fingerprint" in article
        assert "engine_version" in article
        assert article["user_tags"] == []

    def test_run_json_matches_input(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(rs, corpus_root=corpus_root, config={})
        with open(os.path.join(case_dir, "run.json")) as f:
            run = json.load(f)
        assert run["article"]["id"] == "test-001"

    def test_placeholder_reports(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(rs, corpus_root=corpus_root, config={})
        with open(os.path.join(case_dir, "reader_review.md")) as f:
            content = f.read()
        assert "Reader Review" in content

    def test_manifest_created(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        export_corpus_case(rs, corpus_root=corpus_root, config={})
        manifest_path = os.path.join(corpus_root, "manifest.json")
        assert os.path.isfile(manifest_path)
        with open(manifest_path) as f:
            entries = json.load(f)
        assert len(entries) == 1
        assert entries[0]["case_id"] is not None
        assert entries[0]["fingerprint"] is not None

    def test_manifest_dedup_by_fingerprint(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        export_corpus_case(rs, corpus_root=corpus_root, config={})
        export_corpus_case(rs, corpus_root=corpus_root, config={})
        manifest_path = os.path.join(corpus_root, "manifest.json")
        with open(manifest_path) as f:
            entries = json.load(f)
        assert len(entries) == 1

    def test_different_articles_both_in_manifest(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs1 = _run_state(article={
            "id": "a1", "source": "S1", "date": "2026-01-01",
            "title": "Article One", "text": "First article text.",
        })
        rs2 = _run_state(article={
            "id": "a2", "source": "S2", "date": "2026-01-02",
            "title": "Article Two", "text": "Second article text.",
        })
        export_corpus_case(rs1, corpus_root=corpus_root, config={})
        export_corpus_case(rs2, corpus_root=corpus_root, config={})
        manifest_path = os.path.join(corpus_root, "manifest.json")
        with open(manifest_path) as f:
            entries = json.load(f)
        assert len(entries) == 2

    def test_directory_structure(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(rs, corpus_root=corpus_root, config={})
        # Should be corpus_root/genre/year/month/case_folder
        rel = os.path.relpath(case_dir, corpus_root)
        parts = rel.split(os.sep)
        assert len(parts) == 4  # genre/year/month/case_folder

    def test_fail_safe_on_bad_input(self):
        result = export_corpus_case(None, corpus_root="/nonexistent/path")
        assert result is None

    def test_fail_safe_on_non_dict(self):
        result = export_corpus_case("not_a_dict", corpus_root="/nonexistent/path")
        assert result is None

    def test_genre_in_path(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state(article={
            "id": "a1", "source": "BBC", "date": "2026-03-07",
            "title": "News Story", "text": "body",
            "genre": "journalism",
        })
        case_dir = export_corpus_case(rs, corpus_root=corpus_root, config={})
        assert "news_reporting" in case_dir

    def test_engine_version_from_config(self, tmp_path):
        corpus_root = str(tmp_path / "corpus")
        rs = _run_state()
        case_dir = export_corpus_case(
            rs, corpus_root=corpus_root, config={"engine_version": "v2.5"}
        )
        with open(os.path.join(case_dir, "article.json")) as f:
            article = json.load(f)
        assert article["engine_version"] == "v2.5"
