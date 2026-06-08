#!/usr/bin/env python3
"""StableAgent V11.4 CLI — 胶囊管理 + CLI Mode 命令行工具。

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

    # V11.4: CLI Mode
    python -m stable_agent.cli serve [--host 127.0.0.1] [--port 8000]
    python -m stable_agent.cli health [--json]
    python -m stable_agent.cli task run -t "任务内容" [--open-dashboard] [--json]
    python -m stable_agent.cli feedback remember --run-id ID --note "..." [--json]
    python -m stable_agent.cli feedback dont --run-id ID --note "..." [--json]
    python -m stable_agent.cli feedback correct --run-id ID --phrase "..." --meaning "..." [--json]
    python -m stable_agent.cli effectiveness summary [--json]
    python -m stable_agent.cli effectiveness task create --task-id T01 --description "..." [--json]
    python -m stable_agent.cli effectiveness run record --task-id T01 --mode stableagent [--json]
    python -m stable_agent.cli dashboard open [--run-id ID] [--print-only]
    python -m stable_agent.cli impact show --latest [--json]
    python -m stable_agent.cli research scan --source arxiv --query "self evolving agents" [--json]
    python -m stable_agent.cli research propose --finding-id FINDING_ID [--json]
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import webbrowser
from pathlib import Path

# Default server config
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _base_url(args: argparse.Namespace) -> str:
    host = getattr(args, "host", DEFAULT_HOST)
    port = getattr(args, "port", DEFAULT_PORT)
    return f"http://{host}:{port}"


def _server_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return whether the configured local HTTP endpoint is accepting TCP."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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


def _output(data: dict, args: argparse.Namespace) -> None:
    """Output JSON or human-readable summary."""
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False))
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
# V11.4: CLI Mode Commands
# ===================================================================


def cmd_task_run(args: argparse.Namespace) -> None:
    """执行 StableAgent 任务 (CLI Mode)。

    Phase 1: 默认仍然走 HTTP MCP(向后兼容 V11.4 部署);带 ``--local`` 旗标时
    走 in-process LocalRuntime,**完全不依赖 HTTP server**。两条路径走同一个
    ResponseAdapter,所以 dict shape 完全一致(Phase 0 contract snapshot 保护)。
    """
    task_input: str = args.task_input
    open_dashboard: bool = args.open_dashboard
    use_json: bool = args.json
    base = _base_url(args)

    # Phase 1: opt-in LocalRuntime path — no HTTP, no socket.
    if getattr(args, "local", False):
        from stable_agent.core.os_agent_handler import run_os_agent
        output = run_os_agent(
            task_input=task_input,
            open_dashboard=open_dashboard,
            base_url=base,
        )
        _output(output, args)
        if open_dashboard and output.get("observer_url"):
            try:
                webbrowser.open(output["observer_url"])
                if not use_json:
                    print(f"\n已在浏览器中打开: {output['observer_url']}")
            except Exception:
                if not use_json:
                    print(f"\n无法打开浏览器,请手动访问: {output['observer_url']}")
        if not output.get("ok"):
            sys.exit(1)
        return

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

    host = getattr(args, "host", DEFAULT_HOST)
    port = getattr(args, "port", DEFAULT_PORT)
    if not _server_port_open(host, port, timeout=1.0):
        error_data = {
            "ok": False,
            "run_id": "",
            "dashboard_url": "",
            "observer_url": "",
            "missing_required_events": [],
            "understanding_trace": None,
            "token_report": None,
            "expression_matches": None,
            "error": f"StableAgent server 未启动或请求失败: {host}:{port} is not accepting connections",
            "suggestion": "请先运行: PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve",
            "hint": "检查服务是否运行: PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json"
        }
        _output(error_data, args)
        sys.exit(1)

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

    # V11.4: 检查 JSON-RPC 错误
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

    # V11.4: 从 structuredContent 提取核心字段，确保都有默认值
    output = {
        "ok": sc.get("ok", not rpc_result.get("isError", False)),
        "run_id": sc.get("run_id", ""),
        "dashboard_url": f"{base}{sc.get('dashboard_url', '')}" if sc.get("dashboard_url") else "",
        "observer_url": f"{base}{sc.get('observer_url', '')}" if sc.get("observer_url") else "",
        "missing_required_events": sc.get("missing_required_events", []),
        "understanding_trace": sc.get("understanding_trace"),
        "token_report": sc.get("token_report"),
        "expression_matches": sc.get("expression_matches"),
        "error": sc.get("error"),  # V11.4: 错误信息
    }

    # V11.4: 确保 ok=false 时必须有 error 字段
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
        tool_list = tools.get("tools") or tools.get("result", {}).get("tools", [])
        result["tool_count"] = len(tool_list)
        result["has_os_agent"] = any(t.get("name") == "stableagent.task.os_agent" for t in tool_list)
    except Exception as exc:
        logging.getLogger(__name__).debug("MCP tools health probe failed: %s", exc)
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
            "task_id": args.task_id,
            "description": args.description,
            "category": getattr(args, "category", "coding"),
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
        "constraint_preservation": 1.0 if getattr(args, "constraint_preserved", True) else 0.0,
        "rework_count": getattr(args, "rework_count", 0),
        "tokens_used": getattr(args, "estimated_tokens", 0),
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


def cmd_impact_show(args: argparse.Namespace) -> None:
    """Show the latest Learning Impact Report v2."""
    from stable_agent.impact.builder import LearningImpactReportBuilder
    from stable_agent.impact.renderer import render_user_summary_zh

    report = LearningImpactReportBuilder.load_latest()
    if report is None:
        report = LearningImpactReportBuilder.build(
            run_id="latest_unavailable",
            memory_hits=[],
            skill_hits=[],
            profile_hits=[],
            candidate_created=[],
            token_report=None,
            has_ab_validation=False,
        )
    data = {
        "ok": True,
        "learning_impact_report": report.to_dict(),
        "summary_zh": render_user_summary_zh(report),
    }
    if getattr(args, "json", False):
        _output(data, args)
    else:
        print(data["summary_zh"])


def cmd_research_scan(args: argparse.Namespace) -> None:
    """Scan arXiv/GitHub/docs and write evidence-only cards."""
    source = args.source
    query = args.query
    max_results = int(getattr(args, "max_results", 3))

    if source == "arxiv":
        from stable_agent.research.arxiv_watcher import ArxivWatcher
        cards = ArxivWatcher().scan(query, max_results=max_results)
    elif source == "github":
        from stable_agent.research.github_watcher import GitHubWatcher
        cards = GitHubWatcher().scan(query, max_results=max_results)
    elif source == "docs":
        from stable_agent.research.docs_watcher import DocsWatcher
        cards = DocsWatcher().scan(query, max_results=max_results)
    else:
        _output({"ok": False, "error": f"unsupported research source: {source}"}, args)
        sys.exit(1)

    path = _append_research_cards(cards)
    payload = {
        "ok": True,
        "source": source,
        "query": query,
        "count": len(cards),
        "cards": [card.to_dict() for card in cards],
        "store_path": str(path),
        "status": "evidence_only",
    }
    _output(payload, args)


def cmd_research_propose(args: argparse.Namespace) -> None:
    """Build an improvement proposal from an evidence card."""
    from stable_agent.research.evidence_card import ResearchEvidenceCard
    from stable_agent.research.proposal_builder import ProposalBuilder

    finding_id = args.finding_id
    row = _find_research_card(finding_id)
    if row is None:
        _output({"ok": False, "error": f"finding_id not found: {finding_id}"}, args)
        sys.exit(1)
    proposal = ProposalBuilder().build(ResearchEvidenceCard(**row))
    _output({"ok": True, "proposal": proposal.to_dict()}, args)


def _append_research_cards(cards: list[object]) -> Path:
    path = Path(".stableagent/research/findings.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for card in cards:
            payload = card.to_dict() if hasattr(card, "to_dict") else dict(card)  # type: ignore[arg-type]
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _find_research_card(finding_id: str) -> dict | None:
    path = Path(".stableagent/research/findings.jsonl")
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("finding_id") == finding_id:
            return row
    return None


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=False, help="JSON 输出模式")


def _add_server_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"服务器地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"服务器端口 (默认: {DEFAULT_PORT})")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stableagent",
        description="StableAgent V11.4 — Agent Capsule 管理 + CLI Mode 工具",
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

    # ---- V11.4: serve ----
    serve_p = subparsers.add_parser("serve", help="启动 StableAgent Web 服务")
    _add_server_flags(serve_p)
    serve_p.set_defaults(func=cmd_serve)

    # ---- V11.4: health ----
    health_cli_p = subparsers.add_parser("health", help="健康检查 (server/MCP/tools)")
    _add_server_flags(health_cli_p)
    _add_json_flag(health_cli_p)
    health_cli_p.set_defaults(func=cmd_health)

    # ---- V11.4: task run ----
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_sub = task_parser.add_subparsers(dest="action")

    run_p = task_sub.add_parser("run", help="执行 StableAgent 任务")
    run_p.add_argument("--task-input", "-t", required=True, help="任务内容")
    run_p.add_argument("--open-dashboard", action="store_true", default=False, help="完成后打开 Dashboard")
    # Phase 1: opt-in in-process runtime — no HTTP, no socket.
    run_p.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="使用 in-process LocalRuntime,完全不依赖 HTTP server (Phase 1)",
    )
    _add_server_flags(run_p)
    _add_json_flag(run_p)
    run_p.set_defaults(func=cmd_task_run)

    # ---- V11.4: feedback ----
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

    # ---- V11.4: effectiveness ----
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

    # ---- V11.4: dashboard ----
    dash_parser = subparsers.add_parser("dashboard", help="Dashboard 管理")
    dash_sub = dash_parser.add_subparsers(dest="action")

    dash_open_p = dash_sub.add_parser("open", help="打开 Dashboard")
    dash_open_p.add_argument("--run-id", default="", help="Run ID (可选)")
    dash_open_p.add_argument("--print-only", action="store_true", default=False, help="只打印 URL")
    _add_server_flags(dash_open_p)
    dash_open_p.set_defaults(func=cmd_dashboard_open)

    # ---- Recursive Harness: impact ----
    impact_parser = subparsers.add_parser("impact", help="学习影响报告")
    impact_sub = impact_parser.add_subparsers(dest="action")

    impact_show_p = impact_sub.add_parser("show", help="显示 Learning Impact Report")
    impact_show_p.add_argument("--latest", action="store_true", default=False, help="显示最近一次报告")
    _add_json_flag(impact_show_p)
    impact_show_p.set_defaults(func=cmd_impact_show)

    # ---- Recursive Harness: research ----
    research_parser = subparsers.add_parser("research", help="研究证据卡")
    research_sub = research_parser.add_subparsers(dest="action")

    research_scan_p = research_sub.add_parser("scan", help="扫描外部研究源")
    research_scan_p.add_argument("--source", required=True, choices=["arxiv", "github", "docs"], help="研究源")
    research_scan_p.add_argument("--query", required=True, help="查询词或文档 URL")
    research_scan_p.add_argument("--max-results", type=int, default=3, help="最大结果数")
    _add_json_flag(research_scan_p)
    research_scan_p.set_defaults(func=cmd_research_scan)

    research_propose_p = research_sub.add_parser("propose", help="从 finding 生成提案")
    research_propose_p.add_argument("--finding-id", required=True, help="Finding ID")
    _add_json_flag(research_propose_p)
    research_propose_p.set_defaults(func=cmd_research_propose)

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
