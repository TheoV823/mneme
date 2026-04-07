import pytest
from app.profiles.builder import build_mneme_profile
from app.profiles.signals import empty_source_signals


# --- Scalar field merge ---

def test_qa_only_scalar_is_medium_confidence():
    signals = {"qa": {**empty_source_signals(), "decision_style": "analytical"}}
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["value"] == "analytical"
    assert profile["decision_style"]["confidence"] == "medium"
    assert profile["decision_style"]["sources"] == ["qa"]


def test_qa_and_ec_agree_raises_to_high():
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"},
        "extra_context": {**empty_source_signals(), "decision_style": "Analytical"},  # different case
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["confidence"] == "high"
    assert sorted(profile["decision_style"]["sources"]) == ["extra_context", "qa"]


def test_qa_wins_on_conflict():
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"},
        "extra_context": {**empty_source_signals(), "decision_style": "intuitive"},
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["value"] == "analytical"
    assert profile["decision_style"]["confidence"] == "medium"
    assert profile["decision_style"]["sources"] == ["qa"]


def test_ec_only_scalar_is_low_confidence():
    signals = {
        "qa": empty_source_signals(),
        "extra_context": {**empty_source_signals(), "risk_tolerance": "high"},
    }
    profile = build_mneme_profile(signals)
    assert profile["risk_tolerance"]["value"] == "high"
    assert profile["risk_tolerance"]["confidence"] == "low"
    assert profile["risk_tolerance"]["sources"] == ["extra_context"]


def test_absent_scalar_omitted_from_profile():
    signals = {"qa": empty_source_signals()}
    profile = build_mneme_profile(signals)
    assert "decision_style" not in profile
    assert "risk_tolerance" not in profile


# --- List field merge ---

def test_qa_only_list_items_are_medium():
    signals = {
        "qa": {**empty_source_signals(), "prioritization_rules": ["speed over polish", "depth over breadth"]}
    }
    profile = build_mneme_profile(signals)
    items = profile["prioritization_rules"]
    assert len(items) == 2
    assert all(i["confidence"] == "medium" for i in items)
    assert all(i["sources"] == ["qa"] for i in items)


def test_ec_item_matching_qa_upgrades_to_high():
    signals = {
        "qa": {**empty_source_signals(), "constraints": ["no cold email"]},
        "extra_context": {**empty_source_signals(), "constraints": ["NO COLD EMAIL"]},  # same, different case
    }
    profile = build_mneme_profile(signals)
    items = profile["constraints"]
    assert len(items) == 1
    assert items[0]["confidence"] == "high"
    assert sorted(items[0]["sources"]) == ["extra_context", "qa"]


def test_ec_new_item_appended_as_low():
    signals = {
        "qa": {**empty_source_signals(), "anti_patterns": ["micromanagement"]},
        "extra_context": {**empty_source_signals(), "anti_patterns": ["overplanning"]},
    }
    profile = build_mneme_profile(signals)
    items = profile["anti_patterns"]
    values = [i["value"] for i in items]
    assert "micromanagement" in values
    assert "overplanning" in values
    overplanning = next(i for i in items if i["value"] == "overplanning")
    assert overplanning["confidence"] == "low"
    assert overplanning["sources"] == ["extra_context"]


def test_qa_items_never_dropped():
    signals = {
        "qa": {**empty_source_signals(), "prioritization_rules": ["rule A", "rule B"]},
        "extra_context": {**empty_source_signals(), "prioritization_rules": ["rule C"]},
    }
    profile = build_mneme_profile(signals)
    values = [i["value"] for i in profile["prioritization_rules"]]
    assert "rule A" in values
    assert "rule B" in values


def test_empty_list_omitted_from_profile():
    signals = {"qa": empty_source_signals()}
    profile = build_mneme_profile(signals)
    assert "prioritization_rules" not in profile
    assert "constraints" not in profile
    assert "anti_patterns" not in profile


def test_no_extra_context_key_works():
    # extra_context key entirely absent — QA-only flow
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"}
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["confidence"] == "medium"


def test_ec_substring_coverage_bidirectional():
    # "no cold email" is contained in "avoid no cold email campaigns"
    signals = {
        "qa": {**empty_source_signals(), "constraints": ["no cold email"]},
        "extra_context": {**empty_source_signals(), "constraints": ["avoid no cold email campaigns"]},
    }
    profile = build_mneme_profile(signals)
    # Should match (bidirectional substring), upgrade QA item to high
    assert profile["constraints"][0]["confidence"] == "high"
