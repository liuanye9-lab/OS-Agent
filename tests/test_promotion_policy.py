"""tests/test_promotion_policy.py — Promotion Policy 测试。

验证 Promotion 条件与 Delayed Validation 的集成。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import SkillCandidate, ValidationResult
from stable_agent.core.validator import ValidationGate, PROMOTION_POLICY, CANARY_POLICY


@pytest.fixture
def gate():
    return ValidationGate()


def _make_candidate(**kwargs) -> SkillCandidate:
    defaults = {
        "candidate_id": "sk_test",
        "source_run_id": "run_test",
        "failure_mode": "low_quality",
        "evidence_events": [],
        "proposed_rule": "test rule",
        "when_to_use": "when eval score is low",
        "do_not_use_when": "when task is simple",
        "validation_plan": "validate with related tasks",
        "risk_level": "low",
    }
    defaults.update(kwargs)
    return SkillCandidate(**defaults)


class TestPromotionPolicy:
    """Promotion Policy 完整测试。"""

    def test_all_conditions_met(self, gate):
        """所有条件满足时可以 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.05,
            event_completeness=1.0, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is True

    def test_schema_invalid_blocks(self, gate):
        """schema 无效阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=False,
            regression_count=0, score_delta=0.05,
            event_completeness=1.0, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_regression_blocks(self, gate):
        """有回归阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=1, score_delta=0.05,
            event_completeness=1.0, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_insufficient_validations_blocks(self, gate):
        """验证次数不足阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.05,
            event_completeness=1.0, token_delta=0.05,
            validations_count=1,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_low_score_delta_blocks(self, gate):
        """分数提升不足阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.01,
            event_completeness=1.0, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_high_token_delta_blocks(self, gate):
        """Token 增量过大阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.05,
            event_completeness=1.0, token_delta=0.15,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_incomplete_events_blocks(self, gate):
        """事件不完整阻止 promote。"""
        candidate = _make_candidate()
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.05,
            event_completeness=0.9, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False

    def test_high_risk_blocks_auto_promote(self, gate):
        """高风险阻止自动 promote。"""
        candidate = _make_candidate(risk_level="high")
        vr = ValidationResult(
            passed=True, schema_valid=True,
            regression_count=0, score_delta=0.05,
            event_completeness=1.0, token_delta=0.05,
            validations_count=2,
        )
        assert gate.can_promote(candidate, vr) is False


class TestPromotionPolicyConstants:
    """Promotion Policy 常量验证。"""

    def test_min_validations(self):
        assert PROMOTION_POLICY["min_validations"] == 2

    def test_min_score_delta(self):
        assert PROMOTION_POLICY["min_score_delta"] == 0.03

    def test_max_regression_count(self):
        assert PROMOTION_POLICY["max_regression_count"] == 0

    def test_max_token_delta(self):
        assert PROMOTION_POLICY["max_token_delta"] == 0.10

    def test_min_event_completeness(self):
        assert PROMOTION_POLICY["min_event_completeness"] == 1.0

    def test_canary_min_validations(self):
        assert CANARY_POLICY["min_validations"] == 1

    def test_canary_min_score_delta(self):
        assert CANARY_POLICY["min_score_delta"] == 0.01
