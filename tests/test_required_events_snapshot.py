"""Phase 0 — `REQUIRED_NORMAL_EVENTS` snapshot.

冻结 13 个必需事件类型(V9 健康检查的真实约束):

    1.  task.received
    2.  intent.parsed
    3.  context.budgeted
    4.  temporal_memory.retrieved
    5.  rag.retrieved
    6.  context.compression_guard.checked
    7.  context.built
    8.  workflow.plan.created
    9.  workflow.step.started
   10.  workflow.step.completed
   11.  eval.completed
   12.  self_improvement.checked
   13.  task.completed

来源:`stable_agent/gateway/unified_tool_registry.py:1387-1400` (`REQUIRED_NORMAL_EVENTS`)。

> 路线图 [deep-research-report (5).md] Phase 0 提示词列出 6 个事件,
> 是 13 个的子集。Phase 0 冻结全部 13 个,任何一个被默默删除 / 重命名
> 都会让 `event_sync_ok` 假阳性,直接破坏 Dashboard 重放与 H.Agent 报告。

参考 [docs/harness/PHASE0_CONTRACT.md §4](../docs/harness/PHASE0_CONTRACT.md)。
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

# Phase 0 显式冻结的 13 个必需事件(完整 happy-path 链)。
# 如果未来需要新增,必须同步更新:
#   - stable_agent/gateway/unified_tool_registry.py:REQUIRED_NORMAL_EVENTS
#   - tests/golden/os_agent_response_shape.json
#   - docs/harness/PHASE0_CONTRACT.md §4
EXPECTED_REQUIRED_EVENTS_FROZEN_13: tuple[str, ...] = (
    "task.received",
    "intent.parsed",
    "context.budgeted",
    "temporal_memory.retrieved",
    "rag.retrieved",
    "context.compression_guard.checked",
    "context.built",
    "workflow.plan.created",
    "workflow.step.started",
    "workflow.step.completed",
    "eval.completed",
    "self_improvement.checked",
    "task.completed",
)

# 路线图 Phase 0 提示词显式列出的 6 个 — 它们必须是 13 个的子集
ROADMAP_REQUIRED_SUBSET_6: tuple[str, ...] = (
    "task.received",
    "intent.parsed",
    "context.budgeted",
    "context.built",
    "eval.completed",
    "task.completed",
)


def _server_reachable() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError, OSError):
        return False


def _call_os_agent() -> dict[str, Any]:
    body = json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {
                "task_input": "Phase 0 required-events snapshot test",
                "open_dashboard": False,
            },
        },
        "id": "phase0-required-events",
    }).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# 静态契约(不需要 server)
# --------------------------------------------------------------------------- #

def test_roadmap_six_is_subset_of_frozen_thirteen():
    """路线图列的 6 个事件必须是冻结 13 个的子集。"""
    missing = set(ROADMAP_REQUIRED_SUBSET_6) - set(EXPECTED_REQUIRED_EVENTS_FROZEN_13)
    assert not missing, f"roadmap subset references unknown events: {missing}"


def test_required_normal_events_constant_matches_frozen_list():
    """源代码常量 `REQUIRED_NORMAL_EVENTS` 必须等于冻结的 13 个(顺序敏感)。

    定位:`stable_agent/gateway/unified_tool_registry.py:1387-1400`。
    实际 import 不可行(常量是 handler 内的局部 list);改用源码扫描确保
    13 个事件全部出现在该文件中。
    """
    src = Path(__file__).parent.parent / "stable_agent" / "gateway" / "unified_tool_registry.py"
    text = src.read_text(encoding="utf-8")
    for event in EXPECTED_REQUIRED_EVENTS_FROZEN_13:
        assert f'"{event}"' in text, (
            f"required event {event!r} not found in unified_tool_registry.py — "
            "either renamed (contract break) or moved to a different file"
        )


def test_golden_records_thirteen_required_events():
    assert GOLDEN_PATH.exists(), f"golden snapshot missing: {GOLDEN_PATH}"
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["required_events"] == list(EXPECTED_REQUIRED_EVENTS_FROZEN_13), (
        "golden snapshot disagrees with frozen 13 — regenerate via "
        "tools/regen_golden_snapshot.py or rerun Phase 0 audit"
    )


# --------------------------------------------------------------------------- #
# 动态契约(需要 server,不可达则 skip)
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def live_response() -> dict[str, Any]:
    if not _server_reachable():
        pytest.skip(
            "stable_agent serve not running — start with "
            "`PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve`"
        )
    return _call_os_agent()


def test_live_run_required_events_field_returns_thirteen(live_response):
    data = live_response["result"]["structuredContent"]["data"]
    assert data["required_events"] == list(EXPECTED_REQUIRED_EVENTS_FROZEN_13)


def test_live_run_no_missing_required_events_on_happy_path(live_response):
    """成功 run 必须 emit 全部 13 个必需事件 — 否则 Dashboard 重放 / V9 健康检查会假阳性。"""
    data = live_response["result"]["structuredContent"]["data"]
    missing = data["missing_required_events"]
    assert missing == [], (
        f"happy-path run missing required events: {missing}. "
        "Either an emit point was removed (contract break) or "
        "REQUIRED_NORMAL_EVENTS was extended without updating Phase 0 contract."
    )


def test_live_run_emitted_events_cover_all_thirteen(live_response):
    """从 emitted_events 列表角度交叉验证(避免依赖单一字段)。"""
    data = live_response["result"]["structuredContent"]["data"]
    emitted_types = {
        e["event_type"] for e in data["emitted_events"]
        if e.get("_emit_ok")
    }
    missing = set(EXPECTED_REQUIRED_EVENTS_FROZEN_13) - emitted_types
    assert not missing, f"emitted_events missing: {sorted(missing)}"


def test_live_run_event_sync_health_is_green(live_response):
    """V9 健康检查三连绿(契约级):event_sync_ok / event_api_ok / dashboard_replay_ok 必须同时 True。"""
    data = live_response["result"]["structuredContent"]["data"]
    assert data["event_sync_ok"] is True, f"sync_errors={data.get('sync_errors')}"
    assert data["event_api_ok"] is True, f"api_missing={data.get('api_missing_required_events')}"
    assert data["dashboard_replay_ok"] is True
    assert data["sync_errors"] == []


def test_live_run_roadmap_subset_actually_emitted(live_response):
    """路线图 6 个事件必须在 happy path 中真实出现 — 这是路线图与现实的最小契约交集。"""
    data = live_response["result"]["structuredContent"]["data"]
    emitted_types = {
        e["event_type"] for e in data["emitted_events"]
        if e.get("_emit_ok")
    }
    missing = set(ROADMAP_REQUIRED_SUBSET_6) - emitted_types
    assert not missing, f"roadmap subset events missing: {sorted(missing)}"
