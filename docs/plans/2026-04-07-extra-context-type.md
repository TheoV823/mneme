# Extra Context Type Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an optional `extra_context_type` field (`chat` | `document` | `notes`) to the users table and `add-user` CLI so the signal extractor can use type-specific prompting.

**Architecture:** One new nullable column in `users`, threaded through `insert_user()`, `extract_extra_context_signals()`, and the `add-user` CLI option. No new modules. The type hint is appended to the Claude extraction system prompt so the model knows what kind of text it is reading. Four tasks, each independently testable.

**Tech Stack:** Python 3.12, Flask CLI (Click), SQLite (raw sqlite3), pytest, anthropic SDK

---

## Codebase Orientation

Working directory: `C:/dev/mneme/.worktrees/extra-context-type` (branch: `feature/extra-context-type`)

Relevant files:
- `schema.sql` — SQLite DDL (source of truth for `init-db`)
- `app/models/user.py` — `insert_user(db, name, mneme_profile, source=None, extra_context=None)`
- `app/profiles/extractors.py` — `extract_extra_context_signals(text, api_key)` calls `_call_claude_for_extraction(text, api_key)` which uses `_EXTRACTION_SYSTEM_PROMPT`
- `app/cli.py` — `add_user_command` has `--extra-context-path` option; calls `extract_extra_context_signals` and `insert_user`
- `tests/test_models_user.py` — model tests (use `db` fixture)
- `tests/test_signal_extractors.py` — extractor tests (mock `_call_claude_for_extraction`)
- `tests/conftest.py` — `app` and `db` fixtures

Run tests with: `python -m pytest tests/ -q`

Baseline: **78 tests passing**.

---

## Task 1: Add `extra_context_type` column to schema + migration

**Files:**
- Modify: `schema.sql`
- Create: `migrate_add_extra_context_type.sql`

**Step 1: Add column to `schema.sql`**

Open `schema.sql`. Find the `users` table definition. It currently ends with:

```sql
    extra_context  TEXT,
    source        TEXT,
    created_at    TEXT NOT NULL
```

Add `extra_context_type` between `extra_context` and `source`:

```sql
    extra_context  TEXT,
    extra_context_type TEXT CHECK (extra_context_type IN ('chat', 'document', 'notes')),
    source        TEXT,
    created_at    TEXT NOT NULL
```

**Step 2: Create `migrate_add_extra_context_type.sql` in the repo root**

```sql
-- Run once on any database created before 2026-04-07.
-- NOTE: SQLite does not support IF NOT EXISTS on ADD COLUMN — run this exactly once.
ALTER TABLE users ADD COLUMN extra_context_type TEXT CHECK (extra_context_type IN ('chat', 'document', 'notes'));
```

**Step 3: Verify existing tests still pass**

Run:
```bash
python -m pytest tests/test_db.py tests/test_models_user.py -v
```
Expected: all pass (schema loaded fresh per test via `init_db` in conftest).

**Step 4: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 78 tests pass, 0 failures.

**Step 5: Commit**

```bash
git add schema.sql migrate_add_extra_context_type.sql
git commit -m "feat: add extra_context_type column to users schema and migration"
```

---

## Task 2: `app/models/user.py` — add `extra_context_type` parameter

**Files:**
- Modify: `app/models/user.py`
- Modify: `tests/test_models_user.py`

**Step 1: Write the failing test**

Open `tests/test_models_user.py`. Add these two tests at the bottom:

```python
def test_insert_user_with_extra_context_type(db):
    u = insert_user(db, name="Bob", mneme_profile="{}", extra_context="some notes",
                    extra_context_type="notes")
    assert u["extra_context_type"] == "notes"


def test_insert_user_extra_context_type_defaults_to_none(db):
    u = insert_user(db, name="Bob", mneme_profile="{}")
    assert u["extra_context_type"] is None
```

