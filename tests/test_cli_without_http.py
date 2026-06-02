"""tests/test_cli_without_http.py — CLI 脱离 HTTP 测试。

验证 CLI 的 local runtime 支持。
"""

from __future__ import annotations

import pytest

import stable_agent.cli as cli


class TestCliLocalRuntime:
    """CLI local runtime 支持测试。"""

    def test_has_call_local_runtime(self):
        """CLI 必须有 _call_local_runtime 函数。"""
        assert hasattr(cli, "_call_local_runtime")

    def test_cmd_task_run_exists(self):
        """cmd_task_run 函数存在。"""
        assert hasattr(cli, "cmd_task_run")
