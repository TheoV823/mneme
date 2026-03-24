import json
import click
from flask.cli import with_appcontext

from app.db import get_db
from app.config import Config
from app.models.user import insert_user, list_users
from app.models.prompt import insert_prompt
from app.models.run import list_runs
from app.runner.engine import run_benchmark_for_user


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
