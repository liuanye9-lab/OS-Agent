"""StableAgent stdio MCP Server — V11.4 + Phase 1.

把 CLI 包装成标准 stdio MCP server，让 Claude Code 可以通过本地命令加载 StableAgent。

Phase 1 新增:
  - ``--local`` 旗标 / ``STABLE_AGENT_RUNTIME_MODE=local`` 环境变量 → 使用
    in-process LocalRuntime,**完全不依赖 HTTP server**
  - ``--profile {minimal,default,full}`` / ``STABLE_AGENT_TOOL_PROFILE`` →
    限制对外暴露的工具数量(minimal ≤ 12)

默认行为(无旗标 + 无环境变量):仍然走 HTTP MCP(127.0.0.1:8000),向后
兼容 V11.4 客户端配置。

用法:
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio                   # HTTP 模式(V11.4 默认)
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio --local            # in-process 模式
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio --profile minimal  # 限制工具暴露面

Claude Code 配置 (.mcp.json) — Phase 1 推荐:
{
  "mcpServers": {
    "stableagent-stdio": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--local", "--profile", "minimal"],
      "env": {"PYTHONPATH": "/path/to/OS-Agent"}
    }
  }
}
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

# 配置日志到 stderr,stdout 只能写 JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("stable_agent.mcp_stdio")

# 版本信息
SERVER_NAME = "StableAgent OS stdio"
SERVER_VERSION = "11.4.0"
PROTOCOL_VERSION = "2024-11-05"

# Phase 1: 运行时与 profile 状态(由 main() 设置,_handle_tools_call 读取)
_RUNTIME_MODE: str = "http"  # "http" | "local"
_PROFILE: str | None = None

# 核心工具列表（最小集，复用 HTTP MCP 的工具定义）
CORE_TOOLS = [
    {
        "name": "stableagent.task.os_agent",
        "description": "端到端处理一个用户任务，返回 run_id 和 Dashboard URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string", "description": "用户任务描述"},
                "open_dashboard": {"type": "boolean", "default": False, "description": "是否自动打开 Dashboard"},
            },
            "required": ["task_input"],
        },
    },
    {
        "name": "stableagent.feedback.remember",
        "description": "记住这个",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID"},
                "note": {"type": "string", "description": "用户备注"},
            },
            "required": ["run_id", "note"],
        },
    },
    {
        "name": "stableagent.feedback.dont_do_this_again",
        "description": "下次别这样",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID"},
                "note": {"type": "string", "description": "用户备注"},
            },
            "required": ["run_id", "note"],
        },
    },
    {
        "name": "stableagent.feedback.correct_and_remember",
        "description": "纠正表达习惯并记住",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run ID"},
                "phrase": {"type": "string", "description": "需要纠正的表达"},
                "meaning": {"type": "string", "description": "正确含义"},
            },
            "required": ["run_id", "phrase", "meaning"],
        },
    },
    {
        "name": "stableagent.token.summary",
        "description": "Token 使用摘要",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 7, "description": "统计天数"},
            },
        },
    },
    {
        "name": "stableagent.memory.health",
        "description": "记忆健康报告",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "stableagent.capsule.status",
        "description": "胶囊状态",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "stableagent.effectiveness.summary",
        "description": "效果评估摘要",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _make_response(req_id: Any, result: Any) -> dict[str, Any]:
    """构造 JSON-RPC 成功响应。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def _make_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    """构造 JSON-RPC 错误响应。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _handle_initialize(req_id: Any) -> dict[str, Any]:
    """处理 initialize 方法。"""
    return _make_response(req_id, {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
        "capabilities": {
            "tools": {},
        },
    })


def _handle_tools_list(req_id: Any) -> dict[str, Any]:
    """处理 tools/list 方法。

    Phase 1: local 模式从 LocalRuntime 拉真实工具列表(覆盖 47 个注册工具),
    然后按 ``--profile`` 过滤;HTTP 模式仍使用静态 ``CORE_TOOLS``(8 个,
    保持 V11.4 行为)。
    """
    if _RUNTIME_MODE == "local":
        try:
            from stable_agent.gateway.tool_profiles import filter_tool_list
            from stable_agent.runtime.local_runtime import get_default_runtime
            tools = get_default_runtime().list_tools()
            tools = filter_tool_list(tools, profile=_PROFILE)
            return _make_response(req_id, {"tools": tools})
        except Exception as exc:
            logger.exception("local tools/list 失败")
            return _make_error(req_id, -32603, f"tools/list 失败: {exc}")
    return _make_response(req_id, {"tools": CORE_TOOLS})


def _handle_tools_call_local(req_id: Any, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Phase 1 — in-process tool call via LocalRuntime,**不走 HTTP**."""
    try:
        from stable_agent.runtime.local_runtime import get_default_runtime
        runtime = get_default_runtime()
        rpc_result = runtime.call_tool(tool_name, arguments)
        return _make_response(req_id, rpc_result)
    except Exception as exc:
        logger.exception("local tools/call 失败: tool=%s", tool_name)
        return _make_response(req_id, {
            "content": [{"type": "text", "text": f"工具调用失败:{exc}"}],
            "structuredContent": {
                "ok": False,
                "run_id": "",
                "error": f"LocalRuntime 调用失败: {exc}",
            },
            "isError": True,
        })


