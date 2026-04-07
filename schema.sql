CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mneme_profile TEXT NOT NULL,
    extra_context TEXT,
    source TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('shared', 'user_specific')),
    user_id TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    prompt_id TEXT NOT NULL REFERENCES prompts(id),
    prompt_text TEXT NOT NULL,
    model TEXT NOT NULL,
    temperature REAL NOT NULL,
    max_tokens INTEGER NOT NULL,
    output_default TEXT NOT NULL,
    output_mneme TEXT NOT NULL,
    system_prompt_default TEXT NOT NULL,
    system_prompt_mneme TEXT NOT NULL,
    profile_hash TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    api_metadata_default TEXT,
    api_metadata_mneme TEXT,
    execution_order TEXT NOT NULL CHECK (execution_order IN ('default_first', 'mneme_first')),
    created_at TEXT NOT NULL,
    UNIQUE (batch_id, user_id, prompt_id, model, protocol_version)
);

CREATE TABLE IF NOT EXISTS scoring_assignments (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    scorer_type TEXT NOT NULL CHECK (scorer_type IN ('layer1', 'layer2', 'layer3')),
    scorer_id TEXT NOT NULL,
    output_a_is TEXT NOT NULL CHECK (output_a_is IN ('default', 'mneme')),
    visual_order TEXT NOT NULL CHECK (visual_order IN ('a_left', 'a_right')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL UNIQUE REFERENCES scoring_assignments(id),
    closeness_a INTEGER NOT NULL CHECK (closeness_a BETWEEN 1 AND 5),
    closeness_b INTEGER NOT NULL CHECK (closeness_b BETWEEN 1 AND 5),
    usefulness_a INTEGER NOT NULL CHECK (usefulness_a BETWEEN 1 AND 5),
    usefulness_b INTEGER NOT NULL CHECK (usefulness_b BETWEEN 1 AND 5),
    distinctiveness_a INTEGER NOT NULL CHECK (distinctiveness_a BETWEEN 1 AND 5),
    distinctiveness_b INTEGER NOT NULL CHECK (distinctiveness_b BETWEEN 1 AND 5),
    winner_closeness TEXT NOT NULL CHECK (winner_closeness IN ('a', 'b', 'tie')),
    winner_usefulness TEXT NOT NULL CHECK (winner_usefulness IN ('a', 'b', 'tie')),
    winner_distinctiveness TEXT NOT NULL CHECK (winner_distinctiveness IN ('a', 'b', 'tie')),
    preference TEXT NOT NULL CHECK (preference IN ('a', 'b', 'tie')),
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    total_runs_scored INTEGER NOT NULL,
    valid_runs INTEGER NOT NULL,
    excluded_runs INTEGER NOT NULL,
    exclusion_reasons TEXT,
    closeness_win_rate REAL,
    closeness_avg_delta REAL,
    usefulness_win_rate REAL,
    distinctiveness_win_rate REAL,
    per_user_json TEXT,
    created_at TEXT NOT NULL
);

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
