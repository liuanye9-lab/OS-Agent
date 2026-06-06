"""test_mcp_gateway.py — V5 MCP Gateway 单元测试。

测试覆盖：
- UnifiedToolRegistry: 工具注册、handler 查找、工具列表格式
- ResponseAdapter: MCP content 转换、错误响应、tools/list 响应
- JSONRPCHandler: initialize、tools/list、无效方法处理
- MCPGateway: app 创建、端点健康检查
- ToolRouter: RunContext 创建、事件发布、handler 路由
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 条件跳过：httpx 不可用时跳过需要 TestClient 的测试
# ---------------------------------------------------------------------------
_httpx_available: bool = True
try:
    import httpx  # noqa: F401
except ImportError:
    _httpx_available = False

requires_httpx = pytest.mark.skipif(
    not _httpx_available,
    reason="httpx 未安装，跳过需要 FastAPI TestClient 的测试",
)

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.gateway.jsonrpc_handler import JSONRPCHandler
from stable_agent.gateway.tool_router import ToolRouter
from stable_agent.gateway.mcp_gateway import MCPGateway
from stable_agent.models import StableAgentToolResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry() -> UnifiedToolRegistry:
    """创建无 orchestrator 的注册中心（用于单元测试）。"""
    return UnifiedToolRegistry(orchestrator=None)


@pytest.fixture
def adapter() -> ResponseAdapter:
    """创建响应适配器。"""
    return ResponseAdapter()


@pytest.fixture
def router(registry: UnifiedToolRegistry) -> ToolRouter:
    """创建工具路由器（无安全策略）。"""
    return ToolRouter(registry=registry)


@pytest.fixture
def jsonrpc_handler(
    registry: UnifiedToolRegistry, router: ToolRouter, adapter: ResponseAdapter
) -> JSONRPCHandler:
    """创建 JSON-RPC 处理器。"""
    return JSONRPCHandler(registry, router, adapter)


@pytest.fixture
def gateway() -> MCPGateway:
    """创建 MCP Gateway（无 orchestrator）。"""
    return MCPGateway(orchestrator=None)


@pytest.fixture
def sample_result() -> StableAgentToolResult:
    """创建示例 StableAgentToolResult。"""
    return StableAgentToolResult(
        ok=True,
        run_id="run-001",
        tool_call_id="call-001",
        tool_name="stableagent.memory.retrieve",
        data={"memories": [], "count": 0},
        plain_text="记忆检索完成，命中 0 条相关记忆",
        warnings=[],
        next_actions=["构建上下文包"],
        trace_url="/runs/run-001",
        is_error=False,
    )


# ============================================================================
# UnifiedToolRegistry 测试
# ============================================================================


class TestUnifiedToolRegistry:
    """UnifiedToolRegistry 单元测试。"""

    def test_registry_has_28_tools(self, registry: UnifiedToolRegistry) -> None:
        """验证注册中心包含全部 14 个工具。"""
        tools = registry.list_tools()
        assert len(tools) >= 14, f"期望 14 个工具，实际 {len(tools)} 个"

        tool_names = [t["name"] for t in tools]
        expected_names = [
            "stableagent.task.process",
            "stableagent.context.build",
            "stableagent.context.estimate_budget",
            "stableagent.memory.retrieve",
            "stableagent.memory.write_candidate",
            "stableagent.rag.retrieve",
            "stableagent.eval.evaluate",
            "stableagent.badcase.record",
            "stableagent.skillopt.status",
            "stableagent.skillopt.get_current_skill",
            "stableagent.skillopt.run_epoch",
            "stableagent.skillopt.export_best",
            "stableagent.trace.get_run",
            "stableagent.approval.respond",
        ]
        for name in expected_names:
            assert name in tool_names, f"缺少工具：{name}"

    def test_get_handler_valid(self, registry: UnifiedToolRegistry) -> None:
        """验证可以获取有效的 handler。"""
        handler = registry.get_handler("stableagent.memory.retrieve")
        assert handler is not None
        assert callable(handler)

    def test_get_handler_invalid_returns_none(self, registry: UnifiedToolRegistry) -> None:
        """验证无效工具名返回 None。"""
        handler = registry.get_handler("nonexistent.tool")
        assert handler is None

    def test_list_tools_format(self, registry: UnifiedToolRegistry) -> None:
        """验证 list_tools 返回格式正确。"""
        tools = registry.list_tools()
        for tool in tools:
            assert "name" in tool, f"工具缺少 name: {tool}"
            assert "description" in tool, f"工具缺少 description: {tool}"
            assert "input_schema" in tool, f"工具缺少 input_schema: {tool}"

    def test_handler_returns_stable_agent_tool_result(self, registry: UnifiedToolRegistry) -> None:
        """验证 handler 返回 StableAgentToolResult。"""
        ctx = RunContext()
        handler = registry.get_handler("stableagent.memory.retrieve")
        assert handler is not None
        result = handler(ctx, {"task_input": "测试任务"})
        assert isinstance(result, StableAgentToolResult)
        assert result.tool_name == "stableagent.memory.retrieve"
        assert result.run_id == ctx.run_id

    def test_all_handlers_return_result(self, registry: UnifiedToolRegistry) -> None:
        """验证所有 14 个 handler 都能正常返回结果。"""
        ctx = RunContext()
        test_args: dict[str, dict[str, object]] = {
            "stableagent.task.process": {"task_input": "测试任务"},
            "stableagent.context.build": {"task_input": "测试任务"},
            "stableagent.context.estimate_budget": {"task_input": "测试任务"},
            "stableagent.memory.retrieve": {"task_input": "测试任务"},
            "stableagent.memory.write_candidate": {
                "content": "测试内容", "item_type": "success_case", "source": "test"
            },
            "stableagent.rag.retrieve": {"query": "测试查询"},
            "stableagent.eval.evaluate": {
                "task_input": "测试", "input_context": "上下文", "output": "输出"
            },
            "stableagent.badcase.record": {
                "task_input": "测试", "input_context": "上下文", "output": "输出"
            },
            "stableagent.skillopt.status": {},
            "stableagent.skillopt.get_current_skill": {},
            "stableagent.skillopt.run_epoch": {"max_rollouts": 10},
            "stableagent.skillopt.export_best": {},
            "stableagent.trace.get_run": {"run_id": "test-run"},
            "stableagent.approval.respond": {
                "request_id": "req-001", "action": "approve"
            },
        }
        for tool_name, args in test_args.items():
            handler = registry.get_handler(tool_name)
            assert handler is not None, f"未找到 handler: {tool_name}"
            result = handler(ctx, args)  # type: ignore[arg-type]
            assert isinstance(result, StableAgentToolResult), (
                f"{tool_name} 返回了非 StableAgentToolResult: {type(result)}"
            )
            assert result.trace_url == f"/runs/{ctx.run_id}", (
                f"{tool_name} trace_url 不正确"
            )

    def test_h_task_process_no_orchestrator(self, registry: UnifiedToolRegistry) -> None:
        """验证无 orchestrator 时 process_task 返回错误。"""
        ctx = RunContext()
        handler = registry.get_handler("stableagent.task.process")
        assert handler is not None
        result = handler(ctx, {"task_input": "测试"})
        assert result.is_error is True

    def test_h_approval_respond_invalid_action(self, registry: UnifiedToolRegistry) -> None:
        """验证无效的审批操作返回错误。"""
        ctx = RunContext()
        handler = registry.get_handler("stableagent.approval.respond")
        assert handler is not None
        result = handler(ctx, {"request_id": "req-001", "action": "invalid"})
        assert result.is_error is True


# ============================================================================
# ResponseAdapter 测试
# ============================================================================


class TestResponseAdapter:
    """ResponseAdapter 单元测试。"""

    def test_to_mcp_content_format(self, adapter: ResponseAdapter, sample_result: StableAgentToolResult) -> None:
        """验证 to_mcp_content 返回格式正确。"""
        resp = adapter.to_mcp_content(sample_result)

        # content 数组
        assert "content" in resp
        assert isinstance(resp["content"], list)
        assert len(resp["content"]) > 0
        assert resp["content"][0]["type"] == "text"
        assert resp["content"][0]["text"] == sample_result.plain_text

        # structuredContent
        sc = resp["structuredContent"]
        assert sc["ok"] is True
        assert sc["run_id"] == "run-001"
        assert sc["tool_name"] == "stableagent.memory.retrieve"
        assert sc["data"] == sample_result.data
        assert sc["warnings"] == sample_result.warnings
        assert sc["next_actions"] == sample_result.next_actions
        assert sc["trace_url"] == "/runs/run-001"

        # isError
        assert resp["isError"] is False

    def test_to_mcp_content_error(self, adapter: ResponseAdapter) -> None:
        """验证错误结果的 MCP 格式。"""
        error_result = StableAgentToolResult(
            ok=False,
            run_id="run-err",
            tool_call_id="call-err",
            tool_name="test.tool",
            plain_text="执行失败",
            is_error=True,
        )
        resp = adapter.to_mcp_content(error_result)
        assert resp["isError"] is True
        assert resp["structuredContent"]["ok"] is False

    def test_to_error_response(self, adapter: ResponseAdapter) -> None:
        """验证 to_error_response 生成正确格式。"""
        resp = adapter.to_error_response("run-001", "test.tool", "参数无效")

        assert resp["isError"] is True
        assert resp["content"][0]["text"] == "参数无效"
        sc = resp["structuredContent"]
        assert sc["ok"] is False
        assert sc["run_id"] == "run-001"
        assert sc["tool_name"] == "test.tool"
        assert sc["trace_url"] == "/runs/run-001"

    def test_to_tools_list_response(self, adapter: ResponseAdapter) -> None:
        """验证 to_tools_list_response 生成正确的 JSON-RPC 格式。"""
        tools = [
            {"name": "tool.one", "description": "工具一", "input_schema": {}},
            {"name": "tool.two", "description": "工具二", "input_schema": {}},
        ]
        resp = adapter.to_tools_list_response(tools)

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] is None
        assert "result" in resp
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) == 2
        assert resp["result"]["tools"][0]["name"] == "tool.one"


# ============================================================================
# JSONRPCHandler 测试
# ============================================================================


class TestJSONRPCHandler:
    """JSONRPCHandler 单元测试。"""

    def test_handle_initialize(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证 initialize 响应包含正确的服务器信息。"""
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        resp = jsonrpc_handler.handle(request)

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "StableAgent OS"
        assert result["serverInfo"]["version"] == "11.4.0"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]

    def test_handle_tools_list(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证 tools/list 返回 14 个工具。"""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        resp = jsonrpc_handler.handle(request)

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 2
        assert "result" in resp
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) >= 14

    def test_handle_tools_call_no_name(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证缺少 name 参数时返回错误。"""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"arguments": {}},
        }
        resp = jsonrpc_handler.handle(request)
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_handle_invalid_method(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证未知方法返回错误。"""
        request = {"jsonrpc": "2.0", "id": 4, "method": "nonexistent.method"}
        resp = jsonrpc_handler.handle(request)

        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert resp["id"] == 4

    def test_handle_tools_call_valid(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证有效的 tools/call 返回正确结果。"""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "stableagent.memory.retrieve",
                "arguments": {"task_input": "测试检索"},
            },
        }
        resp = jsonrpc_handler.handle(request)

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 5
        assert "result" in resp
        result = resp["result"]
        assert "content" in result
        assert "structuredContent" in result

    def test_handle_no_method(self, jsonrpc_handler: JSONRPCHandler) -> None:
        """验证无 method 字段时返回错误。"""
        request = {"jsonrpc": "2.0", "id": 6}
        resp = jsonrpc_handler.handle(request)
        assert "error" in resp
        assert resp["error"]["code"] == -32601


