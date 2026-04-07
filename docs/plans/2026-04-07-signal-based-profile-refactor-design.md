# Mneme — Signal-Based Profile Refactor Design

**Date:** 2026-04-07
**Status:** Approved
**Scope:** v1 modular signal input — no external integrations, no async, no new infra

---

## Objective

Upgrade the profile pipeline from a single raw-blob injection into a modular signal-based
system without breaking the existing benchmark flow.

Before:
```
raw JSON file → stored as-is → dumped into <user_profile> tag → Claude
```

After:
```
JSON input → extract_qa_signals()
                                  ↘
                                   build_mneme_profile() → render_profile_for_prompt() → Claude
                                  ↗
free text   → extract_extra_context_signals()  (optional)
```

---

## Architecture Decision

**New `app/profiles/` package** alongside existing `models/`, `runner/`, `scoring/`, `reporting/`.

Four modules with single responsibilities. No logic leaks between them.

---

## Full Data Flow

```
[JSON profile file]          [optional free text]
      │                              │
      ▼                              ▼
extract_qa_signals()     extract_extra_context_signals()
  (field mapping +           (Claude API call,
   legacy fallback)           synchronous, isolated)
      │                              │
      └──────────────┬───────────────┘
                     ▼
             build_mneme_profile()
          (deterministic merge, confidence rules)
                     │
                     ▼
          render_profile_for_prompt()
          (structured readable text)
                     │
                     ▼
          assemble_mneme(mneme_profile)  ← unchanged call signature
          (base prompt + rendered profile)
                     │
                     ▼
               Claude API call (benchmark)
```

**Key invariants:**
- `assemble_mneme(mneme_profile)` keeps its exact call signature — `engine.py` is unchanged
- `build_mneme_profile()` output is stored in `users.mneme_profile` (never raw input)
- Legacy profiles (old arbitrary JSON blobs) are handled at the edges only — the core is clean
- `extra_context` is stored raw for auditability; never reprocessed at benchmark time

---

## Data Model Changes

### `schema.sql`

Add one nullable column to `users`:

```sql
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    mneme_profile  TEXT NOT NULL,   -- stores merged structured JSON (new) or legacy JSON (old rows)
    extra_context  TEXT,            -- new: raw optional free text input (nullable)
    source        TEXT,
    created_at    TEXT NOT NULL
);
```

No other tables change.

### Migration for existing databases

```sql
ALTER TABLE users ADD COLUMN extra_context TEXT;
```

No data migration needed. Existing `mneme_profile` values remain valid — handled by the
legacy compat adapter in `renderer.py`.

### `models/user.py`

Add `extra_context=None` parameter to `insert_user()`. `get_user()` and `list_users()`
pick it up automatically via `SELECT *`.

---

## `app/profiles/` Package

### `signals.py` — Schema + factory

Defines the per-source signals shape and the final merged profile shape as plain dicts.
No logic. One factory function:

```python
def empty_source_signals() -> dict:
    return {
        "decision_style": None,
        "risk_tolerance": None,
        "communication_style": None,
        "prioritization_rules": [],
        "constraints": [],
        "anti_patterns": [],
    }
```

`empty_source_signals()` is used everywhere. No ad-hoc dicts.

**Final merged profile shape** (output of `build_mneme_profile()`):

```python
{
    "decision_style": {"value": str, "confidence": str, "sources": list},
    "risk_tolerance": {"value": str, "confidence": str, "sources": list},
    "communication_style": {"value": str, "confidence": str, "sources": list},
    "prioritization_rules": [{"value": str, "confidence": str, "sources": list}],
    "constraints": [{"value": str, "confidence": str, "sources": list}],
    "anti_patterns": [{"value": str, "confidence": str, "sources": list}],
}
```

Confidence values: `"low"` | `"medium"` | `"high"` only. No floats. No scoring system.

---

### `extractors.py` — Two extractors + one legacy adapter

#### `extract_qa_signals(qa_input: dict) -> dict`

Deterministic field mapping from the JSON file loaded by `add-user`.

