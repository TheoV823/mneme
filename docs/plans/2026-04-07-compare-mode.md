# Compare Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a CLI `compare` command that runs a prompt against both default AI and Mneme-personalized AI, presents both outputs blind (randomized A/B), captures a human preference, and persists the result — plus a `compare-stats` command to show cumulative win rate.

**Architecture:** New `app/models/comparison.py` handles persistence; new `app/runner/compare.py` calls the Claude API twice and randomizes A/B assignment; two new CLI commands (`compare`, `compare-stats`) wire it together. All logic lives in small, testable units. No frontend.

**Tech Stack:** Python 3.12, Flask CLI (Click), SQLite (raw sqlite3), anthropic SDK, pytest

---

## Codebase Orientation

The worktree is at `C:/dev/mneme/.worktrees/compare-mode` on branch `feature/compare-mode`.

Relevant existing files:
- `schema.sql` — SQLite table definitions (source of truth, used by `init-db`)
- `app/__init__.py` — Flask app factory; registers CLI commands
- `app/cli.py` — All CLI command functions live here
- `app/models/user.py` — Pattern to follow for model files
- `app/runner/claude_client.py` — `call_claude(*, api_key, model, system_prompt, user_prompt, temperature, max_tokens)` → `{"output": str, "metadata": dict}`
- `app/runner/prompt_assembly.py` — `assemble_default()` and `assemble_mneme(mneme_profile)`
- `app/config.py` — `Config.ANTHROPIC_API_KEY`, `Config.MODEL`, `Config.TEMPERATURE`, `Config.MAX_TOKENS`
- `tests/conftest.py` — `app` and `db` fixtures (use `db` fixture for model tests)

Run tests with: `python -m pytest tests/ -q`

---

## Task 1: Add `comparison_results` table to schema + create migration

**Files:**
- Modify: `schema.sql`
- Create: `migrate_add_comparison_results.sql`

**Step 1: Add table to schema.sql**

Open `schema.sql`. After the `metrics_snapshots` table block, add:

```sql
CREATE TABLE IF NOT EXISTS comparison_results (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    prompt       TEXT NOT NULL,
    option_a_mode TEXT NOT NULL CHECK (option_a_mode IN ('default', 'mneme')),
    option_b_mode TEXT NOT NULL CHECK (option_b_mode IN ('default', 'mneme')),
    winner       TEXT NOT NULL CHECK (winner IN ('A', 'B', 'tie', 'skip')),
    preferred_mode TEXT CHECK (preferred_mode IN ('default', 'mneme')),
    created_at   TEXT NOT NULL
);
```

**Step 2: Create migration file**

Create `migrate_add_comparison_results.sql`:

```sql
-- Run once on any database created before 2026-04-07 (the compare-mode feature date).
-- CREATE TABLE IF NOT EXISTS is safe to run multiple times — it is a no-op if the table exists.
CREATE TABLE IF NOT EXISTS comparison_results (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    prompt       TEXT NOT NULL,
    option_a_mode TEXT NOT NULL CHECK (option_a_mode IN ('default', 'mneme')),
    option_b_mode TEXT NOT NULL CHECK (option_b_mode IN ('default', 'mneme')),
    winner       TEXT NOT NULL CHECK (winner IN ('A', 'B', 'tie', 'skip')),
    preferred_mode TEXT CHECK (preferred_mode IN ('default', 'mneme')),
    created_at   TEXT NOT NULL
);
```

**Step 3: Verify the schema is valid SQL**

Run:
```bash
python -m pytest tests/test_db.py -v
```
Expected: all existing DB tests still pass (schema loaded by `init_db` in conftest).

**Step 4: Commit**

```bash
git add schema.sql migrate_add_comparison_results.sql
git commit -m "feat: add comparison_results table to schema and migration"
```

---

## Task 2: `app/models/comparison.py` — persistence layer

**Files:**
- Create: `app/models/comparison.py`
- Create: `tests/test_models_comparison.py`

**Step 1: Write the failing tests first**

Create `tests/test_models_comparison.py`:

