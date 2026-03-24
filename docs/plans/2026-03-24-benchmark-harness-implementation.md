# Mneme Benchmark Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Flask monolith that runs blind A/B benchmarks comparing default vs mneme-amplified Claude outputs, scores them through a web UI, and reports whether personalization produces a measurable signal.

**Architecture:** Flask app with CLI commands for benchmark execution, web UI for blind scoring and reporting dashboard. SQLite for all data. No ORM — raw sqlite3. Internally modular: models/, runner/, scoring/, reporting/, web/.

**Tech Stack:** Python 3.11+, Flask, Click, Anthropic SDK, SQLite, Jinja2, pytest

**Design Doc:** `docs/plans/2026-03-24-benchmark-harness-design.md`

---

## Task 1: Project Scaffolding and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `run.py`
- Create: `.env.example`

**Step 1: Create requirements.txt**

```txt
flask==3.1.0
click==8.1.7
anthropic==0.52.0
python-dotenv==1.0.1
pytest==8.3.4
```

**Step 2: Create .env.example**

```txt
ANTHROPIC_API_KEY=sk-ant-...
MNEME_DB_PATH=mneme.db
MNEME_MODEL=claude-sonnet-4-20250514
MNEME_TEMPERATURE=0.7
MNEME_MAX_TOKENS=2048
MNEME_PROTOCOL_VERSION=v1
SECRET_KEY=change-me-in-production
```

**Step 3: Create app/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    DB_PATH = os.environ.get("MNEME_DB_PATH", "mneme.db")
    MODEL = os.environ.get("MNEME_MODEL", "claude-sonnet-4-20250514")
    TEMPERATURE = float(os.environ.get("MNEME_TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.environ.get("MNEME_MAX_TOKENS", "2048"))
    PROTOCOL_VERSION = os.environ.get("MNEME_PROTOCOL_VERSION", "v1")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    APP_VERSION = "0.1.0"
```

**Step 4: Create app/__init__.py (Flask app factory)**

```python
from flask import Flask
from app.config import Config
from app.db import init_db_command, get_db, close_db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    app.config["DATABASE"] = Config.DB_PATH

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    return app
```

**Step 5: Create run.py**

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
```

**Step 6: Install dependencies**

Run: `pip install -r requirements.txt`

**Step 7: Verify Flask starts**

Run: `python run.py`
Expected: Flask dev server starts on http://127.0.0.1:5000

**Step 8: Commit**

```bash
git add requirements.txt .env.example app/__init__.py app/config.py run.py
git commit -m "feat: project scaffolding with Flask app factory and config"
```

---

## Task 2: SQLite Schema and Database Layer

**Files:**
- Create: `schema.sql`
- Create: `app/db.py`
- Create: `tests/__init__.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
import os
import tempfile
import pytest
from app import create_app
from app.db import get_db, init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config["DATABASE"] = db_path
    app.config["TESTING"] = True

    with app.app_context():
        init_db()
        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def test_tables_exist(db):
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t["name"] for t in tables]
    assert "users" in table_names
    assert "prompts" in table_names
    assert "runs" in table_names
    assert "scoring_assignments" in table_names
    assert "scores" in table_names


def test_runs_unique_constraint(db):
    """Cannot insert two runs with same (batch_id, user_id, prompt_id, model, protocol_version)."""
    import uuid
    from app.utils.timestamps import now_iso

    user_id = str(uuid.uuid4())
    prompt_id = str(uuid.uuid4())

    db.execute(
        "INSERT INTO users (id, name, mneme_profile, created_at) VALUES (?, ?, ?, ?)",
        (user_id, "test", '{"key": "val"}', now_iso()),
    )
    db.execute(
        "INSERT INTO prompts (id, text, category, scope, created_at) VALUES (?, ?, ?, ?, ?)",
        (prompt_id, "test prompt", "decision", "shared", now_iso()),
    )

    run_args = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "prompt_id": prompt_id,
        "prompt_text": "test prompt",
        "model": "test-model",
        "temperature": 0.7,
        "max_tokens": 2048,
        "output_default": "default output",
        "output_mneme": "mneme output",
        "system_prompt_default": "sys default",
        "system_prompt_mneme": "sys mneme",
        "profile_hash": "abc123",
        "batch_id": "batch-001",
        "protocol_version": "v1",
        "api_metadata_default": "{}",
        "api_metadata_mneme": "{}",
        "execution_order": "default_first",
        "created_at": now_iso(),
    }

    cols = ", ".join(run_args.keys())
    placeholders = ", ".join(["?"] * len(run_args))
    db.execute(f"INSERT INTO runs ({cols}) VALUES ({placeholders})", list(run_args.values()))

    run_args["id"] = str(uuid.uuid4())
    with pytest.raises(Exception):
        db.execute(f"INSERT INTO runs ({cols}) VALUES ({placeholders})", list(run_args.values()))


def test_score_check_constraints(db):
    """Score values must be 1-5."""
    import uuid
    from app.utils.timestamps import now_iso

    with pytest.raises(Exception):
        db.execute(
            "INSERT INTO scores (id, assignment_id, closeness_a, closeness_b, usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b, winner_closeness, winner_usefulness, winner_distinctiveness, preference, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), str(uuid.uuid4()), 6, 1, 1, 1, 1, 1, "a", "a", "a", "a", now_iso()),
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL (db module doesn't exist)

**Step 3: Create utils (needed by tests)**

```python
# app/utils/__init__.py
```

```python
# app/utils/ids.py
import uuid


def new_id():
    return str(uuid.uuid4())
```

```python
# app/utils/timestamps.py
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat()
```

```python
# app/utils/hashing.py
import hashlib
import json


def canonical_hash(data):
    """SHA-256 of canonical JSON (sorted keys, compact separators)."""
    if isinstance(data, str):
        data = json.loads(data)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

```python
# app/utils/validation.py
VALID_SCOPES = ("shared", "user_specific")
VALID_SCORER_TYPES = ("layer1", "layer2", "layer3")
VALID_ASSIGNMENT_STATUSES = ("pending", "in_progress", "completed", "skipped")
VALID_AB = ("default", "mneme")
VALID_WINNERS = ("a", "b", "tie")
VALID_VISUAL_ORDERS = ("a_left", "a_right")
VALID_EXECUTION_ORDERS = ("default_first", "mneme_first")
SCORE_MIN = 1
SCORE_MAX = 5
```

**Step 4: Create schema.sql**

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mneme_profile TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'user_specific')),
    user_id TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    prompt_text TEXT NOT NULL,
    model TEXT NOT NULL,
    temperature REAL NOT NULL,
    max_tokens INTEGER NOT NULL,
    output_default TEXT NOT NULL,
    output_mneme TEXT NOT NULL,
    system_prompt_default TEXT NOT NULL,
    system_prompt_mneme TEXT NOT NULL,
    profile_hash TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    api_metadata_default TEXT,
    api_metadata_mneme TEXT,
    execution_order TEXT NOT NULL CHECK (execution_order IN ('default_first', 'mneme_first')),
    created_at TEXT NOT NULL,
    UNIQUE (batch_id, user_id, prompt_id, model, protocol_version)
);

