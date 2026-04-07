# Signal-Based Profile Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the profile pipeline from raw-JSON-blob injection into a modular
signal extraction → merge → structured prompt injection system, without breaking
any existing benchmark or test behavior.

**Architecture:** A new `app/profiles/` package holds four single-responsibility modules
(signals, extractors, builder, renderer). The existing `assemble_mneme()` call
signature is unchanged — it calls the renderer internally. Legacy profiles (old
arbitrary JSON) are normalized at the edges; the core is clean and deterministic.

**Tech Stack:** Python 3.12, Flask, SQLite (raw sqlite3), pytest, anthropic SDK

**Design doc:** `docs/plans/2026-04-07-signal-based-profile-refactor-design.md`

---

## Pre-flight checks

Before starting, confirm the test suite passes clean:

```bash
cd C:\dev\mneme
pytest --tb=short -q
```

Expected: all green. If not, stop and fix before proceeding.

---

## Task 1: Schema — add `extra_context` column

**Files:**
- Modify: `schema.sql`
- Create: `migrate_add_extra_context.sql`

### Step 1: Add column to schema.sql

Open `schema.sql`. The `users` table currently ends at `created_at`. Add one line:

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mneme_profile TEXT NOT NULL,
    extra_context TEXT,
    source TEXT,
    created_at TEXT NOT NULL
);
```

(Only the `extra_context TEXT,` line is new — insert it between `mneme_profile` and `source`.)

### Step 2: Create migration script for existing databases

Create `migrate_add_extra_context.sql` at the repo root:

```sql
-- Run once on any database created before 2026-04-07
-- Safe to run multiple times (SQLite ignores duplicate column errors when using this pattern)
ALTER TABLE users ADD COLUMN extra_context TEXT;
```

### Step 3: Run existing DB tests to confirm schema change is safe

```bash
pytest tests/test_db.py tests/test_models_user.py -v
```

Expected: all pass (tests use temp DBs that get the new schema fresh).

### Step 4: Commit

```bash
git add schema.sql migrate_add_extra_context.sql
git commit -m "feat: add extra_context column to users table"
```

---

## Task 2: Update `models/user.py` — accept and store `extra_context`

**Files:**
- Modify: `app/models/user.py`
- Modify: `tests/test_models_user.py`

### Step 1: Write the failing test

Add to `tests/test_models_user.py`:

```python
def test_insert_user_with_extra_context(db):
    user = insert_user(
        db,
        name="Test User",
        mneme_profile='{"decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]}}',
        extra_context="I prefer written briefs over meetings.",
        source="test",
    )
    assert user["extra_context"] == "I prefer written briefs over meetings."


def test_insert_user_extra_context_defaults_to_none(db):
    user = insert_user(db, name="No Context User", mneme_profile='{"x": 1}')
    assert user["extra_context"] is None


def test_get_user_includes_extra_context(db):
    inserted = insert_user(
        db, name="EC User", mneme_profile='{}', extra_context="some context"
    )
    fetched = get_user(db, inserted["id"])
    assert fetched["extra_context"] == "some context"
```

Make sure the imports at the top of the test file include `insert_user` and `get_user`.

### Step 2: Run to confirm they fail

```bash
pytest tests/test_models_user.py -v -k "extra_context"
```

Expected: FAIL — `insert_user` doesn't accept `extra_context` yet.

### Step 3: Update `app/models/user.py`

Replace the entire file with:

```python
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_user(db, name, mneme_profile, source=None, extra_context=None):
    user_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO users (id, name, mneme_profile, extra_context, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, mneme_profile, extra_context, source, created_at),
    )
    db.commit()
    return {
        "id": user_id,
        "name": name,
        "mneme_profile": mneme_profile,
        "extra_context": extra_context,
        "source": source,
        "created_at": created_at,
    }


def get_user(db, user_id):
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users(db):
    rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]