```python
import pytest
from app.models.comparison import insert_comparison, get_comparisons_for_user, compute_win_rate
from app.models.user import insert_user


def _make_user(db):
    return insert_user(db, name="Alice", mneme_profile='{"decision_style": null}', source="test")


# --- insert_comparison + get_comparisons_for_user ---

def test_insert_comparison_and_retrieve(db):
    user = _make_user(db)
    c = insert_comparison(
        db,
        user_id=user["id"],
        prompt="How do you grow a product?",
        option_a_mode="default",
        option_b_mode="mneme",
        winner="B",
        preferred_mode="mneme",
    )
    assert c["id"]
    assert c["winner"] == "B"
    assert c["preferred_mode"] == "mneme"
    assert c["user_id"] == user["id"]

    rows = get_comparisons_for_user(db, user["id"])
    assert len(rows) == 1
    assert rows[0]["prompt"] == "How do you grow a product?"
    assert rows[0]["preferred_mode"] == "mneme"


def test_insert_comparison_tie_has_no_preferred_mode(db):
    user = _make_user(db)
    c = insert_comparison(
        db,
        user_id=user["id"],
        prompt="test prompt",
        option_a_mode="mneme",
        option_b_mode="default",
        winner="tie",
        preferred_mode=None,
    )
    assert c["winner"] == "tie"
    assert c["preferred_mode"] is None


def test_get_comparisons_for_user_empty(db):
    user = _make_user(db)
    rows = get_comparisons_for_user(db, user["id"])
    assert rows == []


def test_get_comparisons_for_user_multiple(db):
    user = _make_user(db)
    insert_comparison(db, user_id=user["id"], prompt="p1", option_a_mode="default",
                      option_b_mode="mneme", winner="A", preferred_mode="default")
    insert_comparison(db, user_id=user["id"], prompt="p2", option_a_mode="mneme",
                      option_b_mode="default", winner="A", preferred_mode="mneme")
    rows = get_comparisons_for_user(db, user["id"])
    assert len(rows) == 2


# --- compute_win_rate ---

def test_compute_win_rate_typical():
    comparisons = [
        {"winner": "A", "preferred_mode": "mneme"},
        {"winner": "B", "preferred_mode": "default"},
        {"winner": "A", "preferred_mode": "mneme"},
        {"winner": "tie", "preferred_mode": None},
        {"winner": "skip", "preferred_mode": None},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["mneme_wins"] == 2
    assert stats["default_wins"] == 1
    assert stats["ties"] == 1
    assert stats["skips"] == 1
    assert stats["total"] == 5
    assert abs(stats["win_rate"] - 2 / 3) < 0.001


def test_compute_win_rate_no_decisive():
    comparisons = [
        {"winner": "tie", "preferred_mode": None},
        {"winner": "skip", "preferred_mode": None},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["win_rate"] is None


def test_compute_win_rate_all_mneme():
    comparisons = [
        {"winner": "A", "preferred_mode": "mneme"},
        {"winner": "B", "preferred_mode": "mneme"},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["win_rate"] == 1.0


def test_compute_win_rate_empty():
    stats = compute_win_rate([])
    assert stats["mneme_wins"] == 0
    assert stats["total"] == 0
    assert stats["win_rate"] is None
```

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_models_comparison.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.models.comparison'`

**Step 3: Implement `app/models/comparison.py`**

```python
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_comparison(db, *, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode):
    row_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO comparison_results
           (id, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (row_id, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode, created_at),
    )
    db.commit()
    return {
        "id": row_id,
        "user_id": user_id,
        "prompt": prompt,
        "option_a_mode": option_a_mode,
        "option_b_mode": option_b_mode,
        "winner": winner,
        "preferred_mode": preferred_mode,
        "created_at": created_at,
    }


def get_comparisons_for_user(db, user_id):
    rows = db.execute(
        "SELECT * FROM comparison_results WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def compute_win_rate(comparisons):
    """Return win-rate stats dict.

    win_rate = mneme_wins / (mneme_wins + default_wins).
    Ties and skips are excluded from the denominator but counted separately.
    Returns None for win_rate when there are no decisive comparisons.
    """
    mneme_wins = sum(1 for c in comparisons if c["preferred_mode"] == "mneme")
    default_wins = sum(1 for c in comparisons if c["preferred_mode"] == "default")
    ties = sum(1 for c in comparisons if c["winner"] == "tie")
    skips = sum(1 for c in comparisons if c["winner"] == "skip")
    total = len(comparisons)
    denominator = mneme_wins + default_wins
    win_rate = mneme_wins / denominator if denominator > 0 else None
    return {
        "mneme_wins": mneme_wins,
        "default_wins": default_wins,
        "ties": ties,
        "skips": skips,
        "total": total,
        "win_rate": win_rate,
    }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_models_comparison.py -v
```
Expected: all 8 tests PASS.

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 78 + 8 = 86 tests pass, 0 failures.

