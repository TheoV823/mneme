# Compare Mode

Compare Mode is the validation layer for Mneme. It answers one question:

> Does AI personalized with my decision profile produce outputs I prefer over default AI?

## Commands

### `flask compare`

Runs a single prompt against both default AI and Mneme AI, presents both outputs
as a blind comparison (Option A / Option B), and asks you to pick the better one.

```
flask compare --user-id <id> --prompt "How would you grow a SaaS product?"
```

**Output format:**

```
Running comparison for Alice...

────────────────────────────────────────────────────────────
PROMPT:
How would you grow a SaaS product?
────────────────────────────────────────────────────────────
Option A:

[output text]
────────────────────────────────────────────────────────────
Option B:

[output text]
────────────────────────────────────────────────────────────
Which is better? (A/B/tie/skip):
```

**Choices:**
- `A` or `a` — Option A was better
- `B` or `b` — Option B was better
- `tie` — both equally good
- `skip` — skip this comparison (e.g. low-quality outputs)

The A/B assignment is randomized per comparison to prevent position bias.
You never see which output came from which mode until the result is saved.

---

### `flask compare-stats`

Shows cumulative win-rate stats for a user.

```
flask compare-stats --user-id <id>
```

**Output format:**

```
Mneme comparison stats for Alice:
  Total comparisons : 10
  Mneme wins        : 7
  Default wins      : 2
  Ties              : 1
  Skips             : 0
  Win rate          : 77.8%
```

**Win rate formula:**
```
win_rate = mneme_wins / (mneme_wins + default_wins)
```
Ties and skips are excluded from the denominator but counted separately.
`N/A` is shown when there are no decisive comparisons yet.

---

## Interpreting Results

| Win rate | Signal |
|----------|--------|
| ≥ 60% | Strong signal — profile is improving outputs |
| 45–60% | Weak / inconclusive |
| < 45% | No signal or negative |

Aim for **10–20 comparisons per user** before drawing conclusions.
5 comparisons gives a directional signal but not a reliable rate.

---

## How It Fits

Compare Mode is the proof layer, not the benchmark layer.

- **Benchmark** (`run-benchmark`) — structured, blinded, stored, used for aggregate metrics across users
- **Compare** (`compare`) — fast, interactive, for rapid personal validation

Use Compare Mode first to confirm the profile is working for a specific user.
Use the benchmark for reproducible, aggregate evidence across users.

---

## Storage

Results are stored in the `comparison_results` table:

| Column | Description |
|--------|-------------|
| `user_id` | Who ran the comparison |
| `prompt` | The exact prompt used |
| `option_a_mode` / `option_b_mode` | Which mode was shown as A and B |
| `winner` | Your choice: `a`, `b`, `tie`, or `skip` |
| `preferred_mode` | Derived: `default`, `mneme`, or NULL for tie/skip |
| `created_at` | ISO timestamp |

**Run the migration on existing databases:**
```bash
sqlite3 mneme.db < migrate_add_comparison_results.sql
```
