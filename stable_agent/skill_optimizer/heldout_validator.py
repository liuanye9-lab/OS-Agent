"""Held-out validation for candidate skill edits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class HeldoutValidationResult:
    passed: bool
    baseline_score: float
    candidate_score: float
    score_delta: float
    regression_count: int
    event_completeness: float
    reason_zh: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HeldoutValidator:
    def validate(
        self,
        *,
        baseline_score: float,
        candidate_score: float,
        regression_count: int = 0,
        event_completeness: float = 1.0,
    ) -> HeldoutValidationResult:
        delta = round(candidate_score - baseline_score, 4)
        passed = delta > 0 and regression_count == 0 and event_completeness >= 1.0
        reason = "候选 skill 在 held-out 验证中提升且无回归。" if passed else "候选 skill 没有证明稳定提升，因此拒绝。"
        return HeldoutValidationResult(
            passed=passed,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            score_delta=delta,
            regression_count=regression_count,
            event_completeness=event_completeness,
            reason_zh=reason,
        )

    def validate_result(self, result: dict[str, Any]) -> HeldoutValidationResult:
        return self.validate(
            baseline_score=float(result.get("baseline_score", 0.0)),
            candidate_score=float(result.get("candidate_score", 0.0)),
            regression_count=int(result.get("regression_count", 0)),
            event_completeness=float(result.get("event_completeness", 0.0)),
        )