**Step 6: Commit**

```bash
git add app/models/comparison.py tests/test_models_comparison.py
git commit -m "feat: add comparison_results model with insert, fetch, and win-rate"
```

---

## Task 3: `app/runner/compare.py` — runs two LLM calls, randomizes A/B

**Files:**
- Create: `app/runner/compare.py`
- Create: `tests/test_compare_runner.py`

**Step 1: Write the failing tests first**

Create `tests/test_compare_runner.py`:

```python
from unittest.mock import patch, call
from app.runner.compare import run_comparison


_FAKE_USER = {"id": "u1", "mneme_profile": '{"decision_style": null}'}
_FAKE_DEFAULT = {"output": "default_output", "metadata": {}}
_FAKE_MNEME = {"output": "mneme_output", "metadata": {}}

_CALL_KWARGS = dict(user=_FAKE_USER, prompt_text="test prompt",
                    api_key="k", model="m", temperature=0.7, max_tokens=100)


def test_run_comparison_a_is_default_when_coin_true():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]) as mock_call:
        with patch("app.runner.compare.random.choice", return_value=True):
            result = run_comparison(**_CALL_KWARGS)

    assert result["option_a_mode"] == "default"
    assert result["option_b_mode"] == "mneme"
    assert result["output_a"] == "default_output"
    assert result["output_b"] == "mneme_output"


def test_run_comparison_a_is_mneme_when_coin_false():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]):
        with patch("app.runner.compare.random.choice", return_value=False):
            result = run_comparison(**_CALL_KWARGS)

    assert result["option_a_mode"] == "mneme"
    assert result["option_b_mode"] == "default"
    assert result["output_a"] == "mneme_output"
    assert result["output_b"] == "default_output"


def test_run_comparison_calls_claude_twice():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]) as mock_call:
        with patch("app.runner.compare.random.choice", return_value=True):
            run_comparison(**_CALL_KWARGS)

    assert mock_call.call_count == 2


def test_run_comparison_result_keys():
    with patch("app.runner.compare.call_claude", side_effect=[_FAKE_DEFAULT, _FAKE_MNEME]):
        with patch("app.runner.compare.random.choice", return_value=True):
            result = run_comparison(**_CALL_KWARGS)

    assert set(result.keys()) == {"output_a", "output_b", "option_a_mode", "option_b_mode"}
```

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_compare_runner.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.runner.compare'`

**Step 3: Implement `app/runner/compare.py`**

```python
import random
from app.runner.claude_client import call_claude
from app.runner.prompt_assembly import assemble_default, assemble_mneme


def run_comparison(*, user, prompt_text, api_key, model, temperature, max_tokens):
    """Run a single prompt against both default and Mneme-personalized AI.

    Both API calls are made before returning. A/B assignment is randomized
    so the caller sees a blind comparison without knowing which mode is which.

    Returns:
        {
            "output_a": str,
            "output_b": str,
            "option_a_mode": "default" | "mneme",
            "option_b_mode": "default" | "mneme",
        }

    Raises:
        Any exception from call_claude propagates — do not swallow.
        The caller is responsible for handling API failures.
    """
    system_default = assemble_default()
    system_mneme = assemble_mneme(user["mneme_profile"])

    result_default = call_claude(
        api_key=api_key, model=model, system_prompt=system_default,
        user_prompt=prompt_text, temperature=temperature, max_tokens=max_tokens,
    )
    result_mneme = call_claude(
        api_key=api_key, model=model, system_prompt=system_mneme,
        user_prompt=prompt_text, temperature=temperature, max_tokens=max_tokens,
    )

    # Randomly assign which mode is shown as A vs B (blind comparison)
    if random.choice([True, False]):
        option_a_mode, option_b_mode = "default", "mneme"
        output_a, output_b = result_default["output"], result_mneme["output"]
    else:
        option_a_mode, option_b_mode = "mneme", "default"
        output_a, output_b = result_mneme["output"], result_default["output"]

    return {
        "output_a": output_a,
        "output_b": output_b,
        "option_a_mode": option_a_mode,
        "option_b_mode": option_b_mode,
    }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_compare_runner.py -v
```
Expected: all 4 tests PASS.

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 90 tests pass, 0 failures.

**Step 6: Commit**

```bash
git add app/runner/compare.py tests/test_compare_runner.py
git commit -m "feat: add compare runner — two LLM calls with randomized A/B assignment"
```

