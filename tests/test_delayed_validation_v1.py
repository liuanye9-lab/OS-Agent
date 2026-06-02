"""tests/test_delayed_validation_v1.py — Delayed Validation v1 测试。

验证真实的 Delayed Validation 实现 (不再是 stub)。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import SkillCandidate, ValidationResult
from stable_agent.core.validator import ValidationGate


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


class TestDelayedValidationV1:
    """真实 Delayed Validation 测试。"""

    def test_no_related_tasks_returns_not_passed(self, gate):
        """没有 related tasks 时返回 passed=False。"""
        candidate = _make_candidate()
        result = gate.validate_delayed(candidate, related_tasks=None)
        assert result.passed is False
        assert result.validations_count == 0
        assert "no related tasks" in result.reason

    def test_empty_related_tasks_returns_not_passed(self, gate):
        """空 related tasks 列表返回 passed=False。"""
        candidate = _make_candidate()
        result = gate.validate_delayed(candidate, related_tasks=[])
        assert result.passed is False

    def test_with_related_tasks_passes(self, gate):
        """有足够 related tasks 且无回归时通过。"""
        candidate = _make_candidate()
        tasks = [
            {"task_input": "test task 1", "eval_score": 0.7, "domain": "coding"},
            {"task_input": "test task 2", "eval_score": 0.7, "domain": "coding"},
        ]
        result = gate.validate_delayed(candidate, related_tasks=tasks)
        assert result.schema_valid is True
        assert result.regression_count == 0
        assert result.score_delta > 0
        assert result.validations_count == 2

    def test_score_delta_positive(self, gate):
        """candidate 带来正向改进。"""
        candidate = _make_candidate()
        tasks = [{"task_input": "test", "eval_score": 0.7}]
        result = gate.validate_delayed(candidate, related_tasks=tasks)
        assert result.score_delta > 0

    def test_high_risk_conservative_improvement(self, gate):
        """高风险 candidate 改进更保守。"""
        low_risk = _make_candidate(risk_level="low")
        high_risk = _make_candidate(risk_level="high")
        tasks = [{"task_input": "test", "eval_score": 0.7}]

        result_low = gate.validate_delayed(low_risk, related_tasks=tasks)
        result_high = gate.validate_delayed(high_risk, related_tasks=tasks)

        assert result_low.score_delta > result_high.score_delta

    def test_schema_valid_always_true(self, gate):
        """Delayed validation 总是标记 schema_valid=True (schema 检查在 validate_schema 中)。"""
        candidate = _make_candidate()
        tasks = [{"task_input": "test", "eval_score": 0.7}]
        result = gate.validate_delayed(candidate, related_tasks=tasks)
        assert result.schema_valid is True

    def test_result_has_reason(self, gate):
        """结果必须有 reason。"""
        candidate = _make_candidate()
        tasks = [{"task_input": "test", "eval_score": 0.7}]
        result = gate.validate_delayed(candidate, related_tasks=tasks)
        assert result.reason
        assert "delayed validation" in result.reason
