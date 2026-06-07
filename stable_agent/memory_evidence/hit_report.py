"""Build run-visible memory hit reports."""

from __future__ import annotations

from typing import Any

from stable_agent.memory_evidence.models import MemoryHitReport


def build_memory_hit_report(
    *,
    hits: list[dict[str, Any]] | None = None,
    misses: list[str] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    stage: str = "temporal_memory_retrieving",
) -> MemoryHitReport:
    memory_hits = list(hits or [])
    return MemoryHitReport(
        memory_hits=memory_hits,
        memory_misses=list(misses or ([] if memory_hits else ["no_relevant_memory"])),
        memory_conflicts=list(conflicts or []),
        memory_used_in_stage=stage,
        why_this_memory_zh=[
            str(item.get("reason_zh") or item.get("why_zh") or "与当前任务相关")
            for item in memory_hits
        ],
    )
