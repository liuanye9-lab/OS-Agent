"""stable_agent/core/contracts.py — ContractBuilder。

构建 stableagent.task.os_agent 的最终返回结果。
确保外部契约不变。

职责：
- 从 RunTrace 构建 ToolRunResult
- 确保所有必需字段存在
- 确保字段类型正确
"""

from __future__ import annotations

from typing import Any

from stable_agent.core.models import RunTrace, ToolRunResult
from stable_agent.impact.builder import LearningImpactBuilder


class ContractBuilder:
    """契约构建器。

    从 RunTrace 构建符合外部契约的 ToolRunResult。
    """

    @staticmethod
    def build_tool_result(
        trace: RunTrace,
        open_dashboard: bool = True,
    ) -> ToolRunResult:
        """从 RunTrace 构建 ToolRunResult。

        Args:
            trace: 运行轨迹。
            open_dashboard: 是否包含 dashboard URL。

        Returns:
            符合外部契约的 ToolRunResult。
        """
        artifacts = trace.artifacts or {}

        return ToolRunResult(
            ok=trace.ok,
            run_id=trace.run_id,
            dashboard_url=f"/runs/{trace.run_id}" if open_dashboard else "",
            observer_url=f"/observe/{trace.run_id}" if open_dashboard else "",
            event_sync_ok=artifacts.get("event_sync_ok", False),
            event_api_ok=artifacts.get("event_api_ok", False),
            dashboard_replay_ok=artifacts.get("dashboard_replay_ok", False),
            api_event_count=artifacts.get("api_event_count", 0),
            emitted_event_count=artifacts.get("emitted_event_count", 0),
            missing_required_events=artifacts.get("missing_required_events", []),
            api_missing_required_events=artifacts.get("api_missing_required_events", []),
            eval_passed=trace.eval_passed,
            eval_score=trace.eval_score,
            si_report=trace.si_report,
            progress_pct=100 if trace.ok else 0,
            current_stage=trace.status,
            understanding_trace=artifacts.get("understanding_trace"),
            token_report=artifacts.get("token_report"),
            dry_run_learning=artifacts.get("dry_run_learning", True),
            force_validation_passed=artifacts.get("force_validation_passed"),
            sync_errors=artifacts.get("sync_errors", []),
            task_type=artifacts.get("task_type", "unknown"),
            workflow_state=artifacts.get("workflow_state", "completed"),
        )

    @staticmethod
    def to_dict(result: ToolRunResult) -> dict[str, Any]:
        """将 ToolRunResult 转换为字典 (用于 StableAgentToolResult.data)。

        Args:
            result: 工具运行结果。

        Returns:
            字典格式的结果。
        """
        return {
            "run_id": result.run_id,
            "dashboard_url": result.dashboard_url,
            "observer_url": result.observer_url,
            "current_stage": result.current_stage,
            "progress_pct": result.progress_pct,
            "status_text_zh": "任务完成" if result.ok else "任务失败",
            "status_text_en": "Task completed" if result.ok else "Task failed",
            "avatar_state": "done" if result.ok else "error",
            "task_type": result.task_type,
            "workflow_state": result.workflow_state,
            "eval_score": result.eval_score,
            "eval_passed": result.eval_passed,
            "si_report": result.si_report,
            "mode": "auto",
            # 事件同步健康
            "emitted_event_count": result.emitted_event_count,
            "event_sync_ok": result.event_sync_ok,
            "sync_errors": result.sync_errors,
            "missing_required_events": result.missing_required_events,
            # RunStore 回读验证
            "event_api_ok": result.event_api_ok,
            "api_event_count": result.api_event_count,
            "api_missing_required_events": result.api_missing_required_events,
            "dashboard_replay_ok": result.dashboard_replay_ok,
            # 学习参数
            "dry_run_learning": result.dry_run_learning,
            "force_validation_passed": result.force_validation_passed,
            # V11 扩展
            "understanding_trace": result.understanding_trace,
            "token_report": result.token_report,
        }

    @staticmethod
    def build_learning_impact(
        run_id: str,
        events: list[dict[str, Any]],
        token_report: dict[str, Any] | None = None,
        si_report: dict[str, Any] | None = None,
        curator_report: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """构建 Learning Impact Report。

        构建失败不影响主任务，返回 None 或 error dict。

        Args:
            run_id: 运行标识。
            events: 本次运行事件列表。
            token_report: Token 预算报告。
            si_report: Self-Improvement 报告。
            curator_report: Curator 报告。

        Returns:
            LearningImpactReport 字典，或 None (构建失败时)。
        """
        try:
            builder = LearningImpactBuilder()
            report = builder.build(
                run_id=run_id,
                events=events,
                token_report=token_report,
                si_report=si_report,
                curator_report=curator_report,
            )
            return report.to_dict()
        except Exception as exc:
            return {"error": f"Learning Impact Report 构建失败: {exc}"}