```

### Step 4: Run tests

```bash
pytest tests/test_models_user.py -v
```

Expected: all pass.

### Step 5: Run full suite to check nothing broke

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 6: Commit

```bash
git add app/models/user.py tests/test_models_user.py
git commit -m "feat: add extra_context param to insert_user"
```

---

## Task 3: Create `app/profiles/` package — `signals.py`

**Files:**
- Create: `app/profiles/__init__.py`
- Create: `app/profiles/signals.py`
- Create: `tests/test_signal_extractors.py` (partial — just import checks for now)

### Step 1: Create the package directory and empty `__init__.py`

Create `app/profiles/__init__.py` as an empty file.

### Step 2: Write tests for `signals.py`

Create `tests/test_signal_extractors.py` with:

```python
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
```

### Step 3: Run to confirm they fail

```bash
pytest tests/test_signal_extractors.py -v -k "signals"
```

Expected: FAIL — module doesn't exist yet.

### Step 4: Create `app/profiles/signals.py`

```python
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
```

### Step 5: Run tests

```bash
pytest tests/test_signal_extractors.py -v -k "signals"
```

Expected: all pass.

### Step 6: Commit

```bash
git add app/profiles/__init__.py app/profiles/signals.py tests/test_signal_extractors.py
git commit -m "feat: add profiles package with signals schema and factory"
```

---

## Task 4: `extractors.py` — QA extractor and legacy adapter

**Files:**
- Create: `app/profiles/extractors.py`
- Modify: `tests/test_signal_extractors.py`

### Step 1: Add tests for `extract_qa_signals` and `legacy_profile_to_signals`

Append to `tests/test_signal_extractors.py`:

```python
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
    qa = {"style": "analytical", "values": ["clarity", "precision"]}
    signals = extract_qa_signals(qa)
    # Legacy adapter maps style → decision_style, values → prioritization_rules
    assert signals["decision_style"] == "analytical"
    assert signals["prioritization_rules"] == ["clarity", "precision"]


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
```

### Step 2: Run to confirm they fail

```bash
pytest tests/test_signal_extractors.py -v -k "qa_signals or legacy"
```

Expected: FAIL — extractors module doesn't exist.

### Step 3: Create `app/profiles/extractors.py` (QA + legacy only — no Claude call yet)

```python
import json
import logging
from app.profiles.signals import empty_source_signals

logger = logging.getLogger(__name__)

