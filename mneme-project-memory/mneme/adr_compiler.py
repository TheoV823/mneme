"""
adr_compiler.py — Validate, resolve precedence, and compile an ADR corpus.

The compiler is a deterministic three-stage pipeline:

    parse  ->  validate_corpus  ->  resolve_precedence  ->  active set

Each stage fails hard on bad input rather than silently dropping records.
``compile_adrs`` is the public entry point that runs all stages over a
directory of ADR markdown files.
"""

from __future__ import annotations

import re
from datetime import date as _date
from pathlib import Path

from mneme.adr_parser import parse_adr_directory
from mneme.adr_schema import (
    ADR,
    PRIORITY_RANK,
    VALID_PRIORITIES,
    VALID_STATUSES,
    ADRPrecedenceError,
    ADRValidationError,
)


# ── Validation ────────────────────────────────────────────────────────────────


_ID_PATTERN = re.compile(r"^ADR-\d+$")
_SCOPE_SEGMENT = re.compile(r"^[a-z0-9_]+$")
_REQUIRED_FIELDS: tuple[str, ...] = ("id", "title", "status", "priority", "date")


def validate_corpus(adrs: list[ADR]) -> None:
    """Validate an ADR corpus and raise ``ADRValidationError`` on any problem.

    Errors are aggregated: the raised exception lists every detected
    problem, not just the first. This is intentional — it lets a maintainer
    fix the corpus in one pass instead of rerunning the compiler per error.

    Args:
        adrs: List of parsed ADR records.

    Raises:
        ADRValidationError: If any record is missing required fields, uses
                            an invalid enum value, has a malformed id /
                            date / scope, or if the supersession graph is
                            broken (unknown refs, cycles).
    """
    errors: list[str] = []

    # Per-record field checks.
    for adr in adrs:
        errors.extend(_check_required_fields(adr))
        errors.extend(_check_enums(adr))
        errors.extend(_check_id_format(adr))
        errors.extend(_check_date(adr))
        errors.extend(_check_scope(adr))

    # Cross-record checks.
    errors.extend(_check_unique_ids(adrs))
    errors.extend(_check_supersedes_refs(adrs))
    errors.extend(_check_no_supersession_cycles(adrs))

    if errors:
        raise ADRValidationError(errors)


def _check_required_fields(adr: ADR) -> list[str]:
    out: list[str] = []
    for field_name in _REQUIRED_FIELDS:
        value = getattr(adr, field_name, None)
        # ``scope`` is allowed to be empty (= global). It is not in the
        # required list above; ``_check_scope`` validates its format.
        if value in (None, ""):
            out.append(
                f"{adr.source_path or adr.id or '<unknown>'}: "
                f"missing required field '{field_name}'"
            )
    return out


def _check_enums(adr: ADR) -> list[str]:
    out: list[str] = []
    if adr.status and adr.status not in VALID_STATUSES:
        out.append(
            f"{adr.id or adr.source_path}: invalid status {adr.status!r} "
            f"(expected one of {VALID_STATUSES})"
        )
    if adr.priority and adr.priority not in VALID_PRIORITIES:
        out.append(
            f"{adr.id or adr.source_path}: invalid priority {adr.priority!r} "
            f"(expected one of {VALID_PRIORITIES})"
        )
    return out


def _check_id_format(adr: ADR) -> list[str]:
    if adr.id and not _ID_PATTERN.match(adr.id):
        return [
            f"{adr.source_path or adr.id}: invalid id {adr.id!r} "
            f"(expected pattern 'ADR-<number>')"
        ]
    return []


def _check_date(adr: ADR) -> list[str]:
    if not adr.date:
        return []
    try:
        _date.fromisoformat(adr.date)
    except ValueError:
        return [
            f"{adr.id or adr.source_path}: invalid date {adr.date!r} "
            f"(expected ISO 8601 YYYY-MM-DD)"
        ]
    return []


def _check_scope(adr: ADR) -> list[str]:
    # Empty scope == global. Allowed.
    if adr.scope == "":
        return []
    if adr.scope.startswith(".") or adr.scope.endswith("."):
        return [
            f"{adr.id or adr.source_path}: invalid scope {adr.scope!r} "
            f"(no leading or trailing dot)"
        ]
    segments = adr.scope.split(".")
    for seg in segments:
        if not _SCOPE_SEGMENT.match(seg):
            return [
                f"{adr.id or adr.source_path}: invalid scope {adr.scope!r} "
                f"(segments must match [a-z0-9_]+, dot-separated)"
            ]
    return []


def _check_unique_ids(adrs: list[ADR]) -> list[str]:
    seen: dict[str, int] = {}
    for adr in adrs:
        if not adr.id:
            continue
        seen[adr.id] = seen.get(adr.id, 0) + 1
    return [f"duplicate ADR id {adr_id!r} ({n} occurrences)"
            for adr_id, n in seen.items() if n > 1]


def _check_supersedes_refs(adrs: list[ADR]) -> list[str]:
    known = {a.id for a in adrs if a.id}
    out: list[str] = []
    for adr in adrs:
        for ref in adr.supersedes:
            if ref not in known:
                out.append(
                    f"{adr.id}: supersedes references unknown ADR {ref!r}"
                )
    return out


def _check_no_supersession_cycles(adrs: list[ADR]) -> list[str]:
    """Detect cycles in the supersession graph using DFS.

    Self-supersession (A -> A) is treated as a cycle and reported.
    """
    graph: dict[str, list[str]] = {}
    for adr in adrs:
        if not adr.id:
            continue
        # Only follow refs that exist in the corpus; unknown refs are
        # already reported by ``_check_supersedes_refs`` and would
        # otherwise cause spurious cycle reports.
        graph[adr.id] = [r for r in adr.supersedes if any(a.id == r for a in adrs)]

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    cycles: list[list[str]] = []

    def dfs(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                # Cycle: from first occurrence of nxt in stack to end.
                start = stack.index(nxt)
                cycles.append(stack[start:] + [nxt])
            elif color.get(nxt, WHITE) == WHITE:
                dfs(nxt, stack)
        stack.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node, [])

    # Deduplicate cycles by their canonical form (sorted node tuple) so
    # the same cycle reached from different starts is reported once.
    seen: set[tuple[str, ...]] = set()
    out: list[str] = []
    for cyc in cycles:
        key = tuple(sorted(set(cyc)))
        if key in seen:
            continue
        seen.add(key)
        out.append("circular supersession detected: " + " -> ".join(cyc))
    return out


# ── Compile orchestrator (precedence to be added in milestone 3) ──────────────


def compile_adrs(adr_dir: str | Path) -> list[ADR]:
    """Parse, validate, and resolve precedence over a directory of ADRs.

    NOTE: precedence resolution is implemented in milestone 3. For now,
    this function performs parse + validate and returns the raw parsed
    list. The signature is stable so callers can adopt early.

    Args:
        adr_dir: Path to a directory containing ADR markdown files.

    Returns:
        Parsed (and, in milestone 3+, precedence-resolved) ADR records.

    Raises:
        ADRParseError:      If any file fails to parse.
        ADRValidationError: If the corpus fails schema validation.
    """
    adrs = parse_adr_directory(adr_dir)
    validate_corpus(adrs)
    return adrs


__all__ = [
    "validate_corpus",
    "compile_adrs",
    "ADRPrecedenceError",
]
