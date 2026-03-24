from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_user(db, name, mneme_profile, source=None):
    user_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO users (id, name, mneme_profile, source, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, mneme_profile, source, created_at),
    )
    db.commit()
    return {"id": user_id, "name": name, "mneme_profile": mneme_profile, "source": source, "created_at": created_at}


def get_user(db, user_id):
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users(db):
    rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]
