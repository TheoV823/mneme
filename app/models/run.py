from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_run(db, *, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
               output_default, output_mneme, system_prompt_default, system_prompt_mneme,
               profile_hash, batch_id, protocol_version, api_metadata_default,
               api_metadata_mneme, execution_order):
    run_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO runs (id, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
           output_default, output_mneme, system_prompt_default, system_prompt_mneme,
           profile_hash, batch_id, protocol_version, api_metadata_default, api_metadata_mneme,
           execution_order, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, user_id, prompt_id, prompt_text, model, temperature, max_tokens,
         output_default, output_mneme, system_prompt_default, system_prompt_mneme,
         profile_hash, batch_id, protocol_version, api_metadata_default, api_metadata_mneme,
         execution_order, created_at),
    )
    db.commit()
    return {"id": run_id, "created_at": created_at}


def get_run(db, run_id):
    row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def run_exists(db, batch_id, user_id, prompt_id, model, protocol_version):
    row = db.execute(
        """SELECT 1 FROM runs
           WHERE batch_id = ? AND user_id = ? AND prompt_id = ? AND model = ? AND protocol_version = ?""",
        (batch_id, user_id, prompt_id, model, protocol_version),
    ).fetchone()
    return row is not None


def list_runs(db, batch_id):
    rows = db.execute("SELECT * FROM runs WHERE batch_id = ? ORDER BY created_at", (batch_id,)).fetchall()
    return [dict(r) for r in rows]
