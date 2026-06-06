"""User model data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PreferenceStatus = Literal["candidate", "pending_review", "active", "rejected"]


@dataclass
class ExpressionProfile:
    preferred_language: str
    explanation_style: list[str]
    formatting_preferences: list[str]
    prompt_training_enabled: bool
    clarification_policy: str
    codex_prompt_preferences: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CognitiveProfile:
    thinking_models: list[str]
    decision_preferences: list[str]
    risk_preferences: list[str]
    evidence_requirements: list[str]
    interview_orientation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TemperamentPolicy:
    name: str
    rules: list[str]
    pause_conditions: list[str]
    high_risk_requires_review: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def requires_review(self, action: str, *, risk_level: str = "low") -> bool:
        if self.high_risk_requires_review and risk_level.lower() in {"high", "forbidden"}:
            return True
        lowered = action.lower()
        guarded_words = (
            "auto merge",
            "auto-merge",
            "deploy",
            "promote",
            "best_skill",
            "delete safety",
            "删除安全",
            "自动合并",
            "自动部署",
            "自动晋升",
        )
        return any(word in lowered for word in guarded_words)


@dataclass
class PreferenceCandidate:
    type: str
    rule: str
    evidence: str
    status: PreferenceStatus = "candidate"
    evidence_ref: str = ""
    confidence: float = 0.6
    requires_human_review: bool = False
    source_text_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
