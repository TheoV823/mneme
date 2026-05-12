# tests/test_adr_import.py
"""Tests for the ADR import flow (graph projection, conflicts, persistence)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mneme.adr_import import DecisionNode, project_decision_graph
from mneme.adr_parser import parse_adr_directory

FIXTURES = Path(__file__).parent / "fixtures"


def test_project_decision_graph_returns_active_superseded_deprecated():
    adrs = parse_adr_directory(FIXTURES / "adrs_import_basic")
    nodes = project_decision_graph(adrs)
    by_id = {n.id: n for n in nodes}

    # ADR-101 is accepted and not superseded -> "active"
    assert by_id["ADR-101"].status == "active"
    assert by_id["ADR-101"].supersedes == []
    assert by_id["ADR-101"].superseded_by is None

    # ADR-102 is accepted and not superseded -> "active"
    assert by_id["ADR-102"].status == "active"

    # ADR-103 has status=superseded in its frontmatter -> "superseded"
    assert by_id["ADR-103"].status == "superseded"


def test_project_decision_graph_derives_superseded_by_from_supersedes():
    adrs = parse_adr_directory(FIXTURES / "adrs_e2e_clean")
    nodes = project_decision_graph(adrs)
    by_id = {n.id: n for n in nodes}

    # ADR-012 supersedes ADR-011 -> ADR-011.superseded_by == "ADR-012",
    # and ADR-011 status flips to "superseded" even though its frontmatter
    # says "accepted" (the active-set semantics dominate).
    assert by_id["ADR-011"].superseded_by == "ADR-012"
    assert by_id["ADR-011"].status == "superseded"
    assert by_id["ADR-012"].supersedes == ["ADR-011"]
    assert by_id["ADR-012"].status == "active"


def test_project_decision_graph_proposed_status_marked_inactive():
    """ADR-013 in adrs_e2e_clean is status=proposed -> not active."""
    adrs = parse_adr_directory(FIXTURES / "adrs_e2e_clean")
    nodes = project_decision_graph(adrs)
    by_id = {n.id: n for n in nodes}
    # We render proposed as "inactive" to keep the graph status enum to
    # exactly {active, superseded, deprecated, inactive}. The user's spec
    # named three; "inactive" carries the proposed/draft case.
    assert by_id["ADR-013"].status == "inactive"
