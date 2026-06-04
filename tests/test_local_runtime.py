"""tests/test_local_runtime.py — Local Runtime 测试。

验证 LocalStableAgentRuntime 的初始化和接口。
"""

from __future__ import annotations

import pytest

from stable_agent.runtime.local_runtime import LocalStableAgentRuntime


class TestLocalRuntime:
    """Local Runtime 接口测试。"""

    def test_class_exists(self):
        """LocalStableAgentRuntime 类存在。"""
        assert LocalStableAgentRuntime is not None

    def test_has_call_tool(self):
        """必须有 call_tool 方法。"""
        assert hasattr(LocalStableAgentRuntime, "call_tool")

    def test_has_health_check(self):
        """必须有 health_check 方法。"""
        assert hasattr(LocalStableAgentRuntime, "health_check")

    def test_has_ensure_initialized(self):
        """必须有 _ensure_initialized 方法。"""
        assert hasattr(LocalStableAgentRuntime, "_ensure_initialized")

    def test_health_check_initializes_real_runtime(self):
        runtime = LocalStableAgentRuntime()
        result = runtime.health_check()
        assert result["ok"] is True
        assert result["initialized"] is True
