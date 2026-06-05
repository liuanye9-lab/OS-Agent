"""Phase 5 — Run detail API.

Replaces the SaaS-coupled ``/api/runs/{id}`` endpoint with an
Observer-friendly view that:

  - Pulls events from :class:`RunStore`
  - Aggregates Phase 0 V9 health (event_sync_ok / dashboard_replay_ok /
    missing_required_events) directly from event payloads
  - **Refuses to report 0% / blank when the run actually completed** —
    Phase 5 prompt explicitly forbids that "completed-but-shows-zero" UX.

Independent of SaaS schema so this works in CLI / LocalRuntime mode.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


def build_run_detail_router(
    *, run_store: Any,
) -> APIRouter:
    """Mount points:

      - ``GET /api/runs/{run_id}/detail``  Observer-targeted detail view.

    The route name picks the ``/detail`` suffix on purpose so it does NOT
    collide with SaaS' existing ``GET /api/runs/{id}`` (Phase 0 contract
    invariant: don't break existing endpoints).
    """
    router = APIRouter()

    @router.get("/api/runs/{run_id}/detail")
    async def get_detail(run_id: str) -> dict[str, Any]:
        if run_store is None:
            raise HTTPException(status_code=503, detail="RunStore unavailable")
        events = run_store.get_events(run_id) or []
        if not events:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

        return _summarize_run(run_id, events)

    return router


def _summarize_run(run_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase 5 detail view. Pure function so unit tests can pin it."""
    event_types = [e.get("event_type") for e in events if isinstance(e, dict)]

    # Pick the **last** task_completed / eval_completed event payloads
    # because they carry the V9 health snapshot we want to surface.
    completed_event = _find_last(events, "task.completed")
    eval_event = _find_last(events, "eval.completed")
    intent_event = _find_first(events, "intent.parsed")

    # Phase 0 13 必需事件 — Observer must show "complete" only when all 13
    # are present, mirroring sc.data.missing_required_events.
    REQUIRED = {
        "task.received", "intent.parsed", "context.budgeted",
        "temporal_memory.retrieved", "rag.retrieved",
        "context.compression_guard.checked", "context.built",
        "workflow.plan.created", "workflow.step.started",
        "workflow.step.completed", "eval.completed",
        "self_improvement.checked", "task.completed",
    }
    emitted = {t for t in event_types if t}
    missing = sorted(REQUIRED - emitted)

    is_completed = "task.completed" in emitted

    # Phase 5 prompt: "completed run 不能出现 0% 假象". When the run reached
    # task.completed, we report progress 100 even if no event happened
    # to carry progress_pct=100. This matches PHASE0_CONTRACT.md §3.1.
    progress_pct = _last_value(events, "progress_pct")
    if is_completed and (progress_pct is None or progress_pct == 0):
        progress_pct = 100

    current_stage = _last_value(events, "stage") or _last_value(events, "current_stage") or "unknown"
    if is_completed and current_stage in ("unknown", ""):
        current_stage = "completed"

    return {
        "run_id": run_id,
        "event_count": len(events),
        "current_stage": current_stage,
        "progress_pct": progress_pct,
        "is_completed": is_completed,
        "missing_required_events": missing,
        "event_sync_ok": is_completed and not missing,
        "task_input": (intent_event or {}).get("task_input", "") if intent_event else "",
        "eval_score": (eval_event or {}).get("eval_score") if eval_event else None,
        "eval_passed": (eval_event or {}).get("eval_passed") if eval_event else None,
        "completed_at": (completed_event or {}).get("timestamp") if completed_event else None,
    }


def _find_first(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for e in events:
        if isinstance(e, dict) and e.get("event_type") == event_type:
            return e
    return None


def _find_last(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    for e in reversed(events):
        if isinstance(e, dict) and e.get("event_type") == event_type:
            return e
    return None


def _last_value(events: list[dict[str, Any]], key: str) -> Any:
    """Walk events newest-first and return the first non-None ``key`` value."""
    for e in reversed(events):
        if not isinstance(e, dict):
            continue
        if key in e and e[key] is not None:
            return e[key]
    return None
