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
