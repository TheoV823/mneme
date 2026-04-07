from app.profiles.signals import empty_source_signals

_normalize = lambda x: x.strip().lower() if x else ""


def _scalar_field(qa_val, ec_val):
    """Merge one scalar signal field. Returns a SignalField dict or None."""
    has_qa = qa_val is not None
    has_ec = ec_val is not None

    if has_qa and has_ec:
        if _normalize(qa_val) == _normalize(ec_val):
            return {"value": qa_val, "confidence": "high", "sources": ["qa", "extra_context"]}
        else:
            # QA wins on conflict — never override a QA signal
            return {"value": qa_val, "confidence": "medium", "sources": ["qa"]}
    elif has_qa:
        return {"value": qa_val, "confidence": "medium", "sources": ["qa"]}
    elif has_ec:
        return {"value": ec_val, "confidence": "low", "sources": ["extra_context"]}
    else:
        return None


def _list_field(qa_items, ec_items):
    """Merge one list signal field. Returns list of SignalItem dicts.

    Rules:
    - QA items start at medium confidence.
    - EC items that match a QA item (bidirectional substring) upgrade it to high.
    - EC items with no QA match are appended at low confidence.
    - QA items are never dropped.
    """
    merged = [
        {"value": item, "confidence": "medium", "sources": ["qa"]}
        for item in qa_items
    ]
    norm_qa = [_normalize(item) for item in qa_items]

    for ec_item in ec_items:
        norm_ec = _normalize(ec_item)
        matched_idx = None
        for i, nq in enumerate(norm_qa):
            if nq and norm_ec and (norm_ec in nq or nq in norm_ec):
                matched_idx = i
                break

        if matched_idx is not None:
            merged[matched_idx]["confidence"] = "high"
            merged[matched_idx]["sources"] = ["qa", "extra_context"]
        else:
            merged.append({"value": ec_item, "confidence": "low", "sources": ["extra_context"]})

    return merged


def build_mneme_profile(signals):
    """Merge per-source signals into a final mneme profile dict.

    Args:
        signals: {"qa": {...}, "extra_context": {...}}
                 extra_context key is optional.

    Returns:
        Structured profile dict. Fields absent from all sources are omitted.
        Confidence: "low" | "medium" | "high" only.

    Invariant: QA defines the profile. Extra context can only confirm or extend.
    """
    qa = signals.get("qa") or empty_source_signals()
    ec = signals.get("extra_context") or empty_source_signals()

    profile = {}

    for field in ("decision_style", "risk_tolerance", "communication_style"):
        merged = _scalar_field(qa.get(field), ec.get(field))
        if merged is not None:
            profile[field] = merged

    for field in ("prioritization_rules", "constraints", "anti_patterns"):
        qa_items = qa.get(field) or []
        ec_items = ec.get(field) or []
        items = _list_field(qa_items, ec_items)
        if items:
            profile[field] = items

    return profile
