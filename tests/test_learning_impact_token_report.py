"""tests/test_learning_impact_token_report.py — Token 报告测试。

验证 token_report 解析和 token_impact_score 计算。
"""

from __future__ import annotations

import pytest
from stable_agent.impact.builder import LearningImpactBuilder


class TestTokenImpact:
    """Token 影响测试。"""

    def test_high_saving_ratio(self):
        """高 saving_ratio 对应高 token_impact_score。"""
        token_report = {
            "baseline_tokens_estimated": 2000,
            "injected_tokens": 1000,
            "dropped_tokens": 1000,
            "saved_tokens_estimated": 1000,
            "saving_ratio": 0.5,
            "summary_zh": "节省 50% token",
            "is_estimated": True,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_tok_1", events=[], token_report=token_report)

        assert report.token_impact is not None
        assert report.token_impact.saving_ratio == pytest.approx(0.5, abs=0.01)
        assert report.token_impact_score == pytest.approx(0.5, abs=0.01)
        assert any("50%" in msg for msg in report.what_improved_zh)

    def test_zero_saving_ratio(self):
        """saving_ratio=0 时，token_impact_score=0。"""
        token_report = {
            "baseline_tokens_estimated": 100,
            "injected_tokens": 100,
            "dropped_tokens": 0,
            "saved_tokens_estimated": 0,
            "saving_ratio": 0.0,
            "summary_zh": "无节省",
            "is_estimated": True,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_tok_2", events=[], token_report=token_report)

        assert report.token_impact_score == 0.0

    def test_capped_at_0_8(self):
        """token_impact_score 最大为 0.8。"""
        token_report = {
            "baseline_tokens_estimated": 5000,
            "injected_tokens": 500,
            "dropped_tokens": 4500,
            "saved_tokens_estimated": 4500,
            "saving_ratio": 0.9,
            "summary_zh": "节省 90% token",
            "is_estimated": True,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_tok_3", events=[], token_report=token_report)

        assert report.token_impact_score == pytest.approx(0.8, abs=0.01)

    def test_is_estimated_flag_preserved(self):
        """is_estimated 标志被保留。"""
        token_report = {
            "baseline_tokens_estimated": 1000,
            "injected_tokens": 800,
            "dropped_tokens": 200,
            "saved_tokens_estimated": 200,
            "saving_ratio": 0.2,
            "summary_zh": "节省 20%",
            "is_estimated": False,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_tok_4", events=[], token_report=token_report)

        assert report.token_impact is not None
        assert report.token_impact.is_estimated is False

    def test_none_token_report(self):
        """token_report=None 时不报错。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_tok_5", events=[], token_report=None)

        assert report.token_impact is None
        assert report.token_impact_score == 0.0
