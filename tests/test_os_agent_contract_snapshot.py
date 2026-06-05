"""Phase 0 契约 snapshot 测试 — `stableagent.task.os_agent`.

冻结三个返回面的形状:
  1. CLI envelope (9 字段) — `stable_agent/cli.py:244-254`
  2. MCP `structuredContent` 顶层 (26 字段) — `_make_result` @ unified_tool_registry.py:178
  3. `structuredContent.data` 内层 (27 字段) — `_h_task_os_agent` data block @ :1469

Snapshot 数据见 `tests/golden/os_agent_response_shape.json`,在 Phase 0 由真实 live run 生成。

测试设计:
- 服务未启动 → skip(而不是 fail),保持本地/CI 友好
- 服务可用 → 触发一次真实 run,把响应形状与 golden snapshot 严格比对
- 类型/键集合校验,绝不依赖具体值(`run_id` 每次都不同)

参考 [docs/harness/PHASE0_CONTRACT.md](../docs/harness/PHASE0_CONTRACT.md)。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

GOLDEN_PATH = Path(__file__).parent / "golden" / "os_agent_response_shape.json"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
MCP_URL = "http://127.0.0.1:8000/mcp/"


def _server_reachable() -> bool:
    """快速探测本地 stable_agent serve 是否在 8000 端口监听。"""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError, OSError):
        return False


def _call_os_agent(task_input: str = "Phase 0 contract snapshot test") -> dict[str, Any]:
    """触发一次真实 os_agent 调用,返回完整 JSON-RPC response."""
    body = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {"task_input": task_input, "open_dashboard": False},
        },
        "id": "phase0-contract-snapshot",
    }).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    assert GOLDEN_PATH.exists(), f"golden snapshot missing: {GOLDEN_PATH}"
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live_response() -> dict[str, Any]:
    if not _server_reachable():
        pytest.skip(
            "stable_agent serve not running on 127.0.0.1:8000 — "
            "start with `PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve` "
            "to run contract snapshot tests"
        )
    return _call_os_agent()


# --------------------------------------------------------------------------- #
# 1. CLI envelope 投影(9 字段)
# --------------------------------------------------------------------------- #

CLI_ENVELOPE_FIELDS = {
    "ok",
    "run_id",
    "dashboard_url",
    "observer_url",
    "missing_required_events",
    "understanding_trace",
    "token_report",
    "expression_matches",
    "error",
}


def test_golden_lists_cli_envelope_9_fields(golden):
    """golden snapshot 必须列出 CLI envelope 全部 9 个字段。"""
    assert set(golden["cli_envelope_keys"]) == CLI_ENVELOPE_FIELDS


def test_cli_envelope_projectable_from_sc(golden, live_response):
    """live `structuredContent` 可投影出 CLI envelope 全部 9 个字段(允许部分为 None)。"""
    sc = live_response["result"]["structuredContent"]
    # CLI 投影需要的源字段(参考 cli.py:244-254)
    needed_in_sc = {
        "ok", "run_id", "dashboard_url", "observer_url",
        "missing_required_events", "understanding_trace", "token_report",
        "expression_matches",
    }
    missing = needed_in_sc - set(sc.keys())
    assert not missing, f"CLI envelope projection broken — sc missing: {missing}"


# --------------------------------------------------------------------------- #
# 2. structuredContent 顶层 26 字段
# --------------------------------------------------------------------------- #

def test_sc_top_level_keys_match_golden(golden, live_response):
    """sc 顶层键集合必须与 golden 一致 — additive 允许,删除/重命名禁止。"""
    sc = live_response["result"]["structuredContent"]
    expected = set(golden["structured_content_top_keys"])
    actual = set(sc.keys())

    removed = expected - actual
    added = actual - expected

    assert not removed, (
        f"contract break — sc top-level keys removed: {sorted(removed)}. "
        f"Update PHASE0_CONTRACT.md before removing fields."
    )
    if added:
        # additive 是允许的,但提示更新 golden
        pytest.warns(UserWarning) if False else None  # informational only
        # 不报错,只是允许
        pass


def test_sc_data_keys_match_golden(golden, live_response):
    """sc.data 27 字段不可删除/重命名(V9 健康检查面)。"""
    sc = live_response["result"]["structuredContent"]
    data = sc.get("data", {})
    expected = set(golden["structured_content_data_keys"])
    actual = set(data.keys())

    removed = expected - actual
    assert not removed, (
        f"contract break — sc.data keys removed: {sorted(removed)}. "
        f"Phase 1+ refactor MUST preserve these for Dashboard / V9 health checks."
    )


# --------------------------------------------------------------------------- #
# 3. 关键不变量(types / values)
# --------------------------------------------------------------------------- #

def test_ok_is_bool(live_response):
    sc = live_response["result"]["structuredContent"]
    assert isinstance(sc["ok"], bool)


def test_run_id_is_run_prefixed_string(live_response):
    sc = live_response["result"]["structuredContent"]
    assert isinstance(sc["run_id"], str)
    assert sc["run_id"].startswith("run_"), (
        "run_id format change requires CONTRACT bump — "
        "Dashboard URLs hardcode this prefix"
    )


def test_missing_required_events_is_list(live_response):
    sc = live_response["result"]["structuredContent"]
    assert isinstance(sc["missing_required_events"], list)


def test_data_event_sync_invariants(live_response):
    """V9 健康检查不变量(契约级):

    - event_sync_ok ⇒ event_api_ok
    - event_sync_ok ⇒ missing_required_events == []
    - event_sync_ok ⇒ sync_errors == []
    - dashboard_replay_ok ≡ event_api_ok
    """
    data = live_response["result"]["structuredContent"]["data"]
    sync_ok = data["event_sync_ok"]
    api_ok = data["event_api_ok"]
    replay_ok = data["dashboard_replay_ok"]

    if sync_ok:
        assert api_ok, "event_sync_ok=True but event_api_ok=False"
        assert data["missing_required_events"] == []
        assert data["sync_errors"] == []

    assert replay_ok == api_ok, "dashboard_replay_ok must equal event_api_ok"


def test_data_progress_terminal_state(live_response):
    """终态契约值(任务成功路径)。"""
    data = live_response["result"]["structuredContent"]["data"]
    assert data["progress_pct"] == 100
    assert data["current_stage"] == "completed"
    assert data["avatar_state"] == "done"


def test_understanding_trace_top_and_data_consistency(live_response):
    """sc.understanding_trace 与 sc.data.understanding_trace 必须一致(顶层是副本)。"""
    sc = live_response["result"]["structuredContent"]
    top = sc.get("understanding_trace")
    inner = sc.get("data", {}).get("understanding_trace")
    if top is None and inner is None:
        return
    assert top == inner, "sc.understanding_trace must mirror sc.data.understanding_trace"


def test_token_report_top_and_data_consistency(live_response):
    sc = live_response["result"]["structuredContent"]
    top = sc.get("token_report")
    inner = sc.get("data", {}).get("token_report")
    if top is None and inner is None:
        return
    assert top == inner, "sc.token_report must mirror sc.data.token_report"


def test_dashboard_url_path_format(live_response):
    """sc 顶层 dashboard_url 是 `/runs/{run_id}` 路径(无 base);CLI 才拼 base。"""
    sc = live_response["result"]["structuredContent"]
    url = sc.get("dashboard_url", "")
    if url:  # open_dashboard=False 时可能为 ""
        assert url.startswith("/runs/"), f"dashboard_url path format broken: {url}"
        assert sc["run_id"] in url
