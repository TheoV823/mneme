-- Run once on databases that do not yet have this table.
-- CREATE TABLE IF NOT EXISTS will not alter or recreate the table if it already exists.
CREATE TABLE IF NOT EXISTS comparison_results (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    prompt TEXT NOT NULL,
    option_a_mode TEXT NOT NULL CHECK (option_a_mode IN ('default', 'mneme')),
    option_b_mode TEXT NOT NULL CHECK (option_b_mode IN ('default', 'mneme')),
    winner TEXT NOT NULL CHECK (winner IN ('a', 'b', 'tie', 'skip')),
    preferred_mode TEXT CHECK (preferred_mode IN ('default', 'mneme')),
    created_at TEXT NOT NULL,
    CHECK (
        (winner IN ('tie', 'skip') AND preferred_mode IS NULL)
        OR
        (winner IN ('a', 'b') AND preferred_mode IS NOT NULL)
    )
);
