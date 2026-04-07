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
