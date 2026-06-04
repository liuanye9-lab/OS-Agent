#!/usr/bin/env python3
"""StableAgent Capsule CLI — 胶囊管理 + CLI Mode 命令行工具。

Usage:
    # Capsule 管理
    python -m stable_agent.cli capsule init
    python -m stable_agent.cli capsule status
    python -m stable_agent.cli capsule doctor
    python -m stable_agent.cli capsule export [output.zip]
    python -m stable_agent.cli capsule import <zip_path> [--target PATH]

    # 记忆 & Token
    python -m stable_agent.cli memory health
    python -m stable_agent.cli token summary [--days 7]

    # MCP 配置
    python -m stable_agent.cli mcp config

    # CLI Mode
    python -m stable_agent.cli serve [--host 127.0.0.1] [--port 8000]
    python -m stable_agent.cli health [--json]
    python -m stable_agent.cli task run -t "任务内容" [--open-dashboard] [--json]
    python -m stable_agent.cli task estimate -t "任务内容" [--json]
    python -m stable_agent.cli feedback remember --run-id ID --note "..." [--json]
    python -m stable_agent.cli feedback dont --run-id ID --note "..." [--json]
    python -m stable_agent.cli feedback correct --run-id ID --phrase "..." --meaning "..." [--json]
    python -m stable_agent.cli effectiveness summary [--json]
    python -m stable_agent.cli effectiveness task create --task-id T01 --description "..." [--json]
    python -m stable_agent.cli effectiveness run record --task-id T01 --mode stableagent [--json]
    python -m stable_agent.cli dashboard open [--run-id ID] [--print-only]

    # V12.1: Learning Impact Report
    python -m stable_agent.cli impact show --run-id ID [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

# Default server config
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def normalize_h_agent_output(data: dict) -> dict:
    """Normalize CLI output to h-agent-v1 contract format."""
    result = {
        "ok": data.get("ok", False),
        "run_id": data.get("run_id", ""),
        "dashboard_url": data.get("dashboard_url", ""),
        "observer_url": data.get("observer_url", ""),
        "output_text": data.get("output_text") or data.get("text") or data.get("output") or "",
        "eval_passed": data.get("eval_passed", False),
        "eval_score": data.get("eval_score", None),
        "missing_required_events": data.get("missing_required_events", []),
        "understanding_trace": data.get("understanding_trace", None),
        "token_report": data.get("token_report", None),
        "error": data.get("error", None),
        "suggestion": data.get("suggestion", None),
        "contract_version": "h-agent-v1",
    }
    # Auto-fill error if failed but no error message
    if not result["ok"] and not result["error"]:
        result["error"] = "工具调用失败，原因未知"
    # Auto-fill output_text if success but empty
    if result["ok"] and not result["output_text"]:
        result["output_text"] = "任务执行完成"
    # Preserve extra fields for backward compatibility
    for key in data:
        if key not in result:
            result[key] = data[key]
    return result


def _base_url(args: argparse.Namespace) -> str:
    host = getattr(args, "host", DEFAULT_HOST)
    port = getattr(args, "port", DEFAULT_PORT)
    return f"http://{host}:{port}"


def _http_get(url: str, timeout: float = 5.0) -> dict:
    """GET request returning JSON dict. Raises on failure."""
    import urllib.request
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post(url: str, body: dict, timeout: float = 30.0) -> dict:
    """POST JSON request returning JSON dict. Raises on failure."""
    import urllib.request
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_local_runtime(task_input: str, open_dashboard: bool = True) -> dict:
    """通过 local runtime 调用 stableagent.task.os_agent。"""
    from stable_agent.runtime.local_runtime import LocalStableAgentRuntime

    runtime = LocalStableAgentRuntime()
    raw = runtime.call_tool("stableagent.task.os_agent", {
        "task_input": task_input,
        "open_dashboard": open_dashboard,
    })

    sc = raw.get("structuredContent", {})
    content = raw.get("content", [])
    content_text = content[0].get("text", "") if content and isinstance(content[0], dict) else ""
    return {
        "ok": sc.get("ok", not raw.get("isError", False)),
        "run_id": sc.get("run_id", ""),
        "dashboard_url": sc.get("dashboard_url", ""),
        "observer_url": sc.get("observer_url", ""),
        "output_text": sc.get("output_text") or sc.get("plain_text_zh") or sc.get("plain_text_en") or content_text,
        "missing_required_events": sc.get("missing_required_events", []),
        "understanding_trace": sc.get("understanding_trace"),
        "token_report": sc.get("token_report"),
        "error": sc.get("error"),
    }


def _output(data: dict, args: argparse.Namespace) -> None:
    """Output JSON or human-readable summary.

    When --json flag is used, output is normalized to h-agent-v1 contract.
    """
    if getattr(args, "json", False):
        normalized = normalize_h_agent_output(data)
        print(json.dumps(normalized, ensure_ascii=False))
    else:
        _print_summary(data)


def _print_summary(data: dict) -> None:
    ok = data.get("ok", False)
    status = "OK" if ok else "FAIL"
    print(f"[{status}]")
    for key, value in data.items():
        if key == "ok":
            continue
        if isinstance(value, (dict, list)):
            print(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            print(f"  {key}: {value}")


def cmd_capsule_init(args: argparse.Namespace) -> None:
    """初始化胶囊。"""
    from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    manifest = CapsuleManager.create_capsule(path)
    print(f"胶囊已创建: {path}")
    print(f"  capsule_id: {manifest.capsule_id}")
    print(f"  schema_version: {manifest.schema_version}")


def cmd_capsule_status(args: argparse.Namespace) -> None:
    """查看胶囊状态。"""
    from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    status = CapsuleManager.get_capsule_status(path)
    print(json.dumps(status, ensure_ascii=False, indent=2))


def cmd_capsule_doctor(args: argparse.Namespace) -> None:
    """胶囊健康检查。"""
    from stable_agent.capsule.capsule_doctor import CapsuleDoctor
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    report = CapsuleDoctor.check(path)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ok:
        print(f"\n健康分数: {report.health_score:.2f} (有错误)")
        sys.exit(1)
    else:
        print(f"\n健康分数: {report.health_score:.2f}")


def cmd_capsule_export(args: argparse.Namespace) -> None:
    """导出胶囊为 ZIP。"""
    from stable_agent.capsule.import_export import CapsuleImportExport
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    capsule_path = args.path or str(get_default_capsule_path())
    output = args.output or "capsule_export.zip"
    result = CapsuleImportExport.export_capsule(capsule_path, output)
    print(f"胶囊已导出: {result}")


def cmd_capsule_import(args: argparse.Namespace) -> None:
    """从 ZIP 导入胶囊。"""
    from stable_agent.capsule.import_export import CapsuleImportExport
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    zip_path = args.zip_path
    target = args.target or str(get_default_capsule_path())
    manifest = CapsuleImportExport.import_capsule(zip_path, target)
    print(f"胶囊已导入: {target}")
    print(f"  capsule_id: {manifest.capsule_id}")


def cmd_memory_health(args: argparse.Namespace) -> None:
    """记忆健康报告。"""
    from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    path = Path(args.path or str(get_default_capsule_path()))
    mgr = MemoryLifecycleManager(capsule_path=path)
    report = mgr.generate_memory_health_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_token_summary(args: argparse.Namespace) -> None:
    """Token 使用摘要。"""
    from stable_agent.token.budget_ledger import BudgetLedger
    ledger = BudgetLedger()
    summary = ledger.summarize_period(days=args.days)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_mcp_config(args: argparse.Namespace) -> None:
    """输出 MCP 配置。"""
    config = {
        "mcpServers": {
            "stableagent": {
                "url": "http://127.0.0.1:8000/mcp"
            }
        }
    }
    print(json.dumps(config, indent=2))


# ===================================================================
# CLI Mode Commands
# ===================================================================


def cmd_task_run(args: argparse.Namespace) -> None:
    """执行 StableAgent 任务 (CLI Mode)。

    V12.0: 默认使用 local runtime，不需要启动 HTTP server。
    如果指定 --http，则走 HTTP MCP。
    """
    task_input: str = args.task_input
    open_dashboard: bool = args.open_dashboard
    use_json: bool = args.json
    use_http: bool = getattr(args, "http", False)
    base = _base_url(args)

    # V12.0: 默认使用 local runtime
    if not use_http:
        try:
            result = _call_local_runtime(task_input, open_dashboard)
            _output(result, args)
            if not result.get("ok", False):
                sys.exit(1)
            return
        except Exception as local_exc:
            if not use_json:
                print(f"Local runtime 失败 ({local_exc})，尝试 HTTP 回退...")

    # HTTP 回退路径
    mcp_url = f"{base}/mcp/"

    rpc_body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {"task_input": task_input, "open_dashboard": open_dashboard},
        },
        "id": "cli-task-run",
    }

    try:
        result = _http_post(mcp_url, rpc_body, timeout=60.0)
    except Exception as exc:
        error_data = {
            "ok": False,
            "run_id": "",
            "dashboard_url": "",
            "observer_url": "",
            "missing_required_events": [],
            "understanding_trace": None,
            "token_report": None,
            "expression_matches": None,
            "error": f"StableAgent server 未启动或请求失败: {exc}",
            "suggestion": "请先运行: PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve",
            "hint": "检查服务是否运行: PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json"
        }
        _output(error_data, args)
        sys.exit(1)

    # 检查 JSON-RPC 错误
    if "error" in result:
        rpc_error = result["error"]
        error_data = {
            "ok": False,
            "run_id": "",
            "dashboard_url": "",
            "observer_url": "",
            "missing_required_events": [],
            "understanding_trace": None,
            "token_report": None,
            "expression_matches": None,
            "error": f"JSON-RPC 错误: {rpc_error.get('message', '未知错误')}",
            "code": rpc_error.get("code"),
            "suggestion": "检查工具名称和参数是否正确"
        }
        _output(error_data, args)
        sys.exit(1)

    rpc_result = result.get("result", {})
    sc = rpc_result.get("structuredContent", {})

    # 从 structuredContent 提取核心字段，确保都有默认值
    output = {
        "ok": sc.get("ok", not rpc_result.get("isError", False)),
        "run_id": sc.get("run_id", ""),
        "dashboard_url": f"{base}{sc.get('dashboard_url', '')}" if sc.get("dashboard_url") else "",
        "observer_url": f"{base}{sc.get('observer_url', '')}" if sc.get("observer_url") else "",
        "missing_required_events": sc.get("missing_required_events", []),
        "understanding_trace": sc.get("understanding_trace"),
        "token_report": sc.get("token_report"),
        "expression_matches": sc.get("expression_matches"),
        "error": sc.get("error"),  # 错误信息
    }

    # 确保 ok=false 时必须有 error 字段
    if not output["ok"] and not output["error"]:
        output["error"] = sc.get("plain_text") or rpc_result.get("plain_text") or "工具调用失败，原因未知"

    _output(output, args)

    if open_dashboard and output.get("observer_url"):
        try:
            webbrowser.open(output["observer_url"])
            if not use_json:
                print(f"\n已在浏览器中打开: {output['observer_url']}")
        except Exception:
            if not use_json:
                print(f"\n无法打开浏览器，请手动访问: {output['observer_url']}")
    if not output["ok"]:
        sys.exit(1)


def cmd_task_estimate(args: argparse.Namespace) -> None:
    """Estimate task risk without executing it (CLI Mode).

    Returns a risk assessment in h-agent-v1 contract format.
    """
    task_input: str = args.task_input

    # Risk assessment patterns
    high_risk_patterns = [
        r"rm\s+-rf", r"drop\s+table", r"\bdelete\b", r"force\s+push",
        r"git\s+push\s+--force", r"\bdeploy\b", r"删除所有文件", r"删除数据库",
        r"清空数据库", r"\bformat\b", r"sudo\s+rm",
    ]
    medium_risk_patterns = [
        r"\binstall\b", r"\bupdate\b", r"\bmodify\b", r"\bexecute\b",
        r"修改", r"安装", r"执行", r"写入", r"删除",
    ]

    input_lower = task_input.lower()
    estimated_risk = "low"

    # Check high risk patterns
    for pattern in high_risk_patterns:
        if re.search(pattern, input_lower):
            estimated_risk = "high"
            break

    # Check medium risk patterns (only if not already high)
    if estimated_risk != "high":
        for pattern in medium_risk_patterns:
            if re.search(pattern, input_lower):
                estimated_risk = "medium"
                break

    requires_approval = estimated_risk in ("medium", "high")

    # Generate estimated steps based on risk level
    if estimated_risk == "high":
        estimated_steps = ["parse_task", "risk_warning", "request_approval", "execute_with_rollback"]
        suggestion = "高风险操作，建议人工审核后再执行。请确认操作范围和回滚方案。"
    elif estimated_risk == "medium":
        estimated_steps = ["parse_task", "confirm_scope", "execute"]
        suggestion = "中等风险操作，建议确认操作范围后执行。"
    else:
        estimated_steps = ["parse_task", "execute"]
        suggestion = "低风险操作，可以直接执行。"

    # Rough token estimation based on input length and risk
    base_tokens = len(task_input) * 2
    if estimated_risk == "high":
        estimated_tokens = base_tokens + 2000
    elif estimated_risk == "medium":
        estimated_tokens = base_tokens + 800
    else:
        estimated_tokens = base_tokens + 200

    result = {
        "ok": True,
        "contract_version": "h-agent-v1",
        "task_input": task_input,
        "estimated_risk": estimated_risk,
        "requires_approval": requires_approval,
        "estimated_steps": estimated_steps,
        "estimated_tokens": estimated_tokens,
        "suggestion": suggestion,
    }

    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_summary(result)


def cmd_serve(args: argparse.Namespace) -> None:
    """启动 StableAgent Web 服务。"""
    host: str = args.host
    port: int = args.port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError:
        print(f"错误: 端口 {port} 已被占用。")
        print(f"请先停止占用端口 {port} 的进程，或使用 --port 指定其他端口。")
        sys.exit(1)

    base = f"http://{host}:{port}"
    print(f"启动 StableAgent 服务...")
    print(f"  Health URL:        {base}/api/health")
    print(f"  MCP URL:           {base}/mcp/")
    print(f"  Dashboard URL:     {base}/")
    print(f"  Effectiveness URL: {base}/effectiveness")
    print()
    try:
        import uvicorn
        uvicorn.run("web.server:app", host=host, port=port, log_level="info")
    except ImportError:
        print("错误: uvicorn 未安装。请运行: pip install uvicorn")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n服务已停止。")
    except Exception as exc:
        print(f"服务启动失败: {exc}")
        sys.exit(1)


def cmd_health(args: argparse.Namespace) -> None:
    """健康检查。"""
    base = _base_url(args)
    result: dict = {
        "ok": True, "server": False, "mcp": False,
        "tool_count": 0, "has_os_agent": False,
        "health_url": f"{base}/api/health",
        "mcp_url": f"{base}/mcp/health",
        "tools_url": f"{base}/mcp/tools",
    }
    try:
        health = _http_get(f"{base}/api/health", timeout=3.0)
        result["server"] = health.get("ok", False)
    except Exception:
        result["ok"] = False
        result["error"] = "StableAgent server not reachable"
        _output(result, args)
        sys.exit(1)
    try:
        mcp_health = _http_get(f"{base}/mcp/health", timeout=3.0)
        result["mcp"] = mcp_health.get("ok", False)
    except Exception:
        result["mcp"] = False
    try:
        tools = _http_get(f"{base}/mcp/tools", timeout=3.0)
        tool_list = tools.get("result", {}).get("tools", [])
        result["tool_count"] = len(tool_list)
        result["has_os_agent"] = any(t.get("name") == "stableagent.task.os_agent" for t in tool_list)
    except Exception:
        pass
    result["ok"] = result["server"] and result["mcp"]
    _output(result, args)
    if not result["ok"]:
        sys.exit(1)


def cmd_feedback_remember(args: argparse.Namespace) -> None:
    """记住这个。"""
    base = _base_url(args)
    try:
        result = _http_post(f"{base}/api/feedback/remember",
                            {"run_id": args.run_id, "note": args.note}, timeout=10.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}", "hint": "请先运行: python -m stable_agent.cli serve"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_feedback_dont(args: argparse.Namespace) -> None:
    """下次别这样。"""
    base = _base_url(args)
    try:
        result = _http_post(f"{base}/api/feedback/dont-do-this-again",
                            {"run_id": args.run_id, "note": args.note}, timeout=10.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}", "hint": "请先运行: python -m stable_agent.cli serve"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_feedback_correct(args: argparse.Namespace) -> None:
    """纠正并记住。"""
    base = _base_url(args)
    try:
        result = _http_post(f"{base}/api/feedback/correct-and-remember", {
            "run_id": args.run_id, "note": args.meaning,
            "context": {"phrase": args.phrase, "corrected_meaning": args.meaning},
        }, timeout=10.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}", "hint": "请先运行: python -m stable_agent.cli serve"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_effectiveness_summary(args: argparse.Namespace) -> None:
    base = _base_url(args)
    try:
        result = _http_get(f"{base}/api/effectiveness/summary", timeout=5.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_effectiveness_task_create(args: argparse.Namespace) -> None:
    base = _base_url(args)
    try:
        result = _http_post(f"{base}/api/effectiveness/task", {
            "title": args.task_id, "description": args.description,
            "task_type": getattr(args, "category", "coding"),
        }, timeout=10.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_effectiveness_run_record(args: argparse.Namespace) -> None:
    base = _base_url(args)
    body = {
        "task_id": args.task_id, "mode": args.mode,
        "model": getattr(args, "model", "other"),
        "stableagent_run_id": getattr(args, "stableagent_run_id", ""),
        "success": args.success,
        "test_passed": getattr(args, "test_passed", True),
        "intent_drift": getattr(args, "intent_drift", False),
        "over_editing": getattr(args, "over_editing", False),
        "constraint_preserved": getattr(args, "constraint_preserved", True),
        "rework_count": getattr(args, "rework_count", 0),
        "estimated_tokens": getattr(args, "estimated_tokens", 0),
        "user_satisfaction": getattr(args, "user_satisfaction", 3),
    }
    try:
        result = _http_post(f"{base}/api/effectiveness/run", body, timeout=10.0)
    except Exception as exc:
        _output({"ok": False, "error": f"请求失败: {exc}"}, args)
        sys.exit(1)
    _output(result, args)


def cmd_dashboard_open(args: argparse.Namespace) -> None:
    base = _base_url(args)
    run_id: str = args.run_id or ""
    url = f"{base}/observe/{run_id}?check=1" if run_id else f"{base}/"
    if getattr(args, "print_only", False):
        print(url)
    else:
        print(f"Dashboard URL: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            print("无法打开浏览器，请手动访问上述 URL。")


# ===================================================================
# Doctor + Skill Commands (Phase 6)
# ===================================================================


def cmd_doctor(args: argparse.Namespace) -> None:
    """综合健康检查。"""
    base = _base_url(args)
    use_json = getattr(args, "json", False)
    checks = {}

    # 1. Server health
    try:
        health = _http_get(f"{base}/api/health", timeout=3.0)
        checks["server"] = health.get("ok", False)
    except Exception:
        checks["server"] = False

    # 2. MCP health
    try:
        mcp_health = _http_get(f"{base}/mcp/health", timeout=3.0)
        checks["mcp"] = mcp_health.get("ok", False)
    except Exception:
        checks["mcp"] = False

    # 3. Tools
    try:
        tools = _http_get(f"{base}/mcp/tools", timeout=3.0)
        tool_list = tools.get("result", {}).get("tools", [])
        checks["tool_count"] = len(tool_list)
        checks["has_os_agent"] = any(t.get("name") == "stableagent.task.os_agent" for t in tool_list)
    except Exception:
        checks["tool_count"] = 0
        checks["has_os_agent"] = False

    # 4. Profile
    from stable_agent.gateway.tool_profiles import get_tool_profile
    checks["profile"] = get_tool_profile().value

    # 5. Skills directory
    skills_dir = Path.cwd() / ".skills"
    checks["skills_dir_exists"] = skills_dir.exists()
    checks["skills_index_exists"] = (skills_dir / "index.sqlite").exists()

    # Summary
    checks["ok"] = all([
        checks.get("server", False),
        checks.get("mcp", False),
        checks.get("has_os_agent", False),
    ])

    if use_json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
    else:
        print("StableAgent Doctor")
        print("=" * 40)
        for key, value in checks.items():
            status = "OK" if value is True else ("FAIL" if value is False else value)
            print(f"  {key}: {status}")
        print("=" * 40)
        if checks["ok"]:
            print("All checks passed!")
        else:
            print("Some checks failed. Run with --json for details.")

    if not checks["ok"]:
        sys.exit(1)


def cmd_skill_list(args: argparse.Namespace) -> None:
    """列出 skills。"""
    from stable_agent.skills.repository import SkillRepository
    repo = SkillRepository(base_path=Path.cwd() / ".skills")
    status_filter = getattr(args, "status", None)
    skills = repo.list_skills(status=status_filter)

    if getattr(args, "json", False):
        print(json.dumps([{
            "skill_id": s.skill_id,
            "status": s.status.value,
            "domain": s.domain,
            "risk_level": s.risk_level,
            "created_at": s.created_at,
        } for s in skills], ensure_ascii=False, indent=2))
    else:
        if not skills:
            print("No skills found.")
            return
        print(f"Skills ({len(skills)}):")
        for s in skills:
            print(f"  [{s.status.value}] {s.skill_id} (domain={s.domain}, risk={s.risk_level})")


def cmd_skill_show(args: argparse.Namespace) -> None:
    """显示 skill 详情。"""
    from stable_agent.skills.repository import SkillRepository
    repo = SkillRepository(base_path=Path.cwd() / ".skills")
    record = repo.get_skill(args.skill_id)
    if not record:
        print(f"Skill not found: {args.skill_id}")
        sys.exit(1)

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(record), ensure_ascii=False, indent=2, default=str))
    else:
        print(f"Skill: {record.skill_id}")
        print(f"  Status: {record.status.value}")
        print(f"  Domain: {record.domain}")
        print(f"  Risk: {record.risk_level}")
        print(f"  Created: {record.created_at}")
        print(f"  Intent: {record.intent[:200]}")
        print(f"  Procedure: {record.procedure[:200]}")


def cmd_skill_validate(args: argparse.Namespace) -> None:
    """验证 skill。"""
    from stable_agent.skills.repository import SkillRepository
    from stable_agent.core.validator import ValidationGate
    from stable_agent.core.models import SkillCandidate

    repo = SkillRepository(base_path=Path.cwd() / ".skills")
    record = repo.get_skill(args.skill_id)
    if not record:
        print(f"Skill not found: {args.skill_id}")
        sys.exit(1)

    # 创建 candidate 用于验证
    candidate = SkillCandidate(
        candidate_id=record.skill_id,
        source_run_id=record.source_runs[0] if record.source_runs else "",
        failure_mode="",
        evidence_events=[],
        proposed_rule=record.intent,
        when_to_use=record.procedure,
        do_not_use_when=record.guardrails,
        validation_plan="manual validation",
        risk_level=record.risk_level,
    )

    gate = ValidationGate()
    result = gate.validate_schema(candidate)

    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2))
    else:
        print(f"Validation result for {args.skill_id}:")
        print(f"  Schema valid: {result.schema_valid}")
        print(f"  Passed: {result.passed}")
        if result.reason:
            print(f"  Reason: {result.reason}")


def cmd_skill_promote(args: argparse.Namespace) -> None:
    """晋升 skill。"""
    from stable_agent.skills.repository import SkillRepository
    repo = SkillRepository(base_path=Path.cwd() / ".skills")
    reason = getattr(args, "reason", "manual promote via CLI")
    success = repo.promote_skill(args.skill_id, reason=reason)

    if getattr(args, "json", False):
        print(json.dumps({"ok": success, "skill_id": args.skill_id}, ensure_ascii=False))
    else:
        if success:
            print(f"Skill {args.skill_id} promoted successfully.")
        else:
            print(f"Failed to promote skill {args.skill_id}.")
            sys.exit(1)


def cmd_integration_doctor(args: argparse.Namespace) -> None:
    """Integration environment health check for H.Agent."""
    import importlib
    import os

    use_json = getattr(args, "json", False)
    checks: dict = {}
    all_ok = True

    # 1. Check Python version >= 3.11
    py_version = sys.version_info
    py_ok = py_version >= (3, 11)
    checks["python_version"] = {
        "ok": py_ok,
        "version": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
        "required": ">=3.11",
    }
    if not py_ok:
        all_ok = False

    # 2. Check requirements.txt packages are importable
    req_file = Path.cwd() / "requirements.txt"
    missing_packages: list = []
    if req_file.exists():
        req_lines = req_file.read_text().splitlines()
        for line in req_lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Extract package name (before ==, >=, ~=, etc.)
            pkg_name = line.split("==")[0].split(">=")[0].split("~=")[0].split("<=")[0].split(">")[0].split("<")[0].strip()
            dist_name = pkg_name.split("[", 1)[0]
            import_aliases = {
                "python-dotenv": "dotenv",
            }
            import_name = import_aliases.get(dist_name, dist_name.replace("-", "_"))
            try:
                importlib.import_module(import_name)
            except ImportError:
                try:
                    importlib.import_module(dist_name)
                except ImportError:
                    missing_packages.append(pkg_name)
        checks["requirements"] = {
            "ok": len(missing_packages) == 0,
            "missing": missing_packages,
        }
        if missing_packages:
            all_ok = False
    else:
        checks["requirements"] = {"ok": False, "error": "requirements.txt not found"}
        all_ok = False

    # 3. Check stable_agent can be imported
    try:
        importlib.import_module("stable_agent")
        checks["stable_agent_import"] = {"ok": True}
    except ImportError as exc:
        checks["stable_agent_import"] = {"ok": False, "error": str(exc)}
        all_ok = False

    # 4. Check if LocalStableAgentRuntime can be initialized
    try:
        from stable_agent.runtime.local_runtime import LocalStableAgentRuntime
        runtime = LocalStableAgentRuntime()
        checks["runtime_init"] = {"ok": True}
    except ImportError as exc:
        checks["runtime_init"] = {"ok": False, "error": f"Import failed: {exc}"}
        all_ok = False
    except Exception as exc:
        checks["runtime_init"] = {"ok": False, "error": f"Init failed: {exc}"}
        all_ok = False

    # 5. Check if stableagent.task.os_agent tool exists in tool schemas
    try:
        from stable_agent.gateway.mcp_gateway import MCPGateway
        gateway = MCPGateway()
        tools = gateway.registry.list_tools()
        tool_names = [t.get("name", "") if isinstance(t, dict) else getattr(t, "name", "") for t in tools]
        has_os_agent = "stableagent.task.os_agent" in tool_names
        checks["os_agent_tool"] = {"ok": has_os_agent, "tool_count": len(tool_names)}
        if not has_os_agent:
            all_ok = False
    except ImportError as exc:
        checks["os_agent_tool"] = {"ok": False, "error": f"Import failed: {exc}"}
        all_ok = False
    except Exception as exc:
        checks["os_agent_tool"] = {"ok": False, "error": f"Check failed: {exc}"}
        all_ok = False

    # 6. Run a quick task run --json dry check (verify normalize works)
    try:
        from stable_agent.cli import normalize_h_agent_output
        test_result = normalize_h_agent_output({"ok": True, "run_id": "test_run"})
        contract_ok = test_result.get("contract_version") == "h-agent-v1"
        checks["contract_normalize"] = {"ok": contract_ok}
        if not contract_ok:
            all_ok = False
    except Exception as exc:
        checks["contract_normalize"] = {"ok": False, "error": str(exc)}
        all_ok = False

    # Summary
    checks["ok"] = all_ok
    checks["contract_version"] = "h-agent-v1"
    checks["timestamp"] = datetime.now(timezone.utc).isoformat()
    checks["h_agent_ready"] = all_ok
    if all_ok:
        checks["summary"] = "All integration checks passed. Environment is h-agent ready."
    else:
        failed = [k for k, v in checks.items() if isinstance(v, dict) and not v.get("ok", True)]
        checks["summary"] = f"Integration checks failed: {', '.join(failed)}"

    if use_json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
    else:
        print("StableAgent Integration Doctor")
        print("=" * 45)
        for key, value in checks.items():
            if isinstance(value, dict):
                status = "OK" if value.get("ok") else "FAIL"
                detail = ""
                if "error" in value:
                    detail = f" ({value['error']})"
                elif "missing" in value and value["missing"]:
                    detail = f" (missing: {', '.join(value['missing'])})"
                elif "version" in value:
                    detail = f" ({value['version']})"
                print(f"  [{status}] {key}{detail}")
            else:
                print(f"  {key}: {value}")
        print("=" * 45)
        if all_ok:
            print("All integration checks passed!")
        else:
            print("Some checks failed. Run with --json for details.")

    if not all_ok:
        sys.exit(1)


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=False, help="JSON 输出模式")


def cmd_impact_show(args: argparse.Namespace) -> None:
    """查看 Learning Impact Report。

    优先从本地 RunStore 读取，如果没有则尝试 HTTP API。
    """
    run_id: str = args.run_id
    use_json = getattr(args, "json", False)

    # 尝试本地 RunStore
    report = None
    try:
        from stable_agent.observation.run_store import RunStore
        rs = RunStore()
        events = rs.get_events(run_id)
        if events:
            # 从事件中提取 token_report 和 si_report
            token_report = None
            si_report = None
            for evt in events:
                if evt.get("event_type") == "token.budget.estimated" and evt.get("token_report"):
                    token_report = evt["token_report"]
                if evt.get("si_report"):
                    si_report = evt["si_report"]
                if evt.get("learning_triggered") is not None:
                    si_report = si_report or {}
                    si_report["learning_triggered"] = evt.get("learning_triggered")
                    si_report["validation_passed"] = evt.get("validation_passed")
                    si_report["skill_patches"] = evt.get("skill_patches", [])
                    si_report["human_review_required"] = evt.get("human_review_required")
                    si_report["best_skill_exported"] = evt.get("best_skill_exported", False)

            from stable_agent.impact.builder import LearningImpactBuilder
            builder = LearningImpactBuilder()
            impact = builder.build(
                run_id=run_id,
                events=events,
                token_report=token_report,
                si_report=si_report,
            )
            report = impact.to_dict()
    except Exception as exc:
        if not use_json:
            print(f"本地 RunStore 读取失败: {exc}")

    # 如果本地没有，尝试 HTTP API
    if report is None:
        base = _base_url(args)
        try:
            report = _http_get(f"{base}/api/runs/{run_id}/impact", timeout=5.0)
        except Exception as exc:
            if use_json:
                print(json.dumps({"ok": False, "error": f"无法获取 impact report: {exc}"}, ensure_ascii=False))
            else:
                print(f"无法获取 impact report: {exc}")
                print("请确保 run_id 正确，或先运行: python -m stable_agent.cli serve")
            sys.exit(1)

    if use_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # 人类友好输出
    print("=" * 50)
    print("StableAgent Learning Impact Report")
    print("=" * 50)
    print()

    overall = report.get("overall_impact_score", 0)
    print(f"总体提升: {int(overall * 100)}%")
    print(f"  记忆命中: {int(report.get('memory_impact_score', 0) * 100)}%")
    print(f"  Token 节省: {int(report.get('token_impact_score', 0) * 100)}%")
    print(f"  Skill 使用: {int(report.get('skill_impact_score', 0) * 100)}%")
    print(f"  个性化提升: {int(report.get('personalization_score', 0) * 100)}%")
    print()

    memory_hits = report.get("memory_hits", [])
    print(f"记忆命中: {len(memory_hits)} 条")
    for m in memory_hits[:3]:
        print(f"  - {m.get('content_preview', '')[:60]}")
    print()

    token = report.get("token_impact")
    if token:
        print(f"Token 节省: {token.get('saved_tokens_estimated', 0)} / {token.get('baseline_tokens_estimated', 0)}")
    else:
        print("Token 节省: 无数据")
    print()

    skills_used = report.get("skills_used", [])
    candidates = report.get("skill_candidates_created", [])
    print(f"Skill 使用: {len(skills_used)} 条")
    print(f"新候选 Skill: {len(candidates)} 条")
    for c in candidates[:3]:
        status = "需要验证" if c.get("needs_validation") else "已验证"
        print(f"  - {c.get('skill_id', '')} ({status})")
    print()

    improved = report.get("what_improved_zh", [])
    not_improved = report.get("what_did_not_improve_zh", [])
    if improved:
        print("本次提升:")
        for item in improved:
            print(f"  + {item}")
    if not_improved:
        print("本次未提升:")
        for item in not_improved:
            print(f"  - {item}")
    print()

    next_actions = report.get("next_learning_actions_zh", [])
    if next_actions:
        print("下一步:")
        for action in next_actions:
            print(f"  → {action}")
    print()

    summary = report.get("user_visible_summary_zh", "")
    if summary:
        print(f"摘要: {summary}")


def _add_server_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"服务器地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"服务器端口 (默认: {DEFAULT_PORT})")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stableagent",
        description="StableAgent Capsule — Agent Capsule 管理 + CLI Mode 工具",
    )
    subparsers = parser.add_subparsers(dest="command")

    # capsule
    cap_parser = subparsers.add_parser("capsule", help="胶囊管理")
    cap_sub = cap_parser.add_subparsers(dest="action")

    init_p = cap_sub.add_parser("init", help="初始化胶囊")
    init_p.add_argument("--path", help="胶囊路径")
    init_p.set_defaults(func=cmd_capsule_init)

    status_p = cap_sub.add_parser("status", help="查看状态")
    status_p.add_argument("--path", help="胶囊路径")
    status_p.set_defaults(func=cmd_capsule_status)

    doctor_p = cap_sub.add_parser("doctor", help="健康检查")
    doctor_p.add_argument("--path", help="胶囊路径")
    doctor_p.set_defaults(func=cmd_capsule_doctor)

    export_p = cap_sub.add_parser("export", help="导出为 ZIP")
    export_p.add_argument("output", nargs="?", help="输出文件路径")
    export_p.add_argument("--path", help="胶囊路径")
    export_p.set_defaults(func=cmd_capsule_export)

    import_p = cap_sub.add_parser("import", help="从 ZIP 导入")
    import_p.add_argument("zip_path", help="ZIP 文件路径")
    import_p.add_argument("--target", help="目标路径")
    import_p.set_defaults(func=cmd_capsule_import)

    # memory
    mem_parser = subparsers.add_parser("memory", help="记忆管理")
    mem_sub = mem_parser.add_subparsers(dest="action")

    health_p = mem_sub.add_parser("health", help="记忆健康报告")
    health_p.add_argument("--path", help="胶囊路径")
    health_p.set_defaults(func=cmd_memory_health)

    # token
    tok_parser = subparsers.add_parser("token", help="Token 管理")
    tok_sub = tok_parser.add_subparsers(dest="action")

    summary_p = tok_sub.add_parser("summary", help="Token 使用摘要")
    summary_p.add_argument("--days", type=int, default=7, help="统计天数")
    summary_p.set_defaults(func=cmd_token_summary)

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="MCP 配置")
    mcp_sub = mcp_parser.add_subparsers(dest="action")

    config_p = mcp_sub.add_parser("config", help="输出 MCP 配置")
    config_p.set_defaults(func=cmd_mcp_config)

    # ---- serve ----
    serve_p = subparsers.add_parser("serve", help="启动 StableAgent Web 服务")
    _add_server_flags(serve_p)
    serve_p.set_defaults(func=cmd_serve)

    # ---- health ----
    health_cli_p = subparsers.add_parser("health", help="健康检查 (server/MCP/tools)")
    _add_server_flags(health_cli_p)
    _add_json_flag(health_cli_p)
    health_cli_p.set_defaults(func=cmd_health)

    # ---- task run ----
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_sub = task_parser.add_subparsers(dest="action")

    run_p = task_sub.add_parser("run", help="执行 StableAgent 任务")
    run_p.add_argument("--task-input", "-t", required=True, help="任务内容")
    run_p.add_argument("--open-dashboard", action="store_true", default=False, help="完成后打开 Dashboard")
    run_p.add_argument("--http", action="store_true", default=False, help="使用 HTTP MCP 模式 (需要先启动 server)")
    _add_server_flags(run_p)
    _add_json_flag(run_p)
    run_p.set_defaults(func=cmd_task_run)

    estimate_p = task_sub.add_parser("estimate", help="任务风险评估（不执行）")
    estimate_p.add_argument("--task-input", "-t", required=True, help="任务内容")
    _add_json_flag(estimate_p)
    estimate_p.set_defaults(func=cmd_task_estimate)

    # ---- feedback ----
    fb_parser = subparsers.add_parser("feedback", help="反馈管理")
    fb_sub = fb_parser.add_subparsers(dest="action")

    fb_remember_p = fb_sub.add_parser("remember", help="记住这个")
    fb_remember_p.add_argument("--run-id", required=True, help="Run ID")
    fb_remember_p.add_argument("--note", required=True, help="用户备注")
    _add_server_flags(fb_remember_p)
    _add_json_flag(fb_remember_p)
    fb_remember_p.set_defaults(func=cmd_feedback_remember)

    fb_dont_p = fb_sub.add_parser("dont", help="下次别这样")
    fb_dont_p.add_argument("--run-id", required=True, help="Run ID")
    fb_dont_p.add_argument("--note", required=True, help="用户备注")
    _add_server_flags(fb_dont_p)
    _add_json_flag(fb_dont_p)
    fb_dont_p.set_defaults(func=cmd_feedback_dont)

    fb_correct_p = fb_sub.add_parser("correct", help="纠正并记住")
    fb_correct_p.add_argument("--run-id", required=True, help="Run ID")
    fb_correct_p.add_argument("--phrase", required=True, help="需要纠正的表达")
    fb_correct_p.add_argument("--meaning", required=True, help="正确含义")
    _add_server_flags(fb_correct_p)
    _add_json_flag(fb_correct_p)
    fb_correct_p.set_defaults(func=cmd_feedback_correct)

    # ---- effectiveness ----
    eff_parser = subparsers.add_parser("effectiveness", help="效果评估")
    eff_sub = eff_parser.add_subparsers(dest="action")

    eff_summary_p = eff_sub.add_parser("summary", help="效果评估摘要")
    _add_server_flags(eff_summary_p)
    _add_json_flag(eff_summary_p)
    eff_summary_p.set_defaults(func=cmd_effectiveness_summary)

    eff_task_p = eff_sub.add_parser("task", help="评测任务管理")
    eff_task_sub = eff_task_p.add_subparsers(dest="sub_action")

    eff_task_create_p = eff_task_sub.add_parser("create", help="创建评测任务")
    eff_task_create_p.add_argument("--task-id", required=True, help="任务 ID")
    eff_task_create_p.add_argument("--description", required=True, help="任务描述")
    eff_task_create_p.add_argument("--category", default="coding", help="任务类别")
    _add_server_flags(eff_task_create_p)
    _add_json_flag(eff_task_create_p)
    eff_task_create_p.set_defaults(func=cmd_effectiveness_task_create)

    eff_run_p = eff_sub.add_parser("run", help="评测运行管理")
    eff_run_sub = eff_run_p.add_subparsers(dest="sub_action")

    eff_run_record_p = eff_run_sub.add_parser("record", help="记录评测运行")
    eff_run_record_p.add_argument("--task-id", required=True, help="任务 ID")
    eff_run_record_p.add_argument("--mode", required=True, choices=["stableagent", "baseline"], help="运行模式")
    eff_run_record_p.add_argument("--model", default="other", help="模型名称")
    eff_run_record_p.add_argument("--stableagent-run-id", default="", help="StableAgent Run ID")
    eff_run_record_p.add_argument("--success", type=lambda x: x.lower() == "true", default=True, help="是否成功")
    eff_run_record_p.add_argument("--test-passed", type=lambda x: x.lower() == "true", default=True, help="测试是否通过")
    eff_run_record_p.add_argument("--intent-drift", type=lambda x: x.lower() == "true", default=False, help="是否意图漂移")
    eff_run_record_p.add_argument("--over-editing", type=lambda x: x.lower() == "true", default=False, help="是否过度编辑")
    eff_run_record_p.add_argument("--constraint-preserved", type=lambda x: x.lower() == "true", default=True, help="约束是否保留")
    eff_run_record_p.add_argument("--rework-count", type=int, default=0, help="返工次数")
    eff_run_record_p.add_argument("--estimated-tokens", type=int, default=0, help="估算 token 数")
    eff_run_record_p.add_argument("--user-satisfaction", type=int, default=3, help="用户满意度 1-5")
    _add_server_flags(eff_run_record_p)
    _add_json_flag(eff_run_record_p)
    eff_run_record_p.set_defaults(func=cmd_effectiveness_run_record)

    # ---- dashboard ----
    dash_parser = subparsers.add_parser("dashboard", help="Dashboard 管理")
    dash_sub = dash_parser.add_subparsers(dest="action")

    dash_open_p = dash_sub.add_parser("open", help="打开 Dashboard")
    dash_open_p.add_argument("--run-id", default="", help="Run ID (可选)")
    dash_open_p.add_argument("--print-only", action="store_true", default=False, help="只打印 URL")
    _add_server_flags(dash_open_p)
    dash_open_p.set_defaults(func=cmd_dashboard_open)

    # ---- doctor ----
    doctor_p = subparsers.add_parser("doctor", help="综合健康检查")
    _add_server_flags(doctor_p)
    _add_json_flag(doctor_p)
    doctor_p.set_defaults(func=cmd_doctor)

    # ---- V12.1: impact ----
    impact_parser = subparsers.add_parser("impact", help="Learning Impact Report")
    impact_sub = impact_parser.add_subparsers(dest="action")

    impact_show_p = impact_sub.add_parser("show", help="查看学习提升报告")
    impact_show_p.add_argument("--run-id", required=True, help="Run ID")
    _add_server_flags(impact_show_p)
    _add_json_flag(impact_show_p)
    impact_show_p.set_defaults(func=cmd_impact_show)

    # ---- skill ----
    skill_parser = subparsers.add_parser("skill", help="技能管理")
    skill_sub = skill_parser.add_subparsers(dest="action")

    skill_list_p = skill_sub.add_parser("list", help="列出技能")
    skill_list_p.add_argument("--status", default=None, help="按状态过滤")
    _add_json_flag(skill_list_p)
    skill_list_p.set_defaults(func=cmd_skill_list)

    skill_show_p = skill_sub.add_parser("show", help="显示技能详情")
    skill_show_p.add_argument("skill_id", help="技能 ID")
    _add_json_flag(skill_show_p)
    skill_show_p.set_defaults(func=cmd_skill_show)

    skill_validate_p = skill_sub.add_parser("validate", help="验证技能")
    skill_validate_p.add_argument("skill_id", help="技能 ID")
    _add_json_flag(skill_validate_p)
    skill_validate_p.set_defaults(func=cmd_skill_validate)

    skill_promote_p = skill_sub.add_parser("promote", help="晋升技能")
    skill_promote_p.add_argument("skill_id", help="技能 ID")
    skill_promote_p.add_argument("--reason", default="manual promote via CLI", help="晋升原因")
    _add_json_flag(skill_promote_p)
    skill_promote_p.set_defaults(func=cmd_skill_promote)

    # ---- Integration ----
    int_parser = subparsers.add_parser("integration", help="集成管理")
    int_sub = int_parser.add_subparsers(dest="action")

    int_doctor_p = int_sub.add_parser("doctor", help="集成环境健康检查")
    _add_json_flag(int_doctor_p)
    int_doctor_p.set_defaults(func=cmd_integration_doctor)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if hasattr(args, "func"):
        args.func(args)
    else:
        print(f"请指定子命令: {args.command} <action>")
        sys.exit(1)


if __name__ == "__main__":
    main()
