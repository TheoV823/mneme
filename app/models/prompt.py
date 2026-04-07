from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_prompt(db, text, category, scope, user_id=None):
    prompt_id = new_id()
    created_at = now_iso()
    db.execute(
        "INSERT INTO prompts (id, text, category, scope, user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (prompt_id, text, category, scope, user_id, created_at),
    )
    db.commit()
    return {"id": prompt_id, "text": text, "category": category, "scope": scope, "user_id": user_id, "created_at": created_at}


def get_prompts_for_user(db, user_id):
    rows = db.execute(
        "SELECT * FROM prompts WHERE scope = 'shared' OR user_id = ? ORDER BY category",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_prompt(db, prompt_id):
    row = db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
    return dict(row) if row else None
