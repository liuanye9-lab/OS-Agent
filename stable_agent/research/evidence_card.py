"""Research evidence card model."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any, Literal

ResearchStatus = Literal["evidence_only", "proposal", "candidate", "rejected"]


@dataclass
class ResearchEvidenceCard:
    finding_id: str
    source_type: str
    source_url: str
    title: str
    claims: list[str]
    evidence_summary: str
    applicable_modules: list[str]
    risks: list[str]
    proposed_changes: list[str]
    status: ResearchStatus = "evidence_only"

    @classmethod
    def create(
        cls,
        *,
        source_type: str,
        source_url: str,
        title: str,
        claims: list[str],
        evidence_summary: str,
        applicable_modules: list[str] | None = None,
        risks: list[str] | None = None,
        proposed_changes: list[str] | None = None,
        status: ResearchStatus = "evidence_only",
    ) -> "ResearchEvidenceCard":
        if status not in {"evidence_only", "proposal", "candidate", "rejected"}:
            raise ValueError("invalid research status")
        return cls(
            finding_id=f"finding_{uuid.uuid4().hex[:12]}",
            source_type=source_type,
            source_url=source_url,
            title=title,
            claims=claims,
            evidence_summary=evidence_summary,
            applicable_modules=applicable_modules or [],
            risks=risks or ["external evidence must be validated before use"],
            proposed_changes=proposed_changes or [],
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
