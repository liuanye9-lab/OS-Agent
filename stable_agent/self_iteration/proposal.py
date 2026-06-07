"""Self-iteration proposal model."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SelfIterationProposal:
    proposal_id: str
    source_type: str
    source_ref: str
    objective_zh: str
    status: str = "ready_for_human_review"
    proposed_files: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=lambda: ["no_auto_merge", "no_auto_deploy", "human_review_required"])

    @classmethod
    def create(cls, *, source_type: str, source_ref: str, objective_zh: str, proposed_files: list[str] | None = None) -> "SelfIterationProposal":
        return cls(
            proposal_id=f"self_iter_{uuid.uuid4().hex[:12]}",
            source_type=source_type,
            source_ref=source_ref,
            objective_zh=objective_zh,
            proposed_files=proposed_files or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
