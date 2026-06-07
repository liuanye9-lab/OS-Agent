from stable_agent.validation.ab_runner import ValidationResult
from stable_agent.validation.promotion_policy import PromotionPolicy


def test_promotion_requires_human_review():
    result = ValidationResult(2, 0.04, 0.01, 0, 1.0, True, True, "ready_for_human_review", "ok")
    policy = PromotionPolicy()
    assert policy.can_promote(result, human_review_approved=False) is False
    assert policy.can_promote(result, human_review_approved=True) is True
