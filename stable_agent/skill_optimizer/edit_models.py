"""Bounded SkillOpt edit models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SkillEditOperation = Literal[
    "ADD_SECTION",
    "DELETE_SECTION",
    "REPLACE_SECTION",
    "ADD_RULE",
    "REPLACE_RULE",
    "DELETE_RULE",
]

ALLOWED_OPERATIONS: set[str] = {
    "ADD_SECTION",
    "DELETE_SECTION",
    "REPLACE_SECTION",
    "ADD_RULE",
    "REPLACE_RULE",
    "DELETE_RULE",
}


@dataclass
class BoundedSkillEdit:
    operation: SkillEditOperation
    target: str
    content: str = ""
    reason_zh: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundedEditResult:
    accepted: bool
    content: str
    reason_zh: str
    changed_lines: int = 0
    changed_sections: int = 0
    rejected: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
