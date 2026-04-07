from app.profiles.signals import empty_source_signals, is_structured_profile


def test_empty_source_signals_has_all_keys():
    s = empty_source_signals()
    assert s["decision_style"] is None
    assert s["risk_tolerance"] is None
    assert s["communication_style"] is None
    assert s["prioritization_rules"] == []
    assert s["constraints"] == []
    assert s["anti_patterns"] == []


def test_empty_source_signals_returns_new_dict_each_call():
    a = empty_source_signals()
    b = empty_source_signals()
    a["decision_style"] = "changed"
    assert b["decision_style"] is None


def test_is_structured_profile_true_for_valid_shape():
    profile = {
        "decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]}
    }
    assert is_structured_profile(profile) is True


def test_is_structured_profile_false_for_legacy():
    assert is_structured_profile({"style": "analytical", "values": ["clarity"]}) is False


def test_is_structured_profile_false_for_non_dict():
    assert is_structured_profile("raw string") is False
    assert is_structured_profile(None) is False


from app.profiles.extractors import extract_qa_signals, legacy_profile_to_signals


# --- extract_qa_signals ---

def test_extract_qa_signals_canonical_input():
    qa = {
        "decision_style": "analytical",
        "risk_tolerance": "medium",
        "communication_style": "direct",
        "prioritization_rules": ["speed over polish", "depth over breadth"],
        "constraints": ["no surprise decisions"],
        "anti_patterns": ["analysis paralysis"],
    }
    signals = extract_qa_signals(qa)
    assert signals["decision_style"] == "analytical"
    assert signals["risk_tolerance"] == "medium"
    assert signals["communication_style"] == "direct"
    assert signals["prioritization_rules"] == ["speed over polish", "depth over breadth"]
    assert signals["constraints"] == ["no surprise decisions"]
    assert signals["anti_patterns"] == ["analysis paralysis"]


def test_extract_qa_signals_alternate_key_names():
    qa = {
        "thinking_style": "intuitive",
        "risk": "low",
        "communication": "verbose",
        "priorities": ["team first"],
        "avoid": ["micromanagement"],
    }
    signals = extract_qa_signals(qa)
    assert signals["decision_style"] == "intuitive"
    assert signals["risk_tolerance"] == "low"
    assert signals["communication_style"] == "verbose"
    assert signals["prioritization_rules"] == ["team first"]
    assert signals["anti_patterns"] == ["micromanagement"]


def test_extract_qa_signals_partial_input():
    qa = {"decision_style": "fast"}
    signals = extract_qa_signals(qa)
    assert signals["decision_style"] == "fast"
    assert signals["risk_tolerance"] is None
    assert signals["prioritization_rules"] == []


def test_extract_qa_signals_single_string_list_field():
    qa = {"prioritization_rules": "speed over polish"}
    signals = extract_qa_signals(qa)
    assert signals["prioritization_rules"] == ["speed over polish"]


def test_extract_qa_signals_falls_back_to_legacy_for_unknown_keys():
    # Neither "style" nor "tone" is in _QA_FIELD_MAP, so matched stays False
    # and legacy_profile_to_signals() is called
    qa = {"style": "analytical", "tone": "direct"}
    signals = extract_qa_signals(qa)
    # legacy_profile_to_signals maps "style" -> decision_style
    assert signals["decision_style"] == "analytical"
    # "tone" is an unrecognized scalar — not mapped to anything
    assert signals["prioritization_rules"] == []


def test_extract_qa_signals_empty_dict():
    signals = extract_qa_signals({})
    assert signals == empty_source_signals()


# --- legacy_profile_to_signals ---

def test_legacy_style_and_values():
    profile = {"style": "analytical", "values": ["clarity"]}
    signals = legacy_profile_to_signals(profile)
    assert signals["decision_style"] == "analytical"
    assert signals["prioritization_rules"] == ["clarity"]


def test_legacy_unknown_list_becomes_constraints():
    profile = {"foo": ["bar", "baz"]}
    signals = legacy_profile_to_signals(profile)
    assert signals["constraints"] == ["bar", "baz"]


def test_legacy_unknown_non_list_field_ignored():
    profile = {"random_key": "random_value"}
    signals = legacy_profile_to_signals(profile)
    assert signals["decision_style"] is None
    assert signals["constraints"] == []


def test_legacy_empty_profile():
    signals = legacy_profile_to_signals({})
    assert signals == empty_source_signals()


from unittest.mock import patch
from app.profiles.extractors import extract_extra_context_signals


def test_extract_extra_context_signals_valid_response():
    claude_response = (
        '{"decision_style": "intuitive", "risk_tolerance": "high", '
        '"communication_style": "brief", '
        '"prioritization_rules": ["outcomes over process"], '
        '"constraints": ["budget < 10k"], "anti_patterns": ["endless debate"]}'
    )
    with patch("app.profiles.extractors._call_claude_for_extraction", return_value=claude_response):
        signals = extract_extra_context_signals("some text", api_key="fake")

    assert signals["decision_style"] == "intuitive"
    assert signals["risk_tolerance"] == "high"
    assert signals["prioritization_rules"] == ["outcomes over process"]
    assert signals["constraints"] == ["budget < 10k"]
    assert signals["anti_patterns"] == ["endless debate"]


def test_extract_extra_context_signals_invalid_json_returns_empty():
    with patch("app.profiles.extractors._call_claude_for_extraction", return_value="not json"):
        signals = extract_extra_context_signals("some text", api_key="fake")
    from app.profiles.signals import empty_source_signals
    assert signals == empty_source_signals()


def test_extract_extra_context_signals_api_failure_returns_empty():
    with patch(
        "app.profiles.extractors._call_claude_for_extraction",
        side_effect=Exception("network error"),
    ):
        signals = extract_extra_context_signals("some text", api_key="fake")
    from app.profiles.signals import empty_source_signals
    assert signals == empty_source_signals()


def test_extract_extra_context_signals_partial_response():
    # Claude returns some fields null, some missing
    claude_response = (
        '{"decision_style": null, "risk_tolerance": "low", '
        '"communication_style": null, '
        '"prioritization_rules": [], "constraints": [], "anti_patterns": []}'
    )
    with patch("app.profiles.extractors._call_claude_for_extraction", return_value=claude_response):
        signals = extract_extra_context_signals("some text", api_key="fake")
    assert signals["decision_style"] is None
    assert signals["risk_tolerance"] == "low"
    assert signals["prioritization_rules"] == []
