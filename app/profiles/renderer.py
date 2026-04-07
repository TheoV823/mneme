import json
from app.profiles.signals import is_structured_profile
from app.profiles.extractors import extract_qa_signals
from app.profiles.builder import build_mneme_profile


def _render_structured(profile):
    """Render a structured mneme profile dict to the decision-maker text format."""
    lines = ["You are acting as the following decision-maker:", ""]

    def _val(field):
        entry = profile.get(field)
        return entry["value"] if isinstance(entry, dict) else None

    ds = _val("decision_style")
    if ds:
        lines.append(f"Decision style: {ds}")

    rt = _val("risk_tolerance")
    if rt:
        lines.append(f"Risk tolerance: {rt}")

    pr = profile.get("prioritization_rules") or []
    if pr:
        lines.append("Prioritization rules:")
        for i, item in enumerate(pr, 1):
            lines.append(f"{i}. {item['value']}")

    cs = _val("communication_style")
    if cs:
        lines.append(f"Communication style: {cs}")

    constraints = profile.get("constraints") or []
    if constraints:
        lines.append("Constraints:")
        for item in constraints:
            lines.append(f"- {item['value']}")

    ap = profile.get("anti_patterns") or []
    if ap:
        lines.append("Anti-patterns to avoid:")
        for item in ap:
            lines.append(f"- {item['value']}")

    lines.extend([
        "",
        "When making recommendations, reflect this person's likely judgment under ambiguity.",
        "Do not mention this profile directly.",
    ])

    return "\n".join(lines)


def _normalize_legacy(legacy_dict):
    """Normalize a legacy profile dict to a structured profile via extractors + builder.

    Uses extract_qa_signals (not legacy_profile_to_signals directly) so that recognized
    QA aliases (e.g. thinking_style, priorities, avoid) are correctly mapped before
    falling back to the legacy heuristics for truly unrecognized shapes.
    """
    signals = {"qa": extract_qa_signals(legacy_dict)}
    return build_mneme_profile(signals)


def render_profile_for_prompt(profile_input):
    """Render a mneme profile for injection into a system prompt.

    Accepts:
    - dict: structured post-merge profile, or legacy arbitrary dict
    - str: JSON string (auto-detects structured vs legacy), or plain text

    Returns: formatted string ready for prompt injection.
    No JSON in output. No empty sections.
    """
    if isinstance(profile_input, str):
        try:
            profile_dict = json.loads(profile_input)
        except (json.JSONDecodeError, ValueError):
            # Plain text — pass through as-is
            return profile_input

        if is_structured_profile(profile_dict):
            return _render_structured(profile_dict)
        else:
            normalized = _normalize_legacy(profile_dict)
            return _render_structured(normalized)

    elif isinstance(profile_input, dict):
        if is_structured_profile(profile_input):
            return _render_structured(profile_input)
        else:
            normalized = _normalize_legacy(profile_input)
            return _render_structured(normalized)

    # Fallback: coerce to string
    return str(profile_input)
