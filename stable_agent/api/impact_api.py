"""Phase 5 — Impact API.

The Impact Report aggregates *what changed because of OS-Agent on this run*:

  - **memory hits**: events that touched temporal memory
  - **skill hits**: candidate / validated / promoted skills used or proposed
  - **token impact**: from ``token.budget.estimated`` event payload
  - **required-event completeness**: from Phase 0 13 events
  - **learning impact**: candidate / regression / patch events,
    captured in deterministic order so Observer can render a timeline

This is the load-bearing piece for Phase 5 prompt's "memory hit /
skill hit / impact report" panel and for Phase 6's audit log.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


# Event vocab used by the V9 emitter (see unified_tool_registry.py).
MEMORY_EVENT_TYPES = (
    "temporal_memory.retrieved",
    "memory.update.candidate",
    "memory.review.completed",
)
SKILL_EVENT_TYPES = (
    "skill.candidate.created",
    "skill.patch.proposed",
    "skill.validated",
    "skill.promoted",
    "skill.exported",
)
LEARNING_EVENT_TYPES = (
    "regression.generated",
    "skill.candidate.created",
    "skill.patch.proposed",
    "validation.checked",
    "human_review.required",
    "human_review.completed",
)


def build_impact_router(*, run_store: Any) -> APIRouter:
    """Mount ``GET /api/runs/{run_id}/impact``."""
    router = APIRouter()

    @router.get("/api/runs/{run_id}/impact")
    async def get_impact(run_id: str) -> dict[str, Any]:
        if run_store is None:
            raise HTTPException(status_code=503, detail="RunStore unavailable")
        events = run_store.get_events(run_id) or []
        if not events:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return build_impact_report(run_id, events)

    return router


def build_impact_report(
    run_id: str, events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure function — given a run's event list, return the impact view.

    Designed so :mod:`tests.test_observer_impact_compare` can assert
    behavior without a FastAPI app.
    """
    memory_hits = [
        _shrink_event(e) for e in events
        if isinstance(e, dict) and e.get("event_type") in MEMORY_EVENT_TYPES
    ]
    skill_hits = [
        _shrink_event(e) for e in events
        if isinstance(e, dict) and e.get("event_type") in SKILL_EVENT_TYPES
    ]
    learning_timeline = [
        _shrink_event(e) for e in events
        if isinstance(e, dict) and e.get("event_type") in LEARNING_EVENT_TYPES
    ]

    token_impact = _extract_token_impact(events)
    eval_impact = _extract_eval_impact(events)

    # required-event completeness ratio in [0, 1] — Phase 0 13 events
    REQUIRED = {
        "task.received", "intent.parsed", "context.budgeted",
        "temporal_memory.retrieved", "rag.retrieved",
        "context.compression_guard.checked", "context.built",
        "workflow.plan.created", "workflow.step.started",
        "workflow.step.completed", "eval.completed",
        "self_improvement.checked", "task.completed",
    }
    emitted = {
        e.get("event_type") for e in events
        if isinstance(e, dict) and e.get("event_type")
    }
    completeness = len(REQUIRED & emitted) / len(REQUIRED) if REQUIRED else 1.0

    return {
        "run_id": run_id,
        "memory_hits": memory_hits,
        "memory_hit_count": len(memory_hits),
        "skill_hits": skill_hits,
        "skill_hit_count": len(skill_hits),
        "learning_timeline": learning_timeline,
        "token_impact": token_impact,
        "eval_impact": eval_impact,
        "required_event_completeness": completeness,
    }


# --------------------------------------------------------------------------- #
# Helpers — keep payloads small so Observer JS doesn't ship an MB of JSON
# --------------------------------------------------------------------------- #

def _shrink_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return only the keys Observer renders, dropping noisy nested data."""
    keep = {
        "event_type", "stage", "stage_label_zh", "timestamp",
        "decision_summary_zh", "why_zh", "next_step_zh",
        "selected_memories", "skill_id", "skill_version",
        "candidate_skill_ids", "validation_id", "task_group_id",
        "approval_id", "risk_level",
    }
    return {k: v for k, v in event.items() if k in keep}


def _extract_token_impact(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull token.budget.estimated payload + token_report fallback."""
    for e in reversed(events):
        if not isinstance(e, dict):
            continue
        if e.get("event_type") == "token.budget.estimated":
            tr = e.get("token_report") or {}
            return {
                "saved_tokens_estimated": tr.get("saved_tokens_estimated"),
                "saving_ratio": tr.get("saving_ratio"),
                "baseline_tokens_estimated": tr.get("baseline_tokens_estimated"),
                "candidate_context_tokens": tr.get("candidate_context_tokens"),
                "summary_zh": tr.get("summary_zh", ""),
            }
    return {
        "saved_tokens_estimated": None,
        "saving_ratio": None,
        "baseline_tokens_estimated": None,
        "candidate_context_tokens": None,
        "summary_zh": "",
    }


def _extract_eval_impact(events: list[dict[str, Any]]) -> dict[str, Any]:
    for e in reversed(events):
        if isinstance(e, dict) and e.get("event_type") == "eval.completed":
            return {
                "eval_score": e.get("eval_score"),
                "eval_passed": e.get("eval_passed"),
                "decision_summary_zh": e.get("decision_summary_zh", ""),
            }
    return {"eval_score": None, "eval_passed": None, "decision_summary_zh": ""}
