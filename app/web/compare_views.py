from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db
from app.config import Config
from app.models.user import list_users, get_user, insert_user
from app.models.comparison import insert_comparison, get_comparisons_for_user, compute_win_rate
from app.runner.compare import run_comparison
from app.profiles.extractors import extract_qa_signals
from app.profiles.builder import build_mneme_profile
import json

compare = Blueprint("compare", __name__)


@compare.route("/compare")
def index():
    db = get_db()
    users = list_users(db)
    selected_user_id = request.args.get("user_id", "")
    return render_template("compare/index.html", users=users, selected_user_id=selected_user_id)


@compare.route("/compare/run", methods=["POST"])
def run():
    user_id = request.form.get("user_id", "").strip()
    prompt_text = request.form.get("prompt", "").strip()

    if not user_id:
        flash("Please select a user.")
        return redirect(url_for("compare.index"))
    if not prompt_text:
        flash("Please enter a prompt.")
        return redirect(url_for("compare.index", user_id=user_id))

    db = get_db()
    user = get_user(db, user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for("compare.index"))

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
        flash(f"LLM call failed: {e}")
        return redirect(url_for("compare.index", user_id=user_id))

    session["compare_pending"] = {
        "user_id": user_id,
        "user_name": user["name"],
        "prompt": prompt_text,
        "output_a": result["output_a"],
        "output_b": result["output_b"],
        "option_a_mode": result["option_a_mode"],
        "option_b_mode": result["option_b_mode"],
    }
    return redirect(url_for("compare.result"))


@compare.route("/compare/result")
def result():
    pending = session.get("compare_pending")
    if not pending:
        flash("No active comparison. Run one first.")
        return redirect(url_for("compare.index"))
    return render_template("compare/result.html", pending=pending)


@compare.route("/compare/vote", methods=["POST"])
def vote():
    pending = session.get("compare_pending")
    if not pending:
        flash("Session expired. Run the comparison again.")
        return redirect(url_for("compare.index"))

    choice = request.form.get("choice", "").strip().lower()
    if choice not in ("a", "b", "tie", "skip"):
        flash("Invalid choice.")
        return redirect(url_for("compare.result"))

    winner = choice
    if winner == "a":
        preferred_mode = pending["option_a_mode"]
    elif winner == "b":
        preferred_mode = pending["option_b_mode"]
    else:
        preferred_mode = None

    db = get_db()
    insert_comparison(
        db,
        user_id=pending["user_id"],
        prompt=pending["prompt"],
        option_a_mode=pending["option_a_mode"],
        option_b_mode=pending["option_b_mode"],
        winner=winner,
        preferred_mode=preferred_mode,
    )
    session.pop("compare_pending", None)

    label = {"a": "Option A", "b": "Option B", "tie": "Tie", "skip": "Skipped"}[winner]
    flash(f"Saved — {label}" + (f" ({preferred_mode})" if preferred_mode else ""))
    return redirect(url_for("compare.index", user_id=pending["user_id"]))


@compare.route("/compare/stats")
def stats():
    db = get_db()
    users = list_users(db)
    selected_user_id = request.args.get("user_id", "")

    stats_data = None
    selected_user = None
    if selected_user_id:
        selected_user = get_user(db, selected_user_id)
        if selected_user:
            comparisons = get_comparisons_for_user(db, selected_user_id)
            stats_data = compute_win_rate(comparisons) if comparisons else None

    return render_template("compare/stats.html",
        users=users,
        selected_user=selected_user,
        selected_user_id=selected_user_id,
        stats=stats_data,
    )


@compare.route("/compare/add-user", methods=["GET", "POST"])
def add_user():
    if request.method == "GET":
        return render_template("compare/add_user.html")

    name = request.form.get("name", "").strip()
    profile_json = request.form.get("profile_json", "").strip()

    if not name:
        flash("Name is required.")
        return render_template("compare/add_user.html", name=name, profile_json=profile_json)

    if not profile_json:
        flash("Profile JSON is required.")
        return render_template("compare/add_user.html", name=name, profile_json=profile_json)

    try:
        qa_input = json.loads(profile_json)
    except json.JSONDecodeError as e:
        flash(f"Invalid JSON: {e}")
        return render_template("compare/add_user.html", name=name, profile_json=profile_json)

    qa_signals = extract_qa_signals(qa_input)
    merged_profile = build_mneme_profile({"qa": qa_signals})

    db = get_db()
    user = insert_user(db, name=name, mneme_profile=json.dumps(merged_profile), source="web")
    flash(f"User created: {user['name']} ({user['id'][:8]}...)")
    return redirect(url_for("compare.index", user_id=user["id"]))
