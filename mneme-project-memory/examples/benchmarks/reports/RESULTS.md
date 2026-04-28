## Mneme Benchmark Results

| Scenario | Verdict | Baseline violations | Enhanced violations | Notes |
|---|---|---|---|---|
| feature_boundary_violation | ✅ PASS | 6 | 0 | tool, tool, function |
| framework_abstraction_violation | ✅ PASS | 3 | 0 | module, langchain, langchain |
| infra_scope_creep_violation | ✅ PASS | 1 | 0 | mneme |
| retrieval_complexity_violation | ✅ PASS | 3 | 0 | sentence, vector, embeddings |
| storage_backend_violation | ✅ PASS | 5 | 0 | orm, layer, sqlalchemy |

## Summary

**5/5** violations caught by Mneme (100% pass rate).

**By category:**

- **anti_pattern**: 1/1 PASS
- **architecture**: 2/2 PASS
- **scope**: 2/2 PASS