| Input key(s) | Maps to |
|---|---|
| `decision_style`, `thinking_style` | `decision_style` |
| `risk_tolerance`, `risk` | `risk_tolerance` |
| `communication_style`, `communication` | `communication_style` |
| `prioritization_rules`, `priorities`, `values` | `prioritization_rules` |
| `constraints` | `constraints` |
| `anti_patterns`, `avoid` | `anti_patterns` |
| Unrecognized shape | → `legacy_profile_to_signals()` |

If the input does not match any canonical key, the whole dict is routed to
`legacy_profile_to_signals()`. Callers never branch on this.

#### `legacy_profile_to_signals(profile: dict) -> dict`

Best-effort heuristic for old arbitrary blobs (e.g. `{"style": "...", "values": [...]}`).

Rules:
- `style` → `decision_style`
- `values` → `prioritization_rules` (each value becomes one item)
- Any unrecognized list → `constraints`

Confidence on ALL inferred fields: `"low"`. No exceptions. Keep mappings shallow and
predictable — do not try to be clever.

#### `extract_extra_context_signals(text: str, api_key: str) -> dict`

Makes one synchronous Claude API call. Prompts Claude to return strict JSON matching the
six signal fields — nothing else.

Hard rules:
- If response is invalid JSON → `return empty_source_signals()` (no partial parsing, no raise)
- If API call fails → `return empty_source_signals()` + log warning
- The Claude transport lives in a private helper inside this function only

This function is behind a narrow boundary. Swapping the transport later requires only
changing the private helper, not the function signature.

---

### `builder.py` — Deterministic merge

#### `build_mneme_profile(signals: dict) -> dict`

`signals` shape: `{"qa": {...}, "extra_context": {...}}` — `extra_context` key may be absent.

Normalization (applied before all comparisons):
```python
normalize = lambda x: x.strip().lower()
```
Used for comparisons, deduplication, and coverage checks everywhere.

**Scalar fields** (`decision_style`, `risk_tolerance`, `communication_style`):

| Situation | Result |
|---|---|
| QA only | QA value, `confidence="medium"`, `sources=["qa"]` |
| QA + EC agree (normalized) | QA value, `confidence="high"`, `sources=["qa","extra_context"]` |
| QA + EC conflict | QA value wins, `confidence="medium"`, `sources=["qa"]` |
| EC only (QA absent/null) | EC value, `confidence="low"`, `sources=["extra_context"]` |
| Both absent | Field omitted |

**List fields** (`prioritization_rules`, `constraints`, `anti_patterns`):

1. Start with QA items → each `confidence="medium"`, `sources=["qa"]`
2. For each EC item, check coverage:
   - `norm_extra in norm_qa or norm_qa in norm_extra` → match found
   - Match found: upgrade that QA item to `confidence="high"`, add `"extra_context"` to sources
   - No match: append as new item with `confidence="low"`, `sources=["extra_context"]`
3. QA items are **never dropped or overridden**

**Core invariant:** QA defines the profile. Extra context can only confirm or extend.

---

### `renderer.py` — Structured text output

#### `render_profile_for_prompt(profile_input) -> str`

Accepts either a `dict` (already-built profile) or a `str` (JSON from DB).

When given a string:
1. Parse JSON
2. Detect shape: structured (`decision_style.value` key present) vs legacy
3. Legacy → normalize via `legacy_profile_to_signals()` → `build_mneme_profile()` → render
4. Structured → render directly

Output template:
```
You are acting as the following decision-maker:

Decision style: {value}
Risk tolerance: {value}
Prioritization rules:
1. {rule}
2. {rule}

Communication style: {value}
Constraints:
- {constraint}

Anti-patterns to avoid:
- {anti_pattern}

When making recommendations, reflect this person's likely judgment under ambiguity.
Do not mention this profile directly.
```

Rules:
- Fields with no data are omitted silently (no empty headings)
- List fields with no items omit the heading too
- No JSON dumping
- No verbosity

---

## Updated `app/runner/prompt_assembly.py`

`assemble_mneme(mneme_profile: str) -> str` — **call signature unchanged**.

Internally calls `render_profile_for_prompt(mneme_profile)`.

