"""ResponseAdapter — 将 StableAgentToolResult 转换为 MCP 标准格式。

提供三组转换：工具调用结果 → MCP content、错误 → 错误响应、
工具列表 → JSON-RPC tools/list 响应。

用法::

    adapter = ResponseAdapter()
    mcp_response = adapter.to_mcp_content(tool_result)
    error_response = adapter.to_error_response(run_id, tool_name, "失败原因")
    tools_list = adapter.to_tools_list_response(tools)
"""

from __future__ import annotations

from typing import Any

from stable_agent.models import StableAgentToolResult


class ResponseAdapter:
    """将 StableAgentToolResult 转换为 MCP content 格式。

    负责 V5 工具返回结果到 MCP 协议格式的标准化转换，
    支持成功响应、错误响应和 tools/list 响应的生成。
    """

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def to_mcp_content(self, result: StableAgentToolResult) -> dict[str, Any]:
        """将 StableAgentToolResult 转换为 MCP content 格式。

        生成标准的 MCP tools/call 响应，包含 content 数组和
        structuredContent 对象。

        Args:
            result: StableAgentToolResult 实例。

        Returns:
            MCP 格式的 content 响应字典，结构为：
            {
                "content": [{"type": "text", "text": "..."}],
                "structuredContent": {...},
                "isError": bool
            }

        Examples:
            >>> result = StableAgentToolResult(
            ...     ok=True, run_id="r1", tool_name="test.tool",
            ...     plain_text="成功", data={"count": 5})
            >>> adapter = ResponseAdapter()
            >>> resp = adapter.to_mcp_content(result)
            >>> resp["content"][0]["type"]
            'text'
            >>> resp["structuredContent"]["ok"]
            True
        """
        # V11.4: 提取 data 中的核心字段到顶层，方便 Claude Code 直接访问
        data = result.data or {}

        # observer_url: 从 run_id 构建完整路径
        observer_url = f"/observe/{result.run_id}" if result.run_id else ""

        return {
            "content": [
                {"type": "text", "text": result.plain_text}
            ],
            "structuredContent": {
                # 核心字段（顶层）
                "ok": result.ok,
                "run_id": result.run_id,
                "dashboard_url": result.dashboard_url or result.trace_url or f"/runs/{result.run_id}",
                "observer_url": observer_url,
                "missing_required_events": data.get("missing_required_events", []),
                "understanding_trace": data.get("understanding_trace"),
                "token_report": data.get("token_report"),
                "expression_matches": data.get("expression_matches"),
                "learning_impact_report": data.get("learning_impact_report"),
                "memory_hit_report": data.get("memory_hit_report"),
                # V11.4: 错误信息
                "error": data.get("error") if not result.ok else None,
                # 工具元数据
                "tool_call_id": result.tool_call_id,
                "tool_name": result.tool_name,
                "data": data,
                "warnings": result.warnings,
                "next_actions": result.next_actions,
                "trace_url": result.trace_url or f"/runs/{result.run_id}",
                # Commercial SaaS (P0): 完整状态字段
                "current_stage": data.get("current_stage") or data.get("stage", "execution"),
                "progress_pct": data.get("progress_pct"),
                "status_text_zh": data.get("status_text_zh") or result.plain_text_zh or result.plain_text,
                "status_text_en": data.get("status_text_en") or result.plain_text_en or result.plain_text,
                "plain_text_zh": result.plain_text_zh or result.plain_text,
                "plain_text_en": result.plain_text_en or result.plain_text,
                "avatar_state": data.get("avatar_state"),
                "decision_summary_zh": data.get("decision_summary_zh"),
                "decision_summary_en": data.get("decision_summary_en"),
                "why_zh": data.get("why_zh"),
                "why_en": data.get("why_en"),
            },
            "isError": result.is_error,
        }

    def to_error_response(
        self,
        run_id: str,
        tool_name: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """生成 MCP 错误响应。

        当工具执行失败或出现异常时，使用此方法生成标准化错误响应。

        Args:
            run_id: 运行 ID。
            tool_name: 工具名称。
            error_msg: 错误描述信息。

        Returns:
            MCP 格式的错误响应字典。

        Examples:
            >>> adapter = ResponseAdapter()
            >>> resp = adapter.to_error_response("r1", "test.tool", "参数无效")
            >>> resp["isError"]
            True
            >>> resp["content"][0]["text"]
            '参数无效'
        """
        observer_url = f"/observe/{run_id}" if run_id else ""

        return {
            "content": [
                {"type": "text", "text": error_msg}
            ],
            "structuredContent": {
                # 核心字段（顶层）
                "ok": False,
                "run_id": run_id,
                "dashboard_url": f"/runs/{run_id}",
                "observer_url": observer_url,
                "missing_required_events": [],
                "understanding_trace": None,
                "token_report": None,
                "expression_matches": None,
                "error": error_msg,
                # 工具元数据
                "tool_name": tool_name,
                "data": {},
                "warnings": [],
                "next_actions": [],
                "trace_url": f"/runs/{run_id}",
            },
            "isError": True,
        }

    @staticmethod
    def _normalize_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """确保单个工具定义包含 MCP 标准字段 inputSchema。

        优先使用 inputSchema；若缺失则从 input_schema 转换；
        两者都不存在时使用 {"type": "object", "properties": {}}。
        """
        normalized = dict(tool)
        schema = normalized.pop("inputSchema", None) or normalized.pop("input_schema", None)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        normalized["inputSchema"] = schema
        return normalized

    def to_tools_list_response(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """生成 MCP tools/list 的 JSON-RPC 响应。

        将工具定义列表包装为标准的 JSON-RPC 2.0 响应格式。
        自动将每个工具的 input_schema 转换为 MCP 标准的 inputSchema。

        Args:
            tools: 工具定义列表，每个元素包含 name、description、inputSchema。

        Returns:
            JSON-RPC 2.0 格式的 tools/list 响应字典。

        Examples:
            >>> adapter = ResponseAdapter()
            >>> tools = [{"name": "test.tool", "description": "测试工具"}]
            >>> resp = adapter.to_tools_list_response(tools)
            >>> resp["jsonrpc"]
            '2.0'
            >>> resp["result"]["tools"][0]["name"]
            'test.tool'
        """
        normalized_tools = [self._normalize_tool(t) for t in tools]
        return {
            "jsonrpc": "2.0",
            "id": None,
            "result": {"tools": normalized_tools},
        }
