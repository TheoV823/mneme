from flask import Flask
from app.config import Config
from app.db import init_db_command, close_db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    app.config["DATABASE"] = Config.DB_PATH

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from app.cli import add_user_command, add_prompt_command, run_benchmark_command
    app.cli.add_command(add_user_command)
    app.cli.add_command(add_prompt_command)
    app.cli.add_command(run_benchmark_command)

    return app