You'll need to check what imports are already at the top of `test_models_user.py` — `insert_user` should already be imported.

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_models_user.py::test_insert_user_with_extra_context_type tests/test_models_user.py::test_insert_user_extra_context_type_defaults_to_none -v
```
Expected: FAIL — `insert_user` doesn't accept `extra_context_type` yet.

**Step 3: Update `app/models/user.py`**

Current function signature:
```python
def insert_user(db, name, mneme_profile, source=None, extra_context=None):
```

Updated function (full replacement):

```python
def insert_user(db, name, mneme_profile, source=None, extra_context=None, extra_context_type=None):
    user_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO users (id, name, mneme_profile, extra_context, extra_context_type, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, name, mneme_profile, extra_context, extra_context_type, source, created_at),
    )
    db.commit()
    return {
        "id": user_id,
        "name": name,
        "mneme_profile": mneme_profile,
        "extra_context": extra_context,
        "extra_context_type": extra_context_type,
        "source": source,
        "created_at": created_at,
    }
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_models_user.py -v
```
Expected: all tests (existing + 2 new) PASS.

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 80 tests pass (78 + 2), 0 failures.

**Step 6: Commit**

```bash
git add app/models/user.py tests/test_models_user.py
git commit -m "feat: add extra_context_type param to insert_user"
```

---

## Task 3: `app/profiles/extractors.py` — type-aware extraction prompt

**Files:**
- Modify: `app/profiles/extractors.py`
- Modify: `tests/test_signal_extractors.py`

### Context

Currently `extract_extra_context_signals(text, api_key)` calls `_call_claude_for_extraction(text, api_key)` which uses a single global `_EXTRACTION_SYSTEM_PROMPT`.

The goal: when `context_type` is provided, append a type-specific hint to the system prompt so Claude knows what kind of text it is reading.

Type hints:
- `"chat"` → `"Focus on: tone, recurring trade-offs, and decision habits inferred from conversation patterns."`
- `"document"` → `"Focus on: explicitly stated priorities, formal structure, and written constraints."`
- `"notes"` → `"Focus on: heuristics, rules of thumb, and personal working-style principles."`

### Step 1: Write the failing tests

Open `tests/test_signal_extractors.py`. At the bottom, add:

```python
# --- extract_extra_context_signals with context_type ---

