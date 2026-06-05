"""Phase 5 — Compare API.

Surfaces :class:`stable_agent.eval.ab_validation_runner.ValidationReport`
to the Observer console. Two routes:

  - ``GET /api/runs/{run_id}/compare`` — newest report tagged with
    ``run_id``
  - ``GET /api/validations/{validation_id}`` — one specific report

The actual storage lives in
:mod:`stable_agent.api.validation_store.ValidationReportStore`. The API
is only a JSON projection.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from stable_agent.api.validation_store import ValidationReportStore


def build_compare_router(*, validation_store: ValidationReportStore) -> APIRouter:
    """Mount ``GET /api/runs/{run_id}/compare`` and ``/api/validations/{id}``."""
    router = APIRouter()

    @router.get("/api/runs/{run_id}/compare")
    async def get_compare(run_id: str) -> dict[str, Any]:
        records = validation_store.find_by_run(run_id)
        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"no validation report for run {run_id}",
            )
        # Newest first (ValidationReportStore.find_by_run already sorts).
        latest = records[0]
        return _project(latest)

    @router.get("/api/validations/{validation_id}")
    async def get_validation(validation_id: str) -> dict[str, Any]:
        try:
            rec = validation_store.get(validation_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if rec is None:
            raise HTTPException(
                status_code=404,
                detail=f"validation_id not found: {validation_id}",
            )
        return _project(rec)

    return router


def _project(record: dict[str, Any]) -> dict[str, Any]:
    """Trim sidecar / per-case fields the Observer doesn't need.

    Phase 5 keeps payloads under control so the comparison panel is
    snappy. Detail drill-down can hit the raw JSON file.
    """
    report = record.get("report", {})
    return {
        "validation_id": record.get("validation_id"),
        "run_id": record.get("run_id"),
        "saved_at": record.get("saved_at"),
        "candidate_skill_id": report.get("candidate_skill_id"),
        "candidate_version": report.get("candidate_version"),
        "group_id": report.get("group_id"),
        "case_count": report.get("case_count"),
        "avg_score_delta": report.get("avg_score_delta"),
        "avg_token_delta_ratio": report.get("avg_token_delta_ratio"),
        "avg_latency_delta_ratio": report.get("avg_latency_delta_ratio"),
        "regression_count": report.get("regression_count"),
        "regression_rate": report.get("regression_rate"),
        "required_events_completeness": report.get("required_events_completeness"),
        "passed": report.get("passed"),
        "reason": report.get("reason"),
        "cases": report.get("cases", []),
    }
