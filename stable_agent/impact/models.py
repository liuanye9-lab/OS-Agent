"""Learning Impact Report v2 model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LearningImpactReport:
    run_id: str
    overall_impact_score: float
    personalization_score: float
    memory_impact_score: float
    skill_impact_score: float
    token_impact_score: float
    evidence_score: float
    memory_hits: list[dict[str, Any]] = field(default_factory=list)
    skill_hits: list[dict[str, Any]] = field(default_factory=list)
    profile_hits: list[dict[str, Any]] = field(default_factory=list)
    candidate_created: list[dict[str, Any]] = field(default_factory=list)
    what_improved_zh: list[str] = field(default_factory=list)
    what_did_not_improve_zh: list[str] = field(default_factory=list)
    next_learning_actions_zh: list[str] = field(default_factory=list)
    user_visible_summary_zh: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
