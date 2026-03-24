# Mneme Benchmark Harness — Design Document

**Date:** 2026-03-24
**Status:** Approved
**Protocol Version:** v1

## Purpose

Test whether injecting user profile data ("mneme profiles") into Claude's system prompt produces meaningfully better outputs. The benchmark answers one question:

> Does mneme-amplified output win on Closeness to User Thinking at >= 60% win rate AND >= 0.5 average delta?

## Architecture Decision

**Option A: Flask Monolith + SQLite + CLI Runner + Web Scoring/Reporting UI**

- Benchmarks run from CLI
- Humans score in browser
- Reports come from the same DB
- Internally modular: separate folders for models, runner, scoring, reporting

Why: lowest build time, enough structure for repeatable benchmarks, avoids pointless frontend complexity.

---

## Data Model

### Tables

#### `users`

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| name | TEXT | NOT NULL |
| mneme_profile | TEXT | NOT NULL, full profile JSON |
| source | TEXT | e.g. "reddit" |
| created_at | TEXT | NOT NULL, ISO timestamp |

#### `prompts`

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| text | TEXT | NOT NULL |
| category | TEXT | NOT NULL (decision, strategy, creative, analysis, personal) |
| scope | TEXT | NOT NULL, CHECK IN (shared, user_specific) |
| user_id | TEXT | FK to users, NULL for shared |
| created_at | TEXT | NOT NULL, ISO timestamp |

#### `runs` (immutable, append-only)

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| user_id | TEXT | NOT NULL, FK to users |
| prompt_id | TEXT | NOT NULL, FK to prompts |
| prompt_text | TEXT | NOT NULL, exact snapshot used |
| model | TEXT | NOT NULL |
| temperature | REAL | NOT NULL |
| max_tokens | INTEGER | NOT NULL |
| output_default | TEXT | NOT NULL |
| output_mneme | TEXT | NOT NULL |
| system_prompt_default | TEXT | NOT NULL, verbatim |
| system_prompt_mneme | TEXT | NOT NULL, verbatim |
| profile_hash | TEXT | NOT NULL, SHA-256 of canonical profile JSON |
| batch_id | TEXT | NOT NULL |
| protocol_version | TEXT | NOT NULL |
| api_metadata_default | TEXT | JSON: request_id, stop_reason, input_tokens, output_tokens, latency_ms |
| api_metadata_mneme | TEXT | JSON: same fields |
| execution_order | TEXT | NOT NULL, CHECK IN (default_first, mneme_first) |
| created_at | TEXT | NOT NULL, ISO timestamp |

**Unique constraint:** (batch_id, user_id, prompt_id, model, protocol_version)

#### `scoring_assignments`

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| run_id | TEXT | NOT NULL, FK to runs |
| scorer_type | TEXT | NOT NULL, CHECK IN (layer1, layer2, layer3) |
| scorer_id | TEXT | NOT NULL |
| output_a_is | TEXT | NOT NULL, CHECK IN (default, mneme) |
| visual_order | TEXT | NOT NULL, CHECK IN (a_left, a_right) |
| status | TEXT | NOT NULL, CHECK IN (pending, in_progress, completed, skipped) |
| created_at | TEXT | NOT NULL, ISO timestamp |

#### `scores`

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| assignment_id | TEXT | NOT NULL UNIQUE, FK to scoring_assignments |
| closeness_a | INTEGER | NOT NULL, CHECK 1-5 |
| closeness_b | INTEGER | NOT NULL, CHECK 1-5 |
| usefulness_a | INTEGER | NOT NULL, CHECK 1-5 |
| usefulness_b | INTEGER | NOT NULL, CHECK 1-5 |
| distinctiveness_a | INTEGER | NOT NULL, CHECK 1-5 |
| distinctiveness_b | INTEGER | NOT NULL, CHECK 1-5 |
| winner_closeness | TEXT | NOT NULL, CHECK IN (a, b, tie) |
| winner_usefulness | TEXT | NOT NULL, CHECK IN (a, b, tie) |
| winner_distinctiveness | TEXT | NOT NULL, CHECK IN (a, b, tie) |
| preference | TEXT | NOT NULL, CHECK IN (a, b, tie) |
| notes | TEXT | |
| created_at | TEXT | NOT NULL, ISO timestamp |

#### `metrics_snapshots` (optional cache)

| Column | Type | Constraint |
|--------|------|------------|
| id | TEXT PK | UUID |
| layer | TEXT | NOT NULL |
| total_runs_scored | INTEGER | NOT NULL |
| valid_runs | INTEGER | NOT NULL |
| excluded_runs | INTEGER | NOT NULL |
| exclusion_reasons | TEXT | JSON |
| closeness_win_rate | REAL | |
| closeness_avg_delta | REAL | |
| usefulness_win_rate | REAL | |
| distinctiveness_win_rate | REAL | |
| per_user_json | TEXT | |
| created_at | TEXT | NOT NULL, ISO timestamp |

### Key Design Decisions

