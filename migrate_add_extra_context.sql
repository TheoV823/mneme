-- Run once on any database created before 2026-04-07
-- NOTE: SQLite does not support IF NOT EXISTS on ADD COLUMN — run this exactly once.
ALTER TABLE users ADD COLUMN extra_context TEXT;
