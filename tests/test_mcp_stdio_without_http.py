"""tests/test_mcp_stdio_without_http.py — stdio MCP 脱离 HTTP 测试。

验证 stdio MCP 的 local runtime 路径。
"""

from __future__ import annotations

import pytest

import stable_agent.mcp_stdio as mcp_stdio


class TestMcpStdioLocalRuntime:
    """stdio MCP local runtime 支持测试。"""

    def test_use_http_mode_default_false(self):
        """默认不使用 HTTP 模式。"""
        assert mcp_stdio._use_http_mode() is False

    def test_use_http_mode_with_env(self, monkeypatch):
        """环境变量 STABLE_AGENT_USE_HTTP=true 时使用 HTTP。"""
        monkeypatch.setenv("STABLE_AGENT_USE_HTTP", "true")
        assert mcp_stdio._use_http_mode() is True

    def test_use_http_mode_with_env_1(self, monkeypatch):
        """环境变量 STABLE_AGENT_USE_HTTP=1 时使用 HTTP。"""
        monkeypatch.setenv("STABLE_AGENT_USE_HTTP", "1")
        assert mcp_stdio._use_http_mode() is True

    def test_has_call_via_local_runtime(self):
        """必须有 _call_via_local_runtime 函数。"""
        assert hasattr(mcp_stdio, "_call_via_local_runtime")

    def test_handle_initialize_works(self):
        """initialize 方法仍然正常工作。"""
        result = mcp_stdio._handle_initialize(1)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "protocolVersion" in result["result"]
