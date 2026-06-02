"""tests/test_os_agent_contract.py — 契约冻结测试。

验证 stableagent.task.os_agent 的返回字段必须包含所有必需字段。
这些字段是外部契约，重构前后不可变。

Phase 1: Contract Freeze
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import ToolRunResult, RunTrace
from stable_agent.core.contracts import ContractBuilder


# ── 必需返回字段 (外部契约) ──────────────────────────────────────

REQUIRED_RESULT_FIELDS = {
    "ok",
    "run_id",
    "dashboard_url",
    "observer_url",
    "event_sync_ok",
    "event_api_ok",
    "dashboard_replay_ok",
    "api_event_count",
    "emitted_event_count",
    "missing_required_events",
    "api_missing_required_events",
    "eval_passed",
    "eval_score",
    "si_report",
    "progress_pct",
    "current_stage",
}

# ContractBuilder.to_dict 必须输出的字段
# 注意: ok 是 ToolRunResult 顶层字段，通过 _make_result 单独传递，不在 to_dict 中
REQUIRED_DICT_FIELDS = {
    "run_id",
    "dashboard_url",
    "observer_url",
    "current_stage",
    "progress_pct",
    "status_text_zh",
    "status_text_en",
    "avatar_state",
    "task_type",
    "workflow_state",
    "eval_score",
    "eval_passed",
    "si_report",
    "mode",
    "emitted_event_count",
    "event_sync_ok",
    "sync_errors",
    "missing_required_events",
    "event_api_ok",
    "api_event_count",
    "api_missing_required_events",
    "dashboard_replay_ok",
    "dry_run_learning",
    "force_validation_passed",
    "understanding_trace",
    "token_report",
}


# ── Required Events (正常路径) ───────────────────────────────────

REQUIRED_NORMAL_EVENTS = [
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
]

# Required Events (失败学习路径)
REQUIRED_FAILURE_EVENTS = [
    "regression.generated",
    "memory.update.candidate",
    "skill.patch.proposed",
    "validation.checked",
]


# ── Fixtures ────────────────────────────────────────────────────

def _make_trace(**kwargs) -> RunTrace:
    """创建测试用 RunTrace。"""
    defaults = {
        "run_id": "run_test_001",
        "ok": True,
        "status": "completed",
        "eval_passed": True,
        "eval_score": 0.85,
        "events": [],
        "output_text": "test output",
        "artifacts": {
            "event_sync_ok": True,
            "event_api_ok": True,
            "dashboard_replay_ok": True,
            "api_event_count": 13,
            "emitted_event_count": 13,
            "missing_required_events": [],
            "api_missing_required_events": [],
            "dry_run_learning": True,
            "force_validation_passed": None,
            "sync_errors": [],
            "task_type": "coding",
            "workflow_state": "completed",
            "understanding_trace": None,
            "token_report": None,
        },
        "si_report": None,
    }
    defaults.update(kwargs)
    return RunTrace(**defaults)


# ── ContractBuilder 测试 ────────────────────────────────────────

class TestContractBuilderFields:
    """ContractBuilder 生成的 ToolRunResult 必须包含所有契约字段。"""

    def test_tool_result_has_all_required_fields(self):
        """ToolRunResult dataclass 必须包含所有必需字段。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)

        for field_name in REQUIRED_RESULT_FIELDS:
            assert hasattr(result, field_name), f"ToolRunResult 缺少字段: {field_name}"

    def test_to_dict_has_all_required_fields(self):
        """ContractBuilder.to_dict 输出必须包含所有必需字段。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)
        data = ContractBuilder.to_dict(result)

        for field_name in REQUIRED_DICT_FIELDS:
            assert field_name in data, f"to_dict 缺少字段: {field_name}"

    def test_ok_field_is_bool(self):
        """ok 字段必须是 bool。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)
        assert isinstance(result.ok, bool)

    def test_run_id_is_string(self):
        """run_id 字段必须是字符串。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)
        assert isinstance(result.run_id, str)
        assert len(result.run_id) > 0

    def test_dashboard_url_format(self):
        """dashboard_url 必须是 /runs/{run_id} 格式。"""
        trace = _make_trace(run_id="run_abc123")
        result = ContractBuilder.build_tool_result(trace, open_dashboard=True)
        assert result.dashboard_url == "/runs/run_abc123"

    def test_observer_url_format(self):
        """observer_url 必须是 /observe/{run_id} 格式。"""
        trace = _make_trace(run_id="run_abc123")
        result = ContractBuilder.build_tool_result(trace, open_dashboard=True)
        assert result.observer_url == "/observe/run_abc123"

    def test_missing_required_events_is_list(self):
        """missing_required_events 必须是列表。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)
        assert isinstance(result.missing_required_events, list)

    def test_progress_pct_is_int(self):
        """progress_pct 必须是整数。"""
        trace = _make_trace()
        result = ContractBuilder.build_tool_result(trace)
        assert isinstance(result.progress_pct, int)

    def test_progress_pct_100_on_success(self):
        """成功时 progress_pct 必须是 100。"""
        trace = _make_trace(ok=True)
        result = ContractBuilder.build_tool_result(trace)
        assert result.progress_pct == 100

    def test_progress_pct_0_on_failure(self):
        """失败时 progress_pct 必须是 0。"""
        trace = _make_trace(ok=False)
        result = ContractBuilder.build_tool_result(trace)
        assert result.progress_pct == 0


class TestContractBuilderFailurePath:
    """失败路径的契约字段。"""

    def test_failed_trace_has_required_fields(self):
        """失败的 trace 也必须包含所有契约字段。"""
        trace = _make_trace(
            ok=False,
            eval_passed=False,
            eval_score=0.3,
            artifacts={
                "event_sync_ok": False,
                "event_api_ok": False,
                "dashboard_replay_ok": False,
                "api_event_count": 5,
                "emitted_event_count": 5,
                "missing_required_events": ["task.completed"],
                "api_missing_required_events": ["task.completed"],
                "dry_run_learning": True,
                "force_validation_passed": None,
                "sync_errors": ["emit error"],
                "task_type": "unknown",
                "workflow_state": "failed",
            },
        )
        result = ContractBuilder.build_tool_result(trace)
        data = ContractBuilder.to_dict(result)

        # ok 在 ToolRunResult 上，不在 to_dict 中
        assert result.ok is False
        assert data["eval_passed"] is False
        assert "task.completed" in data["missing_required_events"]
        assert len(data["sync_errors"]) > 0


class TestRequiredEventsDefinition:
    """Required events 定义验证。"""

    def test_normal_events_count(self):
        """正常路径必须有 13 个必需事件。"""
        assert len(REQUIRED_NORMAL_EVENTS) == 13

    def test_failure_events_count(self):
        """失败学习路径必须有 4 个额外必需事件。"""
        assert len(REQUIRED_FAILURE_EVENTS) == 4

    def test_normal_events_start_with_task_received(self):
        """正常路径第一个事件必须是 task.received。"""
        assert REQUIRED_NORMAL_EVENTS[0] == "task.received"

    def test_normal_events_end_with_task_completed(self):
        """正常路径最后一个事件必须是 task.completed。"""
        assert REQUIRED_NORMAL_EVENTS[-1] == "task.completed"

    def test_failure_events_contain_regression(self):
        """失败路径必须包含 regression.generated。"""
        assert "regression.generated" in REQUIRED_FAILURE_EVENTS

    def test_failure_events_contain_skill_patch(self):
        """失败路径必须包含 skill.patch.proposed。"""
        assert "skill.patch.proposed" in REQUIRED_FAILURE_EVENTS