1. **Immutable runs** — append-only, no UPDATE. Bad runs are excluded, not modified.
2. **Blinding via scoring_assignments** — randomization of A/B and left/right stored separately from scores.
3. **Stored system prompts** — both default and mneme prompts stored verbatim for full audit.
4. **prompt_text snapshot** — exact prompt used, not just FK, so edits don't break reproducibility.
5. **profile_hash** — SHA-256 of canonical JSON (sorted keys, stable separators) for clean audit key.
6. **Scores reference assignments, not runs** — supports multiple scoring layers on the same run.

---

## Project Structure

```
mneme/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Settings, protocol_version, app_version
│   ├── db.py                # SQLite connection, schema init
│   │
│   ├── models/              # Data access layer (SQL queries, no business logic)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── prompt.py
│   │   ├── run.py           # Insert-only
│   │   ├── assignment.py
│   │   └── score.py
│   │
│   ├── runner/              # Benchmark execution (CLI only)
│   │   ├── __init__.py
│   │   ├── engine.py        # Orchestrates: assemble → call → store
│   │   ├── prompt_assembly.py
│   │   └── claude_client.py # Thin Anthropic SDK wrapper
│   │
│   ├── scoring/             # Blind scoring logic
│   │   ├── __init__.py
│   │   ├── assigner.py      # Randomized A/B + left/right assignments
│   │   └── unblinder.py     # Read-only join for reporting
│   │
│   ├── reporting/           # Metrics computation
│   │   ├── __init__.py
│   │   ├── metrics.py       # Win rates, deltas, per-user breakdowns
│   │   └── export.py        # CSV/JSON export
│   │
│   ├── utils/               # Shared helpers
│   │   ├── __init__.py
│   │   ├── ids.py           # UUID generation
│   │   ├── timestamps.py    # ISO timestamp helpers
│   │   ├── hashing.py       # Canonical JSON + SHA-256
│   │   └── validation.py    # Score bounds, enum checks
│   │
│   ├── web/                 # Flask blueprints
│   │   ├── __init__.py
│   │   ├── scoring_views.py
│   │   ├── dashboard_views.py
│   │   └── admin_views.py   # Minimal, read-only run inspection
│   │
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html
│   │   ├── scoring/
│   │   ├── dashboard/
│   │   └── admin/
│   │
│   ├── static/              # CSS, minimal JS
│   │
│   └── cli.py               # Click commands
│
├── schema.sql
├── requirements.txt
├── run.py
├── docs/
│   └── plans/
└── tests/
    ├── test_runner.py
    ├── test_scoring.py
    ├── test_blinding.py     # Blinding integrity tests
    └── test_metrics.py
```

---

## Flow 1: Benchmark Runner

**Trigger:** `python -m app.cli run-benchmark --batch batch-001 --user-id <id>`

For each user + prompt combination in the batch:

1. Load user and mneme_profile from DB
2. Load assigned prompts (3 shared + 2 user-specific)
3. For each prompt:
   a. Snapshot prompt_text
   b. Assemble system_prompt_default (base prompt, no profile)
   c. Assemble system_prompt_mneme (base prompt + `<user_profile>` block)
   d. Randomize execution order (coin flip: default-first or mneme-first)
   e. Call Claude API twice (in randomized order)
   f. Compute profile_hash (SHA-256 of canonical JSON)
   g. INSERT immutable run record with both outputs, both system prompts, prompt_text snapshot, profile_hash, batch_id, protocol_version, api_metadata, execution_order
4. Print summary

### Prompt Assembly

**Default system prompt:**
```
You are a helpful assistant. Respond thoughtfully to the user's request.
```

**Mneme system prompt:**
```
You are a helpful assistant. Respond thoughtfully to the user's request.

<user_profile>
{canonical mneme_profile JSON}
</user_profile>

Use the above profile to tailor your response to how this person thinks,
decides, and communicates. Do not mention the profile directly.
```

### Controls

- Temperature: fixed (0.7)
- max_tokens: fixed (locked in config)
- top_p: fixed if supported
- Execution order: randomized per-run to prevent position bias
- Profile hash: canonical JSON (sorted keys, `separators=(',', ':')`)

### Failure Handling

- API failure → run NOT inserted, error printed, skip to next prompt
- Idempotent: skips if run exists for (batch_id, user_id, prompt_id, model, protocol_version)

### API Metadata Stored

request_id, stop_reason, input_tokens, output_tokens, latency_ms — per call.

---

## Flow 2: Blind Scoring

### Phase 2a: Generate Assignments (CLI)

**Trigger:** `python -m app.cli generate-assignments --batch batch-001 --scorer-type layer1 --scorer-id <id>`

For each completed run lacking an assignment for this scorer:
1. Coin flip → output_a_is = "default" or "mneme"
2. Coin flip → visual_order = "a_left" or "a_right"
3. INSERT scoring_assignment with status = "pending"
4. Shuffle full assignment list (presentation order != insertion order)

### Phase 2b: Scoring UI (Web)

**Route:** `GET /score`

