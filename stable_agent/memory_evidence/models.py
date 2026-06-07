"""Evidence-gated memory models."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

MemoryStatus = Literal["candidate", "active", "conflict", "deprecated"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class MemoryCandidate:
    memory_id: str
    content_summary: str
    source_type: str
    source_ref: str
    confidence: float
    status: MemoryStatus
    created_at: str
    last_used_at: str | None
    evidence_refs: list[str]

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.status == "active" and not self.evidence_refs:
            raise ValueError("active memory requires evidence_refs")
        self.content_summary = sanitize_private_text(self.content_summary)
        self.source_ref = sanitize_private_text(self.source_ref)

    @classmethod
    def create(
        cls,
        *,
        content_summary: str,
        source_type: str,
        source_ref: str,
        confidence: float = 0.6,
        evidence_refs: list[str] | None = None,
        status: MemoryStatus = "candidate",
    ) -> "MemoryCandidate":
        return cls(
            memory_id=f"mem_{uuid.uuid4().hex[:12]}",
            content_summary=content_summary,
            source_type=source_type,
            source_ref=source_ref,
            confidence=confidence,
            status=status,
            created_at=utc_now_iso(),
            last_used_at=None,
            evidence_refs=list(evidence_refs or []),
        )

    def can_activate(self) -> bool:
        return bool(self.evidence_refs) and self.status not in {"conflict", "deprecated"}

    def mark_active(self) -> "MemoryCandidate":
        if not self.can_activate():
            raise ValueError("memory cannot become active without evidence_refs or while conflicted")
        return MemoryCandidate(
            memory_id=self.memory_id,
            content_summary=self.content_summary,
            source_type=self.source_type,
            source_ref=self.source_ref,
            confidence=self.confidence,
            status="active",
            created_at=self.created_at,
            last_used_at=utc_now_iso(),
            evidence_refs=list(self.evidence_refs),
        )

    def mark_conflict(self) -> "MemoryCandidate":
        data = self.to_dict()
        data["status"] = "conflict"
        return MemoryCandidate(**data)

    def mark_deprecated(self) -> "MemoryCandidate":
        data = self.to_dict()
        data["status"] = "deprecated"
        return MemoryCandidate(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryHitReport:
    memory_hits: list[dict[str, Any]] = field(default_factory=list)
    memory_misses: list[str] = field(default_factory=list)
    memory_conflicts: list[dict[str, Any]] = field(default_factory=list)
    memory_used_in_stage: str = ""
    why_this_memory_zh: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PRIVATE_PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w.-]+"), "[redacted-email]"),
    (re.compile(r"(sk-|ghp_|xoxb-)[A-Za-z0-9_-]+"), "[redacted-secret]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[redacted-id]"),
)


def sanitize_private_text(text: str) -> str:
    value = text or ""
    for pattern, replacement in _PRIVATE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value[:500]
