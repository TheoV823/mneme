## Mneme Benchmark Results

| Scenario | Verdict | Baseline | Enhanced | Recall@K | Precision@K | Irrelevant | Notes |
|---|---|---|---|---|---|---|---|
| feature_boundary_violation | PASS | 4 | 0 | 1.00 | 0.33 | yes | tool, function, multi |
| framework_abstraction_violation | PASS | 1 | 0 | 1.00 | 0.33 | yes | langchain |
| infra_scope_creep_violation | PASS | 4 | 0 | 1.00 | 0.33 | yes | agentic, tool, function |
| retrieval_complexity_violation | PASS | 3 | 0 | 1.00 | 0.33 | yes | sentence, vector, embeddings |
| storage_backend_violation | PASS | 5 | 0 | 1.00 | 0.33 | yes | sqlalchemy, alembic, psycopg2-binary |

## Summary

**Layer 2 (enforcement)** — 5/5 violations caught (100% pass rate).

**Layer 1 (retrieval, n=5)** — mean Recall@3 1.00, mean Precision@3 0.33, irrelevant injection rate 100%.

**By category:**

- **anti_pattern**: 1/1 PASS
- **architecture**: 2/2 PASS
- **scope**: 2/2 PASS