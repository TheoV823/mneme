def empty_source_signals():
    """Return a blank per-source signals dict. Always call this — never use ad-hoc dicts."""
    return {
        "decision_style": None,
        "risk_tolerance": None,
        "communication_style": None,
        "prioritization_rules": [],
        "constraints": [],
        "anti_patterns": [],
    }


def is_structured_profile(profile_dict):
    """Return True if profile_dict is a post-merge mneme profile (has value/confidence/sources shape)."""
    return (
        isinstance(profile_dict, dict)
        and isinstance(profile_dict.get("decision_style"), dict)
        and "value" in profile_dict.get("decision_style", {})
    )
