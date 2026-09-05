"""
readiness.py — Protection readiness view for Mneme setup (M1.3a).

Setup translates the P1.2 Architecture Protection Audit classification into
a readiness view (frozen contract:
docs/plans/m1-3-audit-to-setup-activation.md section 5):

    Protected          → existing protection detected
    Mneme-ready        → protection opportunity
    Requires modelling → needs modelling or remains guidance
    Guidance           → not appropriate for deterministic enforcement

This module adds NO interpretation of its own. It delegates to the frozen
P1.2 semantics in ``mneme.enforcer`` — ``assess_protection`` /
``generate_protection_report`` are the single source of truth for the
Protected / Mneme-ready / Requires modelling / Guidance tiers, so setup and
``mneme audit`` always agree on the same memory/repository (parity is
pinned by tests). ``repo_root`` enables the same external CI evidence scan
the audit command performs with ``--repo-root``.

Critical frozen rule:

    Installing Mneme does not make a Protectable decision Protected.

Setup never mutates decisions, so readiness is a pure view: running setup
cannot change any decision's tier and cannot inflate protection metrics
(acceptance gate G4). Only ``active`` decisions count toward the summary,
exactly as in ``mneme audit``; superseded/deprecated decisions are reported
for provenance but never counted.
"""

from __future__ import annotations

from mneme.enforcer import (
    ProtectionTier,
    assess_protection,
    generate_protection_report,
)
from mneme.schemas import Decision

READINESS_LABELS: dict[str, str] = {
    "protected": "Protected",
    "mneme_ready": "Mneme-ready",
    "requires_modelling": "Requires modelling",
    "guidance": "Guidance",
}

READINESS_ORDER: tuple[ProtectionTier, ...] = (
    "protected",
    "mneme_ready",
    "requires_modelling",
    "guidance",
)


def assess_readiness(
    decision: Decision,
    repo_root: str | None = None,
) -> ProtectionTier:
    """Classify one decision's protection readiness via frozen P1.2 semantics."""
    return assess_protection(decision, repo_root=repo_root).protection_tier


def readiness_counts(
    decisions: list[Decision],
    repo_root: str | None = None,
) -> dict[ProtectionTier, int]:
    """Count decisions per P1.2 protection tier for the setup summary.

    Uses the canonical aggregate report so the counts are exactly the
    ``mneme audit`` summary values for the same corpus and repository:
    only active decisions count toward any tier (guidance excluded from the
    protection-relevant denominator by the frozen semantics).
    """
    report = generate_protection_report(decisions, repo_root=repo_root)
    return {
        "protected": report.protected,
        "mneme_ready": report.mneme_ready,
        "requires_modelling": report.requires_modelling,
        "guidance": report.guidance,
    }
