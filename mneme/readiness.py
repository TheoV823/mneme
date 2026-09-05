"""
readiness.py — Protection readiness view over project decisions.

M1.3 setup translates Audit/decision classifications into a readiness view
(frozen contract: docs/plans/m1-3-audit-to-setup-activation.md section 5):

    Protected          → existing protection detected
    Mneme-ready        → protection opportunity
    Requires modelling → needs modelling or remains guidance
    Guidance           → not appropriate for deterministic enforcement

Critical frozen rule:

    Installing Mneme does not make a Protectable decision Protected.

A decision is reported ``protected`` ONLY where actual mechanical protection
evidence exists — a typed FORBID_LITERAL rule — mirroring the frozen
Architecture Audit metric semantics (P1.2: Protected = deterministic intent
with verified existing enforcement). The governability tier ``enforceable``
also covers single-term anti-patterns; those remain ``mneme_ready`` here
because Mneme proposes that guardrail, it is not yet existing protection.

Setup never mutates decisions, so readiness is a pure view: running setup
cannot change any decision's classification and cannot inflate protection
metrics (acceptance gate G4).
"""

from __future__ import annotations

from typing import Literal

from mneme.enforcer import assess_governability
from mneme.schemas import Decision

ReadinessClass = Literal[
    "protected",
    "mneme_ready",
    "requires_modelling",
    "guidance",
]

READINESS_LABELS: dict[str, str] = {
    "protected": "Protected",
    "mneme_ready": "Mneme-ready",
    "requires_modelling": "Requires modelling",
    "guidance": "Guidance",
}

READINESS_ORDER: tuple[ReadinessClass, ...] = (
    "protected",
    "mneme_ready",
    "requires_modelling",
    "guidance",
)


def assess_readiness(decision: Decision) -> ReadinessClass:
    """Classify one decision's protection readiness.

    Uses Mneme's authoritative governability assessment (``assess_governability``)
    and maps it to the frozen readiness vocabulary without inflating it:

    - ``protected``          FORBID_LITERAL typed rules exist (verified
                             mechanical enforcement evidence).
    - ``mneme_ready``        No typed rule, but a concrete safe guardrail
                             exists (single-term anti-pattern).
    - ``requires_modelling`` Deterministic intent needs interpretation
                             (multi-term anti-patterns or "no X" constraints).
    - ``guidance``           No deterministic intent for enforcement.
    """
    a = assess_governability(decision)
    if a.has_literal_rules:
        return "protected"
    if a.has_single_term_anti_patterns:
        return "mneme_ready"
    if a.has_multi_term_anti_patterns or a.has_no_constraints:
        return "requires_modelling"
    return "guidance"


def readiness_counts(decisions: list[Decision]) -> dict[ReadinessClass, int]:
    """Count decisions per readiness class, returning all four keys."""
    counts: dict[ReadinessClass, int] = {key: 0 for key in READINESS_ORDER}
    for decision in decisions:
        counts[assess_readiness(decision)] += 1
    return counts
