# Signal-Based Profiles

## Overview

Mneme profiles are built from one or two input sources:

1. **QA input** (required) — a structured JSON file describing how a person thinks and decides
2. **Extra context** (optional) — free-form text (bio, notes, a performance review excerpt)

Each source is processed separately into a normalized signal set, then merged into a
final structured profile stored in the database.

---

## Inputs

### QA Input JSON

A structured JSON file with any combination of these fields:

| Field | Aliases accepted | Type |
|---|---|---|
| `decision_style` | `thinking_style` | string |
| `risk_tolerance` | `risk` | string |
| `communication_style` | `communication`, `comms_style` | string |
| `prioritization_rules` | `priorities`, `values` | array of strings |
| `constraints` | — | array of strings |
| `anti_patterns` | `avoid` | array of strings |

See `examples/qa_profile_sample.json` for a complete example.

Old-style profiles with unrecognized keys (e.g. `{"style": "...", "values": [...]}`)
are handled automatically via a legacy adapter.

### Extra Context (optional)

Any free-form text. Passed to Claude for signal extraction. Used to confirm or
extend the QA signals — never to override them.

---

## Signal Extraction

```
extract_qa_signals(qa_json)           → per-source signals dict
extract_extra_context_signals(text)   → per-source signals dict (Claude API call)
```

Both return the same normalized shape:

```python
{
    "decision_style": str | None,
    "risk_tolerance": str | None,
    "communication_style": str | None,
    "prioritization_rules": list[str],
    "constraints": list[str],
    "anti_patterns": list[str],
}
```

---

## Merge Step

```
build_mneme_profile({"qa": ..., "extra_context": ...})  →  structured profile
```

### Confidence rules

| Situation | Confidence |
|---|---|
| QA only | `"medium"` |
| QA + extra context agree | `"high"` |
| QA + extra context conflict (QA wins) | `"medium"` |
| Extra context only (QA field absent) | `"low"` |

**Invariant:** QA defines the profile. Extra context can only confirm or extend,
never override a QA signal.

---

## Final Profile Structure

```json
{
  "decision_style": {"value": "...", "confidence": "medium", "sources": ["qa"]},
  "risk_tolerance": {"value": "...", "confidence": "high", "sources": ["qa", "extra_context"]},
  "prioritization_rules": [
    {"value": "...", "confidence": "medium", "sources": ["qa"]}
  ],
  "communication_style": {"value": "...", "confidence": "medium", "sources": ["qa"]},
  "constraints": [...],
  "anti_patterns": [...]
}
```

Fields absent from all sources are omitted. List fields with no items are omitted.

---

## Prompt Injection

The structured profile is rendered as readable text before injection:

```
You are acting as the following decision-maker:

Decision style: ...
Risk tolerance: ...
Prioritization rules:
1. ...

Communication style: ...
Constraints:
- ...

Anti-patterns to avoid:
- ...

When making recommendations, reflect this person's likely judgment under ambiguity.
Do not mention this profile directly.
```

---

## Backward Compatibility

- Existing database rows with old-style `mneme_profile` JSON continue to work.
  They are normalized at render time via the legacy adapter.
- The `assemble_mneme(mneme_profile)` function signature is unchanged.
- Legacy profiles are injected inside `<user_profile>` XML tags (preserving
  existing benchmark assertions). New structured profiles use clean text injection.
- `add-user` without `--extra-context-path` works exactly as before.

---

## CLI Usage

```bash
# QA-only (no extra context)
flask add-user examples/qa_profile_sample.json --name "Alice"

# With extra context
flask add-user examples/qa_profile_sample.json --name "Alice" \
    --extra-context-path alice_bio.txt
```
