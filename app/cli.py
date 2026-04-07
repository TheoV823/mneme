import json
import random
import click
from flask.cli import with_appcontext

from app.db import get_db, init_db
from app.config import Config
from app.models.user import insert_user, list_users, get_user
from app.profiles.extractors import extract_qa_signals, extract_extra_context_signals
from app.profiles.builder import build_mneme_profile
from app.models.prompt import insert_prompt, get_prompts_for_user
from app.runner.compare import run_comparison
from app.models.comparison import insert_comparison, get_comparisons_for_user, compute_win_rate
from app.models.run import insert_run, list_runs
from app.runner.engine import run_benchmark_for_user
from app.scoring.assigner import generate_assignments
from app.scoring.unblinder import unblind_scores
from app.reporting.metrics import compute_verdict, compute_per_user, compute_consistency
from app.utils.hashing import canonical_hash


@click.command("add-user")
@click.argument("profile_path")
@click.option("--name", required=True)
@click.option("--source", default=None)
@click.option(
    "--extra-context-path",
    default=None,
    help="Optional path to a plain-text file with extra context (bio, notes, etc.)",
)
@click.option(
    "--extra-context-type",
    default=None,
    type=click.Choice(["chat", "document", "notes"], case_sensitive=False),
    help="Type of extra context: chat | document | notes",
)
@with_appcontext
def add_user_command(profile_path, name, source, extra_context_path, extra_context_type):
    with open(profile_path) as f:
        raw = f.read()
    qa_input = json.loads(raw)  # validate JSON

    qa_signals = extract_qa_signals(qa_input)
    signals = {"qa": qa_signals}

    extra_text = None
    if extra_context_path:
        with open(extra_context_path) as f:
            extra_text = f.read()
        ec_signals = extract_extra_context_signals(extra_text, Config.ANTHROPIC_API_KEY,
                                                   context_type=extra_context_type)
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
        extra_context_type=extra_context_type,
    )
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
    click.echo(f"Generated {len(assignments)} assignments. Score at: http://localhost:5000/login")


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
                    f"{stats['win_rate']:.0%}  d{stats['avg_delta']:+.1f}  [{stats['pattern']}]")

    consistency = compute_consistency(unblinded)
    click.echo(f"\n CONSISTENCY: {consistency['agreement_rate']:.0%} agreement")
    if consistency["concern"]:
        click.echo(f"   WARNING: Above 25% disagreement threshold")
    click.echo()


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


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    """Generate demo data for end-to-end testing."""
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
    for cat in ["decision", "strategy", "creative"]:
        insert_prompt(db, text=f"Demo {cat} prompt: How would you approach this?", category=cat, scope="shared")

    for u in users:
        for cat in ["analysis", "personal"]:
            insert_prompt(db, text=f"Demo {cat} prompt for {u['name']}", category=cat, scope="user_specific", user_id=u["id"])

    # Create fake runs
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


@click.command("compare")
@click.option("--user-id", required=True, help="User ID to compare against.")
@click.option("--prompt", "prompt_text", required=True, help="Prompt to send to both AI modes.")
@with_appcontext
def compare_command(user_id, prompt_text):
    """Run a prompt against default AI and Mneme AI. Choose which output you prefer."""
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
    while True:
        choice = click.prompt("Which is better? (A/B/tie/skip)").strip().lower()
        if choice in valid:
            break

    # winner stored as lowercase: 'a', 'b', 'tie', 'skip'
    winner = choice

    if winner == "a":
        preferred_mode = result["option_a_mode"]
    elif winner == "b":
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


@click.command("compare-stats")
@click.option("--user-id", required=True, help="User ID to show stats for.")
@with_appcontext
def compare_stats_command(user_id):
    """Show cumulative Mneme win rate for a user across all comparisons."""
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
