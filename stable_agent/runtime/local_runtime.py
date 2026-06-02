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
            from stable_agent.gateway.tool_router import ToolRouter
            from stable_agent.gateway.run_context import RunContext

            # 创建 ToolRouter (会自动初始化 RunStore, EventStream)
            self._tool_router = ToolRouter()

            # 创建 Orchestrator
            from stable_agent.orchestrator import Orchestrator
            self._orchestrator = Orchestrator()

            # 创建 UnifiedToolRegistry
            from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
            self._registry = UnifiedToolRegistry(
                orchestrator=self._orchestrator,
                tool_router=self._tool_router,
            )

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
            from stable_agent.gateway.run_context import RunContext

            # 构造 RunContext
            run_id = f"local_{int(time.time() * 1000)}"
            ctx = RunContext(
                run_id=run_id,
                trace_id=f"trace_{run_id}",
                tool_name=tool_name,
            )

            # 调用 handler
            result = self._registry.call_tool(ctx, tool_name, arguments)

            # 转换为 MCP-compatible 格式
            if hasattr(result, 'to_dict'):
                data = result.to_dict()
            elif isinstance(result, dict):
                data = result
            else:
                data = {"ok": False, "error": f"Unexpected result type: {type(result)}"}

            return {
                "content": [{"type": "text", "text": data.get("plain_text", str(data))}],
                "structuredContent": data,
                "isError": data.get("is_error", False),
            }

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
