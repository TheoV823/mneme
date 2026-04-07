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
                         generate_assignments_command, report_command, export_command,
                         seed_demo_command, compare_command, compare_stats_command)
    app.cli.add_command(add_user_command)
    app.cli.add_command(add_prompt_command)
    app.cli.add_command(run_benchmark_command)
    app.cli.add_command(generate_assignments_command)
    app.cli.add_command(report_command)
    app.cli.add_command(export_command)
    app.cli.add_command(seed_demo_command)
    app.cli.add_command(compare_command)
    app.cli.add_command(compare_stats_command)

    from app.web.scoring_views import scoring
    app.register_blueprint(scoring)

    from app.web.dashboard_views import dashboard
    app.register_blueprint(dashboard)

    return app
