-- Run once on any database created before 2026-04-07 (the compare-mode feature date).
-- CREATE TABLE IF NOT EXISTS is safe to run multiple times — it is a no-op if the table exists.
CREATE TABLE IF NOT EXISTS comparison_results (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    prompt       TEXT NOT NULL,
    option_a_mode TEXT NOT NULL CHECK (option_a_mode IN ('default', 'mneme')),
    option_b_mode TEXT NOT NULL CHECK (option_b_mode IN ('default', 'mneme')),
    winner       TEXT NOT NULL CHECK (winner IN ('A', 'B', 'tie', 'skip')),
    preferred_mode TEXT CHECK (preferred_mode IN ('default', 'mneme')),
    created_at   TEXT NOT NULL
);
