"""tests/test_learning_impact_low_signal.py — 低信号场景测试。

验证当数据不足或没有提升时，报告诚实解释原因，不伪造提升。
"""

from __future__ import annotations

import pytest
from stable_agent.impact.builder import LearningImpactBuilder
from stable_agent.impact.scoring import ImpactScorer
from stable_agent.impact.models import LearningImpactReport


class TestLowSignalScenarios:
    """低信号场景测试。"""

    def test_no_events_at_all(self):
        """没有任何事件时，所有分数为 0。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_empty", events=[])

        assert report.memory_impact_score == 0.0
        assert report.token_impact_score == 0.0
        assert report.skill_impact_score == 0.0
        assert report.overall_impact_score == 0.0
        assert len(report.memory_hits) == 0

    def test_memory_event_with_zero_count(self):
        """memory 事件 count=0 时，不声称有记忆命中。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [],
                "count": 0,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_zero_mem", events=events)

        assert report.memory_impact_score == 0.0
        assert len(report.memory_hits) == 0
        assert any("没有命中历史记忆" in r for r in report.what_did_not_improve_zh)

    def test_empty_token_report(self):
        """token_report 为空时，不声称节省 token。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_no_token", events=[], token_report=None)

        assert report.token_impact_score == 0.0
        assert report.token_impact is None

    def test_si_report_no_learning(self):
        """si_report learning_triggered=False 时不声称触发学习。"""
        events = []
        si_report = {
            "learning_triggered": False,
            "skill_patches": [],
            "validation_passed": False,
            "human_review_required": False,
            "best_skill_exported": False,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_no_learn", events=events, si_report=si_report)

        assert report.skill_impact_score == 0.0
        assert len(report.skill_candidates_created) == 0

    def test_must_explain_when_overall_low(self):
        """综合分 < 0.3 时，必须解释为什么体感弱。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_low", events=[])

        assert report.overall_impact_score < 0.3
        assert len(report.what_did_not_improve_zh) > 0
        # 必须包含"提升较弱"相关解释
        combined = " ".join(report.what_did_not_improve_zh)
        assert "提升较弱" in combined or "没有命中" in combined or "未使用" in combined

    def test_no_fake_improvement_without_data(self):
        """没有数据时，what_improved_zh 应为空。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake", events=[])

        assert len(report.what_improved_zh) == 0
