"""Research watcher source models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ResearchQuery:
    source: str
    query: str
    max_results: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementProposal:
    proposal_id: str
    finding_id: str
    status: str
    summary_zh: str
    proposed_changes: list[str]
    requires_validation: bool = True
    requires_human_review: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
