"""Artifact storage for self-iteration proposals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: str | Path = ".self_iteration") -> None:
        self.root = Path(root)

    def write(self, kind: str, artifact_id: str, payload: dict[str, Any]) -> Path:
        folder_map = {
            "proposal": "proposals",
            "prompt": "pr_prompts",
            "report": "reports",
        }
        folder = self.root / folder_map.get(kind, "reports")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{artifact_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