_QA_FIELD_MAP = {
    "decision_style": "decision_style",
    "thinking_style": "decision_style",
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
_SCALAR_FIELDS = {"decision_style", "risk_tolerance", "communication_style"}


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
# Stub — full implementation in Task 5.

_EXTRACTION_MODEL = "claude-haiku-4-20250514"
_EXTRACTION_SYSTEM_PROMPT = (
    "You are a signal extractor. Extract structured decision-making signals from the "
    "provided text. Return ONLY a valid JSON object with exactly these keys: "
    "decision_style (string or null), risk_tolerance (string or null), "
    "communication_style (string or null), prioritization_rules (array of strings), "
    "constraints (array of strings), anti_patterns (array of strings). "
    "No explanation. No markdown. JSON only."
)


def _call_claude_for_extraction(text, api_key):
    """Private: call Claude API to extract signals. Returns raw response string."""
    from app.runner.claude_client import call_claude
    result = call_claude(
        api_key=api_key,
        model=_EXTRACTION_MODEL,
        system_prompt=_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=text,
        temperature=0,
        max_tokens=1024,
    )
    return result["output"]


def extract_extra_context_signals(text, api_key):
    """Extract signals from free-form extra context text via Claude API.

    Returns empty_source_signals() on any failure — never raises.
    This is the narrow boundary for the Claude transport: swap _call_claude_for_extraction
    to change models or providers without touching anything else.
    """
    try:
        raw = _call_claude_for_extraction(text, api_key)
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
```

### Step 4: Run tests

```bash
pytest tests/test_signal_extractors.py -v
```

Expected: all pass (Claude call tests not yet written — that's Task 5).

### Step 5: Run full suite

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 6: Commit

```bash
git add app/profiles/extractors.py tests/test_signal_extractors.py
git commit -m "feat: add extract_qa_signals and legacy_profile_to_signals"
```

---

## Task 5: `extractors.py` — tests for `extract_extra_context_signals`

**Files:**
- Modify: `tests/test_signal_extractors.py`

The Claude call is mocked — no live API needed.

### Step 1: Add tests

Append to `tests/test_signal_extractors.py`:

```python
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
```

### Step 2: Run tests

```bash
pytest tests/test_signal_extractors.py -v -k "extra_context"
```

Expected: all pass (the implementation already exists from Task 4).

### Step 3: Commit

```bash
git add tests/test_signal_extractors.py
git commit -m "test: add extract_extra_context_signals tests with mocked Claude"
```

---

## Task 6: `builder.py` — deterministic merge

**Files:**
- Create: `app/profiles/builder.py`
- Create: `tests/test_profile_builder.py`

### Step 1: Write failing tests

Create `tests/test_profile_builder.py`:

```python
import pytest
from app.profiles.builder import build_mneme_profile
from app.profiles.signals import empty_source_signals


# --- Scalar field merge ---

def test_qa_only_scalar_is_medium_confidence():
    signals = {"qa": {**empty_source_signals(), "decision_style": "analytical"}}
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["value"] == "analytical"
    assert profile["decision_style"]["confidence"] == "medium"
    assert profile["decision_style"]["sources"] == ["qa"]


def test_qa_and_ec_agree_raises_to_high():
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"},
        "extra_context": {**empty_source_signals(), "decision_style": "Analytical"},  # different case
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["confidence"] == "high"
    assert sorted(profile["decision_style"]["sources"]) == ["extra_context", "qa"]


def test_qa_wins_on_conflict():
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"},
        "extra_context": {**empty_source_signals(), "decision_style": "intuitive"},
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["value"] == "analytical"
    assert profile["decision_style"]["confidence"] == "medium"
    assert profile["decision_style"]["sources"] == ["qa"]


def test_ec_only_scalar_is_low_confidence():
    signals = {
        "qa": empty_source_signals(),
        "extra_context": {**empty_source_signals(), "risk_tolerance": "high"},
    }
    profile = build_mneme_profile(signals)
    assert profile["risk_tolerance"]["value"] == "high"
    assert profile["risk_tolerance"]["confidence"] == "low"
    assert profile["risk_tolerance"]["sources"] == ["extra_context"]


def test_absent_scalar_omitted_from_profile():
    signals = {"qa": empty_source_signals()}
    profile = build_mneme_profile(signals)
    assert "decision_style" not in profile
    assert "risk_tolerance" not in profile


# --- List field merge ---

def test_qa_only_list_items_are_medium():
    signals = {
        "qa": {**empty_source_signals(), "prioritization_rules": ["speed over polish", "depth over breadth"]}
    }
    profile = build_mneme_profile(signals)
    items = profile["prioritization_rules"]
    assert len(items) == 2
    assert all(i["confidence"] == "medium" for i in items)
    assert all(i["sources"] == ["qa"] for i in items)


def test_ec_item_matching_qa_upgrades_to_high():
    signals = {
        "qa": {**empty_source_signals(), "constraints": ["no cold email"]},
        "extra_context": {**empty_source_signals(), "constraints": ["NO COLD EMAIL"]},  # same, different case
    }
    profile = build_mneme_profile(signals)
    items = profile["constraints"]
    assert len(items) == 1
    assert items[0]["confidence"] == "high"
    assert sorted(items[0]["sources"]) == ["extra_context", "qa"]


def test_ec_new_item_appended_as_low():
    signals = {
        "qa": {**empty_source_signals(), "anti_patterns": ["micromanagement"]},
        "extra_context": {**empty_source_signals(), "anti_patterns": ["overplanning"]},
    }
    profile = build_mneme_profile(signals)
    items = profile["anti_patterns"]
    values = [i["value"] for i in items]
    assert "micromanagement" in values
    assert "overplanning" in values
    overplanning = next(i for i in items if i["value"] == "overplanning")
    assert overplanning["confidence"] == "low"
    assert overplanning["sources"] == ["extra_context"]


def test_qa_items_never_dropped():
    signals = {
        "qa": {**empty_source_signals(), "prioritization_rules": ["rule A", "rule B"]},
        "extra_context": {**empty_source_signals(), "prioritization_rules": ["rule C"]},
    }
    profile = build_mneme_profile(signals)
    values = [i["value"] for i in profile["prioritization_rules"]]
    assert "rule A" in values
    assert "rule B" in values


def test_empty_list_omitted_from_profile():
    signals = {"qa": empty_source_signals()}
    profile = build_mneme_profile(signals)
    assert "prioritization_rules" not in profile
    assert "constraints" not in profile
    assert "anti_patterns" not in profile


def test_no_extra_context_key_works():
    # extra_context key entirely absent — QA-only flow
    signals = {
        "qa": {**empty_source_signals(), "decision_style": "analytical"}
    }
    profile = build_mneme_profile(signals)
    assert profile["decision_style"]["confidence"] == "medium"


def test_ec_substring_coverage_bidirectional():
    # "no cold email" is contained in "avoid no cold email campaigns"
    signals = {
        "qa": {**empty_source_signals(), "constraints": ["no cold email"]},
        "extra_context": {**empty_source_signals(), "constraints": ["avoid no cold email campaigns"]},
    }
    profile = build_mneme_profile(signals)
    # Should match (bidirectional substring), upgrade QA item to high
    assert profile["constraints"][0]["confidence"] == "high"
```

### Step 2: Run to confirm they fail

```bash
pytest tests/test_profile_builder.py -v
```

Expected: FAIL — builder module doesn't exist.

### Step 3: Create `app/profiles/builder.py`

```python
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
```

### Step 4: Run tests

```bash
pytest tests/test_profile_builder.py -v
```

Expected: all pass.

### Step 5: Run full suite

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 6: Commit

```bash
git add app/profiles/builder.py tests/test_profile_builder.py
git commit -m "feat: add build_mneme_profile with deterministic merge rules"
```

---

## Task 7: `renderer.py` — structured text output

**Files:**
- Create: `app/profiles/renderer.py`
- Create: `tests/test_profile_renderer.py`

### Step 1: Write failing tests

Create `tests/test_profile_renderer.py`:

```python
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
```

### Step 2: Run to confirm they fail

```bash
pytest tests/test_profile_renderer.py -v
```

Expected: FAIL — renderer module doesn't exist.

### Step 3: Create `app/profiles/renderer.py`

```python
import json
from app.profiles.signals import is_structured_profile
from app.profiles.extractors import legacy_profile_to_signals
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
    """Normalize a legacy profile dict to a structured profile via extractors + builder."""
    signals = {"qa": legacy_profile_to_signals(legacy_dict)}
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
```

### Step 4: Run tests

```bash
pytest tests/test_profile_renderer.py -v
```

Expected: all pass.

### Step 5: Run full suite

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 6: Commit

```bash
git add app/profiles/renderer.py tests/test_profile_renderer.py
git commit -m "feat: add render_profile_for_prompt with legacy normalization"
```

---

## Task 8: Update `prompt_assembly.py` — use renderer internally

**Files:**
- Modify: `app/runner/prompt_assembly.py`
- Modify: `tests/test_prompt_assembly.py`

### Step 1: Add new tests to `tests/test_prompt_assembly.py`

Open `tests/test_prompt_assembly.py` and append:

```python
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
```

### Step 2: Run to confirm new tests fail (existing ones pass)

```bash
pytest tests/test_prompt_assembly.py -v
```

Expected: existing 3 tests pass, new 5 tests fail.

### Step 3: Rewrite `app/runner/prompt_assembly.py`

```python
import json
from app.profiles.renderer import render_profile_for_prompt
from app.profiles.signals import is_structured_profile

BASE_SYSTEM_PROMPT = "You are a helpful assistant. Respond thoughtfully to the user's request."

# Kept only for legacy profiles (old arbitrary JSON blobs from pre-refactor users)
LEGACY_INJECTION_TEMPLATE = """

<user_profile>
{profile}
</user_profile>

Use the above profile to tailor your response to how this person thinks, decides, and communicates. Do not mention the profile directly."""


def _is_structured_json(mneme_profile_str):
    """Return True if the profile string is a new structured (post-merge) profile."""
    try:
        return is_structured_profile(json.loads(mneme_profile_str))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return False


def assemble_default():
    return BASE_SYSTEM_PROMPT


def assemble_mneme(mneme_profile):
    """Assemble the mneme system prompt. Call signature unchanged from pre-refactor.

    Structured profiles (new): inject rendered text directly, no XML wrapper.
    Legacy profiles (old): keep <user_profile> XML wrapper to preserve
    existing benchmark run assertions.
    """
    rendered = render_profile_for_prompt(mneme_profile)
    if _is_structured_json(mneme_profile):
        return BASE_SYSTEM_PROMPT + "\n\n" + rendered
    else:
        return BASE_SYSTEM_PROMPT + LEGACY_INJECTION_TEMPLATE.format(profile=rendered)
```

### Step 4: Run all prompt assembly tests

```bash
pytest tests/test_prompt_assembly.py -v
```

Expected: all 8 tests pass (3 original + 5 new).

### Step 5: Run full suite

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 6: Commit

```bash
git add app/runner/prompt_assembly.py tests/test_prompt_assembly.py
git commit -m "feat: assemble_mneme uses renderer; structured profiles get clean text injection"
```

---

## Task 9: Update `cli.py` — `add-user` accepts `--extra-context-path`

**Files:**
- Modify: `app/cli.py`

No dedicated test file needed — this is a thin CLI wrapper around already-tested functions.
Smoke-test manually at the end of this task.

### Step 1: Update the `add_user_command` in `app/cli.py`

Find the `add_user_command` function (starts at line 18) and replace it with:

```python
@click.command("add-user")
@click.argument("profile_path")
@click.option("--name", required=True)
@click.option("--source", default=None)
@click.option(
    "--extra-context-path",
    default=None,
    help="Optional path to a plain-text file with extra context (bio, notes, etc.)",
)
@with_appcontext
def add_user_command(profile_path, name, source, extra_context_path):
    import json
    from app.profiles.extractors import extract_qa_signals, extract_extra_context_signals
    from app.profiles.builder import build_mneme_profile
    from app.config import Config

    with open(profile_path) as f:
        raw = f.read()
    qa_input = json.loads(raw)  # validate JSON

    qa_signals = extract_qa_signals(qa_input)
    signals = {"qa": qa_signals}

    extra_text = None
    if extra_context_path:
        with open(extra_context_path) as f:
            extra_text = f.read()
        ec_signals = extract_extra_context_signals(extra_text, Config.ANTHROPIC_API_KEY)
        signals["extra_context"] = ec_signals
        click.echo(f"  Extra context loaded from {extra_context_path}")

    merged_profile = build_mneme_profile(signals)

    db = get_db()
    user = insert_user(
        db,
        name=name,
        mneme_profile=json.dumps(merged_profile),
        source=source,
        extra_context=extra_text,
    )
    click.echo(f"User created: {user['id']} ({name})")
```

### Step 2: Run full test suite

```bash
pytest --tb=short -q
```

Expected: all green (CLI changes don't affect unit tests).

### Step 3: Smoke-test with the sample canonical input

Create a temp file `test_qa_input.json`:

```json
{
  "decision_style": "analytical and deliberate",
  "risk_tolerance": "medium",
  "prioritization_rules": ["customer impact over efficiency", "speed to learning"],
  "communication_style": "direct, prefers bullet points",
  "constraints": ["no decisions without async alignment first"],
  "anti_patterns": ["analysis paralysis on reversible decisions"]
}
```

Run (with a real or test DB):
```bash
flask add-user test_qa_input.json --name "Test User"
```

Expected: `User created: <uuid> (Test User)`

Clean up: `rm test_qa_input.json`

### Step 4: Commit

```bash
git add app/cli.py
git commit -m "feat: add-user CLI builds structured profile via signal pipeline"
```

---

## Task 10: Add sample canonical QA input + user-facing docs

**Files:**
- Create: `examples/qa_profile_sample.json`
- Create: `docs/signal-based-profiles.md`

### Step 1: Create `examples/qa_profile_sample.json`

Create directory `examples/` if it doesn't exist. Create the file:

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
    "no decisions requiring more than 2 weeks lead time without async alignment first",
    "must preserve team psychological safety"
  ],
  "anti_patterns": [
    "analysis paralysis on reversible decisions",
    "consensus-seeking when a clear owner exists"
  ]
}
```

### Step 2: Create `docs/signal-based-profiles.md`

```markdown
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
```

### Step 3: Run full suite one final time

```bash
pytest --tb=short -q
```

Expected: all green.

### Step 4: Commit

```bash
git add examples/qa_profile_sample.json docs/signal-based-profiles.md
git commit -m "docs: add sample QA input and signal-based profiles documentation"
```

---

## Final verification

Run the complete test suite with verbose output:

```bash
pytest -v
```

Confirm:
- `tests/test_signal_extractors.py` — all pass
- `tests/test_profile_builder.py` — all pass
- `tests/test_profile_renderer.py` — all pass
- `tests/test_prompt_assembly.py` — all pass (including original 3 backward-compat tests)
- All pre-existing tests — unchanged, all pass

---

## Summary of files

### New files
| File | Purpose |
|---|---|
| `app/profiles/__init__.py` | Package marker |
| `app/profiles/signals.py` | Signal schema and factory |
| `app/profiles/extractors.py` | QA extractor, legacy adapter, extra-context extractor |
| `app/profiles/builder.py` | Deterministic merge |
| `app/profiles/renderer.py` | Structured text renderer |
| `tests/test_signal_extractors.py` | Extractor tests (Claude mocked) |
| `tests/test_profile_builder.py` | Merge rule tests |
| `tests/test_profile_renderer.py` | Renderer tests |
| `examples/qa_profile_sample.json` | Sample canonical QA input |
| `docs/signal-based-profiles.md` | Flow documentation |
| `migrate_add_extra_context.sql` | One-time migration for existing DBs |

### Modified files
| File | Change |
|---|---|
| `schema.sql` | Add `extra_context TEXT` column to `users` |
| `app/models/user.py` | Add `extra_context` param to `insert_user()` |
| `app/runner/prompt_assembly.py` | `assemble_mneme()` calls renderer internally |
| `app/cli.py` | `add-user` builds structured profile via signal pipeline |
| `tests/test_prompt_assembly.py` | Extended for new render paths |