**Scorer identity:** set once at session level (login/token), not per-request.

**Flow:**
1. Fetch next pending assignment for this scorer
2. Mark as in_progress (prevents double-scoring on refresh/multi-tab)
3. Timeout recovery: in_progress > 30 min reverts to pending
4. Display prompt + Output A + Output B side by side
5. Visual placement randomized per visual_order field
6. Scorer rates each output 1-5 on three dimensions
7. Scorer picks winner per dimension (a/b/tie)
8. Scorer picks overall preference (a/b/tie)
9. Optional notes field
10. Optional skip button (marks assignment as "skipped")

**What scorer sees:** prompt text, two outputs, progress count. Nothing else.

**What scorer does NOT see:** user identity, which is default/mneme, profile, run metadata.

**On submit (`POST /score`):**
1. Validate scores 1-5, winners in (a, b, tie)
2. Log winner-vs-score inconsistencies (soft check, does not block)
3. INSERT score
4. UPDATE assignment status = "completed"
5. Redirect to next pending

**Progress:** server-side count of completed assignments for this scorer.

### Phase 2c: Unblinding (read-only, post-scoring)

Joins scores + assignments to translate A/B winners back to default/mneme truth. Never modifies data. Never accessible from scoring UI.

---

## Flow 3: Reporting

**Trigger:** `python -m app.cli report --batch batch-001` or `GET /dashboard`

### Section 1: Primary Verdict

```
PRIMARY METRIC: Closeness to User Thinking

  Scored: 47/50 valid runs (3 excluded)
  Win rate:      32/47 = 68.1%    threshold: >= 60%
  Avg delta:     +0.72            threshold: >= 0.5
  Ties:          5/47 (10.6%)
  Losses:        10/47 (21.3%)

  VERDICT: SIGNAL DETECTED
```

- Denominator = all scored runs minus exclusions
- Ties included in denominator, reported separately
- Verdict logic: both thresholds → SIGNAL DETECTED, one → INCONCLUSIVE, neither → NO SIGNAL

### Section 2: Secondary Metrics

Usefulness win rate, distinctiveness win rate, overall preference — same computation, no pass/fail threshold.

### Section 3: Per-User Breakdown

| User | Wins | Losses | Ties | Win% | Avg Delta | Pattern |
|------|------|--------|------|------|-----------|---------|
| ... | | | | | | directional label |

Pattern labels (directional only, not stable truth at n=5):
- dominant: >= 80% win rate AND delta >= 1.0
- strong: >= 60% AND delta >= 0.5
- moderate: >= 60% OR delta >= 0.5
- weak: 40-59%, delta near zero
- negative: < 40%

### Section 4: Per-Prompt-Category Breakdown

Same structure sliced by prompt category.

### Section 5: Score Distributions

Mean, median, std, histogram for each dimension, mneme vs default.

### Section 6: Consistency Check

Winner-vs-score agreement rate. Concern threshold: > 25% disagreement rate triggers review.

### Section 7: Execution Metadata

Total API calls, token counts, estimated cost, avg latency, excluded runs count + reasons.

### Export

- CLI: full text report
- Web: cards + simple CSS charts (no JS charting libraries)
- CSV: unblinded scores, one row per run
- JSON: full structured report

---

## Blinding Integrity Tests

1. A/B randomization is approximately 50/50 over 1000 assignments
2. Scoring endpoint response contains zero metadata beyond prompt + two outputs
3. Unblinding correctly maps A/B winners to default/mneme truth
4. Output text contains no profile-referencing markers
5. Assignment presentation order != insertion order != user grouping
6. Visual left/right placement is randomized independently from A/B mapping

---

## CLI Commands

| Command | Action |
|---------|--------|
| init-db | Create tables from schema.sql |
| add-user | Insert user + mneme profile from JSON file |
| add-prompt | Insert prompt (shared or user-specific) |
| run-benchmark | Execute runs for a batch (idempotent) |
| generate-assignments | Create randomized scoring assignments |
| report | Print verdict, metrics, breakdowns |
| export | CSV/JSON export of unblinded results |
| seed-demo | Generate demo data for end-to-end testing |

---

## Configuration

Via environment variables or `.env`:

| Variable | Default | Notes |
|----------|---------|-------|
| ANTHROPIC_API_KEY | (required) | |
| MNEME_DB_PATH | mneme.db | |
| MNEME_MODEL | claude-sonnet-4-20250514 | Locked per batch |
| MNEME_TEMPERATURE | 0.7 | |
| MNEME_MAX_TOKENS | 2048 | |
| MNEME_PROTOCOL_VERSION | v1 | Stored in every run |
| SECRET_KEY | (required for web) | Flask session key |

---

## What This Design Does NOT Include

- No ORM (raw sqlite3)
- No JavaScript charting (CSS bar charts for MVP)
- No admin CRUD UI (CLI is the operator interface)
- No Layer 2 or Layer 3 scoring automation (added later if Layer 1 shows signal)
- No deployment config (localhost only for MVP)
