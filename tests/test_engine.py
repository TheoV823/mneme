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
