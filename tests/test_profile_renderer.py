import json
from app.profiles.renderer import render_profile_for_prompt


# A fully populated structured profile (post-build_mneme_profile)
FULL_PROFILE = {
    "decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]},
    "risk_tolerance": {"value": "medium", "confidence": "medium", "sources": ["qa"]},
    "communication_style": {"value": "direct", "confidence": "medium", "sources": ["qa"]},
    "prioritization_rules": [
        {"value": "speed over polish", "confidence": "medium", "sources": ["qa"]},
        {"value": "depth over breadth", "confidence": "medium", "sources": ["qa"]},
    ],
    "constraints": [
        {"value": "no surprise decisions", "confidence": "medium", "sources": ["qa"]},
    ],
    "anti_patterns": [
        {"value": "analysis paralysis", "confidence": "medium", "sources": ["qa"]},
    ],
}


def test_render_structured_dict_contains_key_fields():
    result = render_profile_for_prompt(FULL_PROFILE)
    assert "Decision style: analytical" in result
    assert "Risk tolerance: medium" in result
    assert "Communication style: direct" in result
    assert "speed over polish" in result
    assert "no surprise decisions" in result
    assert "analysis paralysis" in result


def test_render_structured_dict_has_numbered_priorities():
    result = render_profile_for_prompt(FULL_PROFILE)
    assert "1. speed over polish" in result
    assert "2. depth over breadth" in result


def test_render_structured_dict_has_bullet_constraints():
    result = render_profile_for_prompt(FULL_PROFILE)
    assert "- no surprise decisions" in result


def test_render_structured_dict_no_raw_json():
    result = render_profile_for_prompt(FULL_PROFILE)
    assert "{" not in result
    assert '"confidence"' not in result


def test_render_structured_dict_has_closing_instruction():
    result = render_profile_for_prompt(FULL_PROFILE)
    assert "Do not mention this profile directly" in result


def test_render_accepts_json_string_of_structured_profile():
    result = render_profile_for_prompt(json.dumps(FULL_PROFILE))
    assert "Decision style: analytical" in result


def test_render_omits_absent_scalar_fields():
    profile = {
        "decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]},
    }
    result = render_profile_for_prompt(profile)
    assert "Risk tolerance" not in result
    assert "Communication style" not in result


def test_render_omits_empty_list_sections():
    profile = {
        "decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]},
        "prioritization_rules": [],
    }
    result = render_profile_for_prompt(profile)
    assert "Prioritization rules" not in result


def test_render_legacy_json_string_normalizes_and_renders():
    # Old-style profile stored as JSON in the DB
    legacy = json.dumps({"style": "intuitive", "values": ["clarity", "speed"]})
    result = render_profile_for_prompt(legacy)
    # Must render without crashing; should contain the legacy data in human-readable form
    assert "intuitive" in result
    assert "clarity" in result


def test_render_legacy_demo_profile():
    # The exact format used by seed_demo_command
    legacy = json.dumps({"style": "style_0", "values": ["clarity"]})
    result = render_profile_for_prompt(legacy)
    assert "style_0" in result
    assert "clarity" in result


def test_render_plain_text_passthrough():
    # Non-JSON string — returned as-is
    result = render_profile_for_prompt("I prefer written briefs.")
    assert result == "I prefer written briefs."
