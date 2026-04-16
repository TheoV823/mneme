"""
app/api.py — Minimal FastAPI wrapper for the Mneme system.

Usage:
    uvicorn app.api:app --reload

Example (inline memory dict):
    curl -X POST http://localhost:8000/complete \
         -H "Content-Type: application/json" \
         -d '{
               "question": "How should I name variables?",
               "memory": {
                 "meta": {"name": "my-project", "description": "Example project"},
                 "items": [
                   {"id": "rule-001", "type": "rule", "title": "Use snake_case",
                    "content": "Always use snake_case for Python identifiers.",
                    "tags": ["naming"], "priority": "high"}
                 ],
                 "examples": []
               }
             }'

Example (path to JSON file):
    curl -X POST http://localhost:8000/complete \
         -H "Content-Type: application/json" \
         -d '{"question": "How should I name variables?",
              "memory": "mneme-project-memory/examples/project_memory.json"}'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mneme.context_builder import format_context_packet
from mneme.llm_adapter import LLMAdapter
from mneme.memory_store import MemoryStore
from mneme.retriever import Retriever
from mneme.schemas import (
    DecisionExample,
    MemoryItem,
    ProjectMeta,
    ProjectMemory,
)

app = FastAPI(title="Mneme API", version="0.1.0")


# ── Request / Response models ─────────────────────────────────────────────────

class CompleteRequest(BaseModel):
    question: str
    memory: Union[dict[str, Any], str]  # inline dict or path to JSON file


class ContextSummary(BaseModel):
    rules: int        # hard rules injected (type=rule)
    constraints: int  # soft constraints injected (preferences + anti-patterns)
    facts: int        # relevant facts / architecture decisions injected
    examples: int     # decision examples injected


class CompleteResponse(BaseModel):
    answer: str
    context_summary: ContextSummary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_memory(memory: dict | str) -> ProjectMemory:
    """Return a ProjectMemory from an inline dict or a JSON file path."""
    if isinstance(memory, str):
        path = Path(memory)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"Memory file not found: {memory}")
        return MemoryStore(path).load()

    raw_meta = memory.get("meta", {})
    return ProjectMemory(
        meta=ProjectMeta(
            name=raw_meta.get("name", ""),
            description=raw_meta.get("description", ""),
            version=raw_meta.get("version", "0.1.0"),
            owner=raw_meta.get("owner", ""),
            created=raw_meta.get("created", ""),
        ),
        items=[
            MemoryItem(
                id=item["id"],
                type=item["type"],
                title=item["title"],
                content=item["content"],
                tags=item.get("tags", []),
                priority=item.get("priority", "medium"),
            )
            for item in memory.get("items", [])
        ],
        examples=[
            DecisionExample(
                id=ex["id"],
                task=ex["task"],
                decision=ex["decision"],
                rationale=ex["rationale"],
                tags=ex.get("tags", []),
            )
            for ex in memory.get("examples", [])
        ],
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/complete", response_model=CompleteResponse)
def complete(req: CompleteRequest) -> CompleteResponse:
    project_memory = _load_memory(req.memory)

    packet = Retriever(project_memory).retrieve(req.question)
    system_context = format_context_packet(packet)
    response = LLMAdapter().complete(user=req.question, system=system_context)

    rules = [i for i in packet.hard_constraints if i.type == "rule"]
    constraints = [i for i in packet.hard_constraints if i.type == "anti_pattern"]

    return CompleteResponse(
        answer=response.content,
        context_summary=ContextSummary(
            rules=len(rules),
            constraints=len(constraints) + len(packet.preferred_patterns),
            facts=len(packet.relevant_facts),
            examples=len(packet.decision_examples),
        ),
    )
