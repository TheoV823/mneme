"""Database connection and schema initialization.

Stub for Task 1 scaffolding. Full implementation in Task 2.
"""

import sqlite3
import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database from schema.sql. Full implementation in Task 2."""
    pass


@click.command("init-db")
def init_db_command():
    """Create database tables from schema.sql."""
    init_db()
    click.echo("Database initialized.")
