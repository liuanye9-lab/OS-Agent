"""Delayed validation A/B runner models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TaskRunScore:
    task_id: str
    eval_score: float
    tokens_used: int
    regression_count: int = 0
    event_completeness: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    validations: int
    score_delta: float
    token_delta: float
    regression_count: int
    event_completeness: float
    passed: bool
    requires_human_review: bool
    status: str
    reason_zh: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DelayedValidationABRunner:
    def compare(self, baseline: list[TaskRunScore], candidate: list[TaskRunScore]) -> ValidationResult:
        if not baseline or not candidate:
            return ValidationResult(0, 0.0, 0.0, 0, 0.0, False, True, "waiting_for_related_tasks", "缺少 related tasks，不能验证。")

        count = min(len(baseline), len(candidate))
        base_score = sum(x.eval_score for x in baseline[:count]) / count
        cand_score = sum(x.eval_score for x in candidate[:count]) / count
        base_tokens = max(1, sum(x.tokens_used for x in baseline[:count]) / count)
        cand_tokens = sum(x.tokens_used for x in candidate[:count]) / count
        regressions = sum(x.regression_count for x in candidate[:count])
        completeness = min(x.event_completeness for x in candidate[:count])

        score_delta = round(cand_score - base_score, 4)
        token_delta = round((cand_tokens - base_tokens) / base_tokens, 4)
        passed = (
            count >= 2
            and score_delta >= 0.03
            and regressions == 0
            and completeness >= 1.0
            and token_delta <= 0.10
        )
        status = "ready_for_human_review" if passed else "candidate"
        reason = "A/B 验证达到推广阈值，仍需人工审核。" if passed else "A/B 验证不足，candidate 不能 promote。"
        return ValidationResult(count, score_delta, token_delta, regressions, completeness, passed, True, status, reason)
