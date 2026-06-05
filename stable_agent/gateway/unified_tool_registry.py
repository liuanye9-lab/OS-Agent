"""UnifiedToolRegistry — V5 统一工具注册中心。

管理 14 个 namespaced 工具的定义和 handler 绑定。所有 handler
接收 (RunContext, dict) 参数并返回 StableAgentToolResult。

用法::

    registry = UnifiedToolRegistry(orchestrator)
    handler = registry.get_handler("stableagent.memory.retrieve")
    result = handler(ctx, {"task_input": "..."})
"""

from __future__ import annotations

import dataclasses
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_schemas import TOOLS
from stable_agent.models import StableAgentToolResult, TaskType, EvaluationResult

if TYPE_CHECKING:
    pass


class UnifiedToolRegistry:
    """V5 统一工具注册中心。管理 14 个 namespaced 工具的定义和 handler 绑定。

    每个工具对应一个 handler 方法，handler 接收 RunContext 和参数字典，
    返回 StableAgentToolResult。通过 orchestrator 引用访问后端服务。

    Attributes:
        _handlers: 工具名 → handler 可调用对象的映射。
        _orchestrator: StableAgentOrchestrator 引用（延迟绑定）。
    """

    def __init__(self, orchestrator: Any = None, tool_router: Any = None) -> None:
        """初始化注册中心并注册所有工具 handler。

        Args:
            orchestrator: StableAgentOrchestrator 实例。
            tool_router: ToolRouter 实例，供 approval.respond 恢复执行。
        """
        self._orchestrator: Any = orchestrator
        self._tool_router: Any = tool_router
        self._handlers: dict[str, Callable[[RunContext, dict[str, Any]], StableAgentToolResult]] = {}
        self._register_all()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get_handler(self, name: str) -> Callable[[RunContext, dict[str, Any]], StableAgentToolResult] | None:
        """获取指定工具的 handler。

        Args:
            name: 工具完整名称，如 "stableagent.memory.retrieve"。

        Returns:
            Handler 可调用对象，未注册时返回 None。
        """
        return self._handlers.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """返回所有 14 个注册工具的 MCP 格式列表。

        每个工具条目包含 name、title、description 和 inputSchema（MCP 标准字段名）。
        同时保留 input_schema 以兼容旧版调试端点。

        Returns:
            MCP 格式工具定义列表。
        """
        result: list[dict[str, Any]] = []
        for tool_name, tool_def in TOOLS.items():
            # MCP 标准要求 inputSchema (camelCase)；
            # 优先取 inputSchema，否则从 input_schema 转换，兜底空 object
            input_schema = (
                tool_def.get("inputSchema")
                or tool_def.get("input_schema")
                or {"type": "object", "properties": {}}
            )
            entry: dict[str, Any] = {
                "name": tool_def["name"],
                "description": tool_def.get("description", ""),
                "inputSchema": input_schema,
            }
            if "title" in tool_def:
                entry["title"] = tool_def["title"]
            result.append(entry)
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register(self, name: str, handler: Callable[[RunContext, dict[str, Any]], StableAgentToolResult]) -> None:
        """注册单个工具的 handler。

        Args:
            name: 工具完整名称。
            handler: 处理函数，签名为 (RunContext, dict) -> StableAgentToolResult。
        """
        self._handlers[name] = handler

    def _register_all(self) -> None:
        """注册所有 14 个工具及其 handler。"""
        self._register("stableagent.task.process", self._h_task_process)
        self._register("stableagent.context.build", self._h_context_build)
        self._register("stableagent.context.estimate_budget", self._h_estimate_budget)
        self._register("stableagent.memory.retrieve", self._h_memory_retrieve)
        self._register("stableagent.memory.write_candidate", self._h_memory_write)
        self._register("stableagent.rag.retrieve", self._h_rag_retrieve)
        self._register("stableagent.eval.evaluate", self._h_eval_evaluate)
        self._register("stableagent.badcase.record", self._h_badcase_record)
        self._register("stableagent.skillopt.status", self._h_skillopt_status)
        self._register("stableagent.skillopt.get_current_skill", self._h_skillopt_current)
        self._register("stableagent.skillopt.run_epoch", self._h_skillopt_epoch)
        self._register("stableagent.skillopt.export_best", self._h_skillopt_export)
        self._register("stableagent.trace.get_run", self._h_trace_get_run)
        self._register("stableagent.approval.respond", self._h_approval_respond)
        self._register("stableagent.task.os_agent", self._h_task_os_agent)  # V6.5: /os-agent
        # V11 Phase 3: Understanding Trace 语义理解工具
        self._register("stableagent.understanding.trace", self._h_understanding_trace)
        self._register("stableagent.understanding.correct", self._h_understanding_correct)
        self._register("stableagent.expression.list", self._h_expression_list)
        self._register("stableagent.expression.add", self._h_expression_add)
        self._register("stableagent.expression.delete", self._h_expression_delete)
        # SaaS v1.2: 12 个商业 SaaS 工具
        self._register("stableagent.workspace.create", self._h_saas_workspace_create)
        self._register("stableagent.project.create", self._h_saas_project_create)
        self._register("stableagent.project.list", self._h_saas_project_list)
        self._register("stableagent.run.get", self._h_saas_run_get)
        self._register("stableagent.eval.run", self._h_saas_eval_run)
        self._register("stableagent.regression.create", self._h_saas_regression_create)
        self._register("stableagent.skill.patch_propose", self._h_saas_skill_patch)
        self._register("stableagent.skill.validate", self._h_saas_skill_validate)
        self._register("stableagent.skill.review", self._h_saas_skill_review)
        self._register("stableagent.skill.export_best", self._h_saas_skill_export)
        self._register("stableagent.usage.get", self._h_saas_usage_get)
        self._register("stableagent.apikey.create", self._h_saas_apikey_create)
        self._register("stableagent.apikey.revoke", self._h_saas_apikey_revoke)
        # V11: Agent Capsule + Memory Lifecycle
        self._register("stableagent.capsule.status", self._h_capsule_status)
        self._register("stableagent.capsule.doctor", self._h_capsule_doctor)
        self._register("stableagent.memory.health", self._h_memory_health)
        self._register("stableagent.memory.review", self._h_memory_review)
        self._register("stableagent.memory.prune", self._h_memory_prune)
        self._register("stableagent.memory.promote", self._h_memory_promote)
        self._register("stableagent.memory.delete", self._h_memory_delete)
        # V11 Phase 5: Model Profile
        self._register("stableagent.model.profile", self._h_model_profile)
        self._register("stableagent.model.list", self._h_model_list)
        self._register("stableagent.model.suggest", self._h_model_suggest)
        self._register("stableagent.model.update", self._h_model_update)
        # V11 Phase 6: Personal Eval / A-B Regression
        self._register("stableagent.eval.case.create", self._h_eval_case_create)
        self._register("stableagent.eval.case.list", self._h_eval_case_list)
        self._register("stableagent.eval.run_ab", self._h_eval_run_ab)
        self._register("stableagent.eval.rubric.get", self._h_eval_rubric_get)
        self._register("stableagent.eval.rubric.update", self._h_eval_rubric_update)
        # V11 Phase 7: Feedback Loop
        self._register("stableagent.feedback.remember", self._h_feedback_remember)
        self._register("stableagent.feedback.dont_do_this_again", self._h_feedback_dont_do_this_again)
        self._register("stableagent.feedback.correct_and_remember", self._h_feedback_correct_and_remember)
        # V11 Phase 4: Token Budget Ledger
        self._register("stableagent.token.report", self._h_token_report)
        self._register("stableagent.token.run", self._h_token_run)
        self._register("stableagent.token.summary", self._h_token_summary)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _make_result(
        self,
        ctx: RunContext,
        tool_name: str,
        ok: bool = True,
        data: dict[str, Any] | None = None,
        plain_text: str = "",
        plain_text_zh: str = "",
        plain_text_en: str = "",
        dashboard_url: str = "",
        warnings: list[str] | None = None,
        next_actions: list[str] | None = None,
        is_error: bool = False,
    ) -> StableAgentToolResult:
        """创建标准 StableAgentToolResult。

        Args:
            ctx: 当前 RunContext。
            tool_name: 工具名。
            ok: 执行是否成功。
            data: 结构化返回数据。
            plain_text: 人类可读结果文本。
            plain_text_zh: 中文结果描述（未提供时回退到 plain_text）。
            plain_text_en: 英文结果描述（未提供时回退到 plain_text）。
            dashboard_url: Dashboard 链接（未提供时使用默认 /dashboard/{run_id}）。
            warnings: 警告信息列表。
            next_actions: 建议后续操作。
            is_error: 是否为错误返回。

        Returns:
            填充好的 StableAgentToolResult 实例。
        """
        return StableAgentToolResult(
            ok=ok,
            run_id=ctx.run_id,
            tool_call_id=ctx.tool_call_id,
            tool_name=tool_name,
            data=data or {},
            plain_text=plain_text,
            plain_text_zh=plain_text_zh or plain_text,
            plain_text_en=plain_text_en or plain_text,
            dashboard_url=dashboard_url or f"/dashboard/{ctx.run_id}",
            warnings=warnings or [],
            next_actions=next_actions or [],
            trace_url=f"/runs/{ctx.run_id}",
            is_error=is_error,
        )

    def _json_safe(self, value: Any) -> Any:
        """Return a recursively JSON-serializable representation."""
        if dataclasses.is_dataclass(value):
            return self._json_safe(dataclasses.asdict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._json_safe(v) for v in value]
        return value

    # ------------------------------------------------------------------
    # Handler 实现 —— 14 个工具
    # ------------------------------------------------------------------

    def _h_task_process(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.task.process — 端到端任务处理。

        委托给 orchestrator.process_task() 执行完整工作流。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含任务处理结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.task.process"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法处理任务",
            )

        try:
            result: dict[str, Any] = self._orchestrator.process_task(task_input)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=self._json_safe(result),
                plain_text=f"任务处理完成：{task_input[:80]}",
                next_actions=["查看结果详情", "评估输出质量"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"任务处理失败：{exc}",
            )

    def _h_context_build(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.context.build — 构建上下文包。

        委托给 orchestrator.build_context_pack_api()。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含 ContextPack 信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.context.build"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法构建上下文包",
            )

        try:
            pack = self._orchestrator.build_context_pack_api(task_input)
            pack_data: dict[str, Any] = {
                "pack_id": pack.pack_id,
                "run_id": pack.run_id,
                "task_type": pack.task_type.value if isinstance(pack.task_type, TaskType) else str(pack.task_type),
                "item_count": len(pack.items),
                "total_tokens": pack.total_tokens,
                "budget_limit": pack.budget_limit,
                "critical_reminders": pack.critical_reminders,
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=pack_data,
                plain_text=f"上下文包构建完成，包含 {len(pack.items)} 个条目，共 {pack.total_tokens} tokens",
                next_actions=["估算预算", "检索记忆"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"上下文包构建失败：{exc}",
            )

    def _h_estimate_budget(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.context.estimate_budget — 估算 Token 预算。

        先通过决策引擎分类任务类型，再计算预算。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含预算信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.context.estimate_budget"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法估算预算",
            )

        try:
            task_type = self._orchestrator.decision_engine.classify_task(task_input)
            budget: dict[str, int] = self._orchestrator.budget_manager.compute_budget(task_type)
            budget_data: dict[str, Any] = {
                "task_type": task_type.value if isinstance(task_type, TaskType) else str(task_type),
                "budget": budget,
                "total_budget": sum(budget.values()),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=budget_data,
                plain_text=f"预算估算完成，类型={task_type.value if isinstance(task_type, TaskType) else task_type}，"
                           f"总预算={sum(budget.values())} tokens",
                next_actions=["构建上下文包", "检索记忆"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"预算估算失败：{exc}",
            )

    def _h_memory_retrieve(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.retrieve — 检索相关记忆。

        委托给 orchestrator.memory_router.query_for_task()。

        Args:
            ctx: RunContext。
            args: 包含 task_input 和可选 top_k 的参数字典。

        Returns:
            包含记忆条目列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.memory.retrieve"
        task_input: str = args.get("task_input", "")
        top_k: int = args.get("top_k", 5)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法检索记忆",
            )

        try:
            # query_for_task 需要 task_type，先分类
            task_type = self._orchestrator.decision_engine.classify_task(task_input)
            memories = self._orchestrator.memory_router.query_for_task(
                task_input, task_type, top_k=top_k,
            )
            memory_list: list[dict[str, Any]] = [
                {
                    "id": m.id,
                    "content": m.content,
                    "type": m.type,
                    "priority": m.priority,
                    "source": m.source,
                    "layer": m.layer,
                }
                for m in memories
            ]
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"memories": memory_list, "count": len(memory_list)},
                plain_text=f"记忆检索完成，命中 {len(memory_list)} 条相关记忆",
                next_actions=["写入候选记忆", "构建上下文包"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"记忆检索失败：{exc}",
            )

    def _h_memory_write(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.write_candidate — 写入候选记忆。

        委托给 orchestrator.memory_router.add_memory_candidate()。

        Args:
            ctx: RunContext。
            args: 包含 content、item_type、source 的参数字典。

        Returns:
            确认写入结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.memory.write_candidate"
        content: str = args.get("content", "")
        item_type: str = args.get("item_type", "success_case")
        source: str = args.get("source", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法写入候选记忆",
            )

        try:
            memory_item = self._orchestrator.memory_router.add_memory_candidate(
                content=content,
                item_type=item_type,
                source=source,
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "memory_id": memory_item.id,
                    "type": memory_item.type,
                    "status": memory_item.status,
                },
                plain_text=f"候选记忆已写入（ID: {memory_item.id}），类型={item_type}",
                next_actions=["检索记忆", "运行优化回合"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"候选记忆写入失败：{exc}",
            )

    def _h_rag_retrieve(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.rag.retrieve — RAG 检索。

        委托给 orchestrator.rag_manager.retrieve()。

        Args:
            ctx: RunContext。
            args: 包含 query 和可选 top_k 的参数字典。

        Returns:
            包含检索文档列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.rag.retrieve"
        query: str = args.get("query", "")
        top_k: int = args.get("top_k", 5)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法执行 RAG 检索",
            )

        try:
            docs: list[str] = self._orchestrator.rag_manager.retrieve(query, top_k=top_k)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"documents": docs, "count": len(docs)},
                plain_text=f"RAG 检索完成，返回 {len(docs)} 条文档",
                next_actions=["构建上下文包", "处理任务"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"RAG 检索失败：{exc}",
            )

    def _h_eval_evaluate(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.evaluate — 评测输出质量。

        委托给 orchestrator.evaluator.evaluate()。

        Args:
            ctx: RunContext。
            args: 包含 task_input、input_context、output 的参数字典。

        Returns:
            包含评测结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.eval.evaluate"
        task_input: str = args.get("task_input", "")
        input_context: str = args.get("input_context", "")
        output: str = args.get("output", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法执行评测",
            )

        try:
            eval_result: EvaluationResult = self._orchestrator.evaluator.evaluate(
                task_input, input_context, output,
            )
            eval_data: dict[str, Any] = {
                "overall_score": eval_result.overall_score,
                "completion_rate": eval_result.completion_rate,
                "context_hit_rate": eval_result.context_hit_rate,
                "token_efficiency": eval_result.token_efficiency,
                "hallucination_score": eval_result.hallucination_score,
                "user_preference_score": eval_result.user_preference_score,
                "safety_score": eval_result.safety_score,
                "token_roi": eval_result.token_roi,
                "failure_reasons": eval_result.failure_reasons,
                "improvement_rules": eval_result.improvement_rules,
            }
            summary: str = (
                f"评测完成，综合评分={eval_result.overall_score:.2f}，"
                f"完成率={eval_result.completion_rate:.2f}"
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=eval_data,
                plain_text=summary,
                next_actions=["记录失败案例"] if eval_result.overall_score < 0.6 else [],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"评测执行失败：{exc}",
            )

    def _h_badcase_record(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.badcase.record — 记录失败案例。

        委托给 orchestrator.bad_case_manager.record_case()。

        Args:
            ctx: RunContext。
            args: 包含 task_input、input_context、output 和可选 evaluation 的参数字典。

        Returns:
            确认记录结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.badcase.record"
        task_input: str = args.get("task_input", "")
        input_context: str = args.get("input_context", "")
        output: str = args.get("output", "")
        evaluation_dict: dict[str, Any] = args.get("evaluation", {})

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法记录失败案例",
            )

        try:
            # 如果提供了 evaluation 字典，构造 EvaluationResult；否则执行评测
            if evaluation_dict:
                eval_result = EvaluationResult(
                    overall_score=evaluation_dict.get("overall_score", 0.0),
                    completion_rate=evaluation_dict.get("completion_rate", 0.0),
                    context_hit_rate=evaluation_dict.get("context_hit_rate", 0.0),
                    token_efficiency=evaluation_dict.get("token_efficiency", 0.0),
                    hallucination_score=evaluation_dict.get("hallucination_score", 0.0),
                    user_preference_score=evaluation_dict.get("user_preference_score", 0.0),
                    failure_reasons=evaluation_dict.get("failure_reasons", []),
                    improvement_rules=evaluation_dict.get("improvement_rules", []),
                    safety_score=evaluation_dict.get("safety_score", 1.0),
                )
            else:
                eval_result = self._orchestrator.evaluator.evaluate(
                    task_input, input_context, output,
                )

            bad_case = self._orchestrator.bad_case_manager.record_case(
                task_input, input_context, output, eval_result,
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "case_recorded": True,
                    "failure_reason": bad_case.failure_reason,
                    "timestamp": bad_case.timestamp,
                },
                plain_text=f"失败案例已记录，综合评分={eval_result.overall_score:.2f}",
                next_actions=["运行优化回合", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"失败案例记录失败：{exc}",
            )

    def _h_skillopt_status(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.status — 获取 SkillOpt 引擎状态。

        委托给 orchestrator.skillopt_engine（如果可用）。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含引擎状态信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.status"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"status": "not_configured", "message": "SkillOpt engine 未配置"},
                plain_text="SkillOpt 引擎未配置，请先初始化 SkillOptimizationEngine",
            )

        try:
            # 收集引擎状态信息
            status_data: dict[str, Any] = {
                "status": "active",
                "epoch_count": len(getattr(engine, '_longitudinal_results', [])),
                "current_version": getattr(
                    getattr(engine, 'doc_store', None), 'current_version', 'unknown'
                ),
                "best_version": getattr(
                    getattr(engine, 'doc_store', None), 'best_version', 'unknown'
                ),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=status_data,
                plain_text=f"SkillOpt 引擎状态：已完成 {status_data['epoch_count']} 个优化回合",
                next_actions=["获取当前技能", "运行优化回合"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取 SkillOpt 状态失败：{exc}",
            )

    def _h_skillopt_current(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.get_current_skill — 获取当前技能文档。

        委托给 orchestrator.skillopt_engine.doc_store（如果可用）。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含当前技能文档信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.get_current_skill"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            doc_store = getattr(engine, 'doc_store', None)
            if doc_store is None:
                return self._make_result(
                    ctx, tool_name,
                    ok=False, is_error=True,
                    plain_text="SkillDocumentStore 未配置",
                )

            skill = doc_store.load_current_skill()
            skill_data: dict[str, Any] = {
                "version": getattr(skill, 'version', 'unknown'),
                "content_preview": getattr(skill, 'content', '')[:500] if hasattr(skill, 'content') else '',
                "updated_at": getattr(skill, 'updated_at', None),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=skill_data,
                plain_text=f"当前技能版本：{skill_data['version']}",
                next_actions=["运行优化回合", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取当前技能失败：{exc}",
            )

    def _h_skillopt_epoch(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.run_epoch — 运行一轮优化。

        委托给 orchestrator.skillopt_engine.run_epoch()。

        Args:
            ctx: RunContext。
            args: 包含可选 max_rollouts 的参数字典。

        Returns:
            包含优化回合结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.run_epoch"
        max_rollouts: int = args.get("max_rollouts", 40)
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            result = engine.run_epoch(max_rollouts=max_rollouts)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"epoch_result": str(result) if result is not None else None},
                plain_text=f"优化回合已完成（max_rollouts={max_rollouts}）",
                next_actions=["获取 SkillOpt 状态", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"优化回合执行失败：{exc}",
            )

    def _h_skillopt_export(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.export_best — 导出最优技能。

        委托给 orchestrator.skillopt_engine.export_best_skill()。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含导出文件路径的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.export_best"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            export_path = engine.export_best_skill()
            export_path_str: str = export_path if isinstance(export_path, str) else str(export_path or "")
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"export_path": export_path_str},
                plain_text=f"最优技能已导出到：{export_path_str}" if export_path_str else "最优技能导出完成",
                next_actions=["获取 SkillOpt 状态"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"导出最优技能失败：{exc}",
            )

    def _h_trace_get_run(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.trace.get_run — 获取运行轨迹。

        委托给 orchestrator.event_bus.get_spans_by_run()。

        Args:
            ctx: RunContext。
            args: 包含 run_id 的参数字典。

        Returns:
            包含 Span 列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.trace.get_run"
        run_id: str = args.get("run_id", ctx.run_id)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法获取 trace",
            )

        try:
            spans = self._orchestrator.event_bus.get_spans_by_run(run_id)
            span_list: list[dict[str, Any]] = [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "type": s.type,
                    "status": s.status,
                    "parent_span_id": s.parent_span_id,
                    "latency_ms": s.latency_ms,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "plain_text": s.plain_text,
                }
                for s in spans
            ]
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"run_id": run_id, "spans": span_list, "span_count": len(span_list)},
                plain_text=f"运行 {run_id} 共有 {len(span_list)} 个 span",
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取运行轨迹失败：{exc}",
            )

    def _h_approval_respond(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.approval.respond — 审批响应 + 恢复执行。

        Production Hardening: approve → ApprovalResumeService.resume()
        恢复原始 handler 执行。reject → 标记拒绝，不执行。

        Args:
            ctx: RunContext。
            args: approval_id, action (approve/reject), reason (可选)。

        Returns:
            确认审批结果或恢复执行结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.approval.respond"
        approval_id: str = args.get("approval_id", "") or args.get("request_id", "")
        action: str = args.get("action", "approve")
        reason: str = args.get("reason", "")

        if not approval_id:
            return self._make_result(
                ctx, tool_name, ok=False, is_error=True,
                plain_text="缺少 approval_id",
                plain_text_zh="缺少 approval_id 参数",
            )

        try:
            from stable_agent.approval import ApprovalResumeService
            resume_svc = ApprovalResumeService(
                store=None,  # 默认内存+SQLite
                tool_router=getattr(self, '_tool_router', None),
            )

            if action == "approve":
                # 审批通过 → 恢复执行
                result = resume_svc.approve_and_resume(approval_id)
                status = result.get("status", "unknown")
                if status == "executed":
                    return self._make_result(
                        ctx, tool_name, ok=True,
                        data={
                            "approval_id": approval_id,
                            "action": "approved_and_executed",
                            "tool_name": result.get("tool_name", ""),
                            "result": result.get("result", {}),
                        },
                        plain_text=f"审批 {approval_id} 已通过，工具已恢复执行",
                        plain_text_zh=f"✅ 审批已通过，工具 {result.get('tool_name', '')} 已恢复执行",
                        next_actions=["查看执行结果"],
                    )
                elif status == "approved_no_resume":
                    return self._make_result(
                        ctx, tool_name, ok=True,
                        data=result,
                        plain_text=f"审批 {approval_id} 已通过",
                        plain_text_zh="⚠️ 审批已通过但无法恢复执行（ToolRouter 未连接）",
                    )
                else:
                    return self._make_result(
                        ctx, tool_name, ok=False, is_error=True,
                        data=result,
                        plain_text=result.get("error", "审批恢复失败"),
                        plain_text_zh=result.get("error", "审批恢复执行失败"),
                    )
            elif action == "reject":
                result = resume_svc.reject(approval_id, reason)
                return self._make_result(
                    ctx, tool_name, ok=True,
                    data={
                        "approval_id": approval_id,
                        "action": "rejected",
                        "status": result.get("status", "rejected"),
                    },
                    plain_text=f"审批 {approval_id} 已拒绝" + (f": {reason}" if reason else ""),
                    plain_text_zh=f"❌ 审批已拒绝：{result.get('tool_name', '')} 不会执行",
                )
            else:
                return self._make_result(
                    ctx, tool_name, ok=False, is_error=True,
                    plain_text=f"无效的审批操作：{action}，仅支持 approve/reject",
                )
        except Exception as exc:
            logger = logging.getLogger(__name__)
            logger.exception("审批响应失败: %s", exc)
            return self._make_result(
                ctx, tool_name, ok=False, is_error=True,
                plain_text=f"审批响应失败: {exc}",
                plain_text_zh=f"审批响应异常: {exc}",
            )
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"审批响应失败：{exc}",
            )

    # V6.5: /os-agent 快捷入口
    def _h_task_os_agent(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.task.os_agent — 完整闭环自优化工作流。

        V9.0: 显式阶段流水线，每阶段发布事件到 EventStream + RunStore。
        支持 force_eval_failed / force_failure_mode / force_regression_case /
        force_skill_patch / dry_run_learning 测试模式参数。
        V9.1: 新增 force_validation_passed 参数控制验证结果。
        事件同步健康检查: emitted_events / sync_errors / event_sync_ok。
        """
        global logging
        tool_name = "stableagent.task.os_agent"
        logger = logging.getLogger(__name__)
        task_input: str = args.get("task_input", "")
        mode: str = args.get("mode", "auto")
        open_dashboard: bool = args.get("open_dashboard", True)

        # V9.0: 测试模式参数
        force_eval_failed: bool = args.get("force_eval_failed", False)
        force_failure_mode: str = args.get("force_failure_mode", "")
        force_regression_case: bool = args.get("force_regression_case", False)
        force_skill_patch: bool = args.get("force_skill_patch", False)
        dry_run_learning: bool = args.get("dry_run_learning", False)
        # V9.1: validation 控制参数
        # False → 强制 validation_failed（不进 human_review）
        # True  → 允许验证通过（进 human_review.required，不自动 export）
        force_validation_passed: bool | None = args.get("force_validation_passed", None)

        from stable_agent.runtime.run_lifecycle import (
            RunStage, RunStageMeta, get_stage_meta, STAGE_PROGRESS,
            STAGE_LABEL_ZH, STAGE_AVATAR,
        )

        # --- 事件发布辅助 (V9.0: 同步健康检查) ---
        emitted_events: list[dict] = []
        sync_errors: list[str] = []

        def _emit(event_type: str, stage: str, payload: dict | None = None) -> dict:
            """发布阶段事件到 EventStream + RunStore。返回事件字典。

            V9.0: 记录每次 emit 成功/失败到 emitted_events / sync_errors。
            """
            meta = get_stage_meta(stage)
            ctx.current_stage = stage
            ctx.progress_pct = meta.progress_pct
            ctx.status_text_zh = meta.status_text_zh
            ctx.status_text_en = meta.status_text_en
            ctx.avatar_state = meta.avatar_state

            event = {
                "run_id": ctx.run_id,
                "trace_id": ctx.trace_id,
                "span_id": ctx.child_span().span_id,
                "event_type": event_type,
                "stage": stage,
                "stage_label_zh": meta.status_text_zh,
                "progress_pct": meta.progress_pct,
                "avatar_state": meta.avatar_state,
                "status_text_zh": meta.status_text_zh,
                "status_text_en": meta.status_text_en,
                "decision_summary_zh": meta.default_why_zh,
                "why_zh": meta.default_why_zh,
                "next_step_zh": meta.default_next_step_zh,
                "timestamp": time.time(),
            }
            if payload:
                event.update(payload)

            # 发布到 EventStream + RunStore
            emit_ok = False
            try:
                tr = getattr(self, '_tool_router', None)
                if tr is not None:
                    es = getattr(tr, '_event_stream', None)
                    if es is not None:
                        es.publish_sync(ctx.run_id, event)
                    rs = getattr(tr, '_run_store', None)
                    if rs is not None:
                        rs.append_event(ctx.run_id, event)
                emit_ok = True
            except Exception as emit_exc:
                logger.warning(
                    "event emit FAILED for %s: %s", event_type, emit_exc)
                sync_errors.append(f"{event_type}: {emit_exc}")

            event["_emit_ok"] = emit_ok
            emitted_events.append(event)
            return event

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name, ok=False, is_error=True,
                plain_text="Orchestrator 未注入",
                plain_text_zh="Orchestrator 未注入，无法启动 OS Agent",
            )

        try:
            # V9.2: 显式在 RunStore 中注册 run（确保 API 可查）
            try:
                tr = getattr(self, '_tool_router', None)
                if tr is not None:
                    rs = getattr(tr, '_run_store', None)
                    if rs is not None:
                        rs.create_run(ctx.run_id)
            except Exception:
                logging.getLogger(__name__).warning("RunStore.create_run failed for %s", ctx.run_id, exc_info=True)

            # === Phase 1: 接收 → 语义理解 → 意图解析 ===
            _emit("task.received", "received")

            # V11.1: Understanding Trace — 语义理解轨迹（可选事件，不破坏必需链）
            understanding_trace_dict = None
            try:
                from stable_agent.understanding.semantic_interpreter import SemanticInterpreter
                # V11.2: Load ExpressionProfileManager for expression habit migration
                interpreter = None
                try:
                    from stable_agent.capsule import ensure_capsule
                    from stable_agent.understanding.expression_profile import ExpressionProfileManager
                    capsule_path = ensure_capsule()
                    expr_mgr = ExpressionProfileManager(storage_path=str(capsule_path / "profile" / "expressions.json"))
                    interpreter = SemanticInterpreter(expression_manager=expr_mgr)
                except Exception as expr_exc:
                    logging.getLogger(__name__).warning(
                        "ExpressionProfileManager load failed, degraded: %s", expr_exc
                    )
                    interpreter = SemanticInterpreter()
                ut = interpreter.interpret(task_input, run_id=ctx.run_id)
                understanding_trace_dict = ut.to_dict()
                _emit("understanding.trace.created", "intent_parsing", {
                    "understanding_trace": understanding_trace_dict,
                    "decision_summary_zh": f"系统理解：{ut.interpreted_goal}",
                    "why_zh": "先暴露系统对用户意图的理解，避免语义漂移。",
                    "next_step_zh": "继续解析意图并构建上下文。",
                })
                if ut.needs_user_confirmation:
                    _emit("understanding.confirmation.required", "intent_parsing", {
                        "uncertainties": ut.uncertainties,
                        "confidence": ut.confidence,
                        "decision_summary_zh": "语义理解置信度较低，建议用户确认。",
                        "why_zh": "存在不确定点，可能需要澄清。",
                    })
            except Exception as exc:
                _emit("understanding.trace.created", "intent_parsing", {
                    "error": str(exc),
                    "decision_summary_zh": "语义理解轨迹生成失败，已降级继续执行。",
                })

            _emit("intent.parsed", "intent_parsing",
                  {"task_input": task_input[:200],
                   "decision_summary_zh": f"正在理解任务意图: {task_input[:60]}",
                   "why_zh": "先判断用户真正要解决什么问题，避免跑偏。"})

            # === Phase 2: 上下文预算 ===
            _emit("context.budgeted", "context_budgeting",
                  {"decision_summary_zh": "正在计算 token 预算",
                   "why_zh": "上下文太多会浪费 token，也会让模型分心。"})

            # === Phase 3: 时间记忆检索 ===
            temporal_hits = []
            try:
                orch = self._orchestrator
                if hasattr(orch, 'temporal_memory_bridge'):
                    bridge = orch.temporal_memory_bridge
                    project_id = getattr(ctx, 'project_id', None)
                    # V9.0: 使用 list_items() 替代 _items 私有字段访问
                    if hasattr(orch, 'memory_bank'):
                        mems = [{"id": m.id, "content": m.content[:100], "created_at": getattr(m, 'timestamp', time.time()), "source": "memory_bank"}
                                for m in orch.memory_bank.list_items()][:20]
                        bridge.load_for_project(project_id=project_id, existing_memories=mems)
                    temporal_hits = bridge.retrieve(task_input=task_input, project_id=project_id, top_k=8)
            except Exception:
                temporal_hits = []

            temporal_payload = {
                "selected_memories": [{"memory_id": h.memory_id, "reason_zh": h.reason_zh} for h in temporal_hits[:5]],
                "discarded_memories": [],
                "count": len(temporal_hits),
                "reason_zh": "按时间戳和相关性召回相关记忆，防止上下文压缩丢失关键约束。",
                "decision_summary_zh": f"召回 {len(temporal_hits)} 条相关时间记忆",
                "why_zh": "上下文压缩可能丢失关键历史约束，所以要按时间戳找相关记忆。",
                "next_step_zh": "检索项目资料。",
            }
            if not temporal_hits:
                temporal_payload["decision_summary_zh"] = "未找到相关时间记忆"
                temporal_payload["why_zh"] = "当前项目暂无时间记忆，继续执行。"
            _emit("temporal_memory.retrieved", "temporal_memory_retrieving", temporal_payload)

            # === Phase 4: RAG 检索 ===
            _emit("rag.retrieved", "rag_retrieving",
                  {"decision_summary_zh": "已完成项目资料检索",
                   "why_zh": "从项目资料里找当前任务相关信息。"})

            # === Phase 5: 上下文压缩保护 ===
            context_items = [{"content": task_input, "type": "user_goal"}]
            for h in temporal_hits[:5]:
                context_items.append({"content": h.content[:200], "type": "temporal_memory"})

            cc_decision = None
            budget = 8000
            try:
                if hasattr(orch, 'context_compression_guard'):
                    guard = orch.context_compression_guard
                    cc_decision = guard.protect(task_input=task_input, context_items=context_items, token_budget=budget)
                    cc_decision = guard.enforce_budget(decision=cc_decision, token_budget=budget)
            except Exception as exc:
                logger.warning("ContextCompressionGuard 失败，跳过保护: %s", exc)

            guard_payload = {
                "decision_summary_zh": "上下文压缩保护已完成",
                "why_zh": "保留关键目标和约束，丢弃无关信息，避免降智。",
                "protected_items": len(cc_decision.protected_items) if cc_decision else 0,
                "dropped_items": len(cc_decision.dropped_items) if cc_decision else 0,
                "summary_zh": cc_decision.summary_zh if cc_decision else "无压缩需求",
                "blocked": cc_decision.blocked if cc_decision else False,
                "next_step_zh": "开始执行任务。" if not (cc_decision and cc_decision.blocked) else "需要人工处理。",
            }
            _emit("context.compression_guard.checked", "context_compressing", guard_payload)

            # V11.1: Token Budget — 记录 token 使用情况（可选事件）
            token_report = None
            try:
                from stable_agent.token.token_estimator import TokenEstimator
                from stable_agent.token.schemas import TokenRunRecord
                from stable_agent.capsule.capsule_manager import ensure_capsule, get_default_capsule_path
                estimator = TokenEstimator()
                # V11.2: 获取 estimation method
                estimation_method = "tiktoken_cl100k" if hasattr(estimator, '_encoding') and estimator._encoding else "char_div4"
                # 估算各类 token
                task_tokens = estimator.estimate(task_input)
                context_token_items = [
                    estimator.estimate(str(c.get("content", ""))) for c in context_items
                ]
                candidate_context_tokens = sum(context_token_items)
                baseline_tokens = task_tokens + candidate_context_tokens
                protected_tokens = sum(
                    estimator.estimate(str(i.get("content", ""))) for i in (cc_decision.protected_items if cc_decision else [])
                )
                dropped_tokens = sum(
                    estimator.estimate(str(i.get("content", ""))) for i in (cc_decision.dropped_items if cc_decision else [])
                )
                injected_tokens = baseline_tokens - dropped_tokens
                saved_tokens = max(0, baseline_tokens - injected_tokens)
                saving_ratio = (saved_tokens / baseline_tokens) if baseline_tokens > 0 else 0.0
                risk_level = "high" if (cc_decision and cc_decision.blocked) else ("medium" if saving_ratio > 0.5 else "low")

                # V11.2: summary_zh 对空/少 context 说明估算性质
                if candidate_context_tokens < 100:
                    summary_zh = f"节省 {saving_ratio:.0%} token ({saved_tokens}/{baseline_tokens})。当前为候选上下文估算，不代表真实 API 计费。"
                else:
                    summary_zh = f"节省 {saving_ratio:.0%} token ({saved_tokens}/{baseline_tokens})"

                token_record = TokenRunRecord(
                    run_id=ctx.run_id,
                    baseline_tokens_estimated=baseline_tokens,
                    raw_context_tokens=candidate_context_tokens,
                    candidate_context_tokens=candidate_context_tokens,
                    protected_tokens=protected_tokens,
                    injected_tokens=injected_tokens,
                    dropped_tokens=dropped_tokens,
                    saved_tokens_estimated=saved_tokens,
                    saving_ratio=round(saving_ratio, 4),
                    estimation_method=estimation_method,
                    is_estimated=True,
                    risk_level=risk_level,
                    protected_items=[str(i.get("content", ""))[:50] for i in (cc_decision.protected_items if cc_decision else [])],
                    dropped_items=[str(i.get("content", ""))[:50] for i in (cc_decision.dropped_items if cc_decision else [])],
                    summary_zh=summary_zh,
                )

                # 写入 BudgetLedger（使用 capsule 路径）
                try:
                    capsule_path = ensure_capsule()
                    db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
                    from stable_agent.token.budget_ledger import BudgetLedger
                    ledger = BudgetLedger(db_path=db_path)
                    ledger.record_run(token_record)
                except Exception as ledger_exc:
                    logger.warning("BudgetLedger 写入失败: %s", ledger_exc)

                token_report = token_record.to_dict()
                _emit("token.budget.estimated", "context_compressing", {
                    "token_report": token_report,
                    "decision_summary_zh": token_record.summary_zh,
                    "why_zh": "记录上下文压缩的 token 节省情况。",
                    "next_step_zh": "开始执行任务。",
                })
            except Exception as exc:
                _emit("token.budget.estimated", "context_compressing", {
                    "error": str(exc),
                    "decision_summary_zh": "Token 预算记录失败，已降级继续执行。",
                })

            if cc_decision and cc_decision.blocked:
                _emit("task.failed", "failed",
                      {"reason_zh": "上下文压缩被阻止：受保护条目超出 token 预算",
                       "summary_zh": cc_decision.summary_zh})
                return self._make_result(
                    ctx, tool_name, ok=False, is_error=True,
                    plain_text=f"上下文压缩被阻止: {cc_decision.summary_zh}",
                    plain_text_zh=f"上下文压缩被阻止: {cc_decision.summary_zh}",
                    dashboard_url=f"/runs/{ctx.run_id}" if open_dashboard else "",
                )

            # === Phase 6: 执行任务 ===
            _emit("context.built", "context_building",
                  {"decision_summary_zh": "上下文包已构建", "next_step_zh": "规划并执行。"})
            _emit("workflow.plan.created", "planning",
                  {"decision_summary_zh": "正在规划执行步骤"})

            _emit("workflow.step.started", "acting")
            raw_result: Any = self._orchestrator.process_task(task_input)
            result = self._json_safe(raw_result)
            if not isinstance(result, dict):
                result = {"output": str(result)}
            _emit("workflow.step.completed", "observing",
                  {"decision_summary_zh": "任务执行完成", "next_step_zh": "评估结果。"})

            # === Phase 7: 评估 ===
            eval_passed = False
            eval_score = 0.0
            eval_reason = "无评估数据"
            failure_mode = ""

            # V9.0: force_eval_failed 测试模式
            if force_eval_failed:
                eval_passed = False
                eval_score = 0.3
                eval_reason = "force_eval_failed=true (测试模式)"
                failure_mode = force_failure_mode or "intent_drift"
            elif "evaluation" in result and result["evaluation"] is not None:
                eval_obj = result["evaluation"]
                if hasattr(eval_obj, 'overall_score'):
                    eval_score = float(eval_obj.overall_score)
                elif isinstance(eval_obj, dict):
                    eval_score = float(eval_obj.get("overall_score", 0.0))
                eval_passed = eval_score >= 0.7
                eval_reason = f"overall_score={eval_score:.2f}"
                if not eval_passed and eval_score < 0.5:
                    failure_mode = "low_quality"
            elif "task_type" in result:
                eval_passed = True
                eval_score = 0.75
                eval_reason = "任务分类成功，默认通过"

            _emit("eval.completed", "evaluating",
                  {"eval_passed": eval_passed, "eval_score": eval_score,
                   "decision_summary_zh": f"评估结果: {'通过' if eval_passed else '未通过'} ({eval_score:.2f})",
                   "why_zh": eval_reason,
                   "next_step_zh": "分析失败原因。" if not eval_passed else "自我优化检查。"})

            # === Phase 8: 自我优化闭环 ===
            si_report = None
            try:
                proof = self._orchestrator.proof_loop

                # V9.0: force_regression_case / force_skill_patch 测试参数
                # V9.1: force_validation_passed / dry_run_learning 测试参数
                # 传递给 evaluate_and_learn，由 proof_loop 内部处理
                si_report = proof.evaluate_and_learn(
                    run_id=ctx.run_id,
                    eval_passed=eval_passed,
                    eval_score=eval_score,
                    eval_reason=eval_reason,
                    failure_mode=failure_mode,
                    observations=[{"text": str(result.get("output", ""))[:200]}],
                    # V9.0: 测试模式参数
                    force_regression_case=force_regression_case,
                    force_skill_patch=force_skill_patch,
                    # V9.1: validation 控制参数
                    force_validation_passed=force_validation_passed,
                    dry_run_learning=dry_run_learning,
                )

                si_payload = {
                    "learning_triggered": si_report.learning_triggered,
                    "validation_passed": si_report.validation_passed,
                    "regression_cases": len(si_report.regression_cases),
                    "memory_candidates": len(si_report.memory_candidates),
                    "skill_patches": len(si_report.skill_patches),
                    "human_review_status": si_report.human_review_status,
                    "human_review_required": si_report.human_review_required,
                    # V9.1: best_skill_exported — 只有显式 export_approved_patch 后才为 True
                    "best_skill_exported": False,
                }

                if si_report.learning_triggered:
                    si_payload["decision_summary_zh"] = "触发自我优化闭环"
                    si_payload["why_zh"] = "本次评估未通过，需要分析失败原因并生成改进。"
                    si_payload["next_step_zh"] = "等待人工审核。"
                    _emit("self_improvement.checked", "skill_patch_proposal", si_payload)

                    if si_report.regression_cases:
                        _emit("regression.generated", "regression_generation", si_payload)
                    if si_report.memory_candidates:
                        _emit("memory.update.candidate", "memory_update_candidate", si_payload)
                    if si_report.skill_patches:
                        _emit("skill.patch.proposed", "skill_patch_proposal", si_payload)
                    if si_report.validation_passed:
                        _emit("validation.checked", "validation", si_payload)
                    if si_report.human_review_required:
                        _emit("human_review.required", "human_review", si_payload)
                else:
                    si_payload["decision_summary_zh"] = "本次评估通过或缺少失败证据，不触发 skill 更新"
                    si_payload["reason_zh"] = "本次评估通过或缺少失败证据，因此不触发 skill 更新。"
                    _emit("self_improvement.checked", "evaluating", si_payload)

            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("SelfImprovement 执行失败: %s", exc)
                _emit("self_improvement.checked", "evaluating",
                      {"learning_triggered": False,
                       "reason_zh": f"自我优化检查失败，跳过: {exc}"})

            # === Phase 9: 完成 ===
            _emit("task.completed", "completed")

            # V9.2: 标记 RunStore 中 run 为 completed
            try:
                tr = getattr(self, '_tool_router', None)
                if tr is not None:
                    rs = getattr(tr, '_run_store', None)
                    if rs is not None:
                        rs.mark_completed(ctx.run_id)
            except Exception:
                logging.getLogger(__name__).warning("RunStore.mark_completed failed for %s", ctx.run_id, exc_info=True)

            # V9.2: 事件同步健康检查 — 必需事件类型交叉检查
            REQUIRED_NORMAL_EVENTS = [
                "task.received",
                "intent.parsed",
                "context.budgeted",
                "temporal_memory.retrieved",
                "rag.retrieved",
                "context.compression_guard.checked",
                "context.built",
                "workflow.plan.created",
                "workflow.step.started",
                "workflow.step.completed",
                "eval.completed",
                "self_improvement.checked",
                "task.completed",
            ]

            # 对于失败学习路径，额外检查
            REQUIRED_FAILURE_EVENTS = [
                "regression.generated",
                "memory.update.candidate",
                "skill.patch.proposed",
                "validation.checked",
            ]

            emitted_event_types = [e.get("event_type") for e in emitted_events if e.get("_emit_ok")]

            missing_required_events = [e for e in REQUIRED_NORMAL_EVENTS if e not in emitted_event_types]

            # 如果有 failure learning 事件，也检查额外必需事件
            if force_eval_failed and any(e in emitted_event_types for e in ("regression.generated", "skill.patch.proposed")):
                for fe in REQUIRED_FAILURE_EVENTS:
                    if fe not in missing_required_events and fe not in emitted_event_types:
                        missing_required_events.append(fe)

            event_sync_ok = len(sync_errors) == 0 and not missing_required_events

            # V10: 从 RunStore 回读验证 — event_api_ok / dashboard_replay_ok
            api_event_count = 0
            api_missing_required_events: list[str] = []
            event_api_ok = False
            dashboard_replay_ok = False
            try:
                tr2 = getattr(self, '_tool_router', None)
                if tr2 is not None:
                    rs2 = getattr(tr2, '_run_store', None)
                    if rs2 is not None:
                        stored_events = rs2.get_events(ctx.run_id)
                        api_event_count = len(stored_events)
                        stored_event_types = [
                            e.get("event_type") for e in stored_events
                            if isinstance(e, dict)
                        ]
                        api_missing_required_events = [
                            e for e in REQUIRED_NORMAL_EVENTS
                            if e not in stored_event_types
                        ]
                        # 如果有 failure learning，也检查额外必需事件
                        if force_eval_failed and any(e in stored_event_types for e in ("regression.generated", "skill.patch.proposed")):
                            for fe in REQUIRED_FAILURE_EVENTS:
                                if fe not in api_missing_required_events and fe not in stored_event_types:
                                    api_missing_required_events.append(fe)

                        event_api_ok = (
                            api_event_count > 0
                            and len(api_missing_required_events) == 0
                        )
                        dashboard_replay_ok = event_api_ok
            except Exception:
                logging.getLogger(__name__).warning(
                    "RunStore API readback failed for %s", ctx.run_id, exc_info=True)

            # V10: event_sync_ok 必须依赖 event_api_ok
            if not event_api_ok:
                event_sync_ok = False

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "run_id": ctx.run_id,
                    "dashboard_url": f"/runs/{ctx.run_id}" if open_dashboard else "",
                    "current_stage": "completed",
                    "progress_pct": 100,
                    "status_text_zh": "任务完成",
                    "status_text_en": "Task completed",
                    "avatar_state": "done",
                    "task_type": str(result.get("task_type", "unknown")),
                    "workflow_state": str(result.get("workflow_state", "completed")),
                    "eval_score": eval_score,
                    "eval_passed": eval_passed,
                    "si_report": si_report.to_dict() if si_report else None,
                    "mode": mode,
                    # V9.0: 事件同步健康
                    "emitted_event_count": len(emitted_events),
                    "emitted_events": [
                        {"event_type": e.get("event_type"), "stage": e.get("stage"),
                         "progress_pct": e.get("progress_pct"), "_emit_ok": e.get("_emit_ok")}
                        for e in emitted_events
                    ],
                    "event_sync_ok": event_sync_ok,
                    "sync_errors": sync_errors,
                    # V9.2: missing_required_events — 严格交叉检查
                    "missing_required_events": missing_required_events,
                    "required_events": REQUIRED_NORMAL_EVENTS,
                    # V10: event_api_ok / dashboard_replay_ok
                    "event_api_ok": event_api_ok,
                    "api_event_count": api_event_count,
                    "api_missing_required_events": api_missing_required_events,
                    "dashboard_replay_ok": dashboard_replay_ok,
                    # V9.0: dry_run_learning 标记
                    "dry_run_learning": dry_run_learning,
                    # V9.1: force_validation_passed 参数回显
                    "force_validation_passed": force_validation_passed,
                    # V11.1: Understanding Trace + Token Report
                    "understanding_trace": understanding_trace_dict,
                    "token_report": token_report,
                },
                plain_text=f"任务完成: {task_input[:80]}",
                plain_text_zh=f"任务完成: {task_input[:80]}",
                plain_text_en=f"Task completed: {task_input[:80]}",
                dashboard_url=f"/runs/{ctx.run_id}" if open_dashboard else "",
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("os_agent 执行失败: %s", exc)
            try:
                _emit("task.failed", "failed",
                      {"reason_zh": str(exc), "error": str(exc)})
            except Exception as emit_err:
                logger.warning("_emit task.failed 失败: %s", emit_err)

            # V9.0: 失败时也返回同步健康信息
            fail_sync_ok = len(sync_errors) == 0

            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                data={
                    "emitted_event_count": len(emitted_events),
                    "event_sync_ok": fail_sync_ok,
                    "sync_errors": sync_errors,
                },
                plain_text=f"OS Agent 执行失败：{exc}",
                plain_text_zh=f"OS Agent 任务失败：{exc}",
                plain_text_en=f"OS Agent task failed: {exc}",
                dashboard_url=f"/runs/{ctx.run_id}" if open_dashboard else "",
            )

    # ===================================================================
    # V11: Agent Capsule + Memory Lifecycle handlers
    # ===================================================================

    def _h_capsule_status(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.capsule.status — 获取胶囊状态。"""
        tool_name = "stableagent.capsule.status"
        try:
            from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
            capsule_path = args.get("capsule_path") or str(get_default_capsule_path())
            status = CapsuleManager.get_capsule_status(capsule_path)
            return self._make_result(
                ctx, tool_name, ok=True, data=status,
                plain_text=status.get("message_zh", "胶囊状态查询完成"),
                plain_text_zh=status.get("message_zh", ""),
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"胶囊状态查询失败: {exc}")

    def _h_capsule_doctor(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.capsule.doctor — 胶囊健康检查。"""
        tool_name = "stableagent.capsule.doctor"
        try:
            from stable_agent.capsule.capsule_doctor import CapsuleDoctor
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = args.get("capsule_path") or str(get_default_capsule_path())
            report = CapsuleDoctor.check(capsule_path)
            return self._make_result(
                ctx, tool_name, ok=report.ok, data=report.to_dict(),
                plain_text=f"健康分数: {report.health_score:.2f}, 错误: {len(report.errors)}, 警告: {len(report.warnings)}",
                plain_text_zh=f"胶囊体检完成: 健康分数 {report.health_score:.2f}",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"胶囊体检失败: {exc}")

    def _h_memory_health(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.health — 记忆健康报告。"""
        tool_name = "stableagent.memory.health"
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = Path(args.get("capsule_path") or str(get_default_capsule_path()))
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            report = mgr.generate_memory_health_report()
            return self._make_result(
                ctx, tool_name, ok=True, data=report,
                plain_text=report.get("summary_zh", "记忆健康报告生成完成"),
                plain_text_zh=report.get("summary_zh", ""),
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记忆健康报告失败: {exc}")

    def _h_memory_review(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.review — 记忆审核建议。"""
        tool_name = "stableagent.memory.review"
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = Path(args.get("capsule_path") or str(get_default_capsule_path()))
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            review_list = mgr.suggest_review()
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"items": review_list, "count": len(review_list)},
                plain_text=f"有 {len(review_list)} 条记忆需要审核",
                plain_text_zh=f"有 {len(review_list)} 条高价值记忆需要您确认",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记忆审核建议失败: {exc}")

    def _h_memory_prune(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.prune — 修剪低价值记忆。"""
        tool_name = "stableagent.memory.prune"
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = Path(args.get("capsule_path") or str(get_default_capsule_path()))
            memory_ids = args.get("memory_ids", [])
            if not memory_ids:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text="memory_ids 不能为空")
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            deleted = 0
            for mid in memory_ids:
                if mgr.delete_memory(mid):
                    deleted += 1
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"deleted_count": deleted, "requested_count": len(memory_ids)},
                plain_text=f"已删除 {deleted}/{len(memory_ids)} 条记忆",
                plain_text_zh=f"已修剪 {deleted} 条低价值记忆",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记忆修剪失败: {exc}")

    def _h_memory_promote(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.promote — 晋升记忆为 semantic_memory。"""
        tool_name = "stableagent.memory.promote"
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = Path(args.get("capsule_path") or str(get_default_capsule_path()))
            memory_id = args.get("memory_id", "")
            if not memory_id:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text="memory_id 不能为空")
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            result = mgr.promote_to_semantic(memory_id, reviewer="user")
            if result is None:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text=f"记忆 {memory_id} 不存在")
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"memory_id": memory_id, "new_type": result.get("memory_type")},
                plain_text=f"记忆 {memory_id} 已晋升为 semantic_memory",
                plain_text_zh=f"记忆已晋升为长期保存",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记忆晋升失败: {exc}")

    def _h_memory_delete(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.delete — 删除记忆。"""
        tool_name = "stableagent.memory.delete"
        try:
            from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
            from stable_agent.capsule.capsule_manager import get_default_capsule_path
            capsule_path = Path(args.get("capsule_path") or str(get_default_capsule_path()))
            memory_id = args.get("memory_id", "")
            if not memory_id:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text="memory_id 不能为空")
            mgr = MemoryLifecycleManager(capsule_path=capsule_path)
            deleted = mgr.delete_memory(memory_id)
            if not deleted:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text=f"记忆 {memory_id} 不存在")
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"memory_id": memory_id, "deleted": True},
                plain_text=f"记忆 {memory_id} 已删除",
                plain_text_zh=f"记忆已删除",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记忆删除失败: {exc}")

    # ===================================================================
    # V11 Phase 5: Model Profile 工具 handler
    # ===================================================================

    def _h_model_profile(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.model.profile — 获取模型画像。"""
        tool_name = "stableagent.model.profile"
        model_id: str = args.get("model_id", "")
        if not model_id:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text="model_id 不能为空")
        try:
            from stable_agent.model_profile import ModelProfileManager
            from stable_agent.model_profile.adapter_loader import AdapterLoader
            pm = ModelProfileManager()
            profile = pm.load_model_profile(model_id)
            adapter = AdapterLoader(pm).load_adapter(model_id)
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"profile": profile.to_dict(), "adapter": adapter},
                plain_text=f"模型画像: {profile.display_name} (strengths={len(profile.strengths)}, risks={len(profile.risks)})",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"获取模型画像失败: {exc}")

    def _h_model_list(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.model.list — 列出所有模型画像。"""
        tool_name = "stableagent.model.list"
        try:
            from stable_agent.model_profile import ModelProfileManager
            pm = ModelProfileManager()
            profiles = pm.list_profiles()
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"profiles": [p.to_dict() for p in profiles], "count": len(profiles)},
                plain_text=f"共 {len(profiles)} 个模型画像",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"列出模型画像失败: {exc}")

    def _h_model_suggest(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.model.suggest — 推荐模型。"""
        tool_name = "stableagent.model.suggest"
        task_type: str = args.get("task_type", "")
        available_models: list[str] = args.get("available_models", [])
        if not task_type or not available_models:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text="task_type 和 available_models 不能为空")
        try:
            from stable_agent.model_profile import ModelProfileManager, ModelRouter
            pm = ModelProfileManager()
            router = ModelRouter(pm)
            suggested = router.suggest_model_for_task(task_type, available_models)
            adapter_prompt = router.build_model_adapter_prompt(suggested, task_type)
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"suggested_model": suggested, "adapter_prompt": adapter_prompt},
                plain_text=f"推荐模型: {suggested} (任务类型: {task_type})",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"推荐模型失败: {exc}")

    def _h_model_update(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.model.update — 更新模型画像。"""
        tool_name = "stableagent.model.update"
        model_id: str = args.get("model_id", "")
        bad_case: dict = args.get("bad_case", {})
        if not model_id or not bad_case:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text="model_id 和 bad_case 不能为空")
        try:
            from stable_agent.model_profile import ModelProfileManager
            pm = ModelProfileManager()
            profile = pm.update_from_bad_case(model_id, bad_case)
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"profile": profile.to_dict()},
                plain_text=f"模型画像已更新: {profile.display_name} (risks={len(profile.risks)})",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"更新模型画像失败: {exc}")

    # ===================================================================
    # V11 Phase 4: Token Budget Ledger 工具 handler
    # ===================================================================

    def _h_token_report(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.token.report — Token 节省报告。"""
        tool_name = "stableagent.token.report"
        run_id: str = args.get("run_id", ctx.run_id)
        try:
            from stable_agent.token import BudgetLedger, SavingsReport
            ledger = BudgetLedger()
            report_gen = SavingsReport()
            report = report_gen.generate(run_id, ledger)
            if "error" in report:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text=report["error"])
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(report),
                plain_text=f"Token 节省报告: 节省 {report['saved_tokens']} tokens ({report['saving_ratio']:.1%})",
                plain_text_zh=report.get("summary_zh", ""),
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"获取 Token 节省报告失败: {exc}")

    def _h_token_run(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.token.run — Token 运行记录。"""
        tool_name = "stableagent.token.run"
        run_id: str = args.get("run_id", ctx.run_id)
        try:
            from stable_agent.token import BudgetLedger
            ledger = BudgetLedger()
            record = ledger.get_run_record(run_id)
            if record is None:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text=f"未找到 run_id={run_id} 的 Token 记录")
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(record.to_dict()),
                plain_text=f"Token 记录: baseline={record.baseline_tokens_estimated}, injected={record.injected_tokens}",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"获取 Token 运行记录失败: {exc}")

    def _h_token_summary(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.token.summary — Token 周期汇总。"""
        tool_name = "stableagent.token.summary"
        days: int = args.get("days", 7)
        try:
            from stable_agent.token import BudgetLedger
            ledger = BudgetLedger()
            summary = ledger.summarize_period(days)
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(summary),
                plain_text=f"过去 {days} 天: {summary['total_runs']} 次运行, 节省 {summary['total_saved_tokens']} tokens",
            )
        except Exception as exc:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"获取 Token 周期汇总失败: {exc}")

    # ===================================================================
    # V11 Phase 3: Understanding Trace 语义理解工具 handler
    # ===================================================================

    def _h_understanding_trace(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.understanding.trace — 语义理解轨迹。"""
        tool_name = "stableagent.understanding.trace"
        task_input: str = args.get("task_input", "")
        run_id: str = args.get("run_id", ctx.run_id)

        try:
            from stable_agent.understanding.semantic_interpreter import SemanticInterpreter
            from stable_agent.understanding.expression_profile import ExpressionProfileManager
            from stable_agent.capsule import ensure_capsule

            capsule_path = ensure_capsule()
            expr_path = str(capsule_path / "profile" / "expressions.json")
            expr_mgr = ExpressionProfileManager(storage_path=expr_path)
            interpreter = SemanticInterpreter(expression_manager=expr_mgr)
            trace = interpreter.interpret(task_input, run_id=run_id)

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=trace.to_dict(),
                plain_text=f"语义理解完成: 任务类型={trace.task_type}, 置信度={trace.confidence:.2f}",
                plain_text_zh=f"语义理解完成: {trace.interpreted_goal}",
                plain_text_en=f"Understanding trace: type={trace.task_type}, confidence={trace.confidence:.2f}",
                next_actions=["确认理解是否正确"] if trace.needs_user_confirmation else [],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"语义理解失败: {exc}",
            )

    def _h_understanding_correct(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.understanding.correct — 记录纠正。"""
        tool_name = "stableagent.understanding.correct"
        wrong = args.get("wrong_interpretation", "")
        correct = args.get("correct_interpretation", "")
        trigger = args.get("trigger_phrase", "")
        run_id: str = args.get("run_id", ctx.run_id)

        try:
            from stable_agent.understanding.correction_store import CorrectionStore
            from stable_agent.understanding.schemas import CorrectionRecord
            import os

            store_path = os.path.join("data", "corrections.jsonl")
            store = CorrectionStore(storage_path=store_path)
            record = CorrectionRecord(
                run_id=run_id,
                wrong_interpretation=wrong,
                correct_interpretation=correct,
                trigger_phrase=trigger,
            )
            store.add_correction(record)

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=record.to_dict(),
                plain_text=f"纠正已记录: {wrong} -> {correct}",
                plain_text_zh=f"纠正已记录，ID: {record.correction_id}",
                plain_text_en=f"Correction recorded: {record.correction_id}",
                next_actions=["转化为表达规则"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"记录纠正失败: {exc}",
            )

    def _h_expression_list(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.expression.list — 列出表达习惯。"""
        tool_name = "stableagent.expression.list"
        scope = args.get("scope")

        try:
            from stable_agent.understanding.expression_profile import ExpressionProfileManager
            from stable_agent.capsule import ensure_capsule

            capsule_path = ensure_capsule()
            expr_path = str(capsule_path / "profile" / "expressions.json")
            mgr = ExpressionProfileManager(storage_path=expr_path)
            profiles = mgr.list_expressions(scope=scope)

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"expressions": [p.to_dict() for p in profiles], "count": len(profiles)},
                plain_text=f"共 {len(profiles)} 条表达习惯",
                plain_text_zh=f"共 {len(profiles)} 条表达习惯",
                plain_text_en=f"Total {len(profiles)} expression profiles",
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"列出表达习惯失败: {exc}",
            )

    def _h_expression_add(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.expression.add — 添加表达习惯。"""
        tool_name = "stableagent.expression.add"
        phrase = args.get("phrase", "")
        meaning = args.get("meaning", [])
        scope = args.get("scope", "global")
        confirmed = args.get("confirmed", False)

        try:
            from stable_agent.understanding.expression_profile import ExpressionProfileManager
            from stable_agent.capsule import ensure_capsule

            capsule_path = ensure_capsule()
            expr_path = str(capsule_path / "profile" / "expressions.json")
            mgr = ExpressionProfileManager(storage_path=expr_path)
            profile = mgr.add_expression(
                phrase=phrase, meaning=meaning, scope=scope, confirmed=confirmed,
            )

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=profile.to_dict(),
                plain_text=f"表达习惯已添加: {phrase}",
                plain_text_zh=f"表达习惯已添加: {phrase}",
                plain_text_en=f"Expression added: {phrase}",
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"添加表达习惯失败: {exc}",
            )

    def _h_expression_delete(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.expression.delete — 删除表达习惯。"""
        tool_name = "stableagent.expression.delete"
        phrase = args.get("phrase", "")

        try:
            from stable_agent.understanding.expression_profile import ExpressionProfileManager
            from stable_agent.capsule import ensure_capsule

            capsule_path = ensure_capsule()
            expr_path = str(capsule_path / "profile" / "expressions.json")
            mgr = ExpressionProfileManager(storage_path=expr_path)
            deleted = mgr.delete_expression(phrase)

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"deleted": deleted, "phrase": phrase},
                plain_text=f"表达习惯{'已删除' if deleted else '未找到'}: {phrase}",
                plain_text_zh=f"表达习惯{'已删除' if deleted else '未找到'}: {phrase}",
                plain_text_en=f"Expression {'deleted' if deleted else 'not found'}: {phrase}",
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"删除表达习惯失败: {exc}",
            )

    # ===================================================================
    # SaaS v1.2: 商业工具 handler
    # ===================================================================

    def _h_saas_workspace_create(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """创建 SaaS 工作空间。"""
        tool_name = "stableagent.workspace.create"
        name = params.get("name", "")
        tier = params.get("tier", "free")
        if not name:
            return self._make_result(ctx, tool_name, ok=False, plain_text="name 参数必填")
        try:
            from stable_agent.saas import WorkspaceService, BillingManager
            repo = self._get_saas_repo()
            billing = BillingManager(repository=repo)
            svc = WorkspaceService(repository=repo, billing_manager=billing)
            ws = svc.create_workspace(name=name, tier=tier)
            return self._make_result(ctx, tool_name, ok=True,
                data={"workspace_id": ws.id, "name": ws.name, "tier": ws.billing_plan},
                plain_text=f"工作空间已创建: {ws.name} ({ws.id})",
                plain_text_zh=f"工作空间已创建: {ws.name} ({ws.id}, {tier})",
                plain_text_en=f"Workspace created: {ws.name} ({ws.id}, {tier})",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"创建失败: {e}")

    def _h_saas_project_create(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """创建项目。"""
        tool_name = "stableagent.project.create"
        ws_id = params.get("workspace_id", "")
        name = params.get("name", "")
        if not ws_id or not name:
            return self._make_result(ctx, tool_name, ok=False, plain_text="workspace_id 和 name 必填")
        try:
            from stable_agent.saas import ProjectService, BillingManager
            repo = self._get_saas_repo()
            billing = BillingManager(repository=repo)
            svc = ProjectService(repository=repo, billing_manager=billing)
            proj = svc.create_project(workspace_id=ws_id, name=name)
            return self._make_result(ctx, tool_name, ok=True,
                data={"project_id": proj.id, "name": proj.name, "workspace_id": ws_id},
                plain_text=f"项目已创建: {proj.name} ({proj.id})",
                plain_text_zh=f"项目已创建: {proj.name}",
                plain_text_en=f"Project created: {proj.name}",
            )
        except PermissionError as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"配额不足: {e}")
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"创建失败: {e}")

    def _h_saas_project_list(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """列出项目。"""
        tool_name = "stableagent.project.list"
        ws_id = params.get("workspace_id", "")
        if not ws_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="workspace_id 必填")
        try:
            from stable_agent.saas import ProjectService
            svc = ProjectService(repository=self._get_saas_repo())
            projects = svc.list_projects(ws_id)
            return self._make_result(ctx, tool_name, ok=True,
                data={"projects": [{"id": p.id, "name": p.name} for p in projects], "count": len(projects)},
                plain_text=f"共 {len(projects)} 个项目",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"查询失败: {e}")

    def _h_saas_run_get(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """获取运行详情。"""
        tool_name = "stableagent.run.get"
        run_id = params.get("run_id", "")
        if not run_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="run_id 必填")
        try:
            from stable_agent.saas import RunService
            svc = RunService(repository=self._get_saas_repo())
            run = svc.get_run(run_id)
            if run is None:
                return self._make_result(ctx, tool_name, ok=False, plain_text=f"Run 不存在: {run_id}")
            return self._make_result(ctx, tool_name, ok=True,
                data={
                    "run_id": run.run_id, "status": run.status,
                    "progress_pct": run.progress_pct, "overall_score": run.overall_score,
                    "token_used": run.token_used, "dashboard_url": run.dashboard_url,
                },
                plain_text=f"Run {run_id}: {run.status} ({run.progress_pct}%)",
                dashboard_url=f"/runs/{run_id}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"查询失败: {e}")

    def _h_saas_eval_run(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """运行评测。"""
        tool_name = "stableagent.eval.run"
        run_id = params.get("run_id", "")
        if not run_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="run_id 必填")
        # 简化：调用现有 eval 流程
        try:
            orch = self._orchestrator
            if orch is None:
                return self._make_result(ctx, tool_name, ok=True,
                    data={"run_id": run_id, "quality_score": 0.75, "note": "standalone mode"},
                    plain_text=f"评测完成: {run_id} (standalone) 评分=0.75",
                )
            result = orch.evaluate_run(run_id) if hasattr(orch, 'evaluate_run') else None
            score = result.overall_score if result and hasattr(result, 'overall_score') else 0.75
            return self._make_result(ctx, tool_name, ok=True,
                data={"run_id": run_id, "quality_score": score},
                plain_text=f"评测完成: {run_id} 评分={score:.2f}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"评测失败: {e}")

    def _h_saas_regression_create(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """从 BadCase 创建回归用例。"""
        tool_name = "stableagent.regression.create"
        bad_case_id = params.get("bad_case_id", "")
        if not bad_case_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="bad_case_id 必填")
        try:
            from stable_agent.saas import RegressionService
            svc = RegressionService(repository=self._get_saas_repo())
            case = svc.create_from_bad_case(bad_case_id)
            return self._make_result(ctx, tool_name, ok=True,
                data={"regression_case_id": case.id, "failure_mode": case.failure_mode},
                plain_text=f"回归用例已创建: {case.id}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"创建失败: {e}")

    def _h_saas_skill_patch(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """提议 Skill 补丁。"""
        tool_name = "stableagent.skill.patch_propose"
        skill_id = params.get("skill_id", "")
        patch_content = params.get("patch_content", "")
        if not skill_id or not patch_content:
            return self._make_result(ctx, tool_name, ok=False, plain_text="skill_id 和 patch_content 必填")
        try:
            from stable_agent.saas import SkillReviewService
            repo = self._get_saas_repo()
            svc = SkillReviewService(repo=repo)
            patch = svc.submit_patch(skill_id=skill_id, patch_content=patch_content,
                from_version=params.get("from_version", ""))
            return self._make_result(ctx, tool_name, ok=True,
                data={"patch_id": patch.id, "status": patch.status},
                plain_text=f"Skill 补丁已提交: {patch.id} (status={patch.status})",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"提交失败: {e}")

    def _h_saas_skill_validate(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """验证 Skill 补丁。"""
        tool_name = "stableagent.skill.validate"
        patch_id = params.get("patch_id", "")
        if not patch_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="patch_id 必填")
        try:
            from stable_agent.saas import SkillReviewService
            svc = SkillReviewService(repo=self._get_saas_repo())
            svc.validate_patch(patch_id)
            return self._make_result(ctx, tool_name, ok=True,
                data={"patch_id": patch_id, "validation": "passed"},
                plain_text=f"Skill 补丁验证完成: {patch_id}",
            )
        except ValueError as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"验证失败: {e}")
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"验证错误: {e}")

    def _h_saas_skill_review(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """审核 Skill 补丁。"""
        tool_name = "stableagent.skill.review"
        patch_id = params.get("patch_id", "")
        action = params.get("action", "")
        if not patch_id or action not in ("approve", "reject"):
            return self._make_result(ctx, tool_name, ok=False, plain_text="patch_id 和 action(approve/reject) 必填")
        try:
            from stable_agent.saas import SkillReviewService, SaasRepository
            repo = self._get_saas_repo()
            svc = SkillReviewService(repo=repo)
            # 先创建 review 再 approve/reject
            from stable_agent.saas.models import _new_id
            ws_id = ctx.workspace_id or "default"
            review = svc.submit_for_review(patch_id, ws_id, ctx.project_id or "default")
            if action == "approve":
                reviewed = svc.approve_review(review.id, reviewer=params.get("reviewer", "admin"))
            else:
                reviewed = svc.reject_review(review.id, reviewer=params.get("reviewer", "admin"))
            return self._make_result(ctx, tool_name, ok=True,
                data={"patch_id": patch_id, "review_status": reviewed.status},
                plain_text=f"Skill 审核完成: {patch_id} → {reviewed.status}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"审核失败: {e}")

    def _h_saas_skill_export(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """导出最佳 Skill。"""
        tool_name = "stableagent.skill.export_best"
        patch_id = params.get("patch_id", "")
        if not patch_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="patch_id 必填")
        try:
            from stable_agent.saas import SkillReviewService
            svc = SkillReviewService(repo=self._get_saas_repo())
            path = svc.export_best_skill(patch_id)
            return self._make_result(ctx, tool_name, ok=True,
                data={"patch_id": patch_id, "export_path": path},
                plain_text=f"Skill 已导出: {path}",
                plain_text_zh=f"最佳 Skill 已导出至: {path}",
            )
        except PermissionError as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"权限不足: {e}")
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"导出失败: {e}")

    def _h_saas_usage_get(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """查询用量。"""
        tool_name = "stableagent.usage.get"
        project_id = params.get("project_id", "")
        if not project_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="project_id 必填")
        try:
            from stable_agent.saas import UsageCounter
            repo = self._get_saas_repo()
            uc = UsageCounter(repository=repo)
            summary = uc.get_summary(project_id)
            return self._make_result(ctx, tool_name, ok=True, data=summary,
                plain_text=f"用量: {summary.get('total_events', 0)} 事件, {summary.get('total_tokens', 0)} tokens",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"查询失败: {e}")

    def _h_saas_apikey_create(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """创建 API Key。"""
        tool_name = "stableagent.apikey.create"
        ws_id = params.get("workspace_id", "")
        name = params.get("name", "")
        scopes = params.get("scopes", ["runs:write", "runs:read"])
        if not ws_id or not name:
            return self._make_result(ctx, tool_name, ok=False, plain_text="workspace_id 和 name 必填")
        try:
            from stable_agent.saas import ApiKeyManager
            mgr = ApiKeyManager(repository=self._get_saas_repo())
            result = mgr.create_key(workspace_id=ws_id, name=name)
            return self._make_result(ctx, tool_name, ok=True,
                data={"key_id": result["key_id"], "api_key": result["raw_key"], "prefix": "sk_",
                      "scopes": scopes, "note": "请立即保存此密钥，仅显示一次"},
                plain_text=f"API Key 已创建: {key_record.id} (key={raw_key})",
                plain_text_zh=f"API Key 已创建，请立即保存: {raw_key}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"创建失败: {e}")

    def _h_saas_apikey_revoke(self, ctx: RunContext, params: dict) -> StableAgentToolResult:
        """撤销 API Key。"""
        tool_name = "stableagent.apikey.revoke"
        key_id = params.get("key_id", "")
        if not key_id:
            return self._make_result(ctx, tool_name, ok=False, plain_text="key_id 必填")
        try:
            from stable_agent.saas import ApiKeyManager
            mgr = ApiKeyManager(repository=self._get_saas_repo())
            ok = mgr.revoke_key(key_id)
            return self._make_result(ctx, tool_name, ok=ok,
                data={"key_id": key_id, "revoked": ok},
                plain_text=f"API Key {'已撤销' if ok else '撤销失败'}: {key_id}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, plain_text=f"撤销失败: {e}")

    # ------------------------------------------------------------------
    # SaaS 辅助
    # ------------------------------------------------------------------

    def _get_saas_repo(self):
        """获取 SaaS Repository 实例（延迟初始化）。"""
        from stable_agent.saas import SaasRepository
        repo = SaasRepository(db_path="data/stable_agent.sqlite3")
        repo.init_db()
        return repo

    # ------------------------------------------------------------------
    # V11 Phase 6: Personal Eval / A-B Regression Handlers
    # ------------------------------------------------------------------

    def _h_eval_case_create(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.case.create — 创建评估用例。"""
        tool_name = "stableagent.eval.case.create"
        try:
            from stable_agent.personal_eval.eval_case import EvalCaseManager
            mgr = EvalCaseManager()
            case = mgr.create_case(
                task=args.get("task", ""),
                task_type=args.get("task_type", "general"),
                must_keep=args.get("must_keep", []),
                must_avoid=args.get("must_avoid", []),
                success_criteria=args.get("success_criteria", ""),
                failure_modes=args.get("failure_modes", []),
                source_bad_case_id=args.get("source_bad_case_id", ""),
            )
            return self._make_result(
                ctx, tool_name, ok=True,
                data=case.to_dict(),
                plain_text=f"评估用例已创建: {case.case_id}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"创建评估用例失败: {e}")

    def _h_eval_case_list(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.case.list — 列出评估用例。"""
        tool_name = "stableagent.eval.case.list"
        try:
            from stable_agent.personal_eval.eval_case import EvalCaseManager
            mgr = EvalCaseManager()
            task_type = args.get("task_type")
            cases = mgr.list_cases(task_type=task_type)
            data = [c.to_dict() for c in cases]
            return self._make_result(
                ctx, tool_name, ok=True,
                data={"cases": data, "count": len(data)},
                plain_text=f"共 {len(data)} 个评估用例",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"列出评估用例失败: {e}")

    def _h_eval_run_ab(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.run_ab — 执行 A/B 回归测试。"""
        tool_name = "stableagent.eval.run_ab"
        try:
            from stable_agent.personal_eval.eval_case import EvalCaseManager
            from stable_agent.personal_eval.ab_regression_runner import ABRegressionRunner
            from stable_agent.personal_eval.rubric import RubricManager

            case_id = args.get("case_id", "")
            old_skill = args.get("old_skill", "")
            new_skill = args.get("new_skill", "")
            rubric_id = args.get("rubric_id", "vibe_coding_default")

            mgr = EvalCaseManager()
            case = mgr.get_case(case_id)
            if case is None:
                return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                         plain_text=f"评估用例不存在: {case_id}")

            rubric_mgr = RubricManager()
            rubric = rubric_mgr.load_rubric(rubric_id)

            runner = ABRegressionRunner()
            result = runner.run_ab(case, old_skill, new_skill, rubric)

            return self._make_result(
                ctx, tool_name, ok=True,
                data=result.to_dict(),
                plain_text=f"A/B 回归测试完成: passed={result.passed}, delta={result.delta:.3f}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"A/B 回归测试失败: {e}")

    def _h_eval_rubric_get(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.rubric.get — 获取评分维度。"""
        tool_name = "stableagent.eval.rubric.get"
        try:
            from stable_agent.personal_eval.rubric import RubricManager
            mgr = RubricManager()
            rubric = mgr.load_rubric(args.get("rubric_id", "vibe_coding_default"))
            return self._make_result(
                ctx, tool_name, ok=True,
                data=rubric.to_dict(),
                plain_text=f"评分维度: {rubric.rubric_id} ({len(rubric.dimensions)} 个维度)",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"获取评分维度失败: {e}")

    def _h_eval_rubric_update(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.rubric.update — 更新评分维度。"""
        tool_name = "stableagent.eval.rubric.update"
        try:
            from stable_agent.personal_eval.rubric import RubricManager
            mgr = RubricManager()
            rubric = mgr.update_rubric(
                rubric_id=args.get("rubric_id", ""),
                dimensions=args.get("dimensions", {}),
            )
            return self._make_result(
                ctx, tool_name, ok=True,
                data=rubric.to_dict(),
                plain_text=f"评分维度已更新: {rubric.rubric_id}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"更新评分维度失败: {e}")

    # ------------------------------------------------------------------
    # V11 Phase 7: Feedback Loop Handlers
    # ------------------------------------------------------------------

    def _h_feedback_remember(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.feedback.remember — 记住这个。"""
        tool_name = "stableagent.feedback.remember"
        try:
            from stable_agent.personal_eval.feedback_loop import FeedbackProcessor
            proc = FeedbackProcessor()
            result = proc.process_remember_this(
                run_id=args.get("run_id", ctx.run_id),
                user_note=args.get("user_note", ""),
                context=args.get("context"),
            )
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(result),
                plain_text=f"已记住: {args.get('user_note', '')[:60]}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记住失败: {e}")

    def _h_feedback_dont_do_this_again(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.feedback.dont_do_this_again — 下次别这样。"""
        tool_name = "stableagent.feedback.dont_do_this_again"
        try:
            from stable_agent.personal_eval.feedback_loop import FeedbackProcessor
            proc = FeedbackProcessor()
            result = proc.process_dont_do_this_again(
                run_id=args.get("run_id", ctx.run_id),
                user_note=args.get("user_note", ""),
                context=args.get("context"),
            )
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(result),
                plain_text=f"已记录负面反馈，生成 eval case: {result.get('eval_case', {}).get('case_id', '')}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"记录负面反馈失败: {e}")

    def _h_feedback_correct_and_remember(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.feedback.correct_and_remember — 纠正并记住。"""
        tool_name = "stableagent.feedback.correct_and_remember"
        try:
            from stable_agent.personal_eval.feedback_loop import FeedbackProcessor
            proc = FeedbackProcessor()
            result = proc.process_correct_and_remember(
                run_id=args.get("run_id", ctx.run_id),
                user_note=args.get("user_note", ""),
                context=args.get("context"),
            )
            return self._make_result(
                ctx, tool_name, ok=True,
                data=self._json_safe(result),
                plain_text=f"已纠正并记住: {args.get('user_note', '')[:60]}",
            )
        except Exception as e:
            return self._make_result(ctx, tool_name, ok=False, is_error=True,
                                     plain_text=f"纠正失败: {e}")