---

## Task 4: `compare` CLI command

**Files:**
- Modify: `app/cli.py` — add `compare_command`
- Modify: `app/__init__.py` — register the new command
- Create: `tests/test_compare_cli.py`

**Step 1: Write the failing tests first**

Create `tests/test_compare_cli.py`:

```python
import pytest
from unittest.mock import patch
from click.testing import CliRunner
from app.cli import compare_command, compare_stats_command
from app.models.user import insert_user
from app.models.comparison import get_comparisons_for_user


_FAKE_RUN_RESULT = {
    "output_a": "Default answer here.",
    "output_b": "Mneme answer here.",
    "option_a_mode": "default",
    "option_b_mode": "mneme",
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def user_id(db, app):
    with app.app_context():
        u = insert_user(db, name="Test User",
                        mneme_profile='{"decision_style": null}', source="test")
        return u["id"]


def test_compare_command_records_winner_b(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "How do you grow a product?"],
                input="B\n",
            )

    assert result.exit_code == 0, result.output
    assert "Option A" in result.output
    assert "Option B" in result.output

    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert len(rows) == 1
    assert rows[0]["winner"] == "B"
    assert rows[0]["preferred_mode"] == "mneme"


def test_compare_command_records_tie(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "Test prompt"],
                input="tie\n",
            )

    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "tie"
    assert rows[0]["preferred_mode"] is None


def test_compare_command_records_skip(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "Test prompt"],
                input="skip\n",
            )

    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "skip"
    assert rows[0]["preferred_mode"] is None


def test_compare_command_unknown_user_exits(runner, app):
    with app.app_context():
        result = runner.invoke(
            compare_command,
            ["--user-id", "nonexistent-id", "--prompt", "test"],
        )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_compare_command_invalid_choice_reprompts(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "test"],
                input="X\nA\n",  # invalid then valid
            )
    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "A"
```

**Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_compare_cli.py -v
```
Expected: `ImportError` (compare_command not defined yet).

**Step 3: Add `compare_command` to `app/cli.py`**

Add this function anywhere after the existing imports in `app/cli.py`. It uses `with_appcontext` like all other commands:

```python
@click.command("compare")
@click.option("--user-id", required=True, help="User ID to compare against.")
@click.option("--prompt", "prompt_text", required=True, help="Prompt to send to both AI modes.")
@with_appcontext
def compare_command(user_id, prompt_text):
    """Run a prompt against default AI and Mneme AI. Choose which output you prefer."""
    from app.runner.compare import run_comparison
    from app.models.comparison import insert_comparison

    db = get_db()
    user = get_user(db, user_id)
    if not user:
        raise click.ClickException(f"User not found: {user_id}")

    click.echo(f"\nRunning comparison for {user['name']}...")

    try:
        result = run_comparison(
            user=user,
            prompt_text=prompt_text,
            api_key=Config.ANTHROPIC_API_KEY,
            model=Config.MODEL,
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
        )
    except Exception as e:
        raise click.ClickException(f"LLM call failed: {e}")

    sep = "─" * 60
    click.echo(f"\n{sep}")
    click.echo(f"PROMPT:\n{prompt_text}")
    click.echo(sep)
    click.echo(f"Option A:\n\n{result['output_a']}")
    click.echo(sep)
    click.echo(f"Option B:\n\n{result['output_b']}")
    click.echo(sep)

    valid = {"a", "b", "tie", "skip"}
    choice = ""
    while choice not in valid:
        raw = click.prompt("Which is better? (A/B/tie/skip)").strip().lower()
        if raw in valid:
            choice = raw

    # Normalise to uppercase A/B for storage
    winner = choice.upper() if choice in ("a", "b") else choice

    if winner == "A":
        preferred_mode = result["option_a_mode"]
    elif winner == "B":
        preferred_mode = result["option_b_mode"]
    else:
        preferred_mode = None

    insert_comparison(
        db,
        user_id=user_id,
        prompt=prompt_text,
        option_a_mode=result["option_a_mode"],
        option_b_mode=result["option_b_mode"],
        winner=winner,
        preferred_mode=preferred_mode,
    )

    if preferred_mode:
        click.echo(f"\n✓ Saved. You preferred: {preferred_mode}")
    else:
        click.echo(f"\n✓ Saved. ({winner})")
