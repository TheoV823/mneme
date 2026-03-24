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
