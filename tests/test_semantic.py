"""Tests for the advisory grading layer: parsing, caching, and the API budget."""
import json

import pytest

from docassert import consistency, semantic
from docassert.models import Item
from docassert.semantic import _parse_grade


# ── _parse_grade ─────────────────────────────────────────────────────────────
def test_parse_grade_clean_json():
    g = _parse_grade('{"score": 0.9, "pass": true, "rationale": "solid"}')
    assert g == {"score": 0.9, "pass": True, "rationale": "solid"}


def test_parse_grade_tolerates_prose_and_fences():
    g = _parse_grade('Here you go:\n```json\n{"score": 0.4, "pass": false, "rationale": "weak"}\n```')
    assert g["score"] == 0.4 and g["pass"] is False


def test_parse_grade_recovers_truncated_response():
    # The exact failure shape seen live: max_tokens cut the rationale short.
    text = '{"score": 0.35, "pass": false, "rationale": "The child only refines the \'2 seconds\' timing aspect (backend fingerprint r'
    g = _parse_grade(text)
    assert g["score"] == 0.35
    assert g["pass"] is False
    assert g["rationale"].endswith("[truncated]")


def test_parse_grade_truncated_without_pass_leaves_it_to_threshold():
    g = _parse_grade('{"score": 0.8, "ratio')
    assert g["score"] == 0.8 and "pass" not in g


def test_parse_grade_raises_on_garbage():
    with pytest.raises(ValueError):
        _parse_grade("I cannot grade this.")


# ── cache replay ─────────────────────────────────────────────────────────────
def _use_tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_advisory_caches_grades(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(semantic, "_grade", lambda p, c, m: (
        calls.append(1) or {"score": 1.0, "pass": True, "rationale": "ok"}))
    for _ in range(2):
        r = semantic.advisory("chk", "prompt", "content")
        assert r.passed and r.score == 1.0
    assert len(calls) == 1


def test_advisory_does_not_cache_failures(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    calls = []

    def boom(p, c, m):
        calls.append(1)
        raise ValueError("no JSON in model response: ''")

    monkeypatch.setattr(semantic, "_grade", boom)
    for _ in range(2):
        r = semantic.advisory("chk", "prompt", "content")
        assert "unavailable" in r.detail
    assert len(calls) == 2  # transient errors retry on the next run


# ── the alignment budget spends on cache misses ──────────────────────────────
def _alignment_graph(n):
    from docassert.graph import Graph
    g = Graph()
    g.add(Item("TST-PR-001", "TST", "PR", "the parent requirement", {},
               "d.md", "prd", "approved", "S"))
    for i in range(1, n + 1):
        g.add(Item(f"TST-US-{i:03d}", "TST", "US", f"story {i}",
                   {"traces": ["TST-PR-001"]}, "d.md", "user-story",
                   "approved", "S"))
    return g


def test_alignment_budget_walks_the_graph_across_runs(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(semantic, "_grade", lambda p, c, m: (
        calls.append(c) or {"score": 1.0, "pass": True, "rationale": "ok"}))
    graph = _alignment_graph(5)
    config = {"alignment": [{"relation": "traces", "prompt": "aligned?"}],
              "alignment_limit": 2}

    first = consistency.run_alignment_checks(graph, config)
    assert len(calls) == 2                       # budget spent on misses
    assert any(r.check_id == "alignment-limit" and "2 of 5" in r.detail
               for r in first)

    second = consistency.run_alignment_checks(graph, config)
    assert len(calls) == 4                       # next two misses, not repeats
    assert len(set(map(json.dumps, calls))) == 4
    graded = [r for r in second if r.check_id.startswith("align:")]
    assert len(graded) == 4                      # 2 cached replays + 2 new

    third = consistency.run_alignment_checks(graph, config)
    assert len(calls) == 5                       # the last miss
    assert not any(r.check_id == "alignment-limit" for r in third)
    graded = [r for r in third if r.check_id.startswith("align:")]
    assert len(graded) == 5                      # full coverage reached


def test_alignment_limit_zero_grades_everything(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(semantic, "_grade", lambda p, c, m: (
        calls.append(1) or {"score": 1.0, "pass": True, "rationale": "ok"}))
    graph = _alignment_graph(4)
    config = {"alignment": [{"relation": "traces", "prompt": "aligned?"}],
              "alignment_limit": 0}
    consistency.run_alignment_checks(graph, config)
    assert len(calls) == 4
