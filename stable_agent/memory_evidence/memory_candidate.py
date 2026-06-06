"""Helpers for memory candidate creation and activation."""

from __future__ import annotations

from stable_agent.memory_evidence.models import MemoryCandidate


def create_memory_candidate(
    content: str,
    *,
    source_type: str = "user_feedback",
    source_ref: str = "",
    evidence_refs: list[str] | None = None,
    confidence: float = 0.6,
) -> MemoryCandidate:
    return MemoryCandidate.create(
        content_summary=content,
        source_type=source_type,
        source_ref=source_ref,
        evidence_refs=evidence_refs or [],
        confidence=confidence,
        status="candidate",
    )


def activate_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    return candidate.mark_active()