```

Also add `get_user` to the imports at the top of `app/cli.py` — it's already imported in the models section: `from app.models.user import insert_user, list_users`. Change that line to:

```python
from app.models.user import insert_user, list_users, get_user
```

**Step 4: Register in `app/__init__.py`**

In `app/__init__.py`, find the block that imports from `app.cli` and adds commands. Add `compare_command` and `compare_stats_command` (coming in Task 5) to both the import and the `add_command` calls:

```python
from app.cli import (add_user_command, add_prompt_command, run_benchmark_command,
                     generate_assignments_command, report_command, export_command,
                     seed_demo_command, compare_command, compare_stats_command)
app.cli.add_command(compare_command)
app.cli.add_command(compare_stats_command)
```

**Important:** `compare_stats_command` doesn't exist yet — to avoid a broken import while Task 5 is pending, add a temporary stub at the bottom of `app/cli.py` right after `compare_command`:

```python
@click.command("compare-stats")
@click.option("--user-id", required=True)
@with_appcontext
def compare_stats_command(user_id):
    """Show Mneme win rate for a user. (stub — implemented in Task 5)"""
    click.echo("compare-stats not yet implemented")
```

This stub will be replaced in Task 5.

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_compare_cli.py -v
```
Expected: all 5 tests PASS.

**Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 95 tests pass, 0 failures.

**Step 7: Commit**

```bash
git add app/cli.py app/__init__.py tests/test_compare_cli.py
git commit -m "feat: add compare CLI command with blind A/B presentation and persistence"
```

---

## Task 5: `compare-stats` CLI command

**Files:**
- Modify: `app/cli.py` — replace stub with real `compare_stats_command`
- Modify: `tests/test_compare_cli.py` — add stats tests

**Step 1: Write the failing tests**

Add these tests to the bottom of `tests/test_compare_cli.py`:

```python
def test_compare_stats_shows_win_rate(runner, app, db, user_id):
    from app.models.comparison import insert_comparison
    with app.app_context():
        insert_comparison(db, user_id=user_id, prompt="p1", option_a_mode="default",
                          option_b_mode="mneme", winner="B", preferred_mode="mneme")
        insert_comparison(db, user_id=user_id, prompt="p2", option_a_mode="default",
                          option_b_mode="mneme", winner="A", preferred_mode="default")
        insert_comparison(db, user_id=user_id, prompt="p3", option_a_mode="mneme",
                          option_b_mode="default", winner="tie", preferred_mode=None)
        result = runner.invoke(compare_stats_command, ["--user-id", user_id])

    assert result.exit_code == 0
    assert "50.0%" in result.output or "50%" in result.output
    assert "Mneme wins" in result.output
    assert "Total" in result.output


def test_compare_stats_no_comparisons(runner, app, db, user_id):
    with app.app_context():
        result = runner.invoke(compare_stats_command, ["--user-id", user_id])
    assert result.exit_code == 0
    assert "No comparisons" in result.output


def test_compare_stats_unknown_user_exits(runner, app):
    with app.app_context():
        result = runner.invoke(compare_stats_command, ["--user-id", "bad-id"])
    assert result.exit_code != 0


def test_compare_stats_no_decisive_shows_na(runner, app, db, user_id):
    from app.models.comparison import insert_comparison
    with app.app_context():
        insert_comparison(db, user_id=user_id, prompt="p1", option_a_mode="default",
                          option_b_mode="mneme", winner="tie", preferred_mode=None)
        result = runner.invoke(compare_stats_command, ["--user-id", user_id])
    assert result.exit_code == 0
    assert "N/A" in result.output or "n/a" in result.output.lower()
```

**Step 2: Run to verify new tests fail**

```bash
python -m pytest tests/test_compare_cli.py::test_compare_stats_shows_win_rate -v
```
Expected: FAIL — stub returns "not yet implemented".

**Step 3: Replace the stub in `app/cli.py`**

Find the stub `compare_stats_command` and replace its entire body:

```python
@click.command("compare-stats")
@click.option("--user-id", required=True, help="User ID to show stats for.")
@with_appcontext
def compare_stats_command(user_id):
    """Show cumulative Mneme win rate for a user across all comparisons."""
    from app.models.comparison import get_comparisons_for_user, compute_win_rate

    db = get_db()
    user = get_user(db, user_id)
    if not user:
        raise click.ClickException(f"User not found: {user_id}")

    comparisons = get_comparisons_for_user(db, user_id)
    if not comparisons:
        click.echo(f"No comparisons found for {user['name']}.")
        return

    stats = compute_win_rate(comparisons)
    wr = f"{stats['win_rate']:.1%}" if stats["win_rate"] is not None else "N/A"

    click.echo(f"\nMneme comparison stats for {user['name']}:")
    click.echo(f"  Total comparisons : {stats['total']}")
    click.echo(f"  Mneme wins        : {stats['mneme_wins']}")
    click.echo(f"  Default wins      : {stats['default_wins']}")
    click.echo(f"  Ties              : {stats['ties']}")
    click.echo(f"  Skips             : {stats['skips']}")
    click.echo(f"  Win rate          : {wr}")
```

