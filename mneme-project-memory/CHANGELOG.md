# Changelog

## v0.4.0 — 2026-05-04

**Architectural Compiler Foundation**

Compiles a versioned corpus of ADR markdown files into a deterministic
active constraint set. ADRs become the source of truth; the compiler is
the deterministic rule for turning them into the constraints the runtime
injects.

### Added

- `mneme/adr_schema.py` — `ADR` dataclass, `ADRStatus` /
  `ADRPriority` enums, `ADRParseError` / `ADRValidationError` /
  `ADRPrecedenceError`.
- `mneme/adr_parser.py` — `parse_adr_file`, `parse_adr_directory`. YAML
  frontmatter parser; structural failures only (missing /
  unterminated / malformed frontmatter).
- `mneme/adr_compiler.py` — three public stages plus an orchestrator
  and a Decision bridge:
  - `validate_corpus(adrs)` — aggregates required-field, enum, id /
    date / scope grammar, `supersedes` reference resolution, and
    cycle-detection errors into a single `ADRValidationError`.
  - `resolve_precedence(adrs)` — returns the active constraint set:
    status filter → explicit `supersedes` (chain-aware) → same-scope
    priority → newer date → `ADRPrecedenceError` if still ambiguous.
  - `compile_adrs(adr_dir)` — end-to-end: parse → validate →
    precedence; output ordered most-specific-first.
  - `adrs_to_decisions(adrs)` — bridge into the existing `Decision`
    schema so the runtime pipeline (`DecisionRetriever`,
    `ConflictDetector`, `ContextBuilder`) consumes ADR corpora
    without code changes.

### Tests

- 47 new tests across parser / validator / precedence / integration.
- Full suite: 217 passed, 2 skipped (same e2e skips as v0.3.2).
- Backwards compatible: `MemoryStore`, `Pipeline`, and the v0.3.x
  enforcement / Claude Code hook paths are unchanged.

### Deferred

- `mneme adr compile` CLI subcommand (library API is sufficient for v1).
- `Pipeline.from_adr_dir()` classmethod (callers can wire
  `adrs_to_decisions(compile_adrs(dir))` themselves).
- Structured `constraints:` / `anti_patterns:` frontmatter fields,
  hyphenated scope segments, multi-scope lists, body-section parsing.

## v0.3.2 — 2026-05-03

**Mneme for Claude Code (packaging)**

No engine changes. Shells out to existing `mneme check` v0.3.x.

### Added

- `mneme-hook` console script — Claude Code `PreToolUse` hook shim
  (`mneme/integrations/claude_code/hook.py`).
  - Reconstructs full post-edit file content before checking (Edit / Write / MultiEdit).
  - Discovers `.mneme/project_memory.json` by walking up from `cwd`; respects
    `MNEME_MEMORY` env override.
  - Fails open on all execution errors (binary missing, IO error, timeout).
  - `MNEME_HOOK_MODE=strict` (default) blocks on any non-zero verdict;
    `MNEME_HOOK_MODE=warn` never blocks.
- `integrations/claude-code/hooks.json` — hook config template.
- `integrations/claude-code/commands/` — four slash commands:
  `/mneme-check`, `/mneme-context`, `/mneme-record`, `/mneme-review`.
- `integrations/claude-code/skills/mneme/SKILL.md` — discovery skill.
- `scripts/install_claude_code.py` — idempotent installer; writes to
  `./.claude/` (project) or `~/.claude/` (`--user`).
- `docs/integrations/claude-code.md` — integration guide including retrieval
  behaviour, mode switching, and troubleshooting.

### Tests

- 21 new integration tests under `tests/integrations/claude_code/`.
- 2 end-to-end tests (skipped when `mneme` not on `$PATH`).
- Full suite: 170 passed, 2 skipped.
