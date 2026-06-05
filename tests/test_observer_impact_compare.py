"""Phase 5 — Observer impact + compare API contract.

Pinned behavior:

  - **Completed run never reports 0%** — `is_completed=True` forces
    progress_pct=100 + current_stage="completed" if those fields are
    blank. Phase 5 prompt invariant: "completed run 不能出现 0% 假象".
  - 13 必需事件缺失时,`event_sync_ok=False` 且 `missing_required_events`
    精确列出缺失项(子集化 Phase 0 检测)。
  - ImpactReport 的 memory / skill / learning timeline 严格按事件类型
    白名单提取,`_shrink_event` 限制输出 keys 防 JSON 膨胀。
  - ValidationReportStore round-trip — 落盘的 JSON 文件可以被 Compare API
    完整读出。
  - Compare API 找不到 run / validation_id 必须返回 404。
  - validation_id 必须满足 ``[A-Za-z0-9_-]{1,64}`` — 路径遍历守护。

测试通过 in-memory ``DictRunStore`` + tmp_path ValidationReportStore,
**不需要** FastAPI / Orchestrator 真正启动。FastAPI app 用 TestClient
在 6 个 e2e 测试里验证路由挂载正确。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stable_agent.api.compare_api import build_compare_router
from stable_agent.api.impact_api import build_impact_report, build_impact_router
from stable_agent.api.run_detail_api import build_run_detail_router
from stable_agent.api.validation_store import ValidationReportStore
from stable_agent.eval.ab_validation_runner import (
    ABResult,
    RunResult,
    ValidationReport,
)


# --------------------------------------------------------------------------- #
# In-memory RunStore stand-in
# --------------------------------------------------------------------------- #

class DictRunStore:
    """Mimics the read surface of :class:`RunStore` for Phase 5 tests."""

    def __init__(self, events_by_run: dict[str, list[dict[str, Any]]]) -> None:
        self._events = events_by_run

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        return list(self._events.get(run_id, []))


REQUIRED_EVENTS = (
    "task.received", "intent.parsed", "context.budgeted",
    "temporal_memory.retrieved", "rag.retrieved",
    "context.compression_guard.checked", "context.built",
    "workflow.plan.created", "workflow.step.started",
    "workflow.step.completed", "eval.completed",
    "self_improvement.checked", "task.completed",
)


def _full_run(run_id: str = "run_full", *, score: float = 0.82) -> list[dict[str, Any]]:
    """Build a happy-path event list (all 13 required events emitted)."""
    events: list[dict[str, Any]] = []
    for i, t in enumerate(REQUIRED_EVENTS):
        ev: dict[str, Any] = {
            "event_type": t,
            "run_id": run_id,
            "timestamp": 1717200000.0 + i,
            "stage": "completed" if t == "task.completed" else t.split(".")[0],
        }
        if t == "intent.parsed":
            ev["task_input"] = "verify Phase 5 detail API"
        if t == "eval.completed":
            ev["eval_score"] = score
            ev["eval_passed"] = score >= 0.7
            ev["decision_summary_zh"] = f"评分 {score:.2f}"
        if t == "task.completed":
            ev["progress_pct"] = 100
        events.append(ev)
    return events


def _partial_run(run_id: str = "run_partial") -> list[dict[str, Any]]:
    """Run that stops after intent.parsed — missing 11 of 13 events."""
    return [
        {"event_type": "task.received", "run_id": run_id, "timestamp": 1.0, "stage": "received"},
        {"event_type": "intent.parsed", "run_id": run_id, "timestamp": 2.0, "task_input": "broken run"},
    ]


# --------------------------------------------------------------------------- #
# 1. Run detail — completed-run-never-shows-zero invariant
# --------------------------------------------------------------------------- #

def test_run_detail_completed_run_reports_full_progress():
    run = _full_run()
    # Strip explicit progress_pct from every event to simulate "missing"
    # values in some emitter codepath.
    for e in run:
        e.pop("progress_pct", None)

    store = DictRunStore({"run_full": run})
    app = FastAPI()
    app.include_router(build_run_detail_router(run_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_full/detail")
    assert resp.status_code == 200
    body = resp.json()

    assert body["is_completed"] is True
    assert body["progress_pct"] == 100, (
        "Phase 5 contract: completed run must never report 0% / blank progress"
    )
    assert body["current_stage"] == "completed"
    assert body["missing_required_events"] == []
    assert body["event_sync_ok"] is True
    assert body["eval_score"] == 0.82


def test_run_detail_partial_run_reports_missing_events():
    store = DictRunStore({"run_partial": _partial_run()})
    app = FastAPI()
    app.include_router(build_run_detail_router(run_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_partial/detail")
    body = resp.json()

    assert body["is_completed"] is False
    assert body["event_sync_ok"] is False
    # Specifically: at least the events after intent.parsed are missing.
    missing = set(body["missing_required_events"])
    assert "task.completed" in missing
    assert "eval.completed" in missing
    assert len(missing) == 11


def test_run_detail_unknown_run_returns_404():
    store = DictRunStore({})
    app = FastAPI()
    app.include_router(build_run_detail_router(run_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_ghost/detail")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 2. Impact report — pure function shape
# --------------------------------------------------------------------------- #

def test_impact_report_required_event_completeness_full():
    report = build_impact_report("run_full", _full_run())
    assert report["required_event_completeness"] == 1.0
    assert report["eval_impact"]["eval_score"] == 0.82


def test_impact_report_collects_memory_and_skill_hits():
    events = _full_run()
    events.extend([
        {
            "event_type": "memory.update.candidate",
            "run_id": "run_full",
            "timestamp": 100.0,
            "selected_memories": [{"memory_id": "m1"}],
            "decision_summary_zh": "提交记忆候选",
        },
        {
            "event_type": "skill.candidate.created",
            "run_id": "run_full",
            "timestamp": 101.0,
            "candidate_skill_ids": ["sk_test"],
            "task_group_id": "grp_001",
            "decision_summary_zh": "Curator 提案",
        },
    ])
    report = build_impact_report("run_full", events)
    assert report["memory_hit_count"] >= 1
    assert report["skill_hit_count"] >= 1
    # _shrink_event must drop noise — assert it didn't keep arbitrary keys.
    skill = report["skill_hits"][0]
    assert "candidate_skill_ids" in skill
    assert "raw_args" not in skill


def test_impact_report_token_impact_falls_back_when_missing():
    """No token.budget.estimated event → impact returns explicit Nones, not crash."""
    report = build_impact_report("r1", _partial_run())
    ti = report["token_impact"]
    assert ti["saved_tokens_estimated"] is None
    assert ti["saving_ratio"] is None


def test_impact_report_token_impact_extracted_from_event():
    events = _full_run()
    events.append({
        "event_type": "token.budget.estimated",
        "run_id": "run_full",
        "timestamp": 50.0,
        "token_report": {
            "saved_tokens_estimated": 234,
            "saving_ratio": 0.18,
            "baseline_tokens_estimated": 1300,
            "candidate_context_tokens": 1066,
            "summary_zh": "节省 18%",
        },
    })
    report = build_impact_report("run_full", events)
    assert report["token_impact"]["saved_tokens_estimated"] == 234
    assert report["token_impact"]["saving_ratio"] == 0.18


# --------------------------------------------------------------------------- #
# 3. Compare API + ValidationReportStore round-trip
# --------------------------------------------------------------------------- #

def _make_report(run_id: str = "run_xyz", *, passed: bool = True) -> ValidationReport:
    cases = (
        ABResult(
            case_id="c0",
            baseline=RunResult("c0", 0.5, 100, 100, True),
            candidate=RunResult("c0", 0.7, 105, 102, True),
        ),
        ABResult(
            case_id="c1",
            baseline=RunResult("c1", 0.6, 100, 100, True),
            candidate=RunResult("c1", 0.78, 108, 100, True),
        ),
    )
    return ValidationReport(
        candidate_skill_id="sk_demo",
        candidate_version=1,
        group_id="grp_demo",
        cases=cases,
        avg_score_delta=0.19,
        avg_token_delta_ratio=0.065,
        avg_latency_delta_ratio=0.01,
        regression_count=0,
        required_events_completeness=1.0,
        passed=passed,
        reason="ok" if passed else "regression",
    )


def test_validation_store_round_trip(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    vid = store.save(_make_report("run_xyz"), run_id="run_xyz")
    assert vid.startswith("val_")

    rec = store.get(vid)
    assert rec is not None
    assert rec["run_id"] == "run_xyz"
    assert rec["report"]["passed"] is True
    assert rec["report"]["candidate_skill_id"] == "sk_demo"

    found = store.find_by_run("run_xyz")
    assert len(found) == 1


def test_validation_store_rejects_traversal_id(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    with pytest.raises(ValueError):
        store.save(_make_report(), validation_id="../../etc/passwd")
    with pytest.raises(ValueError):
        store.get("../../etc/passwd")


def test_compare_api_returns_latest_for_run(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    store.save(_make_report("run_a"), run_id="run_a")

    app = FastAPI()
    app.include_router(build_compare_router(validation_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_a/compare")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run_a"
    assert body["candidate_skill_id"] == "sk_demo"
    assert body["passed"] is True
    assert len(body["cases"]) == 2


def test_compare_api_404_when_run_has_no_report(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    app = FastAPI()
    app.include_router(build_compare_router(validation_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_missing/compare")
    assert resp.status_code == 404


def test_compare_api_get_validation_by_id(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    vid = store.save(_make_report("run_z"), run_id="run_z")

    app = FastAPI()
    app.include_router(build_compare_router(validation_store=store))

    with TestClient(app) as client:
        resp = client.get(f"/api/validations/{vid}")
    assert resp.status_code == 200
    assert resp.json()["validation_id"] == vid


def test_compare_api_rejects_invalid_validation_id(tmp_path: Path):
    store = ValidationReportStore(tmp_path)
    app = FastAPI()
    app.include_router(build_compare_router(validation_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/validations/..%2Fetc%2Fpasswd")
    # FastAPI URL-decodes the path; the store must reject the bad id.
    assert resp.status_code in (400, 404)


# --------------------------------------------------------------------------- #
# 4. Impact API mounts under FastAPI
# --------------------------------------------------------------------------- #

def test_impact_api_under_test_client():
    store = DictRunStore({"run_full": _full_run()})
    app = FastAPI()
    app.include_router(build_impact_router(run_store=store))

    with TestClient(app) as client:
        resp = client.get("/api/runs/run_full/impact")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run_full"
    assert body["required_event_completeness"] == 1.0
    assert "memory_hits" in body and "skill_hits" in body and "learning_timeline" in body
