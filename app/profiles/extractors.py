import json
import logging
from app.profiles.signals import empty_source_signals
from app.runner.claude_client import call_claude

logger = logging.getLogger(__name__)

_QA_FIELD_MAP = {
    "decision_style": "decision_style",
    "thinking_style": "decision_style",
    "style": "decision_style",
    "risk_tolerance": "risk_tolerance",
    "risk": "risk_tolerance",
    "communication_style": "communication_style",
    "communication": "communication_style",
    "comms_style": "communication_style",
    "prioritization_rules": "prioritization_rules",
    "priorities": "prioritization_rules",
    "values": "prioritization_rules",
    "constraints": "constraints",
    "anti_patterns": "anti_patterns",
    "avoid": "anti_patterns",
}

_LIST_FIELDS = {"prioritization_rules", "constraints", "anti_patterns"}


def extract_qa_signals(qa_input):
    """Extract signals from structured QA JSON input.

    Maps canonical and common-variant field names to the signal schema.
    Falls back to legacy_profile_to_signals() for unrecognized shapes.
    Callers never need to branch on old vs new format.
    """
    signals = empty_source_signals()
    matched = False

    for key, value in qa_input.items():
        normalized_key = key.lower().replace("-", "_")
        target = _QA_FIELD_MAP.get(normalized_key)
        if target is None:
            continue
        matched = True
        if target in _LIST_FIELDS:
            if isinstance(value, list):
                signals[target] = [str(v) for v in value]
            elif isinstance(value, str):
                signals[target] = [value]
        else:
            signals[target] = str(value) if value is not None else None

    if not matched:
        return legacy_profile_to_signals(qa_input)

    return signals


def legacy_profile_to_signals(profile):
    """Best-effort heuristic for old arbitrary profile blobs.

    Rules:
    - 'style' key -> decision_style
    - 'values' key -> prioritization_rules
    - First unrecognized list field -> constraints
    All confidence will be assigned 'low' by the builder.
    Keep this function shallow and predictable — do not add cleverness.
    """
    signals = empty_source_signals()

    if "style" in profile:
        signals["decision_style"] = str(profile["style"])

    if "values" in profile:
        v = profile["values"]
        if isinstance(v, list):
            signals["prioritization_rules"] = [str(x) for x in v]
        elif isinstance(v, str):
            signals["prioritization_rules"] = [v]

    # First unrecognized list field becomes constraints
    mapped_keys = {"style", "values"}
    for key, value in profile.items():
        if key not in mapped_keys and isinstance(value, list):
            signals["constraints"] = [str(x) for x in value]
            break

    return signals


# --- Extra context extractor (Claude API) ---

_EXTRACTION_MODEL = "claude-haiku-4-20250514"
_EXTRACTION_SYSTEM_PROMPT = (
    "You are a signal extractor. Extract structured decision-making signals from the "
    "provided text. Return ONLY a valid JSON object with exactly these keys: "
    "decision_style (string or null), risk_tolerance (string or null), "
    "communication_style (string or null), prioritization_rules (array of strings), "
    "constraints (array of strings), anti_patterns (array of strings). "
    "No explanation. No markdown. JSON only."
)

_CONTEXT_TYPE_HINTS = {
    "chat": "Focus on: tone, recurring trade-offs, and decision habits inferred from conversation patterns.",
    "document": "Focus on: explicitly stated priorities, formal structure, and written constraints.",
    "notes": "Focus on: heuristics, rules of thumb, and personal working-style principles.",
}


def _call_claude_for_extraction(text, api_key, context_type=None):
    """Private: call Claude API to extract signals. Returns raw response string."""
    hint = _CONTEXT_TYPE_HINTS.get(context_type, "")
    system_prompt = _EXTRACTION_SYSTEM_PROMPT + (" " + hint if hint else "")
    result = call_claude(
        api_key=api_key,
        model=_EXTRACTION_MODEL,
        system_prompt=system_prompt,
        user_prompt=text,
        temperature=0,
        max_tokens=1024,
    )
    return result["output"]


def extract_extra_context_signals(text, api_key, context_type=None):
    """Extract signals from free-form extra context text via Claude API.

    context_type: 'chat' | 'document' | 'notes' | None
        When provided, appends a type-specific focus hint to the extraction prompt.
        None uses the generic base prompt.

    Returns empty_source_signals() on any failure — never raises.
    """
    try:
        raw = _call_claude_for_extraction(text, api_key, context_type=context_type)
        parsed = json.loads(raw)
    except Exception as e:
        logger.warning("extract_extra_context_signals failed: %s", e)
        return empty_source_signals()

    signals = empty_source_signals()

    for field in ("decision_style", "risk_tolerance", "communication_style"):
        val = parsed.get(field)
        signals[field] = str(val) if val else None

    for field in ("prioritization_rules", "constraints", "anti_patterns"):
        val = parsed.get(field)
        if isinstance(val, list):
            signals[field] = [str(v) for v in val if v]
        else:
            signals[field] = []

    return signals
