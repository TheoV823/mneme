"""
integrations.detect — Read-only detection of supported agent environments.

M1.3 setup detects which supported agent/developer environments are present
in a repository (frozen contract section 4, M1.3a step 5). Detection is
purely observational:

- it never writes configuration;
- it never installs hooks;
- it never enables enforcement — detection and blocking behavior are
  independent concerns (acceptance gate G5).

``native`` marks surfaces Mneme can enforce in (hook/gate integrations);
``False`` marks advisory surfaces such as Cursor, where Mneme can only export
rules files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DetectedIntegration:
    """One agent/developer environment detected in a repository."""

    key: str
    label: str
    evidence: str
    native: bool


_INTEGRATION_MARKERS: tuple[tuple[str, str, str, bool], ...] = (
    # (key, label, project-relative evidence path, native enforcement surface)
    ("claude_code", "Claude Code", ".claude", True),
    ("codex_cli", "Codex CLI", ".codex", True),
    ("kiro", "Kiro", ".kiro", True),
    ("cursor", "Cursor", ".cursor", False),
)


def detect_integrations(root: str | Path) -> list[DetectedIntegration]:
    """Detect supported agent environments under ``root``.

    Returns matches in the fixed marker order above so output is
    deterministic. Directories are the detection evidence; existence checks
    only, no filesystem mutation.
    """
    base = Path(root)
    detected: list[DetectedIntegration] = []
    for key, label, evidence, native in _INTEGRATION_MARKERS:
        if (base / evidence).exists():
            detected.append(
                DetectedIntegration(
                    key=key, label=label, evidence=evidence, native=native
                )
            )
    return detected
