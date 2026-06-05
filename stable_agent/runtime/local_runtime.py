"""LocalRuntime — Phase 1 in-process tool runtime.

让 CLI 和 stdio MCP **无需** HTTP server 即可调用 `stableagent.task.os_agent`
及其它已注册工具。LocalRuntime 复用 `MCPGateway` 的内部组件
(`UnifiedToolRegistry` / `ToolRouter` / `ResponseAdapter`) — 因此输出 dict
形状与 HTTP MCP 完全一致,Phase 0 契约 snapshot 测试同时覆盖两条路径。

设计要点:
- **不动** `_h_task_os_agent` 540 行 handler(Phase 0 blocker B1 — façade only)
- **不替换** HTTP MCP — 它仍然可用,LocalRuntime 是并行入口
- Orchestrator 重量级,采用懒构造单例

用法::

    from stable_agent.runtime.local_runtime import LocalRuntime

    runtime = LocalRuntime()
    response = runtime.call_tool(
        "stableagent.task.os_agent",
        {"task_input": "demo", "open_dashboard": False},
    )
    # response is the same dict shape as HTTP MCP's `result`:
    #   {"content": [...], "structuredContent": {...}, "isError": bool}

参考 [docs/harness/PHASE1_RUNTIME.md](../../docs/harness/PHASE1_RUNTIME.md)。
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class LocalRuntime:
    """In-process tool runtime — same dict shape as HTTP MCP, no network.

    Components are constructed lazily on first `call_tool` because the
    underlying `StableAgentOrchestrator` is heavy(LLM client, evaluator,
    storage, etc.) and most CLI/stdio sessions only call one or two tools.

    Thread-safe initialization via :class:`threading.Lock`.

    Attributes:
        _orchestrator: ``StableAgentOrchestrator`` (lazy).
        _registry: ``UnifiedToolRegistry`` (lazy).
        _router: ``ToolRouter`` (lazy).
        _adapter: ``ResponseAdapter`` (lazy).
        _lock: init guard.
    """

    def __init__(self, orchestrator: Any = None) -> None:
        """Build a LocalRuntime, deferring expensive init to first call.

        Args:
            orchestrator: pre-built ``StableAgentOrchestrator`` (mainly for
                tests). When ``None``, runtime constructs one on first use.
        """
        self._orchestrator: Any = orchestrator
        self._registry: Any = None
        self._router: Any = None
        self._adapter: Any = None
        self._lock: Lock = Lock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a registered tool in-process.

        Args:
            tool_name: full tool name, e.g. ``"stableagent.task.os_agent"``.
            arguments: tool args dict (empty dict allowed).

        Returns:
            Dict matching HTTP MCP's ``result`` payload:
            ``{"content": [...], "structuredContent": {...}, "isError": bool}``.

            On unknown tool / handler error, the dict still contains
            ``structuredContent.ok=False`` and ``error`` — never raises.
        """
        args = dict(arguments or {})
        self._ensure_initialized()
        try:
            tool_result = self._router.route(tool_name, args)
        except Exception as exc:  # pragma: no cover — defensive only
            logger.exception("LocalRuntime route failed: tool=%s", tool_name)
            return self._adapter.to_error_response(
                run_id="",
                tool_name=tool_name,
                error_msg=f"工具调用失败：{exc}",
            )
        return self._adapter.to_mcp_content(tool_result)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP-format tool list (same shape as ``tools/list``)."""
        self._ensure_initialized()
        return self._registry.list_tools()

    @property
    def orchestrator(self) -> Any:
        """Expose orchestrator for tests / advanced wiring (lazy-built)."""
        self._ensure_initialized()
        return self._orchestrator

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _ensure_initialized(self) -> None:
        if self._registry is not None and self._router is not None:
            return
        with self._lock:
            if self._registry is not None and self._router is not None:
                return
            self._build_components()

    def _build_components(self) -> None:
        """Construct registry/router/adapter, mirroring ``MCPGateway.__init__``."""
        # Imported lazily to avoid pulling FastAPI / orchestrator deps when
        # LocalRuntime is only inspected (e.g. CLI ``--help``).
        from stable_agent.gateway.response_adapter import ResponseAdapter
        from stable_agent.gateway.tool_router import ToolRouter
        from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
        from stable_agent.observation.event_stream import EventStream
        from stable_agent.observation.run_store import RunStore

        if self._orchestrator is None:
            self._orchestrator = self._build_orchestrator()

        run_store = RunStore()
        event_stream = EventStream()
        registry = UnifiedToolRegistry(self._orchestrator)
        router = ToolRouter(
            registry=registry,
            security_policy=getattr(self._orchestrator, "security_policy", None),
            approval_manager=getattr(self._orchestrator, "approval_manager", None),
            run_store=run_store,
            event_stream=event_stream,
            event_bus=getattr(self._orchestrator, "event_bus", None),
        )
        # V9.2: registry needs a back-reference so `_emit()` can write events
        # to RunStore + EventStream(契约不变量 — 见 PHASE0_CONTRACT §3.4).
        registry._tool_router = router

        self._registry = registry
        self._router = router
        self._adapter = ResponseAdapter()

    def _build_orchestrator(self) -> Any:
        """Construct a default orchestrator with shared LLM client."""
        from stable_agent.eval_and_bad_case import Evaluator
        from stable_agent.llm_factory import get_llm_client
        from stable_agent.orchestrator import StableAgentOrchestrator

        llm = get_llm_client()
        evaluator = Evaluator(llm_client=llm)
        return StableAgentOrchestrator(evaluator=evaluator, llm_client=llm)


# Module-level singleton for callers that don't want to manage lifetime.
_DEFAULT_RUNTIME: LocalRuntime | None = None
_DEFAULT_LOCK = Lock()


def get_default_runtime() -> LocalRuntime:
    """Return a process-wide :class:`LocalRuntime` singleton."""
    global _DEFAULT_RUNTIME
    if _DEFAULT_RUNTIME is not None:
        return _DEFAULT_RUNTIME
    with _DEFAULT_LOCK:
        if _DEFAULT_RUNTIME is None:
            _DEFAULT_RUNTIME = LocalRuntime()
    return _DEFAULT_RUNTIME
