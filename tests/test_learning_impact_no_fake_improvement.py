"""tests/test_learning_impact_no_fake_improvement.py — 不伪造提升测试。

验证报告不会在没有数据时声称有提升。
这是最重要的诚信测试。
"""

from __future__ import annotations

import json

import pytest
from stable_agent.impact.builder import LearningImpactBuilder
from stable_agent.impact.models import LearningImpactReport
from stable_agent.core.contracts import ContractBuilder


class TestNoFakeImprovement:
    """不伪造提升测试。"""

    def test_no_data_no_improvement_claims(self):
        """没有任何数据时，what_improved_zh 必须为空。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_1", events=[])

        assert len(report.what_improved_zh) == 0, (
            f"不应该有提升声明，但发现: {report.what_improved_zh}"
        )

    def test_no_skill_usage_no_skill_claim(self):
        """没有 skill 使用时，不允许声称 skill 带来提升。"""
        events = []
        si_report = {
            "learning_triggered": False,
            "skill_patches": [],
            "validation_passed": False,
            "human_review_required": False,
            "best_skill_exported": False,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_2", events=events, si_report=si_report)

        assert report.skill_impact_score == 0.0
        assert len(report.skill_candidates_created) == 0

    def test_no_token_report_no_saving_claim(self):
        """token_report 缺失时，不允许声称节省 token。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_3", events=[], token_report=None)

        assert report.token_impact is None
        assert report.token_impact_score == 0.0
        assert not any("token" in msg.lower() or "token" in msg for msg in report.what_improved_zh)

    def test_candidate_needs_validation_shown(self):
        """有 candidate 但未验证时，必须显示"需要后续验证"。"""
        curator_report = {
            "learning_triggered": True,
            "candidates_created": 1,
        }
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_4", events=[], curator_report=curator_report)

        assert len(report.skill_candidates_created) == 1
        assert report.skill_candidates_created[0].needs_validation is True
        assert any("验证" in action for action in report.next_learning_actions_zh)

    def test_build_failure_does_not_affect_main_task(self):
        """learning_impact_report 构建失败不影响 os_agent 主任务。"""
        # 模拟构建失败的场景：传入会导致 builder 内部异常的数据
        # 使用 None 作为 events 会触发 TypeError
        result = ContractBuilder.build_learning_impact(
            run_id="run_nofake_5",
            events=None,  # type: ignore
        )
        # 应该返回 error dict 或有效报告，而不是抛异常
        assert result is not None
        assert isinstance(result, dict)
        # 如果是 error，包含 error 字段；如果成功处理，包含 run_id
        assert "error" in result or "run_id" in result

    def test_report_serialization_no_privacy_leak(self):
        """序列化后的报告不包含 task_input 原文。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {
                        "memory_id": "mem_0",
                        "reason_zh": "用户说'帮我写一个登录页面'",
                        "confidence": 0.8,
                    },
                ],
                "count": 1,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_6", events=events)
        serialized = json.dumps(report.to_dict(), ensure_ascii=False)

        # 不应包含 task_input 字段
        assert "task_input" not in serialized

    def test_low_overall_must_explain(self):
        """综合分 < 0.3 时，必须在 what_did_not_improve_zh 中解释原因。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_7", events=[])

        assert report.overall_impact_score < 0.3
        assert len(report.what_did_not_improve_zh) > 0
        # 必须有具体原因
        combined = " ".join(report.what_did_not_improve_zh)
        assert len(combined) > 10  # 不是空话

    def test_improved_and_not_improved_lists_separate(self):
        """what_improved_zh 和 what_did_not_improve_zh 不应重叠。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": "mem_0", "reason_zh": "匹配", "confidence": 0.8},
                ],
                "count": 1,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_nofake_8", events=events)

        improved_set = set(report.what_improved_zh)
        not_improved_set = set(report.what_did_not_improve_zh)
        overlap = improved_set & not_improved_set
        assert len(overlap) == 0, f"提升和未提升列表重叠: {overlap}"
