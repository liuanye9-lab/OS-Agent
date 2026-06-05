"""Phase 6 — `harness plan` (dry-run) helper.

Given an existing :class:`CuratorInput`, return what :class:`HarnessFlow`
*would* do without writing any files. Used by Phase 6 CLI ``harness
plan`` and by operators to preview the impact of a proposed change.

Implementation note: we run Curator's policy check directly (no skill
write, no validator run) and return a structured preview. This is
strictly read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stable_agent.core.curator_service import CuratorInput, CuratorPolicy


@dataclass(frozen=True)
class PlanResult:
    """Dry-run preview of a HarnessFlow run."""

    would_propose: bool
    reason: str
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "would_propose": self.would_propose,
            "reason": self.reason,
            "next_step": self.next_step,
        }


def plan(inp: CuratorInput, *, policy: CuratorPolicy | None = None) -> PlanResult:
    """Return what HarnessFlow would do for ``inp`` (no side effects)."""
    pol = policy or CuratorPolicy()
    propose, reason = pol.should_propose(inp)
    if not propose:
        return PlanResult(
            would_propose=False, reason=reason,
            next_step="no learning signal — HarnessFlow would skip",
        )
    return PlanResult(
        would_propose=True, reason=reason,
        next_step=(
            "HarnessFlow would: write candidate skill → run validator → "
            "save validation report → submit to ReviewGate"
        ),
    )
