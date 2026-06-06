"""Rejected edit buffer for bounded editor."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from stable_agent.skill_optimizer.edit_models import BoundedSkillEdit


class RejectedBuffer:
    def __init__(self, path: str | Path = ".skills/rejected_edits.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, edit: BoundedSkillEdit, reason: str) -> None:
        record = edit.to_dict()
        record["reason"] = reason
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def is_repeat(self, edit: BoundedSkillEdit) -> bool:
        text = f"{edit.operation}:{edit.target}:{edit.content[:200]}"
        for row in self.load():
            other = f"{row.get('operation')}:{row.get('target')}:{str(row.get('content', ''))[:200]}"
            if difflib.SequenceMatcher(None, text, other).ratio() >= 0.9:
                return True
        return False