def test_extract_extra_context_signals_passes_type_hint_to_prompt():
    """When context_type is given, the system prompt should include the type hint."""
    claude_response = (
        '{"decision_style": "direct", "risk_tolerance": null, '
        '"communication_style": null, '
        '"prioritization_rules": [], "constraints": [], "anti_patterns": []}'
    )
    captured = {}

    def fake_call_claude(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {"output": claude_response, "metadata": {}}

    with patch("app.profiles.extractors.call_claude", fake_call_claude):
        signals = extract_extra_context_signals("some text", api_key="fake",
                                                context_type="chat")

    assert signals["decision_style"] == "direct"
    assert "conversation patterns" in captured["system_prompt"]


def test_extract_extra_context_signals_document_type_hint():
    claude_response = (
        '{"decision_style": null, "risk_tolerance": null, '
        '"communication_style": null, '
        '"prioritization_rules": [], "constraints": [], "anti_patterns": []}'
    )
    captured = {}

    def fake_call_claude(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {"output": claude_response, "metadata": {}}

    with patch("app.profiles.extractors.call_claude", fake_call_claude):
        extract_extra_context_signals("some text", api_key="fake",
                                     context_type="document")

    assert "formal structure" in captured["system_prompt"]


def test_extract_extra_context_signals_notes_type_hint():
    claude_response = (
        '{"decision_style": null, "risk_tolerance": null, '
        '"communication_style": null, '
        '"prioritization_rules": [], "constraints": [], "anti_patterns": []}'
    )
    captured = {}

    def fake_call_claude(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {"output": claude_response, "metadata": {}}

    with patch("app.profiles.extractors.call_claude", fake_call_claude):
        extract_extra_context_signals("some text", api_key="fake",
                                     context_type="notes")

    assert "rules of thumb" in captured["system_prompt"]


def test_extract_extra_context_signals_no_type_uses_base_prompt():
    """When context_type is None (default), no type hint is appended."""
    claude_response = (
        '{"decision_style": null, "risk_tolerance": null, '
        '"communication_style": null, '
        '"prioritization_rules": [], "constraints": [], "anti_patterns": []}'
    )
    captured = {}

    def fake_call_claude(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {"output": claude_response, "metadata": {}}

    with patch("app.profiles.extractors.call_claude", fake_call_claude):
        extract_extra_context_signals("some text", api_key="fake")

    # Base prompt only — no type-specific phrases
    assert "conversation patterns" not in captured["system_prompt"]
    assert "formal structure" not in captured["system_prompt"]
    assert "rules of thumb" not in captured["system_prompt"]
```

**Important:** These tests patch `app.profiles.extractors.call_claude` directly (not `_call_claude_for_extraction`). The existing tests patch `app.profiles.extractors._call_claude_for_extraction`. Both work — just make sure you don't change the existing mock targets.

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_signal_extractors.py::test_extract_extra_context_signals_passes_type_hint_to_prompt -v
```
Expected: FAIL — `extract_extra_context_signals` doesn't accept `context_type` yet.

**Step 3: Update `app/profiles/extractors.py`**

Current constants (around line 92):
```python
_EXTRACTION_MODEL = "claude-haiku-4-20250514"
_EXTRACTION_SYSTEM_PROMPT = (
    "You are a signal extractor. ..."
)
```

Add a type-hint dict after `_EXTRACTION_SYSTEM_PROMPT`:

```python
_CONTEXT_TYPE_HINTS = {
    "chat": "Focus on: tone, recurring trade-offs, and decision habits inferred from conversation patterns.",
    "document": "Focus on: explicitly stated priorities, formal structure, and written constraints.",
    "notes": "Focus on: heuristics, rules of thumb, and personal working-style principles.",
}
```

Update `_call_claude_for_extraction` to accept `context_type`:

```python
def _call_claude_for_extraction(text, api_key, context_type=None):
    """Private: call Claude API to extract signals. Returns raw response string."""
    from app.runner.claude_client import call_claude
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
```

Update `extract_extra_context_signals` signature to accept and pass `context_type`:

```python
def extract_extra_context_signals(text, api_key, context_type=None):
    """Extract signals from free-form extra context text via Claude API.

    context_type: 'chat' | 'document' | 'notes' | None
        When provided, the extraction prompt is tailored to the kind of text
        being read. None uses the generic base prompt.

    Returns empty_source_signals() on any failure — never raises.
    """
    try:
        raw = _call_claude_for_extraction(text, api_key, context_type=context_type)
        parsed = json.loads(raw)
    except Exception as e:
        logger.warning("extract_extra_context_signals failed: %s", e)
        return empty_source_signals()
    # ... rest of function unchanged ...
```

Only the first 3 lines of the function body change (adding `context_type=context_type` to the call). The rest of the signal parsing logic is unchanged.

**Step 4: Run new tests**

```bash
python -m pytest tests/test_signal_extractors.py -v 2>&1 | tail -15
```
Expected: all tests pass (existing 19 + 4 new = 23).

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 84 tests pass (80 + 4), 0 failures.

**Step 6: Commit**

```bash
git add app/profiles/extractors.py tests/test_signal_extractors.py
git commit -m "feat: type-aware extraction prompt — chat/document/notes hint appended to system prompt"
```

---

## Task 4: `app/cli.py` — `--extra-context-type` option for `add-user`

**Files:**
- Modify: `app/cli.py`
- Modify: `tests/test_models_user.py` (or a new CLI test file if one exists)

**Step 1: Write the failing test**

Open `tests/test_models_user.py` and add this test at the bottom:

```python
def test_add_user_command_accepts_extra_context_type(app, db, tmp_path):
    """add-user passes --extra-context-type to insert_user."""
    from click.testing import CliRunner
    from app.cli import add_user_command
    from unittest.mock import patch

    profile_file = tmp_path / "profile.json"
    profile_file.write_text('{"decision_style": "analytical"}')

    runner = CliRunner()
    with app.app_context():
        with patch("app.cli.extract_extra_context_signals",
                   return_value={"decision_style": None, "risk_tolerance": None,
                                 "communication_style": None, "prioritization_rules": [],
                                 "constraints": [], "anti_patterns": []}):
            result = runner.invoke(
                add_user_command,
                ["str(profile_file)", "--name", "Test", "--extra-context-path",
                 str(profile_file), "--extra-context-type", "notes"],
            )

    assert result.exit_code == 0, result.output

    from app.models.user import list_users
    users = list_users(db)
    assert len(users) == 1
    assert users[0]["extra_context_type"] == "notes"
```

Wait — the test above has a bug (passing the profile path as a string literal). Use this corrected version instead:

```python
def test_add_user_command_stores_extra_context_type(app, db, tmp_path):
    """--extra-context-type is stored on the created user."""
    from click.testing import CliRunner
    from app.cli import add_user_command
    from unittest.mock import patch
    from app.models.user import list_users

    profile_file = tmp_path / "profile.json"
    profile_file.write_text('{"decision_style": "analytical"}')

    extra_file = tmp_path / "notes.txt"
    extra_file.write_text("I prefer async communication.")

    fake_ec_signals = {
        "decision_style": None, "risk_tolerance": None, "communication_style": None,
        "prioritization_rules": [], "constraints": [], "anti_patterns": [],
    }

    runner = CliRunner()
    with app.app_context():
        with patch("app.cli.extract_extra_context_signals", return_value=fake_ec_signals):
            result = runner.invoke(
                add_user_command,
                [str(profile_file), "--name", "Test",
                 "--extra-context-path", str(extra_file),
                 "--extra-context-type", "notes"],
            )

    assert result.exit_code == 0, result.output
    users = list_users(db)
    assert len(users) == 1
    assert users[0]["extra_context_type"] == "notes"
```

**Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_models_user.py::test_add_user_command_stores_extra_context_type -v
```
Expected: FAIL (option doesn't exist yet).

**Step 3: Update `app/cli.py`**

Find the `add_user_command` function. It currently has:

```python
@click.option(
    "--extra-context-path",
    default=None,
    help="Optional path to a plain-text file with extra context (bio, notes, etc.)",
)
@with_appcontext
def add_user_command(profile_path, name, source, extra_context_path):
```

Add a new option and parameter (insert after `--extra-context-path`):

```python
@click.option(
    "--extra-context-type",
    default=None,
    type=click.Choice(["chat", "document", "notes"], case_sensitive=False),
    help="Type of extra context: chat | document | notes",
)
@with_appcontext
def add_user_command(profile_path, name, source, extra_context_path, extra_context_type):
```

Inside the function body, find where `extract_extra_context_signals` is called:

```python
ec_signals = extract_extra_context_signals(extra_text, Config.ANTHROPIC_API_KEY)
```

Change to:

```python
ec_signals = extract_extra_context_signals(extra_text, Config.ANTHROPIC_API_KEY,
                                           context_type=extra_context_type)
```

Find where `insert_user` is called:

```python
user = insert_user(
    db,
    name=name,
    mneme_profile=json.dumps(merged_profile),
    source=source,
    extra_context=extra_text,
)
```

Add `extra_context_type`:

```python
user = insert_user(
    db,
    name=name,
    mneme_profile=json.dumps(merged_profile),
    source=source,
    extra_context=extra_text,
    extra_context_type=extra_context_type,
)
```

**Step 4: Run the test**

```bash
python -m pytest tests/test_models_user.py::test_add_user_command_stores_extra_context_type -v
```
Expected: PASS.

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 85 tests pass (84 + 1), 0 failures.

**Step 6: Commit**

```bash
git add app/cli.py tests/test_models_user.py
git commit -m "feat: add --extra-context-type option to add-user CLI"
```

---

## Final Verification

After all 4 tasks:

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```
Expected: **85 tests**, 0 failures.

Check CLI options are wired up:
```bash
flask add-user --help
```
Expected output includes:
```
  --extra-context-path TEXT
  --extra-context-type [chat|document|notes]
```
