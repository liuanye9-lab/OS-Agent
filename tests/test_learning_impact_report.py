"""tests/test_learning_impact_report.py — LearningImpactReport 核心测试。

验证：
- build() 正确生成报告
- 各维度分数计算正确
- to_dict() 序列化正确
- 报告不包含隐私原文
"""

from __future__ import annotations

import pytest
from stable_agent.impact.models import (
    LearningImpactReport,
    MemoryImpact,
    TokenImpact,
    SkillImpact,
)
from stable_agent.impact.builder import LearningImpactBuilder
from stable_agent.impact.scoring import ImpactScorer


class TestLearningImpactBuilder:
    """LearningImpactBuilder 核心测试。"""

    def test_build_with_memory_events(self):
        """有 memory hit 事件时，正确提取记忆命中。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": "mem_001", "reason_zh": "相关性匹配", "confidence": 0.8},
                    {"memory_id": "mem_002", "reason_zh": "时间戳匹配", "confidence": 0.6},
                ],
                "count": 2,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_test_1", events=events)

        assert report.run_id == "run_test_1"
        assert report.memory_impact_score == pytest.approx(0.4, abs=0.01)  # 2/5
        assert len(report.memory_hits) == 2
        assert report.memory_hits[0].memory_id == "mem_001"

    def test_build_with_token_report(self):
        """有 token_report 时，正确提取 token 节省。"""
        events = []
        token_report = {
            "baseline_tokens_estimated": 1000,
            "injected_tokens": 700,
            "dropped_tokens": 300,
            "saved_tokens_estimated": 300,
            "saving_ratio": 0.3,
            "summary_zh": "节省 30% token",
            "is_estimated": True,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_test_2", events=events, token_report=token_report)

        assert report.token_impact is not None
        assert report.token_impact.saved_tokens_estimated == 300
        assert report.token_impact.saving_ratio == pytest.approx(0.3, abs=0.01)
        assert report.token_impact_score == pytest.approx(0.3, abs=0.01)

    def test_build_with_si_report_candidates(self):
        """有 curator candidates 时，正确提取 skill 候选。"""
        events = []
        curator_report = {
            "learning_triggered": True,
            "candidates_created": 1,
            "candidates_proposed": 1,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_test_3", events=events, curator_report=curator_report)

        assert len(report.skill_candidates_created) == 1
        assert report.skill_candidates_created[0].generated_this_run is True
        assert report.skill_candidates_created[0].needs_validation is True
        assert report.skill_impact_score >= 0.4

    def test_to_dict_returns_all_fields(self):
        """to_dict() 返回所有必需字段。"""
        report = LearningImpactReport(run_id="run_test_4")
        d = report.to_dict()

        required_fields = [
            "run_id", "overall_impact_score", "memory_impact_score",
            "token_impact_score", "skill_impact_score", "personalization_score",
            "memory_hits", "token_impact", "skills_used", "skill_candidates_created",
            "what_improved_zh", "what_did_not_improve_zh",
            "next_learning_actions_zh", "user_visible_summary_zh",
        ]
        for field in required_fields:
            assert field in d, f"Missing field: {field}"

    def test_report_does_not_contain_task_input(self):
        """报告不包含完整 task_input 原文。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": "mem_001", "reason_zh": "匹配", "content_preview": "用户喜欢用 TypeScript"},
                ],
                "count": 1,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_test_5", events=events)
        d = report.to_dict()

        # content_preview 最多 80 字符，不包含完整输入
        import json
        serialized = json.dumps(d, ensure_ascii=False)
        # 不应包含完整 task_input（如果有）
        assert "task_input" not in serialized


class TestImpactScorer:
    """ImpactScorer 评分测试。"""

    def test_score_all_zeros(self):
        """所有维度为 0 时，综合分为 0。"""
        report = LearningImpactReport(run_id="run_score_1")
        scorer = ImpactScorer()
        scored = scorer.score(report)

        assert scored.overall_impact_score == 0.0
        assert len(scored.what_did_not_improve_zh) > 0  # 必须诚实解释

    def test_score_high_memory(self):
        """高记忆命中分时，综合分正确。"""
        report = LearningImpactReport(
            run_id="run_score_2",
            memory_impact_score=1.0,
            memory_hits=[MemoryImpact(memory_id="m1")],
        )
        scorer = ImpactScorer()
        scored = scorer.score(report)

        assert scored.overall_impact_score > 0.0

    def test_low_score_honesty(self):
        """低分报告必须诚实解释为什么体感弱。"""
        report = LearningImpactReport(run_id="run_score_3")
        scorer = ImpactScorer()
        scored = scorer.score(report)

        assert scored.overall_impact_score < 0.3
        assert any("提升较弱" in reason for reason in scored.what_did_not_improve_zh)

    def test_summary_generation(self):
        """评分后自动生成 user_visible_summary_zh。"""
        report = LearningImpactReport(run_id="run_score_4")
        scorer = ImpactScorer()
        scored = scorer.score(report)

        assert scored.user_visible_summary_zh != ""
        assert "学习提升" in scored.user_visible_summary_zh