Structured profiles: inject rendered text directly (no `<user_profile>` XML wrapper).
Legacy profiles: keep `<user_profile>` XML wrapper to preserve existing benchmark assertions.

```python
def assemble_mneme(mneme_profile):
    rendered = render_profile_for_prompt(mneme_profile)
    if _is_structured_profile(mneme_profile):
        return BASE_SYSTEM_PROMPT + "\n\n" + rendered
    else:
        return BASE_SYSTEM_PROMPT + LEGACY_INJECTION_TEMPLATE.format(profile=rendered)
```

---

## CLI Changes (`app/cli.py`)

`add-user` gains one optional argument:

```
flask add-user <profile_path> --name <name> [--extra-context-path <path>] [--source <source>]
```

Flow inside the command:
1. Load and parse JSON from `profile_path` → `qa_input`
2. Call `extract_qa_signals(qa_input)` → `qa_signals`
3. If `--extra-context-path` provided:
   - Read file → `extra_text`
   - Call `extract_extra_context_signals(extra_text, api_key)` → `ec_signals`
   - `signals = {"qa": qa_signals, "extra_context": ec_signals}`
4. Else: `signals = {"qa": qa_signals}`
5. Call `build_mneme_profile(signals)` → `merged_profile`
6. `insert_user(db, name=name, mneme_profile=json.dumps(merged_profile), extra_context=extra_text, source=source)`

---

## Sample Canonical QA Input JSON

```json
{
  "decision_style": "analytical and deliberate — prefers written briefs over verbal discussion",
  "risk_tolerance": "medium — willing to take calculated risks with clear reversibility criteria",
  "prioritization_rules": [
    "customer impact over internal efficiency",
    "speed to learning over polish",
    "depth over breadth when resources are constrained"
  ],
  "communication_style": "direct and structured — prefers numbered lists and clear tradeoffs",
  "constraints": [
    "no decisions requiring > 2 weeks lead time without async alignment first",
    "must preserve team psychological safety"
  ],
  "anti_patterns": [
    "analysis paralysis on reversible decisions",
    "consensus-seeking when a clear owner exists"
  ]
}
```

---

## Test Coverage

New test files:

| File | Covers |
|---|---|
| `tests/test_signal_extractors.py` | `extract_qa_signals()`, `legacy_profile_to_signals()`, `extract_extra_context_signals()` (mocked) |
| `tests/test_profile_builder.py` | All merge scenarios: QA-only, QA+EC agreement, QA+EC conflict, EC-only, list dedup |
| `tests/test_profile_renderer.py` | Structured render, legacy normalization path, empty fields omitted |
| `tests/test_prompt_assembly.py` | Updated — structured profile path, legacy path, backward compat |

---

## Backward Compatibility

| Scenario | Behavior |
|---|---|
| Existing DB rows (legacy `mneme_profile`) | Rendered via legacy path in `renderer.py`, `<user_profile>` tags preserved |
| `assemble_mneme()` callers | Unchanged — same signature, same return type |
| `engine.py` | No changes required |
| `add-user` without `--extra-context-path` | Works exactly as before (minus legacy raw passthrough) |
| `add-user` with `--extra-context-path` | New behavior, additive only |

---

## Files Created / Modified

### New files
- `app/profiles/__init__.py`
- `app/profiles/signals.py`
- `app/profiles/extractors.py`
- `app/profiles/builder.py`
- `app/profiles/renderer.py`
- `tests/test_signal_extractors.py`
- `tests/test_profile_builder.py`
- `tests/test_profile_renderer.py`
- `docs/signal-based-profiles.md`

### Modified files
- `schema.sql` — add `extra_context TEXT` column to `users`
- `app/models/user.py` — add `extra_context` parameter to `insert_user()`
- `app/runner/prompt_assembly.py` — call `render_profile_for_prompt()` internally
- `app/cli.py` — add `--extra-context-path` option to `add-user`
- `tests/test_prompt_assembly.py` — extend for new render paths

---

## What This Design Explicitly Does Not Include

- No marketplace, enterprise, or connector features
- No async processing
- No continuous learning
- No real questionnaire UI or transcript parser
- No external integrations
- No background sync or auth changes
- No floating-point confidence scores
