"""Tests for profiles and the profile-completeness check."""
import os
from pathlib import Path

from docassert import consistency as C
from docassert import profiles as P
from docassert import status as S

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"


def _cd_root():
    os.chdir(ROOT)  # build_status / load_profile read criteria/ and profiles/ relatively


PROF = {"name": "t", "enforce_when": "active",
        "required": ["charter", "brd"], "recommended": ["risk-register"]}


def _docs(*specs):
    return [{"kind": k, "status": s, "passing": p} for k, s, p in specs]


# ── completeness state machine ──────────────────────────────────────────────
def test_complete_when_approved_and_passing():
    c = P.completeness(PROF, _docs(("charter", "approved", True), ("brd", "baselined", True)), "active")
    assert c["required_complete"] == 2 and not c["missing_required"] and not c["blocks"]


def test_missing_required_blocks_when_active():
    c = P.completeness(PROF, _docs(("charter", "approved", True)), "active")  # brd missing
    assert c["missing_required"] == ["brd"] and c["enforced"] and c["blocks"]


def test_missing_required_is_advisory_when_proposed():
    c = P.completeness(PROF, _docs(("charter", "approved", True)), "proposed")  # brd missing
    assert c["missing_required"] == ["brd"] and not c["enforced"] and not c["blocks"]


def test_present_but_draft_is_incomplete_not_missing():
    c = P.completeness(PROF, _docs(("charter", "approved", True), ("brd", "draft", True)), "active")
    assert c["incomplete_required"] == ["brd"] and not c["missing_required"] and not c["blocks"]


def test_failing_approved_doc_is_incomplete():
    c = P.completeness(PROF, _docs(("charter", "approved", False), ("brd", "approved", True)), "active")
    assert "charter" in c["incomplete_required"]


def test_recommended_gap_tracked_but_never_blocks():
    c = P.completeness(PROF, _docs(("charter", "approved", True), ("brd", "approved", True)), "active")
    assert c["recommended_gaps"] == ["risk-register"] and not c["blocks"]


# ── loading ─────────────────────────────────────────────────────────────────
def test_load_profile_and_unknown():
    prof = P.load_profile("regulated-industry", PROFILES)
    assert prof and "charter" in prof["required"] and "project" not in prof["required"]
    assert P.load_profile("does-not-exist", PROFILES) is None


def test_available_lists_the_three_profiles():
    assert set(P.available(PROFILES)) == {"regulated-industry", "lean-startup", "agile-delivery"}


# ── integration with the real repo ──────────────────────────────────────────
def test_aurora_required_set_is_complete():
    _cd_root()
    c = S.build_status(ROOT / "documents", project="PRJ-001-AUR")["completeness"]
    assert c["profile"] == "regulated-industry"
    assert c["required_complete"] == c["required_total"] and not c["missing_required"]
    assert not c["blocks"]  # complete → nothing to block


def test_completeness_report_covers_profiled_projects():
    _cd_root()
    ids = {r["id"] for r in S.completeness_report(ROOT / "documents")}
    assert {"PRJ-001-AUR", "PRJ-002-ATL", "PRJ-003-MER", "PRJ-004-PHX"} <= ids


def test_repo_completeness_check_passes():
    _cd_root()
    r = C.check_profile_completeness(ROOT / "documents")
    assert r.passed and r.blocking  # aurora complete; the rest are proposed → advisory


# ── the check blocks on real gaps ───────────────────────────────────────────
def test_check_blocks_on_active_missing_required(monkeypatch):
    monkeypatch.setattr(S, "completeness_report", lambda *_a, **_k: [{
        "id": "PRJ-009-XYZ", "name": "X", "lifecycle": "active", "profile": "lean-startup",
        "unknown": False, "blocks": True, "missing_required": ["risk-register"],
        "incomplete_required": [], "recommended_gaps": [], "required": [], "recommended": [],
        "required_total": 5, "required_complete": 4, "enforce_when": "active", "enforced": True}])
    r = C.check_profile_completeness("documents")
    assert not r.passed and "risk-register" in r.detail


def test_check_blocks_on_unknown_profile(monkeypatch):
    monkeypatch.setattr(S, "completeness_report", lambda *_a, **_k: [{
        "id": "PRJ-009-XYZ", "profile": "ghost-profile", "unknown": True, "blocks": False,
        "missing_required": [], "incomplete_required": []}])
    r = C.check_profile_completeness("documents")
    assert not r.passed and "ghost-profile" in r.detail
