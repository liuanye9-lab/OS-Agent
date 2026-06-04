"""stable_agent/runtime/local_runtime.py — LocalStableAgentRuntime。

让 CLI 和 stdio MCP 不依赖 HTTP server，直接在进程内调用工具。

职责：
- 构造 RunContext
- 调用 UnifiedToolRegistry handler
- 返回 MCP-compatible result
- 可选写 RunStore

不负责：
- HTTP server
- WebSocket
- Dashboard 静态文件
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class LocalStableAgentRuntime:
    """本地运行时。

    直接在进程内调用 UnifiedToolRegistry 的 handler，
    不依赖 HTTP server。
    """

    def __init__(self):
        self._registry = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """延迟初始化 UnifiedToolRegistry + Orchestrator。"""
        if self._initialized:
            return

        try:
            # 创建 Orchestrator
            from stable_agent.orchestrator import StableAgentOrchestrator
            self._orchestrator = StableAgentOrchestrator()

            # Registry and router depend on each other. Build the registry first,
            # then inject the fully constructed router back into it.
            from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
            from stable_agent.gateway.tool_router import ToolRouter
            self._registry = UnifiedToolRegistry(orchestrator=self._orchestrator)
            self._tool_router = ToolRouter(
                registry=self._registry,
                security_policy=getattr(self._orchestrator, "security_policy", None),
                approval_manager=getattr(self._orchestrator, "approval_manager", None),
                event_bus=getattr(self._orchestrator, "event_bus", None),
            )
            self._registry._tool_router = self._tool_router

            self._initialized = True
            logger.info("LocalStableAgentRuntime initialized successfully")
        except Exception as exc:
            logger.error("LocalStableAgentRuntime initialization failed: %s", exc)
            raise

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """调用工具，返回 MCP-compatible result。

        Args:
            tool_name: 工具名称，如 "stableagent.task.os_agent"。
            arguments: 工具参数。

        Returns:
            包含 content, structuredContent, isError 的字典。
        """
        self._ensure_initialized()

        try:
            run_id = f"local_{int(time.time() * 1000)}"
            routed_arguments = {**arguments, "run_id": arguments.get("run_id") or run_id}
            result = self._tool_router.route(tool_name, routed_arguments)

            from stable_agent.gateway.response_adapter import ResponseAdapter
            return ResponseAdapter().to_mcp_content(result)

        except Exception as exc:
            logger.exception("Local tool call failed: tool=%s", tool_name)
            return {
                "content": [{"type": "text", "text": f"工具调用失败: {exc}"}],
                "structuredContent": {
                    "ok": False,
                    "error": str(exc),
                },
                "isError": True,
            }

    def health_check(self) -> dict[str, Any]:
        """健康检查。"""
        try:
            self._ensure_initialized()
            return {"ok": True, "runtime": "local", "initialized": self._initialized}
        except Exception as exc:
            return {"ok": False, "runtime": "local", "error": str(exc)}