def _handle_tools_call(req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    """处理 tools/call 方法。

    Phase 1: 默认 HTTP 模式(V11.4 行为);``--local`` 时走 LocalRuntime。
    """
    tool_name: str = params.get("name", "")
    arguments: dict[str, Any] = params.get("arguments", {})

    if not tool_name:
        return _make_error(req_id, -32602, "缺少必要参数:name")

    # Phase 1: in-process path. LocalRuntime 自己处理未注册工具。
    if _RUNTIME_MODE == "local":
        return _handle_tools_call_local(req_id, tool_name, arguments)

    # 检查工具是否在 HTTP 模式静态列表中(保留 V11.4 行为)
    tool_names = {t["name"] for t in CORE_TOOLS}
    if tool_name not in tool_names:
        return _make_error(req_id, -32602, f"未知工具:{tool_name}")

    # 通过 HTTP MCP 调用实际工具
    try:
        import urllib.request

        rpc_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": f"stdio-{tool_name}",
        }

        data = json.dumps(rpc_body).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/mcp/",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=60.0) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # 返回 MCP 格式的响应
        if "error" in result:
            return _make_response(req_id, {
                "content": [{"type": "text", "text": f"JSON-RPC 错误: {result['error'].get('message', '未知错误')}"}],
                "structuredContent": {
                    "ok": False,
                    "error": result['error'].get('message', '未知错误'),
                },
                "isError": True,
            })

        rpc_result = result.get("result", {})
        return _make_response(req_id, rpc_result)

    except Exception as exc:
        logger.exception("tools/call 失败: tool=%s", tool_name)
        return _make_response(req_id, {
            "content": [{"type": "text", "text": f"工具调用失败：{exc}"}],
            "structuredContent": {
                "ok": False,
                "run_id": "",
                "error": f"StableAgent server 未启动或请求失败: {exc}",
                "suggestion": "请先运行: PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve",
            },
            "isError": True,
        })


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse stdio MCP CLI flags(Phase 1)."""
    parser = argparse.ArgumentParser(prog="stable_agent.mcp_stdio")
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="使用 in-process LocalRuntime,完全不依赖 HTTP server",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        default=False,
        help="强制 HTTP MCP 模式(覆盖 --local 和环境变量)",
    )
    parser.add_argument(
        "--profile",
        choices=("minimal", "default", "full"),
        default=None,
        help="工具暴露面(默认 minimal,通过 STABLE_AGENT_TOOL_PROFILE 配置)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """stdio MCP server 主循环。Phase 1: 支持 ``--local`` / ``--profile``。"""
    global _RUNTIME_MODE, _PROFILE

    args = _parse_args(argv)

    # 解析 runtime mode:CLI 旗标 > 环境变量 > 默认 HTTP(V11.4 兼容)
    if args.http:
        _RUNTIME_MODE = "http"
    elif args.local:
        _RUNTIME_MODE = "local"
    elif os.environ.get("STABLE_AGENT_RUNTIME_MODE", "").lower() == "local":
        _RUNTIME_MODE = "local"
    else:
        _RUNTIME_MODE = "http"

    # 解析 profile:CLI 旗标 > 环境变量 > minimal(stdio 默认)
    if args.profile:
        _PROFILE = args.profile
    else:
        _PROFILE = os.environ.get("STABLE_AGENT_TOOL_PROFILE", "minimal")

    logger.info(
        "StableAgent stdio MCP server 启动 (mode=%s, profile=%s)",
        _RUNTIME_MODE, _PROFILE,
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            error_response = _make_error(None, -32700, f"JSON 解析错误:{exc}")
            print(json.dumps(error_response), flush=True)
            continue

        method: str = request.get("method", "")
        req_id = request.get("id")
        params: dict[str, Any] = request.get("params", {})

        if method == "initialize":
            response = _handle_initialize(req_id)
        elif method == "tools/list":
            response = _handle_tools_list(req_id)
        elif method == "tools/call":
            response = _handle_tools_call(req_id, params)
        elif method == "notifications/initialized":
            # 忽略通知
            continue
        else:
            response = _make_error(req_id, -32601, f"Method not found: {method}")

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
