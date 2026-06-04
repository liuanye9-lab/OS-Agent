"""tests/test_learning_impact_memory_hits.py — 记忆命中测试。

验证 memory 事件解析和 memory_impact_score 计算。
"""

from __future__ import annotations

import pytest
from stable_agent.impact.builder import LearningImpactBuilder
from stable_agent.impact.models import LearningImpactReport


class TestMemoryHits:
    """记忆命中测试。"""

    def test_five_memories_full_score(self):
        """5 条记忆命中时，memory_impact_score = 1.0。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": f"mem_{i}", "reason_zh": f"原因 {i}", "confidence": 0.8}
                    for i in range(5)
                ],
                "count": 5,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_mem_1", events=events)

        assert report.memory_impact_score == pytest.approx(1.0, abs=0.01)
        assert len(report.memory_hits) == 5

    def test_two_memories_partial_score(self):
        """2 条记忆命中时，memory_impact_score = 0.4。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": "mem_0", "reason_zh": "匹配", "confidence": 0.9},
                    {"memory_id": "mem_1", "reason_zh": "时间戳", "confidence": 0.7},
                ],
                "count": 2,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_mem_2", events=events)

        assert report.memory_impact_score == pytest.approx(0.4, abs=0.01)

    def test_content_preview_truncated(self):
        """content_preview 超过 80 字符时被截断。"""
        long_text = "A" * 200
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {"memory_id": "mem_0", "reason_zh": long_text, "confidence": 0.8},
                ],
                "count": 1,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_mem_3", events=events)

        assert len(report.memory_hits) == 1
        assert len(report.memory_hits[0].content_preview) <= 80
        assert report.memory_hits[0].content_preview.endswith("...")

    def test_no_memory_event(self):
        """没有 temporal_memory.retrieved 事件时，score=0。"""
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_mem_4", events=[])

        assert report.memory_impact_score == 0.0
        assert len(report.memory_hits) == 0

    def test_memory_preview_not_full_content(self):
        """记忆预览不包含完整内容，只展示预览。"""
        events = [
            {
                "event_type": "temporal_memory.retrieved",
                "selected_memories": [
                    {
                        "memory_id": "mem_secret",
                        "reason_zh": "用户的项目使用 Next.js + TypeScript，部署在 Vercel",
                        "confidence": 0.9,
                    },
                ],
                "count": 1,
            },
        ]
        builder = LearningImpactBuilder()
        report = builder.build(run_id="run_mem_5", events=events)

        # content_preview 最多 80 字符
        preview = report.memory_hits[0].content_preview
        assert len(preview) <= 80

    def test_memory_used_in_stage(self):
        """记忆命中的 used_in_stage 固定为 temporal_memory_retrieving。"""
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
        report = builder.build(run_id="run_mem_6", events=events)

        assert report.memory_hits[0].used_in_stage == "temporal_memory_retrieving"