**Step 4: Run all compare-cli tests**

```bash
python -m pytest tests/test_compare_cli.py -v
```
Expected: all 9 tests PASS.

**Step 5: Run full suite**

```bash
python -m pytest tests/ -q
```
Expected: 99 tests pass, 0 failures.

**Step 6: Commit**

```bash
git add app/cli.py tests/test_compare_cli.py
git commit -m "feat: add compare-stats CLI command showing cumulative Mneme win rate"
```

---

## Task 6: Documentation

**Files:**
- Create: `docs/compare-mode.md`

**Step 1: Create the doc**

Create `docs/compare-mode.md`:

```markdown
# Compare Mode

Compare Mode is the validation layer for Mneme. It answers one question:

> Does AI personalized with my decision profile produce outputs I prefer over default AI?

## Commands

### `flask compare`

Runs a single prompt against both default AI and Mneme AI, presents both outputs
as a blind comparison (Option A / Option B), and asks you to pick the better one.

```
flask compare --user-id <id> --prompt "How would you grow a SaaS product?"
```

**Output format:**

```
Running comparison for Alice...

────────────────────────────────────────────────────────────
PROMPT:
How would you grow a SaaS product?
────────────────────────────────────────────────────────────
Option A:

[output text]
────────────────────────────────────────────────────────────
Option B:

[output text]
────────────────────────────────────────────────────────────
Which is better? (A/B/tie/skip):
```

**Choices:**
- `A` — Option A was better
- `B` — Option B was better
- `tie` — both equally good
- `skip` — skip this comparison (e.g. low-quality outputs)

The A/B assignment is randomized per comparison to prevent position bias.
You never see which output came from which mode until the result is saved.

---

### `flask compare-stats`

Shows cumulative win-rate stats for a user.

```
flask compare-stats --user-id <id>
```

**Output format:**

```
Mneme comparison stats for Alice:
  Total comparisons : 10
  Mneme wins        : 7
  Default wins      : 2
  Ties              : 1
  Skips             : 0
  Win rate          : 77.8%
```

**Win rate formula:**
```
win_rate = mneme_wins / (mneme_wins + default_wins)
```
Ties and skips are excluded from the denominator but counted separately.
`N/A` is shown when there are no decisive comparisons yet.

---

## Interpreting Results

| Win rate | Signal |
|----------|--------|
| ≥ 60% | Strong signal — profile is improving outputs |
| 45–60% | Weak signal — too close to call |
| < 45% | No signal or negative signal |

Aim for **10–20 comparisons per user** before drawing conclusions.
5 comparisons is enough to see a directional trend.

---

## How It Fits

Compare Mode is the proof layer, not the benchmark layer.

- **Benchmark** (`run-benchmark`) — structured, blinded, stored, used for aggregate metrics
- **Compare** (`compare`) — fast, interactive, for rapid personal validation

Use Compare Mode first to confirm the profile is working.
Use the benchmark for reproducible, aggregate evidence.

---

## Storage

Results are stored in the `comparison_results` table with:
- which prompt was used
- which output was shown as A vs B
- which mode won
- your preference (derived from A/B + mode assignment)

Run the migration on existing databases:
```bash
sqlite3 mneme.db < migrate_add_comparison_results.sql
```
```

**Step 2: Verify tests still pass (no code change, just confirm)**

```bash
python -m pytest tests/ -q
```
Expected: same count as after Task 5, 0 failures.

**Step 3: Commit**

```bash
git add docs/compare-mode.md
git commit -m "docs: add compare-mode documentation"
```

---

## Final Verification

After all 6 tasks, run the full suite one last time:

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: **99 tests**, 0 failures.

Check that CLI commands are registered:

```bash
flask --help
```

Expected output includes:
```
  compare        Run a prompt against default AI and Mneme AI.
  compare-stats  Show cumulative Mneme win rate for a user.
```