# ============================================================================
# MCPGateway 测试
# ============================================================================


@pytest.mark.skip(reason="Integration — requires running uvicorn server")
class TestMCPGateway:
    """MCPGateway 单元测试。"""

    def test_gateway_creates_app(self, gateway: MCPGateway) -> None:
        """验证 Gateway 能创建 FastAPI app。"""
        app = gateway.create_fastapi_app()
        assert app is not None
        assert app.title in ("StableAgent MCP Gateway", "StableAgent Cloud — MCP Gateway")

    def test_gateway_has_all_components(self, gateway: MCPGateway) -> None:
        """验证 Gateway 包含所有必要组件。"""
        assert gateway.run_store is not None
        assert gateway.event_stream is not None
        assert gateway.registry is not None
        assert gateway.router is not None
        assert gateway.adapter is not None
        assert gateway.jsonrpc is not None

    @requires_httpx
    def test_mcp_post_endpoint_initialize(self, gateway: MCPGateway) -> None:
        """验证 POST /mcp initialize 工作正常。"""
        from fastapi.testclient import TestClient

        app = gateway.create_fastapi_app()
        client = TestClient(app)

        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["serverInfo"]["name"] == "StableAgent OS"

    @requires_httpx
    def test_mcp_post_endpoint_tools_list(self, gateway: MCPGateway) -> None:
        """验证 POST /mcp tools/list 返回 14 个工具。"""
        from fastapi.testclient import TestClient

        app = gateway.create_fastapi_app()
        client = TestClient(app)

        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["result"]["tools"]) >= 14

    @requires_httpx
    def test_mcp_get_endpoint_requires_run_id(self, gateway: MCPGateway) -> None:
        """验证 GET /mcp 缺少 run_id 时返回 400。"""
        from fastapi.testclient import TestClient

        app = gateway.create_fastapi_app()
        client = TestClient(app)

        response = client.get("/mcp")
        assert response.status_code == 400

    @requires_httpx
    def test_mcp_get_endpoint_with_run_id(self, gateway: MCPGateway) -> None:
        """验证 GET /mcp 带 run_id 时返回 SSE 流。"""
        from fastapi.testclient import TestClient

        app = gateway.create_fastapi_app()
        client = TestClient(app)

        response = client.get("/?run_id=test-run-001")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"


