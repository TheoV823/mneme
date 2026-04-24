"""
cli.py — Command-line interface for Mneme.

Subcommands
-----------
  add_decision    Append a new Decision to a project_memory.json file.
  list_decisions  Print every Decision in the memory file.
  test_query      Run a query through the retriever and show scores + injected.

Usage::

    mneme list_decisions --memory examples/project_memory.json
    mneme add_decision --memory examples/project_memory.json \\
        --id mneme_042 --decision "Use JSON" --scope storage \\
        --constraint "no postgres"
    mneme test_query --memory examples/project_memory.json \\
        --query "should I add postgres?"

All writes go directly to the JSON file. The Pipeline runtime is never
mutated — add_decision is a file operation only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mneme.context_builder import DEFAULT_MAX_DECISIONS, format_decisions
from mneme.decision_retriever import DecisionRetriever
from mneme.memory_store import MemoryStore


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Subcommand: list_decisions ───────────────────────────────────────────────

def _cmd_list(args: argparse.Namespace) -> int:
    store = MemoryStore(args.memory)
    store.load()
    decisions = store.decisions()
    if not decisions:
        print("(no decisions)")
        return 0
    for d in decisions:
        print(f"[{d.id}] {d.decision}")
        if d.scope:
            print(f"    scope: {', '.join(d.scope)}")
        if d.constraints:
            print(f"    constraints: {', '.join(d.constraints)}")
        if d.anti_patterns:
            print(f"    avoid: {', '.join(d.anti_patterns)}")
    return 0


# ── Subcommand: add_decision ─────────────────────────────────────────────────

def _cmd_add(args: argparse.Namespace) -> int:
    path = Path(args.memory)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("decisions", [])

    now = _utc_now()
    new_entry = {
        "id": args.id,
        "decision": args.decision,
        "rationale": args.rationale or "",
        "scope": list(args.scope or []),
        "constraints": list(args.constraint or []),
        "anti_patterns": list(args.anti_pattern or []),
        "created_at": now,
        "updated_at": now,
    }
    if any(d.get("id") == args.id for d in data["decisions"]):
        print(f"ERROR: decision id '{args.id}' already exists", flush=True)
        return 2

    data["decisions"].append(new_entry)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Added decision [{args.id}]")
    return 0


# ── Subcommand: test_query ───────────────────────────────────────────────────

def _cmd_test(args: argparse.Namespace) -> int:
    store = MemoryStore(args.memory)
    store.load()
    retriever = DecisionRetriever(store.decisions())
    scored = retriever.retrieve(args.query)

    print(f"Query: {args.query}")
    print()
    print("All decisions (ranked by score):")
    for s in scored:
        matched_fields = [f for f, n in s.matches.items() if n > 0]
        reason = ", ".join(matched_fields) if matched_fields else "(no match)"
        print(f"  [{s.decision.id}] score={s.score:.2f} matched={reason}")

    print()
    print(f"Injected (top {args.top}):")
    print(format_decisions(scored, max_items=args.top) or "(none)")
    return 0


# ── Entry point ──────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mneme")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list_decisions
    p_list = sub.add_parser("list_decisions", help="List all decisions")
    p_list.add_argument("--memory", required=True, help="Path to project_memory.json")
    p_list.set_defaults(func=_cmd_list)

    # add_decision
    p_add = sub.add_parser("add_decision", help="Append a new decision")
    p_add.add_argument("--memory", required=True)
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--decision", required=True)
    p_add.add_argument("--rationale", default="")
    p_add.add_argument("--scope", action="append", default=[])
    p_add.add_argument("--constraint", action="append", default=[])
    p_add.add_argument("--anti-pattern", dest="anti_pattern", action="append", default=[])
    p_add.set_defaults(func=_cmd_add)

    # test_query
    p_test = sub.add_parser("test_query", help="Run a query through the retriever")
    p_test.add_argument("--memory", required=True)
    p_test.add_argument("--query", required=True)
    p_test.add_argument("--top", type=int, default=DEFAULT_MAX_DECISIONS)
    p_test.set_defaults(func=_cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
