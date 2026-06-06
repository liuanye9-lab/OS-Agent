"""Simple evidence memory decay policy."""

from __future__ import annotations

from datetime import datetime, timezone

from stable_agent.memory_evidence.models import MemoryCandidate


class DecayPolicy:
    def __init__(self, stale_after_days: int = 90) -> None:
        self.stale_after_days = stale_after_days

    def apply(self, candidates: list[MemoryCandidate], *, now: datetime | None = None) -> list[MemoryCandidate]:
        current = now or datetime.now(timezone.utc)
        out: list[MemoryCandidate] = []
        for candidate in candidates:
            try:
                created = datetime.fromisoformat(candidate.created_at.replace("Z", "+00:00"))
                age_days = (current - created).days
            except ValueError:
                age_days = 0
            if candidate.status == "active" and age_days > self.stale_after_days:
                out.append(candidate.mark_deprecated())
            else:
                out.append(candidate)
        return out