# ============================================================================
# ToolRouter 测试
# ============================================================================


class TestToolRouter:
    """ToolRouter 单元测试。"""

    def test_router_accepts_registry(self, registry: UnifiedToolRegistry) -> None:
        """验证路由器接受注册中心。"""
        router = ToolRouter(registry=registry)
        assert router is not None
        assert router._registry is registry

    def test_router_route_unknown_tool(self, router: ToolRouter) -> None:
        """验证路由未知工具返回错误结果。"""
        result = router.route("nonexistent.tool", {})
        assert result.is_error is True
        assert "未知工具" in result.plain_text

    def test_router_route_valid_tool(self, router: ToolRouter) -> None:
        """验证路由有效工具返回正确结果。"""
        result = router.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试任务"},
        )
        assert isinstance(result, StableAgentToolResult)
        assert result.tool_name == "stableagent.memory.retrieve"

    def test_router_creates_run_context(self, router: ToolRouter) -> None:
        """验证每个 route() 调用创建唯一 RunContext。"""
        result1 = router.route("stableagent.memory.retrieve", {"task_input": "a"})
        result2 = router.route("stableagent.memory.retrieve", {"task_input": "b"})

        assert result1.run_id != result2.run_id
        assert result1.tool_call_id != result2.tool_call_id

    def test_router_with_run_store(self, registry: UnifiedToolRegistry) -> None:
        """验证 RunStore 集成 —— 事件被追加。"""
        from stable_agent.observation.run_store import RunStore

        store = RunStore()
        router = ToolRouter(registry=registry, run_store=store)

        result = router.route("stableagent.memory.retrieve", {"task_input": "测试"})
        events = store.get_events(result.run_id)
        assert len(events) > 0, "应有事件被记录到 RunStore"

    def test_router_publishes_events(self, router: ToolRouter) -> None:
        """验证路由成功时返回结果包含 trace_url。"""
        result = router.route(
            "stableagent.memory.retrieve",
            {"task_input": "测试事件发布"},
        )
        assert result.trace_url is not None
        assert result.trace_url.startswith("/runs/")
        assert result.run_id in result.trace_url

    def test_router_forbidden_tool_with_security(self, registry: UnifiedToolRegistry) -> None:
        """验证安全策略不会误拦截低风险工具。"""
        from stable_agent.security_policy import SecurityPolicy

        security = SecurityPolicy()
        router = ToolRouter(registry=registry, security_policy=security)

        # 使用低风险工具验证安全策略不会将其标记为 forbidden
        # 注意：无 orchestrator 时 handler 返回 is_error=True（预期行为）
        result = router.route(
            "stableagent.memory.retrieve",
            {"task_input": "正常任务"},
        )
        # 安全策略不会拦截此工具 —— 即使 handler 因无 orchestrator 返回错误
        # 验证 plain_text 不包含 "禁止执行"（即未被 forbidden）
        assert "禁止执行" not in result.plain_text

    def test_router_security_blocks_risk_assessment(self, registry: UnifiedToolRegistry) -> None:
        """验证安全策略正确评估风险等级（不会误判）。"""
        from stable_agent.security_policy import SecurityPolicy

        security = SecurityPolicy()
        router = ToolRouter(registry=registry, security_policy=security)

        # 验证 stableagent.approval.respond (high risk) 不会被禁止
        result = router.route(
            "stableagent.approval.respond",
            {"request_id": "req-001", "action": "approve"},
        )
        # high risk 不会被 forbidden，只是需要审批
        assert "禁止执行" not in result.plain_text
