"""StableAgent stdio MCP Server — V11.5.

把 CLI 包装成标准 stdio MCP server，让 Claude Code 可以通过本地命令加载 StableAgent。

用法：
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio --profile minimal

Claude Code 配置 (.mcp.json)：
{
  "mcpServers": {
    "stableagent-stdio": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--profile", "minimal"],
      "env": {
        "PYTHONPATH": "/path/to/OS-Agent",
        "STABLE_AGENT_TOOL_PROFILE": "minimal"
      }
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

# 配置日志到 stderr，stdout 只能写 JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("stable_agent.mcp_stdio")

# 版本信息
SERVER_NAME = "StableAgent OS stdio"
SERVER_VERSION = "11.5.0"
PROTOCOL_VERSION = "2024-11-05"

# 核心工具列表（最小集，复用 HTTP MCP 的工具定义）
# V11.5: 使用 profile 过滤
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

    V11.5: 使用 profile 过滤工具列表。
    """
    tools = _get_tools_for_profile()
    return _make_response(req_id, {
        "tools": tools,
    })


def _handle_tools_call(req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    """处理 tools/call 方法。

    V12.0: 优先使用 local runtime，不需要 HTTP server。
    如果 --http 模式，回退到 HTTP MCP。
    """
    tool_name: str = params.get("name", "")
    arguments: dict[str, Any] = params.get("arguments", {})

    if not tool_name:
        return _make_error(req_id, -32602, "缺少必要参数：name")

    # 检查工具是否在列表中
    tools = _get_tools_for_profile()
    tool_names = {t["name"] for t in tools}
    if tool_name not in tool_names:
        return _make_error(req_id, -32602, f"未知工具：{tool_name}")

    # V12.0: 默认使用 local runtime (不需要启动 HTTP server)
    if not _use_http_mode():
        try:
            result = _call_via_local_runtime(tool_name, arguments)
            return _make_response(req_id, result)
        except Exception as exc:
            logger.warning("Local runtime failed, trying HTTP fallback: %s", exc)

    # HTTP 回退路径
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
                "error": f"工具调用失败: {exc}",
                "suggestion": "Local runtime 初始化失败，请检查 PYTHONPATH 和依赖",
            },
            "isError": True,
        })


def _use_http_mode() -> bool:
    """判断是否使用 HTTP 模式。"""
    import os
    return os.environ.get("STABLE_AGENT_USE_HTTP", "").lower() in ("1", "true", "yes")


def _call_via_local_runtime(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """通过 local runtime 调用工具。"""
    from stable_agent.runtime.local_runtime import LocalStableAgentRuntime

    # 使用模块级单例
    global _local_runtime
    if '_local_runtime' not in globals() or _local_runtime is None:
        _local_runtime = LocalStableAgentRuntime()

    return _local_runtime.call_tool(tool_name, arguments)


# 模块级 local runtime 单例
_local_runtime = None


def _get_tools_for_profile() -> list[dict[str, Any]]:
    """根据当前 profile 返回工具列表。

    V11.5: 支持 tool_profiles 过滤。
    """
    try:
        from stable_agent.gateway.tool_profiles import should_expose_tool
        return [t for t in CORE_TOOLS if should_expose_tool(t["name"])]
    except ImportError:
        # 如果 tool_profiles 不可用，返回全部
        return CORE_TOOLS


def main() -> None:
    """stdio MCP server 主循环。"""
    # V11.5: 解析 --profile 参数
    parser = argparse.ArgumentParser(description="StableAgent stdio MCP Server")
    parser.add_argument("--profile", default="minimal", choices=["minimal", "default", "full"],
                        help="工具暴露级别 (默认: minimal)")
    args, _ = parser.parse_known_args()

    # 设置环境变量
    os.environ["STABLE_AGENT_TOOL_PROFILE"] = args.profile

    logger.info("StableAgent stdio MCP server 启动 (profile=%s)", args.profile)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            error_response = _make_error(None, -32700, f"JSON 解析错误：{exc}")
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
