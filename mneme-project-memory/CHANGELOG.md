# Changelog

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
