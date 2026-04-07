-- Run once on any database created before 2026-04-07
-- Safe to run multiple times (SQLite ignores duplicate column errors when using this pattern)
ALTER TABLE users ADD COLUMN extra_context TEXT;
