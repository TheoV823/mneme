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
