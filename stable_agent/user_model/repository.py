"""Repository for reviewable user model profiles.

The files use a `.yaml` suffix because that is the public contract. The
payload is JSON, which is valid YAML 1.2 and keeps runtime dependencies at
stdlib-only for this layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from stable_agent.user_model.cognitive_profile import default_cognitive_profile
from stable_agent.user_model.expression_profile import default_expression_profile
from stable_agent.user_model.models import CognitiveProfile, ExpressionProfile, TemperamentPolicy
from stable_agent.user_model.temperament_policy import default_temperament_policy


class UserModelRepository:
    def __init__(self, root: str | Path = ".stableagent/user_model") -> None:
        self.root = Path(root)

    def initialize_defaults(self) -> dict[str, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        paths = {
            "expression_profile": self.root / "expression_profile.yaml",
            "cognitive_profile": self.root / "cognitive_profile.yaml",
            "temperament_policy": self.root / "temperament_policy.yaml",
        }
        self._write_if_missing(paths["expression_profile"], default_expression_profile().to_dict())
        self._write_if_missing(paths["cognitive_profile"], default_cognitive_profile().to_dict())
        self._write_if_missing(paths["temperament_policy"], default_temperament_policy().to_dict())
        return paths

    def load_expression_profile(self) -> ExpressionProfile:
        self.initialize_defaults()
        data = self._read_json_yaml(self.root / "expression_profile.yaml")
        return ExpressionProfile(**data)

    def load_cognitive_profile(self) -> CognitiveProfile:
        self.initialize_defaults()
        data = self._read_json_yaml(self.root / "cognitive_profile.yaml")
        return CognitiveProfile(**data)

    def load_temperament_policy(self) -> TemperamentPolicy:
        self.initialize_defaults()
        data = self._read_json_yaml(self.root / "temperament_policy.yaml")
        return TemperamentPolicy(**data)

    def save(self, filename: str, payload: Any) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / filename
        data = asdict(payload) if hasattr(payload, "__dataclass_fields__") else payload
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def profile_hits_for_task(self, task_input: str) -> list[dict[str, Any]]:
        self.initialize_defaults()
        lowered = task_input.lower()
        hits = [
            {"profile": "expression", "rule": "zh-CN", "why_zh": "默认中文优先表达。"},
            {"profile": "temperament", "rule": "audit_before_refactor", "why_zh": "任务涉及跨模块升级，先审计再实现。"},
        ]
        if "pytest" in lowered or "验收" in task_input:
            hits.append({"profile": "cognitive", "rule": "show_verification_evidence", "why_zh": "用户要求测试与验收证据。"})
        return hits

    def _write_if_missing(self, path: Path, data: dict[str, Any]) -> None:
        if path.exists():
            return
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json_yaml(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
