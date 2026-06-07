"""Promotion policy for delayed validation."""

from __future__ import annotations

from dataclasses import dataclass

from stable_agent.validation.ab_runner import ValidationResult


@dataclass
class PromotionPolicy:
    min_validations: int = 2
    min_score_delta: float = 0.03
    max_token_delta: float = 0.10
    high_risk_requires_human_review: bool = True

    def can_promote(self, result: ValidationResult, *, human_review_approved: bool = False) -> bool:
        if result.validations < self.min_validations:
            return False
        if result.score_delta < self.min_score_delta:
            return False
        if result.regression_count != 0:
            return False
        if result.event_completeness < 1.0:
            return False
        if result.token_delta > self.max_token_delta:
            return False
        if self.high_risk_requires_human_review and not human_review_approved:
            return False
        return True