CREATE TABLE IF NOT EXISTS scoring_assignments (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    scorer_type TEXT NOT NULL CHECK (scorer_type IN ('layer1', 'layer2', 'layer3')),
    scorer_id TEXT NOT NULL,
    output_a_is TEXT NOT NULL CHECK (output_a_is IN ('default', 'mneme')),
    visual_order TEXT NOT NULL CHECK (visual_order IN ('a_left', 'a_right')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL UNIQUE REFERENCES scoring_assignments(id),
    closeness_a INTEGER NOT NULL CHECK (closeness_a BETWEEN 1 AND 5),
    closeness_b INTEGER NOT NULL CHECK (closeness_b BETWEEN 1 AND 5),
    usefulness_a INTEGER NOT NULL CHECK (usefulness_a BETWEEN 1 AND 5),
    usefulness_b INTEGER NOT NULL CHECK (usefulness_b BETWEEN 1 AND 5),
    distinctiveness_a INTEGER NOT NULL CHECK (distinctiveness_a BETWEEN 1 AND 5),
    distinctiveness_b INTEGER NOT NULL CHECK (distinctiveness_b BETWEEN 1 AND 5),
    winner_closeness TEXT NOT NULL CHECK (winner_closeness IN ('a', 'b', 'tie')),
    winner_usefulness TEXT NOT NULL CHECK (winner_usefulness IN ('a', 'b', 'tie')),
    winner_distinctiveness TEXT NOT NULL CHECK (winner_distinctiveness IN ('a', 'b', 'tie')),
    preference TEXT NOT NULL CHECK (preference IN ('a', 'b', 'tie')),
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    total_runs_scored INTEGER NOT NULL,
    valid_runs INTEGER NOT NULL,
    excluded_runs INTEGER NOT NULL,
    exclusion_reasons TEXT,
    closeness_win_rate REAL,
    closeness_avg_delta REAL,
    usefulness_win_rate REAL,
    distinctiveness_win_rate REAL,
    per_user_json TEXT,
    created_at TEXT NOT NULL
);
```

**Step 5: Create app/db.py**

```python
import sqlite3
import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("../schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")
```

**Step 6: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: All 3 tests PASS

**Step 7: Commit**

```bash
git add schema.sql app/db.py app/utils/ tests/
git commit -m "feat: SQLite schema with CHECK constraints and db layer"
```

---

## Task 3: Models Layer — Users and Prompts

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/user.py`
- Create: `app/models/prompt.py`
- Create: `tests/test_models_user.py`
- Create: `tests/test_models_prompt.py`

**Step 1: Write the failing tests**

```python
# tests/test_models_user.py
import pytest
from tests.conftest import *
from app.models.user import insert_user, get_user, list_users


def test_insert_and_get_user(db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}', source="reddit")
    fetched = get_user(db, user["id"])
    assert fetched["name"] == "Alice"
    assert fetched["mneme_profile"] == '{"style": "analytical"}'
    assert fetched["source"] == "reddit"


def test_list_users(db):
    insert_user(db, name="Alice", mneme_profile='{}')
    insert_user(db, name="Bob", mneme_profile='{}')
    users = list_users(db)
    assert len(users) == 2
```

```python
# tests/test_models_prompt.py
import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt, get_prompts_for_user


def test_insert_shared_prompt(db):
    p = insert_prompt(db, text="Walk through a decision.", category="decision", scope="shared")
    assert p["scope"] == "shared"
    assert p["user_id"] is None


def test_get_prompts_for_user(db):
    user = insert_user(db, name="Alice", mneme_profile='{}')
    insert_prompt(db, text="Shared prompt 1", category="decision", scope="shared")
    insert_prompt(db, text="Shared prompt 2", category="strategy", scope="shared")
    insert_prompt(db, text="Shared prompt 3", category="creative", scope="shared")
    insert_prompt(db, text="Alice specific 1", category="analysis", scope="user_specific", user_id=user["id"])
    insert_prompt(db, text="Alice specific 2", category="personal", scope="user_specific", user_id=user["id"])

    prompts = get_prompts_for_user(db, user["id"])
    assert len(prompts) == 5
```

**Step 2: Create tests/conftest.py (shared fixtures)**

```python
# tests/conftest.py
import os
import tempfile
import pytest
from app import create_app
from app.db import get_db, init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config["DATABASE"] = db_path
    app.config["TESTING"] = True

    with app.app_context():
        init_db()
        yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/test_models_user.py tests/test_models_prompt.py -v`
Expected: FAIL (models don't exist)

**Step 4: Implement user model**

```python
# app/models/__init__.py
```

```python
# app/models/user.py
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_user(db, name, mneme_profile, source=None):
    user_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO users (id, name, mneme_profile, source, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, mneme_profile, source, created_at),
    )
    db.commit()
    return {"id": user_id, "name": name, "mneme_profile": mneme_profile, "source": source, "created_at": created_at}


def get_user(db, user_id):
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users(db):
    rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]
```

**Step 5: Implement prompt model**

```python
# app/models/prompt.py
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_prompt(db, text, category, scope, user_id=None):
    prompt_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO prompts (id, text, category, scope, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (prompt_id, text, category, scope, user_id, created_at),
    )
    db.commit()
    return {"id": prompt_id, "text": text, "category": category, "scope": scope, "user_id": user_id, "created_at": created_at}


def get_prompts_for_user(db, user_id):
    rows = db.execute(
        "SELECT * FROM prompts WHERE scope = 'shared' OR user_id = ? ORDER BY category",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_prompt(db, prompt_id):
    row = db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
    return dict(row) if row else None
```

**Step 6: Run tests to verify they pass**

Run: `pytest tests/test_models_user.py tests/test_models_prompt.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add app/models/ tests/conftest.py tests/test_models_user.py tests/test_models_prompt.py
git commit -m "feat: user and prompt models with data access layer"
```

---

## Task 4: Models Layer — Runs (Immutable)

**Files:**
- Create: `app/models/run.py`
- Create: `tests/test_models_run.py`

**Step 1: Write the failing test**

```python
# tests/test_models_run.py
import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run, get_run, run_exists


def _make_user_and_prompt(db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}')
    prompt = insert_prompt(db, text="Walk through a decision.", category="decision", scope="shared")
    return user, prompt


def test_insert_and_get_run(db):
    user, prompt = _make_user_and_prompt(db)
    run = insert_run(
        db,
        user_id=user["id"],
        prompt_id=prompt["id"],
        prompt_text=prompt["text"],
        model="test-model",
        temperature=0.7,
        max_tokens=2048,
        output_default="default response",
        output_mneme="mneme response",
        system_prompt_default="You are helpful.",
        system_prompt_mneme="You are helpful.\n<user_profile>...</user_profile>",
        profile_hash="abc123",
        batch_id="batch-001",
        protocol_version="v1",
        api_metadata_default='{"tokens": 100}',
        api_metadata_mneme='{"tokens": 120}',
        execution_order="default_first",
    )
    fetched = get_run(db, run["id"])
    assert fetched["output_default"] == "default response"
    assert fetched["output_mneme"] == "mneme response"
    assert fetched["profile_hash"] == "abc123"
    assert fetched["batch_id"] == "batch-001"


def test_run_exists_idempotency(db):
    user, prompt = _make_user_and_prompt(db)
    assert not run_exists(db, "batch-001", user["id"], prompt["id"], "test-model", "v1")

    insert_run(
        db, user_id=user["id"], prompt_id=prompt["id"], prompt_text=prompt["text"],
        model="test-model", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-001", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    assert run_exists(db, "batch-001", user["id"], prompt["id"], "test-model", "v1")


def test_duplicate_run_raises(db):
    user, prompt = _make_user_and_prompt(db)
    kwargs = dict(
        user_id=user["id"], prompt_id=prompt["id"], prompt_text=prompt["text"],
        model="test-model", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-001", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    insert_run(db, **kwargs)
    with pytest.raises(Exception):
        insert_run(db, **kwargs)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_run.py -v`
Expected: FAIL

**Step 3: Implement run model**

```python
# app/models/run.py
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_run(db, *, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
               output_default, output_mneme, system_prompt_default, system_prompt_mneme,
               profile_hash, batch_id, protocol_version, api_metadata_default,
               api_metadata_mneme, execution_order):
    run_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO runs (id, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
           output_default, output_mneme, system_prompt_default, system_prompt_mneme,
           profile_hash, batch_id, protocol_version, api_metadata_default, api_metadata_mneme,
           execution_order, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
         output_default, output_mneme, system_prompt_default, system_prompt_mneme,
         profile_hash, batch_id, protocol_version, api_metadata_default, api_metadata_mneme,
         execution_order, created_at),
    )
    db.commit()
    return {"id": run_id, "created_at": created_at}


def get_run(db, run_id):
    row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def run_exists(db, batch_id, user_id, prompt_id, model, protocol_version):
    row = db.execute(
        """SELECT 1 FROM runs
           WHERE batch_id = ? AND user_id = ? AND prompt_id = ? AND model = ? AND protocol_version = ?""",
        (batch_id, user_id, prompt_id, model, protocol_version),
    ).fetchone()
    return row is not None


def list_runs(db, batch_id):
    rows = db.execute("SELECT * FROM runs WHERE batch_id = ? ORDER BY created_at", (batch_id,)).fetchall()
    return [dict(r) for r in rows]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models_run.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/models/run.py tests/test_models_run.py
git commit -m "feat: immutable run model with idempotency check"
```

---

## Task 5: Models Layer — Assignments and Scores

**Files:**
- Create: `app/models/assignment.py`
- Create: `app/models/score.py`
- Create: `tests/test_models_assignment.py`
- Create: `tests/test_models_score.py`

**Step 1: Write the failing tests**

```python
# tests/test_models_assignment.py
import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment, get_next_pending, mark_in_progress, mark_completed, mark_skipped, timeout_stale


def _make_run(db):
    user = insert_user(db, name="Alice", mneme_profile='{}')
    prompt = insert_prompt(db, text="Test", category="decision", scope="shared")
    run = insert_run(
        db, user_id=user["id"], prompt_id=prompt["id"], prompt_text="Test",
        model="m", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="b", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    return run


def test_insert_and_get_next(db):
    run = _make_run(db)
    insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                      output_a_is="mneme", visual_order="a_left")
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is not None
    assert pending["status"] == "pending"


def test_mark_in_progress(db):
    run = _make_run(db)
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="default", visual_order="a_right")
    mark_in_progress(db, a["id"])
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is None  # no more pending


def test_mark_skipped(db):
    run = _make_run(db)
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="default", visual_order="a_left")
    mark_skipped(db, a["id"])
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is None
```

```python
# tests/test_models_score.py
import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment, mark_in_progress
from app.models.score import insert_score, get_score_for_assignment


def _make_assignment(db):
    user = insert_user(db, name="Alice", mneme_profile='{}')
    prompt = insert_prompt(db, text="Test", category="decision", scope="shared")
    run = insert_run(
        db, user_id=user["id"], prompt_id=prompt["id"], prompt_text="Test",
        model="m", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="b", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="mneme", visual_order="a_left")
    mark_in_progress(db, a["id"])
    return a


def test_insert_and_get_score(db):
    a = _make_assignment(db)
    score = insert_score(
        db, assignment_id=a["id"],
        closeness_a=4, closeness_b=2,
        usefulness_a=3, usefulness_b=3,
        distinctiveness_a=5, distinctiveness_b=1,
        winner_closeness="a", winner_usefulness="tie", winner_distinctiveness="a",
        preference="a", notes="A felt more personal",
    )
    fetched = get_score_for_assignment(db, a["id"])
    assert fetched["closeness_a"] == 4
    assert fetched["preference"] == "a"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models_assignment.py tests/test_models_score.py -v`
Expected: FAIL

**Step 3: Implement assignment model**

```python
# app/models/assignment.py
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_assignment(db, *, run_id, scorer_type, scorer_id, output_a_is, visual_order):
    aid = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO scoring_assignments (id, run_id, scorer_type, scorer_id, output_a_is, visual_order, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (aid, run_id, scorer_type, scorer_id, output_a_is, visual_order, created_at),
    )
    db.commit()
    return {"id": aid, "run_id": run_id, "output_a_is": output_a_is, "visual_order": visual_order, "status": "pending"}


def get_next_pending(db, scorer_type, scorer_id):
    row = db.execute(
        """SELECT * FROM scoring_assignments
           WHERE scorer_type = ? AND scorer_id = ? AND status = 'pending'
           ORDER BY RANDOM() LIMIT 1""",
        (scorer_type, scorer_id),
    ).fetchone()
    return dict(row) if row else None


def mark_in_progress(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'in_progress' WHERE id = ?", (assignment_id,))
    db.commit()


def mark_completed(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'completed' WHERE id = ?", (assignment_id,))
    db.commit()


def mark_skipped(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'skipped' WHERE id = ?", (assignment_id,))
    db.commit()


def timeout_stale(db, minutes=30):
    db.execute(
        """UPDATE scoring_assignments SET status = 'pending'
           WHERE status = 'in_progress'
           AND created_at < datetime('now', ? || ' minutes')""",
        (f"-{minutes}",),
    )
    db.commit()


def count_completed(db, scorer_type, scorer_id):
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM scoring_assignments WHERE scorer_type = ? AND scorer_id = ? AND status = 'completed'",
        (scorer_type, scorer_id),
    ).fetchone()
    return row["cnt"]


def count_total(db, scorer_type, scorer_id):
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM scoring_assignments WHERE scorer_type = ? AND scorer_id = ?",
        (scorer_type, scorer_id),
    ).fetchone()
    return row["cnt"]
```

**Step 4: Implement score model**

```python
# app/models/score.py
from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_score(db, *, assignment_id, closeness_a, closeness_b,
                 usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
                 winner_closeness, winner_usefulness, winner_distinctiveness,
                 preference, notes=None):
    score_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO scores (id, assignment_id, closeness_a, closeness_b,
           usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
           winner_closeness, winner_usefulness, winner_distinctiveness,
           preference, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (score_id, assignment_id, closeness_a, closeness_b,
         usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
         winner_closeness, winner_usefulness, winner_distinctiveness,
         preference, notes, created_at),
    )
    db.commit()
    return {"id": score_id, "assignment_id": assignment_id}


def get_score_for_assignment(db, assignment_id):
    row = db.execute("SELECT * FROM scores WHERE assignment_id = ?", (assignment_id,)).fetchone()
    return dict(row) if row else None
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_models_assignment.py tests/test_models_score.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add app/models/assignment.py app/models/score.py tests/test_models_assignment.py tests/test_models_score.py
git commit -m "feat: assignment and score models with blinding support"
```

---

## Task 6: Runner — Prompt Assembly

**Files:**
- Create: `app/runner/__init__.py`
- Create: `app/runner/prompt_assembly.py`
- Create: `tests/test_prompt_assembly.py`

**Step 1: Write the failing test**

```python
# tests/test_prompt_assembly.py
from app.runner.prompt_assembly import assemble_default, assemble_mneme

PROFILE = '{"thinking_style": "analytical", "values": ["clarity", "precision"]}'


def test_assemble_default():
    result = assemble_default()
    assert "helpful assistant" in result
    assert "<user_profile>" not in result


def test_assemble_mneme():
    result = assemble_mneme(PROFILE)
    assert "helpful assistant" in result
    assert "<user_profile>" in result
    assert "analytical" in result
    assert "Do not mention the profile" in result


def test_default_and_mneme_share_base():
    default = assemble_default()
    mneme = assemble_mneme(PROFILE)
    assert mneme.startswith(default.rstrip())
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompt_assembly.py -v`
Expected: FAIL

**Step 3: Implement prompt assembly**

```python
# app/runner/__init__.py
```

```python
# app/runner/prompt_assembly.py

BASE_SYSTEM_PROMPT = "You are a helpful assistant. Respond thoughtfully to the user's request."

MNEME_INJECTION_TEMPLATE = """

<user_profile>
{profile}
</user_profile>

Use the above profile to tailor your response to how this person thinks, decides, and communicates. Do not mention the profile directly."""


def assemble_default():
    return BASE_SYSTEM_PROMPT


def assemble_mneme(mneme_profile):
    return BASE_SYSTEM_PROMPT + MNEME_INJECTION_TEMPLATE.format(profile=mneme_profile)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt_assembly.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/runner/ tests/test_prompt_assembly.py
git commit -m "feat: prompt assembly with default and mneme variants"
```

---

## Task 7: Runner — Claude Client

**Files:**
- Create: `app/runner/claude_client.py`
- Create: `tests/test_claude_client.py`

**Step 1: Write the failing test (mocked)**

```python
# tests/test_claude_client.py
from unittest.mock import MagicMock, patch
from app.runner.claude_client import call_claude


def _mock_response():
    msg = MagicMock()
    msg.id = "msg_test123"
    msg.content = [MagicMock(text="This is the response.")]
    msg.stop_reason = "end_turn"
    msg.usage.input_tokens = 50
    msg.usage.output_tokens = 100
    return msg


@patch("app.runner.claude_client.anthropic.Anthropic")
def test_call_claude_returns_output_and_metadata(MockAnthropic):
    client = MockAnthropic.return_value
    client.messages.create.return_value = _mock_response()

    result = call_claude(
        api_key="sk-test",
        model="test-model",
        system_prompt="You are helpful.",
        user_prompt="Tell me something.",
        temperature=0.7,
        max_tokens=2048,
    )

    assert result["output"] == "This is the response."
    assert result["metadata"]["request_id"] == "msg_test123"
    assert result["metadata"]["stop_reason"] == "end_turn"
    assert result["metadata"]["input_tokens"] == 50
    assert result["metadata"]["output_tokens"] == 100
    assert "latency_ms" in result["metadata"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude_client.py -v`
Expected: FAIL

**Step 3: Implement claude client**

```python
# app/runner/claude_client.py
import time
import anthropic


def call_claude(*, api_key, model, system_prompt, user_prompt, temperature, max_tokens):
    client = anthropic.Anthropic(api_key=api_key)

    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    latency_ms = round((time.monotonic() - start) * 1000)

    output = response.content[0].text if response.content else ""

    metadata = {
        "request_id": response.id,
        "stop_reason": response.stop_reason,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
    }

    return {"output": output, "metadata": metadata}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_claude_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/runner/claude_client.py tests/test_claude_client.py
git commit -m "feat: Claude API client with metadata capture"
```

---

## Task 8: Runner — Benchmark Engine

**Files:**
- Create: `app/runner/engine.py`
- Create: `tests/test_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_engine.py
import json
from unittest.mock import patch, MagicMock
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import list_runs
from app.runner.engine import run_benchmark_for_user


def _mock_call_claude(**kwargs):
    return {
        "output": f"Response to: {kwargs['user_prompt'][:20]}",
        "metadata": {"request_id": "r1", "stop_reason": "end_turn",
                      "input_tokens": 50, "output_tokens": 100, "latency_ms": 500},
    }


def test_run_benchmark_creates_runs(app, db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}')
    insert_prompt(db, text="Prompt 1", category="decision", scope="shared")
    insert_prompt(db, text="Prompt 2", category="strategy", scope="shared")

    with patch("app.runner.engine.call_claude", side_effect=_mock_call_claude):
        with app.app_context():
            results = run_benchmark_for_user(
                db, user_id=user["id"], batch_id="batch-001",
                model="test-model", temperature=0.7, max_tokens=2048,
                protocol_version="v1", api_key="sk-test",
            )

    assert results["completed"] == 2
    assert results["skipped"] == 0
    runs = list_runs(db, "batch-001")
    assert len(runs) == 2
    # Verify profile_hash is consistent
    assert runs[0]["profile_hash"] == runs[1]["profile_hash"]


def test_idempotent_skips_existing(app, db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}')
    insert_prompt(db, text="Prompt 1", category="decision", scope="shared")

    with patch("app.runner.engine.call_claude", side_effect=_mock_call_claude):
        with app.app_context():
            run_benchmark_for_user(db, user_id=user["id"], batch_id="batch-001",
                                   model="test-model", temperature=0.7, max_tokens=2048,
                                   protocol_version="v1", api_key="sk-test")
            results = run_benchmark_for_user(db, user_id=user["id"], batch_id="batch-001",
                                             model="test-model", temperature=0.7, max_tokens=2048,
                                             protocol_version="v1", api_key="sk-test")

    assert results["completed"] == 0
    assert results["skipped"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL

**Step 3: Implement engine**

```python
# app/runner/engine.py
import json
import random

from app.models.user import get_user
from app.models.prompt import get_prompts_for_user
from app.models.run import insert_run, run_exists
from app.runner.prompt_assembly import assemble_default, assemble_mneme
from app.runner.claude_client import call_claude
from app.utils.hashing import canonical_hash


def run_benchmark_for_user(db, *, user_id, batch_id, model, temperature, max_tokens,
                            protocol_version, api_key):
    user = get_user(db, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    prompts = get_prompts_for_user(db, user_id)
    profile_hash = canonical_hash(user["mneme_profile"])

    completed = 0
    skipped = 0
    failed = 0

    for prompt in prompts:
        if run_exists(db, batch_id, user_id, prompt["id"], model, protocol_version):
            skipped += 1
            continue

        prompt_text = prompt["text"]
        sys_default = assemble_default()
        sys_mneme = assemble_mneme(user["mneme_profile"])

        # Randomize execution order
        default_first = random.choice([True, False])
        execution_order = "default_first" if default_first else "mneme_first"

        try:
            if default_first:
                result_default = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_default, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
                result_mneme = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_mneme, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
            else:
                result_mneme = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_mneme, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)
                result_default = call_claude(api_key=api_key, model=model,
                    system_prompt=sys_default, user_prompt=prompt_text,
                    temperature=temperature, max_tokens=max_tokens)

            insert_run(
                db,
                user_id=user_id,
                prompt_id=prompt["id"],
                prompt_text=prompt_text,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                output_default=result_default["output"],
                output_mneme=result_mneme["output"],
                system_prompt_default=sys_default,
                system_prompt_mneme=sys_mneme,
                profile_hash=profile_hash,
                batch_id=batch_id,
                protocol_version=protocol_version,
                api_metadata_default=json.dumps(result_default["metadata"]),
                api_metadata_mneme=json.dumps(result_mneme["metadata"]),
                execution_order=execution_order,
            )
            completed += 1
        except Exception as e:
            failed += 1
            print(f"  ERROR on prompt {prompt['id']}: {e}")

    return {"completed": completed, "skipped": skipped, "failed": failed}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/runner/engine.py tests/test_engine.py
git commit -m "feat: benchmark engine with randomized execution order and idempotency"
```

---

## Task 9: Scoring — Assigner and Unblinder

**Files:**
- Create: `app/scoring/__init__.py`
- Create: `app/scoring/assigner.py`
- Create: `app/scoring/unblinder.py`
- Create: `tests/test_blinding.py`

**Step 1: Write the failing tests**

```python
# tests/test_blinding.py
import random
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment
from app.models.score import insert_score
from app.scoring.assigner import generate_assignments
from app.scoring.unblinder import unblind_scores


def _make_runs(db, count=50):
    """Create N runs for blinding tests."""
    user = insert_user(db, name="Alice", mneme_profile='{}')
    runs = []
    for i in range(count):
        p = insert_prompt(db, text=f"Prompt {i}", category="decision", scope="shared")
        r = insert_run(
            db, user_id=user["id"], prompt_id=p["id"], prompt_text=f"Prompt {i}",
            model="m", temperature=0.7, max_tokens=2048,
            output_default=f"default {i}", output_mneme=f"mneme {i}",
            system_prompt_default="s", system_prompt_mneme="s",
            profile_hash="h", batch_id="batch-test", protocol_version="v1",
            api_metadata_default="{}", api_metadata_mneme="{}",
            execution_order="default_first",
        )
        runs.append(r)
    return runs


def test_ab_randomization_is_balanced(db):
    """Over many assignments, A/B split should be approximately 50/50."""
    runs = _make_runs(db, count=200)
    assignments = generate_assignments(db, batch_id="batch-test",
                                        scorer_type="layer1", scorer_id="theo")

    mneme_as_a = sum(1 for a in assignments if a["output_a_is"] == "mneme")
    default_as_a = sum(1 for a in assignments if a["output_a_is"] == "default")

    # With 200 samples, expect 100 +/- 30 (very generous tolerance)
    assert 70 < mneme_as_a < 130, f"mneme_as_a={mneme_as_a}, expected ~100"
    assert 70 < default_as_a < 130, f"default_as_a={default_as_a}, expected ~100"


def test_visual_order_is_randomized(db):
    """Left/right placement should also be approximately 50/50."""
    runs = _make_runs(db, count=200)
    assignments = generate_assignments(db, batch_id="batch-test",
                                        scorer_type="layer1", scorer_id="theo")

    a_left = sum(1 for a in assignments if a["visual_order"] == "a_left")
    assert 70 < a_left < 130, f"a_left={a_left}, expected ~100"


def test_unblinding_maps_correctly(db):
    """Unblinding should correctly translate A/B winners to default/mneme."""
    user = insert_user(db, name="Bob", mneme_profile='{}')
    p = insert_prompt(db, text="Test", category="decision", scope="shared")
    r = insert_run(
        db, user_id=user["id"], prompt_id=p["id"], prompt_text="Test",
        model="m", temperature=0.7, max_tokens=2048,
        output_default="default out", output_mneme="mneme out",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-unblind", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )

    # output_a_is = "mneme", so A is mneme, B is default
    a = insert_assignment(db, run_id=r["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="mneme", visual_order="a_left")
    from app.models.assignment import mark_in_progress, mark_completed
    mark_in_progress(db, a["id"])
    insert_score(
        db, assignment_id=a["id"],
        closeness_a=5, closeness_b=2,
        usefulness_a=4, usefulness_b=3,
        distinctiveness_a=5, distinctiveness_b=1,
        winner_closeness="a", winner_usefulness="a", winner_distinctiveness="a",
        preference="a",
    )
    mark_completed(db, a["id"])

    results = unblind_scores(db, batch_id="batch-unblind")
    assert len(results) == 1
    r0 = results[0]
    # A was mneme and won → true winner is mneme
    assert r0["true_winner_closeness"] == "mneme"
    assert r0["true_winner_usefulness"] == "mneme"
    assert r0["true_winner_distinctiveness"] == "mneme"
    assert r0["true_preference"] == "mneme"
    # Delta: mneme score - default score = A score - B score (since A is mneme)
    assert r0["closeness_delta"] == 3  # 5 - 2
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_blinding.py -v`
Expected: FAIL

**Step 3: Implement assigner**

```python
# app/scoring/__init__.py
```

```python
# app/scoring/assigner.py
import random
from app.models.assignment import insert_assignment


def generate_assignments(db, *, batch_id, scorer_type, scorer_id):
    # Find runs in this batch that don't have assignments for this scorer
    rows = db.execute(
        """SELECT r.id FROM runs r
           WHERE r.batch_id = ?
           AND NOT EXISTS (
               SELECT 1 FROM scoring_assignments sa
               WHERE sa.run_id = r.id AND sa.scorer_type = ? AND sa.scorer_id = ?
           )""",
        (batch_id, scorer_type, scorer_id),
    ).fetchall()

    run_ids = [row["id"] for row in rows]
    random.shuffle(run_ids)

    assignments = []
    for run_id in run_ids:
        output_a_is = random.choice(["default", "mneme"])
        visual_order = random.choice(["a_left", "a_right"])
        a = insert_assignment(
            db, run_id=run_id, scorer_type=scorer_type, scorer_id=scorer_id,
            output_a_is=output_a_is, visual_order=visual_order,
        )
        assignments.append(a)

    return assignments
```

**Step 4: Implement unblinder**

```python
# app/scoring/unblinder.py


def _translate_winner(winner, output_a_is):
    if winner == "tie":
        return "tie"
    if output_a_is == "mneme":
        return "mneme" if winner == "a" else "default"
    else:
        return "default" if winner == "a" else "mneme"


def _compute_delta(score_a, score_b, output_a_is):
    """Return mneme_score - default_score."""
    if output_a_is == "mneme":
        return score_a - score_b
    else:
        return score_b - score_a


def unblind_scores(db, *, batch_id, scorer_type=None):
    query = """
        SELECT s.*, sa.output_a_is, sa.visual_order, sa.scorer_type, sa.scorer_id,
               r.user_id, r.prompt_id, r.prompt_text, r.batch_id, r.profile_hash,
               r.model, r.protocol_version,
               p.category as prompt_category
        FROM scores s
        JOIN scoring_assignments sa ON s.assignment_id = sa.id
        JOIN runs r ON sa.run_id = r.id
        JOIN prompts p ON r.prompt_id = p.id
        WHERE r.batch_id = ? AND sa.status = 'completed'
    """
    params = [batch_id]
    if scorer_type:
        query += " AND sa.scorer_type = ?"
        params.append(scorer_type)

    rows = db.execute(query, params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        a_is = r["output_a_is"]

        r["true_winner_closeness"] = _translate_winner(r["winner_closeness"], a_is)
        r["true_winner_usefulness"] = _translate_winner(r["winner_usefulness"], a_is)
        r["true_winner_distinctiveness"] = _translate_winner(r["winner_distinctiveness"], a_is)
        r["true_preference"] = _translate_winner(r["preference"], a_is)

        r["closeness_delta"] = _compute_delta(r["closeness_a"], r["closeness_b"], a_is)
        r["usefulness_delta"] = _compute_delta(r["usefulness_a"], r["usefulness_b"], a_is)
        r["distinctiveness_delta"] = _compute_delta(r["distinctiveness_a"], r["distinctiveness_b"], a_is)

        results.append(r)

    return results
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_blinding.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add app/scoring/ tests/test_blinding.py
git commit -m "feat: assignment generator and unblinder with blinding integrity tests"
```

---

## Task 10: Reporting — Metrics Engine

**Files:**
- Create: `app/reporting/__init__.py`
- Create: `app/reporting/metrics.py`
- Create: `tests/test_metrics.py`

**Step 1: Write the failing test**

```python
# tests/test_metrics.py
from app.reporting.metrics import compute_verdict, compute_per_user, compute_consistency


def test_verdict_signal_detected():
    """Both thresholds met → SIGNAL DETECTED."""
    unblinded = [
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 0.5, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -0.5, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u2"},
    ]
    v = compute_verdict(unblinded)
    assert v["win_rate"] == 3 / 5  # 60%
    assert v["avg_delta"] == (1 + 0.5 - 0.5 + 1 + 0) / 5  # 0.4
    assert v["verdict"] == "INCONCLUSIVE"  # win rate met but delta not


def test_verdict_clear_signal():
    unblinded = [{"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": f"u{i}"} for i in range(4)]
    unblinded.append({"true_winner_closeness": "default", "closeness_delta": -0.5, "user_id": "u5"})
    v = compute_verdict(unblinded)
    assert v["win_rate"] == 4 / 5  # 80%
    assert v["avg_delta"] == (4 * 1 + (-0.5)) / 5  # 0.7
    assert v["verdict"] == "SIGNAL DETECTED"


def test_verdict_no_signal():
    unblinded = [
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u3"},
    ]
    v = compute_verdict(unblinded)
    assert v["verdict"] == "NO SIGNAL"


def test_per_user_breakdown():
    unblinded = [
        {"true_winner_closeness": "mneme", "closeness_delta": 2, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u2"},
    ]
    breakdown = compute_per_user(unblinded)
    assert breakdown["u1"]["wins"] == 2
    assert breakdown["u1"]["pattern"] == "dominant"
    assert breakdown["u2"]["wins"] == 0


def test_consistency_check():
    scores = [
        {"closeness_a": 5, "closeness_b": 2, "winner_closeness": "a"},  # consistent
        {"closeness_a": 2, "closeness_b": 4, "winner_closeness": "a"},  # inconsistent
        {"closeness_a": 3, "closeness_b": 3, "winner_closeness": "tie"},  # consistent
    ]
    result = compute_consistency(scores)
    assert result["agreement_rate"] == 2 / 3
    assert len(result["disagreements"]) == 1
    assert result["concern"] is True  # > 25% disagreement
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL

**Step 3: Implement metrics**

```python
# app/reporting/__init__.py
```

```python
# app/reporting/metrics.py
from collections import defaultdict

WIN_RATE_THRESHOLD = 0.60
DELTA_THRESHOLD = 0.5
CONSISTENCY_CONCERN_THRESHOLD = 0.25


def compute_verdict(unblinded, dimension="closeness"):
    total = len(unblinded)
    if total == 0:
        return {"wins": 0, "losses": 0, "ties": 0, "total": 0,
                "win_rate": 0, "avg_delta": 0, "verdict": "NO DATA"}

    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    wins = sum(1 for r in unblinded if r[winner_key] == "mneme")
    losses = sum(1 for r in unblinded if r[winner_key] == "default")
    ties = sum(1 for r in unblinded if r[winner_key] == "tie")
    win_rate = wins / total
    avg_delta = sum(r[delta_key] for r in unblinded) / total

    if win_rate >= WIN_RATE_THRESHOLD and avg_delta >= DELTA_THRESHOLD:
        verdict = "SIGNAL DETECTED"
    elif win_rate >= WIN_RATE_THRESHOLD or avg_delta >= DELTA_THRESHOLD:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "NO SIGNAL"

    return {
        "wins": wins, "losses": losses, "ties": ties, "total": total,
        "win_rate": win_rate, "avg_delta": avg_delta, "verdict": verdict,
    }


def compute_per_user(unblinded, dimension="closeness"):
    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    by_user = defaultdict(list)
    for r in unblinded:
        by_user[r["user_id"]].append(r)

    breakdown = {}
    for user_id, rows in by_user.items():
        total = len(rows)
        wins = sum(1 for r in rows if r[winner_key] == "mneme")
        losses = sum(1 for r in rows if r[winner_key] == "default")
        ties = sum(1 for r in rows if r[winner_key] == "tie")
        win_rate = wins / total if total > 0 else 0
        avg_delta = sum(r[delta_key] for r in rows) / total if total > 0 else 0

        if win_rate >= 0.8 and avg_delta >= 1.0:
            pattern = "dominant"
        elif win_rate >= 0.6 and avg_delta >= 0.5:
            pattern = "strong"
        elif win_rate >= 0.6 or avg_delta >= 0.5:
            pattern = "moderate"
        elif win_rate >= 0.4:
            pattern = "weak"
        else:
            pattern = "negative"

        breakdown[user_id] = {
            "wins": wins, "losses": losses, "ties": ties, "total": total,
            "win_rate": win_rate, "avg_delta": avg_delta, "pattern": pattern,
        }

    return breakdown


def compute_per_category(unblinded, dimension="closeness"):
    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    by_cat = defaultdict(list)
    for r in unblinded:
        by_cat[r.get("prompt_category", "unknown")].append(r)

    breakdown = {}
    for cat, rows in by_cat.items():
        total = len(rows)
        wins = sum(1 for r in rows if r[winner_key] == "mneme")
        win_rate = wins / total if total > 0 else 0
        avg_delta = sum(r[delta_key] for r in rows) / total if total > 0 else 0
        breakdown[cat] = {"wins": wins, "total": total, "win_rate": win_rate, "avg_delta": avg_delta}

    return breakdown


def compute_consistency(scores):
    """Check if winner picks agree with raw score direction."""
    total = len(scores)
    disagreements = []

    for i, s in enumerate(scores):
        a, b, w = s["closeness_a"], s["closeness_b"], s["winner_closeness"]
        if a > b and w == "b":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})
        elif b > a and w == "a":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})
        elif a == b and w != "tie":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})

    agreement_count = total - len(disagreements)
    agreement_rate = agreement_count / total if total > 0 else 1.0
    concern = (1 - agreement_rate) > CONSISTENCY_CONCERN_THRESHOLD

    return {
        "agreement_rate": agreement_rate,
        "disagreements": disagreements,
        "concern": concern,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metrics.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/reporting/ tests/test_metrics.py
git commit -m "feat: metrics engine with verdict, per-user breakdown, consistency check"
```

---

## Task 11: CLI Commands

**Files:**
- Modify: `app/cli.py` (create)
- Modify: `app/__init__.py` (register CLI)

**Step 1: Create app/cli.py**

```python
# app/cli.py
import json
import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import get_db
from app.config import Config
from app.models.user import insert_user, list_users
from app.models.prompt import insert_prompt
from app.models.run import list_runs
from app.runner.engine import run_benchmark_for_user
from app.scoring.assigner import generate_assignments
from app.scoring.unblinder import unblind_scores
from app.reporting.metrics import compute_verdict, compute_per_user, compute_consistency


@click.command("add-user")
@click.argument("profile_path")
@click.option("--name", required=True)
@click.option("--source", default=None)
@with_appcontext
def add_user_command(profile_path, name, source):
    with open(profile_path) as f:
        profile = f.read()
    json.loads(profile)  # validate JSON
    db = get_db()
    user = insert_user(db, name=name, mneme_profile=profile, source=source)
    click.echo(f"User created: {user['id']} ({name})")


@click.command("add-prompt")
@click.argument("text")
@click.option("--category", required=True, type=click.Choice(["decision", "strategy", "creative", "analysis", "personal"]))
@click.option("--scope", required=True, type=click.Choice(["shared", "user_specific"]))
@click.option("--user-id", default=None)
@with_appcontext
def add_prompt_command(text, category, scope, user_id):
    db = get_db()
    p = insert_prompt(db, text=text, category=category, scope=scope, user_id=user_id)
    click.echo(f"Prompt created: {p['id']} [{category}/{scope}]")


@click.command("run-benchmark")
@click.option("--batch-id", required=True)
@click.option("--user-id", default=None, help="Run for specific user. Omit for all users.")
@with_appcontext
def run_benchmark_command(batch_id, user_id):
    db = get_db()
    config = Config

    if user_id:
        user_ids = [user_id]
    else:
        user_ids = [u["id"] for u in list_users(db)]

    for uid in user_ids:
        click.echo(f"Running benchmark for user {uid}...")
        results = run_benchmark_for_user(
            db, user_id=uid, batch_id=batch_id,
            model=config.MODEL, temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS, protocol_version=config.PROTOCOL_VERSION,
            api_key=config.ANTHROPIC_API_KEY,
        )
        click.echo(f"  Completed: {results['completed']}, Skipped: {results['skipped']}, Failed: {results['failed']}")


@click.command("generate-assignments")
@click.option("--batch-id", required=True)
@click.option("--scorer-type", required=True, type=click.Choice(["layer1", "layer2", "layer3"]))
@click.option("--scorer-id", required=True)
@with_appcontext
def generate_assignments_command(batch_id, scorer_type, scorer_id):
    db = get_db()
    assignments = generate_assignments(db, batch_id=batch_id, scorer_type=scorer_type, scorer_id=scorer_id)
    click.echo(f"Generated {len(assignments)} assignments. Score at: http://localhost:5000/score")


@click.command("report")
@click.option("--batch-id", required=True)
@click.option("--scorer-type", default="layer1")
@with_appcontext
def report_command(batch_id, scorer_type):
    db = get_db()
    unblinded = unblind_scores(db, batch_id=batch_id, scorer_type=scorer_type)

    if not unblinded:
        click.echo("No scored runs found.")
        return

    runs = list_runs(db, batch_id)
    total_runs = len(runs)
    scored = len(unblinded)
    excluded = total_runs - scored

    click.echo(f"\n{'=' * 60}")
    click.echo(f" MNEME BENCHMARK RESULTS — {batch_id}")
    click.echo(f" Protocol {Config.PROTOCOL_VERSION} | Model: {Config.MODEL} | Temp: {Config.TEMPERATURE}")
    click.echo(f" Scored: {scored}/{total_runs} valid runs ({excluded} excluded)")
    click.echo(f"{'=' * 60}")

    for dim in ["closeness", "usefulness", "distinctiveness"]:
        v = compute_verdict(unblinded, dimension=dim)
        label = "PRIMARY" if dim == "closeness" else "SECONDARY"
        click.echo(f"\n {label}: {dim.title()}")
        click.echo(f"   Win rate: {v['wins']}/{v['total']} = {v['win_rate']:.1%}")
        click.echo(f"   Avg delta: {v['avg_delta']:+.2f}")
        if dim == "closeness":
            click.echo(f"   Ties: {v['ties']}/{v['total']}")
            click.echo(f"   VERDICT: {v['verdict']}")

    click.echo(f"\n PER-USER BREAKDOWN (Closeness)")
    breakdown = compute_per_user(unblinded)
    for uid, stats in breakdown.items():
        click.echo(f"   {uid[:8]}  W:{stats['wins']} L:{stats['losses']} T:{stats['ties']}  "
                    f"{stats['win_rate']:.0%}  Δ{stats['avg_delta']:+.1f}  [{stats['pattern']}]")

    consistency = compute_consistency(unblinded)
    click.echo(f"\n CONSISTENCY: {consistency['agreement_rate']:.0%} agreement")
    if consistency["concern"]:
        click.echo(f"   ⚠ Above 25% disagreement threshold — review scoring")
    click.echo()


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    """Generate demo data for end-to-end testing."""
    import random
    from app.db import get_db, init_db
    from app.models.assignment import insert_assignment, mark_in_progress, mark_completed
    from app.models.score import insert_score

    db = get_db()
    init_db()

    # Create 3 demo users
    users = []
    for i, name in enumerate(["Demo Alice", "Demo Bob", "Demo Carol"]):
        u = insert_user(db, name=name, mneme_profile=json.dumps({"style": f"style_{i}", "values": ["clarity"]}), source="demo")
        users.append(u)

    # Create 3 shared + 2 user-specific prompts per user
    shared_prompts = []
    for cat in ["decision", "strategy", "creative"]:
        p = insert_prompt(db, text=f"Demo {cat} prompt: How would you approach this?", category=cat, scope="shared")
        shared_prompts.append(p)

    for u in users:
        for cat in ["analysis", "personal"]:
            insert_prompt(db, text=f"Demo {cat} prompt for {u['name']}", category=cat, scope="user_specific", user_id=u["id"])

    # Create fake runs
    from app.models.run import insert_run
    from app.utils.hashing import canonical_hash
    from app.models.prompt import get_prompts_for_user

    for u in users:
        prompts = get_prompts_for_user(db, u["id"])
        for p in prompts:
            insert_run(
                db, user_id=u["id"], prompt_id=p["id"], prompt_text=p["text"],
                model="demo-model", temperature=0.7, max_tokens=2048,
                output_default=f"Default response for {u['name']} on {p['category']}",
                output_mneme=f"Mneme response for {u['name']} on {p['category']} — tailored.",
                system_prompt_default="You are helpful.",
                system_prompt_mneme="You are helpful.\n<user_profile>...</user_profile>",
                profile_hash=canonical_hash(u["mneme_profile"]),
                batch_id="demo-batch", protocol_version="v1",
                api_metadata_default=json.dumps({"request_id": "demo", "stop_reason": "end_turn", "input_tokens": 50, "output_tokens": 100, "latency_ms": 500}),
                api_metadata_mneme=json.dumps({"request_id": "demo", "stop_reason": "end_turn", "input_tokens": 60, "output_tokens": 120, "latency_ms": 600}),
                execution_order=random.choice(["default_first", "mneme_first"]),
            )

    # Generate assignments and fake scores
    assignments = generate_assignments(db, batch_id="demo-batch", scorer_type="layer1", scorer_id="demo")
    for a in assignments:
        mark_in_progress(db, a["id"])
        mneme_wins = random.random() < 0.65  # ~65% mneme win rate
        ca = random.randint(3, 5) if mneme_wins and a["output_a_is"] == "mneme" else random.randint(1, 3)
        cb = random.randint(1, 3) if mneme_wins and a["output_a_is"] == "mneme" else random.randint(3, 5)
        insert_score(
            db, assignment_id=a["id"],
            closeness_a=ca, closeness_b=cb,
            usefulness_a=random.randint(2, 5), usefulness_b=random.randint(2, 5),
            distinctiveness_a=random.randint(2, 5), distinctiveness_b=random.randint(2, 5),
            winner_closeness="a" if ca > cb else ("b" if cb > ca else "tie"),
            winner_usefulness=random.choice(["a", "b", "tie"]),
            winner_distinctiveness=random.choice(["a", "b", "tie"]),
            preference="a" if ca > cb else ("b" if cb > ca else "tie"),
        )
        mark_completed(db, a["id"])

    click.echo(f"Seeded: {len(users)} users, {len(assignments)} scored runs in batch 'demo-batch'")
    click.echo("Run: flask report --batch-id demo-batch")
```

**Step 2: Register CLI commands in app factory**

Update `app/__init__.py` to register all CLI commands:

```python
# app/__init__.py
from flask import Flask
from app.config import Config
from app.db import init_db_command, close_db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    app.config["DATABASE"] = Config.DB_PATH

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from app.cli import (add_user_command, add_prompt_command, run_benchmark_command,
                         generate_assignments_command, report_command, seed_demo_command)
    app.cli.add_command(add_user_command)
    app.cli.add_command(add_prompt_command)
    app.cli.add_command(run_benchmark_command)
    app.cli.add_command(generate_assignments_command)
    app.cli.add_command(report_command)
    app.cli.add_command(seed_demo_command)

    return app
```

**Step 3: Test CLI end-to-end**

Run: `flask init-db && flask seed-demo && flask report --batch-id demo-batch`
Expected: Database initialized, demo data seeded, report printed with verdict.

**Step 4: Commit**

```bash
git add app/cli.py app/__init__.py
git commit -m "feat: CLI commands for full benchmark workflow + seed-demo"
```

---

## Task 12: Web — Scoring UI

**Files:**
- Create: `app/web/__init__.py`
- Create: `app/web/scoring_views.py`
- Create: `app/templates/base.html`
- Create: `app/templates/scoring/score.html`
- Create: `app/templates/scoring/complete.html`
- Create: `app/templates/scoring/login.html`
- Create: `app/static/style.css`
- Modify: `app/__init__.py` (register blueprint)

This is the polish point. The scoring UI must be clean, distraction-free, and leak zero metadata.

**Step 1: Create scoring blueprint**

```python
# app/web/__init__.py
```

```python
# app/web/scoring_views.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db
from app.models.assignment import get_next_pending, mark_in_progress, mark_completed, mark_skipped, timeout_stale, count_completed, count_total
from app.models.score import insert_score
from app.models.run import get_run

scoring = Blueprint("scoring", __name__)


@scoring.before_request
def require_scorer():
    if request.endpoint == "scoring.login":
        return
    if "scorer_id" not in session or "scorer_type" not in session:
        return redirect(url_for("scoring.login"))


@scoring.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["scorer_id"] = request.form["scorer_id"]
        session["scorer_type"] = request.form.get("scorer_type", "layer1")
        return redirect(url_for("scoring.score"))
    return render_template("scoring/login.html")


@scoring.route("/score", methods=["GET"])
def score():
    db = get_db()
    scorer_type = session["scorer_type"]
    scorer_id = session["scorer_id"]

    # Timeout stale in_progress assignments
    timeout_stale(db)

    assignment = get_next_pending(db, scorer_type=scorer_type, scorer_id=scorer_id)
    if not assignment:
        completed = count_completed(db, scorer_type, scorer_id)
        return render_template("scoring/complete.html", completed=completed)

    mark_in_progress(db, assignment["id"])

    run = get_run(db, assignment["run_id"])

    # Prepare outputs based on A/B mapping and visual order
    if assignment["output_a_is"] == "mneme":
        output_a = run["output_mneme"]
        output_b = run["output_default"]
    else:
        output_a = run["output_default"]
        output_b = run["output_mneme"]

    # Visual order: which side is A?
    a_on_left = assignment["visual_order"] == "a_left"

    completed = count_completed(db, scorer_type, scorer_id)
    total = count_total(db, scorer_type, scorer_id)

    return render_template("scoring/score.html",
        assignment_id=assignment["id"],
        prompt_text=run["prompt_text"],
        output_a=output_a,
        output_b=output_b,
        a_on_left=a_on_left,
        completed=completed,
        total=total,
    )


@scoring.route("/score", methods=["POST"])
def submit_score():
    db = get_db()
    assignment_id = request.form["assignment_id"]

    if "skip" in request.form:
        mark_skipped(db, assignment_id)
        return redirect(url_for("scoring.score"))

    insert_score(
        db, assignment_id=assignment_id,
        closeness_a=int(request.form["closeness_a"]),
        closeness_b=int(request.form["closeness_b"]),
        usefulness_a=int(request.form["usefulness_a"]),
        usefulness_b=int(request.form["usefulness_b"]),
        distinctiveness_a=int(request.form["distinctiveness_a"]),
        distinctiveness_b=int(request.form["distinctiveness_b"]),
        winner_closeness=request.form["winner_closeness"],
        winner_usefulness=request.form["winner_usefulness"],
        winner_distinctiveness=request.form["winner_distinctiveness"],
        preference=request.form["preference"],
        notes=request.form.get("notes", ""),
    )
    mark_completed(db, assignment_id)

    # Log consistency check
    ca = int(request.form["closeness_a"])
    cb = int(request.form["closeness_b"])
    wc = request.form["winner_closeness"]
    if (ca > cb and wc == "b") or (cb > ca and wc == "a"):
        print(f"CONSISTENCY WARNING: assignment={assignment_id} closeness A={ca} B={cb} winner={wc}")

    return redirect(url_for("scoring.score"))
```

**Step 2: Create templates**

Create `app/templates/base.html`, `app/templates/scoring/login.html`, `app/templates/scoring/score.html`, `app/templates/scoring/complete.html`, and `app/static/style.css` with clean, minimal design. The scoring template shows:
- Prompt text at top
- Two output panels side by side (left/right per visual_order)
- Rating sliders 1-5 for each dimension on each output
- Winner radio buttons per dimension
- Overall preference
- Notes textarea
- Progress bar
- Submit + Skip buttons

**Step 3: Register blueprint in app factory**

Add to `app/__init__.py`:
```python
from app.web.scoring_views import scoring
app.register_blueprint(scoring)
```

**Step 4: Test manually**

Run: `flask seed-demo` then `flask run`, open http://localhost:5000/login
Expected: Login → score page with blind A/B interface

**Step 5: Commit**

```bash
git add app/web/ app/templates/ app/static/ app/__init__.py
git commit -m "feat: blind scoring web UI with session-based scorer identity"
```

---

## Task 13: Web — Dashboard

**Files:**
- Create: `app/web/dashboard_views.py`
- Create: `app/templates/dashboard/index.html`
- Modify: `app/__init__.py` (register blueprint)

**Step 1: Create dashboard blueprint**

```python
# app/web/dashboard_views.py
from flask import Blueprint, render_template, request
from app.db import get_db
from app.config import Config
from app.models.run import list_runs
from app.scoring.unblinder import unblind_scores
from app.reporting.metrics import compute_verdict, compute_per_user, compute_per_category, compute_consistency

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
def index():
    db = get_db()
    batch_id = request.args.get("batch_id", "")
    scorer_type = request.args.get("scorer_type", "layer1")

    if not batch_id:
        # List available batches
        rows = db.execute("SELECT DISTINCT batch_id FROM runs ORDER BY created_at DESC").fetchall()
        batches = [r["batch_id"] for r in rows]
        return render_template("dashboard/index.html", batches=batches, report=None)

    unblinded = unblind_scores(db, batch_id=batch_id, scorer_type=scorer_type)
    runs = list_runs(db, batch_id)

    report = {
        "batch_id": batch_id,
        "protocol_version": Config.PROTOCOL_VERSION,
        "model": Config.MODEL,
        "temperature": Config.TEMPERATURE,
        "total_runs": len(runs),
        "scored_runs": len(unblinded),
        "excluded_runs": len(runs) - len(unblinded),
        "closeness": compute_verdict(unblinded, "closeness"),
        "usefulness": compute_verdict(unblinded, "usefulness"),
        "distinctiveness": compute_verdict(unblinded, "distinctiveness"),
        "per_user": compute_per_user(unblinded),
        "per_category": compute_per_category(unblinded),
        "consistency": compute_consistency(unblinded),
    }

    return render_template("dashboard/index.html", report=report, batches=None)
```

**Step 2: Create dashboard template**

`app/templates/dashboard/index.html` — renders verdict card, win rate bars, per-user table, per-category table, consistency section. All server-rendered HTML + CSS. No JavaScript charting.

**Step 3: Register blueprint**

Add to `app/__init__.py`:
```python
from app.web.dashboard_views import dashboard
app.register_blueprint(dashboard)
```

**Step 4: Test manually**

Run: `flask run`, open http://localhost:5000/dashboard?batch_id=demo-batch
Expected: Dashboard with verdict, breakdowns, consistency check

**Step 5: Commit**

```bash
git add app/web/dashboard_views.py app/templates/dashboard/ app/__init__.py
git commit -m "feat: reporting dashboard with verdict, per-user, and consistency views"
```

---

## Task 14: Export (CLI)

**Files:**
- Create: `app/reporting/export.py`
- Modify: `app/cli.py` (add export command)

**Step 1: Implement export**

```python
# app/reporting/export.py
import csv
import json
import io


def export_csv(unblinded):
    output = io.StringIO()
    if not unblinded:
        return ""
    fieldnames = ["user_id", "prompt_text", "prompt_category",
                  "closeness_a", "closeness_b", "closeness_delta", "true_winner_closeness",
                  "usefulness_a", "usefulness_b", "usefulness_delta", "true_winner_usefulness",
                  "distinctiveness_a", "distinctiveness_b", "distinctiveness_delta", "true_winner_distinctiveness",
                  "preference", "true_preference", "notes"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in unblinded:
        writer.writerow(row)
    return output.getvalue()


def export_json(unblinded, report):
    return json.dumps({"report": report, "rows": unblinded}, indent=2, default=str)
```

**Step 2: Add export CLI command to app/cli.py**

```python
@click.command("export")
@click.option("--batch-id", required=True)
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv")
@click.option("--output", "output_path", default=None)
@with_appcontext
def export_command(batch_id, fmt, output_path):
    from app.reporting.export import export_csv, export_json
    db = get_db()
    unblinded = unblind_scores(db, batch_id=batch_id)

    if fmt == "csv":
        content = export_csv(unblinded)
    else:
        v = compute_verdict(unblinded)
        content = export_json(unblinded, v)

    if output_path:
        with open(output_path, "w") as f:
            f.write(content)
        click.echo(f"Exported to {output_path}")
    else:
        click.echo(content)
```

Register in `app/__init__.py`.

**Step 3: Test**

Run: `flask export --batch-id demo-batch --format csv`
Expected: CSV output with unblinded scores

**Step 4: Commit**

```bash
git add app/reporting/export.py app/cli.py app/__init__.py
git commit -m "feat: CSV and JSON export of unblinded results"
```

---

## Task 15: End-to-End Smoke Test

**Step 1: Full workflow test**

```bash
flask init-db
flask seed-demo
flask report --batch-id demo-batch
flask export --batch-id demo-batch --format csv --output demo-export.csv
flask run  # then open /dashboard?batch_id=demo-batch and /login → /score
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end smoke test verified"
git push
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Scaffolding + deps | Manual verify |
| 2 | Schema + db layer | test_db.py |
| 3 | User + prompt models | test_models_user.py, test_models_prompt.py |
| 4 | Run model (immutable) | test_models_run.py |
| 5 | Assignment + score models | test_models_assignment.py, test_models_score.py |
| 6 | Prompt assembly | test_prompt_assembly.py |
| 7 | Claude client (mocked) | test_claude_client.py |
| 8 | Benchmark engine | test_engine.py |
| 9 | Assigner + unblinder | test_blinding.py |
| 10 | Metrics engine | test_metrics.py |
| 11 | CLI commands | Manual + seed-demo |
| 12 | Scoring web UI | Manual |
| 13 | Dashboard | Manual |
| 14 | Export | Manual |
| 15 | Smoke test | Full pipeline |
