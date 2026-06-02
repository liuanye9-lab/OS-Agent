"""tests/test_os_agent_handler_slim.py — OSAgentHandler 瘦身测试。

验证 Phase 2 重构后的 handler 行数约束和委托行为。
"""

from __future__ import annotations

import inspect

import pytest

from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.core.os_agent_handler import OSAgentHandler
from stable_agent.core.contracts import ContractBuilder


class TestHandlerSlim:
    """_h_task_os_agent 瘦身约束。"""

    def test_handler_le_80_lines(self):
        """_h_task_os_agent 行数 ≤ 80。"""
        source = inspect.getsource(UnifiedToolRegistry._h_task_os_agent)
        line_count = len(source.strip().splitlines())
        assert line_count <= 80, f"_h_task_os_agent 有 {line_count} 行，超过 80 行限制"

    def test_handler_delegates_to_os_agent_handler(self):
        """_h_task_os_agent 必须委托给 OSAgentHandler。"""
        source = inspect.getsource(UnifiedToolRegistry._h_task_os_agent)
        assert "OSAgentHandler" in source

    def test_handler_no_inline_emit(self):
        """_h_task_os_agent 不应包含内联的 _emit 函数。"""
        source = inspect.getsource(UnifiedToolRegistry._h_task_os_agent)
        assert "def _emit(" not in source

    def test_handler_no_inline_proof_loop(self):
        """_h_task_os_agent 不应直接调用 proof_loop。"""
        source = inspect.getsource(UnifiedToolRegistry._h_task_os_agent)
        assert "proof_loop" not in source

    def test_handler_no_process_task(self):
        """_h_task_os_agent 不应直接调用 process_task。"""
        source = inspect.getsource(UnifiedToolRegistry._h_task_os_agent)
        assert "process_task" not in source


class TestOSAgentHandler:
    """OSAgentHandler 结构测试。"""

    def test_handler_has_handle_method(self):
        """OSAgentHandler 必须有 handle 方法。"""
        assert hasattr(OSAgentHandler, "handle")

    def test_handler_has_run_executor(self):
        """OSAgentHandler 必须有 _run_executor 方法。"""
        assert hasattr(OSAgentHandler, "_run_executor")

    def test_handler_has_run_curator(self):
        """OSAgentHandler 必须有 _run_curator 方法。"""
        assert hasattr(OSAgentHandler, "_run_curator")

    def test_handler_imports_correctly(self):
        """OSAgentHandler 可以正常导入。"""
        from stable_agent.core.os_agent_handler import OSAgentHandler as H
        assert H is not None


class TestContractBuilderIntegration:
    """ContractBuilder 集成验证。"""

    def test_contract_builder_importable(self):
        """ContractBuilder 可以正常导入。"""
        from stable_agent.core.contracts import ContractBuilder as CB
        assert CB is not None

    def test_contract_builder_has_build_tool_result(self):
        """ContractBuilder 必须有 build_tool_result 方法。"""
        assert hasattr(ContractBuilder, "build_tool_result")

    def test_contract_builder_has_to_dict(self):
        """ContractBuilder 必须有 to_dict 方法。"""
        assert hasattr(ContractBuilder, "to_dict")
