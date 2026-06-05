"""Phase 1 — LocalRuntime contract.

LocalRuntime 必须返回与 HTTP MCP **完全一致的 dict shape**(同样走过
ResponseAdapter.to_mcp_content),否则 Phase 0 契约 snapshot 测试就只能
覆盖 HTTP 路径,无法保护 in-process 路径。

测试设计:
- Module-scoped LocalRuntime — orchestrator 重量级,只构造一次
- 不依赖 HTTP server — 完全 in-process
- 校验对象:
    1. shape 与 Phase 0 golden snapshot 一致(top + data 键集合)
    2. 13 个 required events 全部 emit
    3. event_sync_ok / event_api_ok / dashboard_replay_ok 三连绿
    4. CLI envelope projection 与 cli.py:244-254 相同 9 字段
    5. Façade ``run_os_agent`` 拒绝空输入

参考 [docs/harness/PHASE1_RUNTIME.md](../docs/harness/PHASE1_RUNTIME.md)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

GOLDEN_PATH = Path(__file__).parent / "golden" / "os_agent_response_shape.json"
TASK_INPUT = "Phase 1 LocalRuntime contract test"


@pytest.fixture(scope="module")
def runtime() -> Any:
    from stable_agent.runtime.local_runtime import LocalRuntime
    return LocalRuntime()


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    assert GOLDEN_PATH.exists(), f"golden snapshot missing: {GOLDEN_PATH}"
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def response(runtime: Any) -> dict[str, Any]:
    """One real LocalRuntime call shared across tests."""
    return runtime.call_tool(
        "stableagent.task.os_agent",
        {"task_input": TASK_INPUT, "open_dashboard": False},
    )


# ------------------------------------------------------------------ #
# 1. Shape parity with HTTP MCP / Phase 0 golden
# ------------------------------------------------------------------ #

def test_local_runtime_returns_mcp_envelope(response):
    """`call_tool` returns ``{content, structuredContent, isError}``."""
    assert "content" in response
    assert "structuredContent" in response
    assert "isError" in response
    assert isinstance(response["content"], list)
    assert isinstance(response["structuredContent"], dict)
    assert isinstance(response["isError"], bool)


def test_local_runtime_sc_top_keys_match_golden(response, golden):
    """Top-level sc keys must match HTTP path(Phase 0 golden)."""
    sc = response["structuredContent"]
    expected = set(golden["structured_content_top_keys"])
    actual = set(sc.keys())

    removed = expected - actual
    assert not removed, (
        f"LocalRuntime drops sc keys vs HTTP MCP: {sorted(removed)}. "
        "ResponseAdapter went out of sync with HTTP path."
    )


def test_local_runtime_sc_data_keys_match_golden(response, golden):
    """sc.data 27 fields must match HTTP path."""
    data = response["structuredContent"]["data"]
    expected = set(golden["structured_content_data_keys"])
    actual = set(data.keys())

    removed = expected - actual
    assert not removed, (
        f"LocalRuntime drops sc.data keys: {sorted(removed)}. "
        "Phase 0 contract violated — Dashboard / V9 health checks will break."
    )


# ------------------------------------------------------------------ #
# 2. Required events parity
# ------------------------------------------------------------------ #

def test_local_runtime_no_missing_required_events(response):
    data = response["structuredContent"]["data"]
    assert data["missing_required_events"] == [], (
        f"LocalRuntime missing required events: {data['missing_required_events']}"
    )


def test_local_runtime_required_events_count_thirteen(response):
    data = response["structuredContent"]["data"]
    assert len(data["required_events"]) == 13


def test_local_runtime_event_sync_health_green(response):
    """V9 health invariant in Phase 0 contract — must hold for in-process path."""
    data = response["structuredContent"]["data"]
    assert data["event_sync_ok"] is True, f"sync_errors={data.get('sync_errors')}"
    assert data["event_api_ok"] is True, (
        f"api_missing={data.get('api_missing_required_events')}"
    )
    assert data["dashboard_replay_ok"] is True
    assert data["sync_errors"] == []


def test_local_runtime_run_id_is_run_prefixed(response):
    sc = response["structuredContent"]
    assert isinstance(sc["run_id"], str)
    assert sc["run_id"].startswith("run_"), (
        "run_id format is part of Phase 0 contract — Dashboard URLs depend on it"
    )


# ------------------------------------------------------------------ #
# 3. Façade — `core.os_agent_handler.run_os_agent`
# ------------------------------------------------------------------ #

def test_run_os_agent_facade_returns_nine_field_envelope(runtime):
    """Facade projects to the same 9 fields as cli.py:244-254."""
    from stable_agent.core.os_agent_handler import run_os_agent

    out = run_os_agent(
        "Phase 1 facade smoke",
        open_dashboard=False,
        runtime=runtime,
    )

    expected_keys = {
        "ok", "run_id", "dashboard_url", "observer_url",
        "missing_required_events", "understanding_trace", "token_report",
        "expression_matches", "error",
    }
    assert set(out.keys()) == expected_keys, (
        f"facade envelope drift — extra={set(out.keys()) - expected_keys}, "
        f"missing={expected_keys - set(out.keys())}"
    )
    assert out["ok"] is True
    assert out["run_id"].startswith("run_")
    assert out["error"] is None


def test_run_os_agent_facade_rejects_empty_input(runtime):
    """Phase 0 invariant: ok=False ⇒ error is non-empty string."""
    from stable_agent.core.os_agent_handler import run_os_agent

    out = run_os_agent("", runtime=runtime)
    assert out["ok"] is False
    assert isinstance(out["error"], str) and out["error"]
    assert out["run_id"] == ""


def test_run_os_agent_facade_url_join(runtime):
    """``base_url`` prefix is composable; default is path-only."""
    from stable_agent.core.os_agent_handler import run_os_agent

    out_path = run_os_agent(
        "facade url-join smoke",
        open_dashboard=True,
        runtime=runtime,
    )
    assert out_path["dashboard_url"].startswith("/")  # no base, leading slash

    out_full = run_os_agent(
        "facade url-join with base",
        open_dashboard=True,
        runtime=runtime,
        base_url="http://example.invalid:8000",
    )
    if out_full["dashboard_url"]:
        assert out_full["dashboard_url"].startswith("http://example.invalid:8000")


# ------------------------------------------------------------------ #
# 4. No HTTP dependency — strict
# ------------------------------------------------------------------ #

def test_local_runtime_does_not_open_http_socket(monkeypatch, runtime):
    """LocalRuntime must NOT open a TCP socket to 127.0.0.1:8000.

    Phase 1 raison d'être: CLI/stdio host that has no HTTP server running
    can still call `stableagent.task.os_agent`. We enforce this by:

      1. Patching urllib.request.urlopen to raise — if anyone tries HTTP
         during a LocalRuntime call_tool, the test explodes.
      2. Asserting that the call still succeeds.
    """
    import urllib.request

    def _explode(*args, **kwargs):
        raise AssertionError(
            "LocalRuntime must not call urlopen — a transitive code path "
            "still depends on HTTP MCP, breaking Phase 1 promise."
        )

    monkeypatch.setattr(urllib.request, "urlopen", _explode)

    response = runtime.call_tool(
        "stableagent.task.os_agent",
        {"task_input": "no-http strict test", "open_dashboard": False},
    )
    assert response["structuredContent"]["data"]["event_sync_ok"] is True


# ------------------------------------------------------------------ #
# 5. List tools (profile-agnostic) parity with HTTP path
# ------------------------------------------------------------------ #

def test_local_runtime_list_tools_includes_os_agent(runtime):
    tools = runtime.list_tools()
    names = {t.get("name") for t in tools}
    assert "stableagent.task.os_agent" in names


def test_local_runtime_unknown_tool_returns_safe_envelope(runtime):
    """Calling a non-existent tool returns ok=False, no exception."""
    response = runtime.call_tool("stableagent.does.not.exist", {})
    assert response["isError"] is True
    assert response["structuredContent"]["ok"] is False
