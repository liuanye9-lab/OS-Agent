"""stable_agent/core/os_agent_handler.py — OSAgentHandler (薄 handler 层)。

从 unified_tool_registry._h_task_os_agent 提取的编排逻辑。
只做参数转发 + 编排，不包含业务逻辑。

职责：
- MCP args → TaskSpec
- 调用 OSAgentExecutor.run()
- 调用 CuratorService (Phase 3)
- 调用 ContractBuilder
- 返回 StableAgentToolResult-compatible dict

不负责：
- 事件发布 (executor 内部)
- 评估 (executor 内部)
- RunStore 操作 (executor 内部)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from stable_agent.core.models import TaskSpec, RunTrace, ToolRunResult
from stable_agent.core.contracts import ContractBuilder
from stable_agent.core.curator import CuratorService
from stable_agent.core.validator import ValidationGate
from stable_agent.skills.repository import SkillRepository

logger = logging.getLogger(__name__)


class OSAgentHandler:
    """OS Agent 薄 handler。

    编排 Executor → Curator → ContractBuilder 的调用链。
    """

    def __init__(
        self,
        orchestrator: Any,
        tool_router: Any = None,
        skill_repo: SkillRepository | None = None,
    ):
        self._orchestrator = orchestrator
        self._tool_router = tool_router
        self._executor = None
        self._skill_repo = skill_repo or SkillRepository()
        self._curator = CuratorService(
            skill_repo=self._skill_repo,
            validator=ValidationGate(skill_repo=self._skill_repo),
        )

    def handle(self, ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
        """处理 stableagent.task.os_agent 请求。

        Args:
            ctx: RunContext 实例。
            args: MCP 工具参数。

        Returns:
            包含所有契约字段的字典，可直接传给 _make_result。
        """
        task = TaskSpec.from_args(args)

        # 1. 执行任务
        trace = self._run_executor(task, ctx)

        # 2. Curator 分析 + 候选生成 (Phase 3)
        curator_report = self._run_curator(trace, task)

        # 3. 构建契约结果
        result = ContractBuilder.build_tool_result(trace, open_dashboard=task.open_dashboard)
        data = ContractBuilder.to_dict(result)

        # 4. 注入 curator_report
        if curator_report:
            data["curator_report"] = curator_report

        # 5. 构建 Learning Impact Report (不影响主任务)
        impact_report = ContractBuilder.build_learning_impact(
            run_id=ctx.run_id,
            events=trace.events,
            token_report=trace.artifacts.get("token_report"),
            si_report=trace.si_report,
            curator_report=curator_report,
        )
        if impact_report:
            data["learning_impact_report"] = impact_report

        return {
            "ok": result.ok,
            "data": data,
            "plain_text": f"任务完成: {task.task_input[:80]}" if result.ok else "任务失败",
            "plain_text_zh": f"任务完成: {task.task_input[:80]}" if result.ok else "任务失败",
            "plain_text_en": f"Task completed: {task.task_input[:80]}" if result.ok else "Task failed",
            "dashboard_url": f"/runs/{ctx.run_id}" if task.open_dashboard else "",
            "is_error": not result.ok,
        }

    def _run_executor(self, task: TaskSpec, ctx: Any) -> RunTrace:
        """执行任务，返回 RunTrace。"""
        from stable_agent.core.executor import OSAgentExecutor

        if self._executor is None:
            self._executor = OSAgentExecutor(
                orchestrator=self._orchestrator,
                tool_router=self._tool_router,
            )
            self._executor._registry = self._tool_router

        loop = asyncio.new_event_loop()
        try:
            trace = loop.run_until_complete(self._executor.run(task, ctx))
        finally:
            loop.close()

        return trace

    def _run_curator(self, trace: RunTrace, task: TaskSpec) -> dict[str, Any] | None:
        """运行 Curator 分析和候选生成。

        规则：
        - eval_score < 0.75 才触发学习
        - force_eval_failed=true 必须触发学习
        - dashboard_replay_ok=false 必须触发学习
        - missing_required_events 非空必须触发学习
        - dry_run_learning=true 时只允许生成 candidate，不允许 promote
        """
        report: dict[str, Any] = {
            "learning_triggered": False,
            "candidates_proposed": 0,
            "candidates_validated": 0,
            "candidates_created": 0,
        }

        try:
            # 分析 trace
            analysis = self._curator.analyze_trace(trace)
            report["analysis"] = analysis

            if not analysis.get("is_learning_worthy"):
                return report

            # 生成候选
            candidates = self._curator.propose_candidates(trace)
            report["learning_triggered"] = True
            report["candidates_proposed"] = len(candidates)

            for candidate in candidates:
                # Schema 验证
                validator = self._curator._validator
                vr = validator.validate_schema(candidate)
                if not vr.schema_valid:
                    logger.info("Candidate %s failed schema validation: %s",
                                candidate.candidate_id, vr.reason)
                    continue

                report["candidates_validated"] += 1

                # 写入 .skills/candidates/
                try:
                    record = self._skill_repo.create_candidate(
                        skill_id=candidate.candidate_id,
                        proposed_rule=candidate.proposed_rule,
                        when_to_use=candidate.when_to_use,
                        do_not_use_when=candidate.do_not_use_when,
                        validation_plan=candidate.validation_plan,
                        domain=candidate.domain,
                        risk_level=candidate.risk_level,
                        source_run_id=candidate.source_run_id,
                    )
                    report["candidates_created"] += 1
                    logger.info("Created candidate skill: %s", record.skill_id)
                except Exception as exc:
                    logger.warning("Failed to create candidate skill: %s", exc)

                # dry_run_learning=true 时不允许 promote
                if task.dry_run_learning:
                    logger.info("dry_run_learning=true, skipping promote for %s",
                                candidate.candidate_id)
                    continue

                # 检查是否可以 promote (需要足够的验证)
                # 注意: promote 需要 delayed validation，不在单次 run 中完成
                # 这里只创建 candidate，promote 由 delayed validation 驱动

        except Exception as exc:
            logger.warning("Curator analysis failed: %s", exc)
            report["error"] = str(exc)

        return report
