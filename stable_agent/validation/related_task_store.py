"""Related task store for delayed validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RelatedTaskStore:
    def __init__(self, path: str | Path = ".stableagent/validation/related_tasks.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, task_id: str, description: str, tags: list[str] | None = None) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"task_id": task_id, "description": description, "tags": tags or []}, ensure_ascii=False) + "\n")

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
