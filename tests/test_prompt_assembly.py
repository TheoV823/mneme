from app.runner.prompt_assembly import assemble_default, assemble_mneme

PROFILE = '{"thinking_style": "analytical", "values": ["clarity", "precision"]}'


def test_assemble_default():
    result = assemble_default()
    assert "helpful assistant" in result
    assert "<user_profile>" not in result


def test_assemble_mneme():
    result = assemble_mneme(PROFILE)
    assert "helpful assistant" in result
    assert "<user_profile>" in result
    assert "analytical" in result
    assert "Do not mention the profile" in result


def test_default_and_mneme_share_base():
    default = assemble_default()
    mneme = assemble_mneme(PROFILE)
    assert mneme.startswith(default.rstrip())


import json
from app.profiles.builder import build_mneme_profile
from app.profiles.signals import empty_source_signals


def _make_structured_profile(decision_style="analytical"):
    signals = {"qa": {**empty_source_signals(), "decision_style": decision_style}}
    return json.dumps(build_mneme_profile(signals))


def test_assemble_mneme_structured_profile_no_xml_tags():
    """New structured profiles must NOT be wrapped in <user_profile> tags."""
    profile = _make_structured_profile()
    result = assemble_mneme(profile)
    assert "<user_profile>" not in result
    assert "Decision style: analytical" in result


def test_assemble_mneme_structured_profile_has_base_prompt():
    profile = _make_structured_profile()
    result = assemble_mneme(profile)
    assert "helpful assistant" in result


def test_assemble_mneme_legacy_profile_keeps_xml_tags():
    """Legacy profiles must retain <user_profile> wrapper for backward compat."""
    legacy = json.dumps({"style": "analytical", "values": ["clarity"]})
    result = assemble_mneme(legacy)
    assert "<user_profile>" in result


def test_assemble_mneme_structured_profile_contains_closing_instruction():
    profile = _make_structured_profile()
    result = assemble_mneme(profile)
    assert "Do not mention this profile directly" in result


def test_assemble_default_unchanged():
    result = assemble_default()
    assert "helpful assistant" in result
    assert "<user_profile>" not in result
    assert "Decision style" not in result
