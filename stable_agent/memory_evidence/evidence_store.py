"""JSONL store for evidence-gated memory candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stable_agent.memory_evidence.models import MemoryCandidate


class EvidenceStore:
    def __init__(self, path: str | Path = ".stableagent/memory_evidence/candidates.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, candidate: MemoryCandidate) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")

    def list_candidates(self) -> list[MemoryCandidate]:
        if not self.path.exists():
            return []
        out: list[MemoryCandidate] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(MemoryCandidate(**json.loads(line)))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return out

    def latest(self) -> MemoryCandidate | None:
        items = self.list_candidates()
        return items[-1] if items else None

    def as_dict(self) -> dict[str, Any]:
        items = self.list_candidates()
        return {"path": str(self.path), "count": len(items), "items": [i.to_dict() for i in items]}
