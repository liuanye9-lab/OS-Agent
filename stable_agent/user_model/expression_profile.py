"""Default expression profile."""

from __future__ import annotations

from stable_agent.user_model.models import ExpressionProfile


def default_expression_profile() -> ExpressionProfile:
    """Return the default profile requested for the Recursive Harness."""
    return ExpressionProfile(
        preferred_language="zh-CN",
        explanation_style=["小白解释", "大白话", "不装懂", "不确定就说明"],
        formatting_preferences=["分阶段", "进度条", "验收标准", "先给结论再给证据"],
        prompt_training_enabled=True,
        clarification_policy="任务不清楚时反问三连；高风险先暂停并请求人审。",
        codex_prompt_preferences={
            "phase_plan_required": True,
            "progress_bar_required": True,
            "acceptance_criteria_required": True,
            "audit_before_refactor": True,
            "preserve_existing_contracts": True,
        },
    )
