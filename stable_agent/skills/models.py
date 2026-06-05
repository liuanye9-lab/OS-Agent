"""Phase 2 SkillRepo v2 — data models.

Skills are stored as Markdown files with YAML frontmatter. The frontmatter
captures all governance metadata; the body holds the human/agent-facing
prose under H1 sections (``# Intent``, ``# Procedure``, ``# Guardrails``,
``# Positive examples``, ``# Negative examples``, ``# Patch history``).

This module defines the in-memory representation. Parsing/serialization
lives in :mod:`stable_agent.skills.repository`. SQLite indexing lives in
:mod:`stable_agent.skills.index_store`. Signatures live in
:mod:`stable_agent.skills.signature`.

Design constraints (Phase 2 PR ack list):
  - **immutable** — all dataclasses are ``frozen``; ``transition`` returns
    a new ``SkillDocument``
  - **no auto-overwrite of ``best_skill.md``** — that's a derived export
  - **promoted-only retrieval** — non-promoted statuses never enter the
    primary retrieval path; index_store enforces this
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class SkillStatus(str, Enum):
    """Lifecycle states for a skill version.

    Legal transitions live in :data:`stable_agent.skills.lifecycle.LEGAL_TRANSITIONS`.
    Only ``promoted`` skills participate in primary retrieval.
    """

    DRAFT = "draft"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Triggers:
    """Retrieval triggers — keyword guards used by router-side filters.

    These are *additive guards* on top of tag/BM25 search; they do not
    drive recall by themselves. ``must_contain`` and ``must_avoid`` are
    hard filters; ``should_contain`` are soft signals.
    """

    must_contain: tuple[str, ...] = field(default_factory=tuple)
    should_contain: tuple[str, ...] = field(default_factory=tuple)
    must_avoid: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Metrics:
    """Validation / usage metrics surfaced to the index_store and Observer."""

    validations: int = 0
    win_rate: float = 0.0
    avg_token_delta: float = 0.0
    avg_latency_delta: float = 0.0
    last_validation_score: float = 0.0


# Canonical body section names. Order matters for round-trip serialization.
SECTION_ORDER: tuple[str, ...] = (
    "Intent",
    "Procedure",
    "Guardrails",
    "Positive examples",
    "Negative examples",
    "Patch history",
)


@dataclass(frozen=True)
class SkillFrontmatter:
    """All governance metadata for one skill version.

    ``signature_sha256`` and ``simhash64`` are computed at write time from
    Intent + Procedure + Guardrails + sorted retrieval_tags — see
    :func:`stable_agent.skills.signature.canonicalize`.
    """

    skill_id: str
    version: int = 1
    status: SkillStatus = SkillStatus.DRAFT
    domain: str = "coding"
    owner: str = "curator_v1"
    created_at: str = ""
    updated_at: str = ""
    retrieval_tags: tuple[str, ...] = field(default_factory=tuple)
    task_types: tuple[str, ...] = field(default_factory=tuple)
    triggers: Triggers = field(default_factory=Triggers)
    metrics: Metrics = field(default_factory=Metrics)
    source_runs: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"
    signature_sha256: str = ""
    simhash64: str = ""  # stored as 16-char hex for portability

    def to_yaml_dict(self) -> dict[str, Any]:
        """Frontmatter shape ready for ``yaml.safe_dump``."""
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "status": self.status.value,
            "domain": self.domain,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retrieval_tags": list(self.retrieval_tags),
            "task_types": list(self.task_types),
            "triggers": {
                "must_contain": list(self.triggers.must_contain),
                "should_contain": list(self.triggers.should_contain),
                "must_avoid": list(self.triggers.must_avoid),
            },
            "metrics": {
                "validations": self.metrics.validations,
                "win_rate": self.metrics.win_rate,
                "avg_token_delta": self.metrics.avg_token_delta,
                "avg_latency_delta": self.metrics.avg_latency_delta,
                "last_validation_score": self.metrics.last_validation_score,
            },
            "source_runs": list(self.source_runs),
            "dependencies": list(self.dependencies),
            "risk_level": self.risk_level,
            "signature_sha256": self.signature_sha256,
            "simhash64": self.simhash64,
        }

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> "SkillFrontmatter":
        """Build a frontmatter instance from a parsed YAML dict.

        Defensive: missing fields default to empty/zero. Unknown fields are
        ignored — frontmatter is meant to be additive.
        """
        triggers_data = data.get("triggers") or {}
        metrics_data = data.get("metrics") or {}

        return cls(
            skill_id=str(data.get("skill_id", "")),
            version=int(data.get("version", 1)),
            status=SkillStatus(data.get("status", SkillStatus.DRAFT.value)),
            domain=str(data.get("domain", "coding")),
            owner=str(data.get("owner", "curator_v1")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            retrieval_tags=tuple(data.get("retrieval_tags") or ()),
            task_types=tuple(data.get("task_types") or ()),
            triggers=Triggers(
                must_contain=tuple(triggers_data.get("must_contain") or ()),
                should_contain=tuple(triggers_data.get("should_contain") or ()),
                must_avoid=tuple(triggers_data.get("must_avoid") or ()),
            ),
            metrics=Metrics(
                validations=int(metrics_data.get("validations", 0)),
                win_rate=float(metrics_data.get("win_rate", 0.0)),
                avg_token_delta=float(metrics_data.get("avg_token_delta", 0.0)),
                avg_latency_delta=float(metrics_data.get("avg_latency_delta", 0.0)),
                last_validation_score=float(metrics_data.get("last_validation_score", 0.0)),
            ),
            source_runs=tuple(data.get("source_runs") or ()),
            dependencies=tuple(data.get("dependencies") or ()),
            risk_level=str(data.get("risk_level", "low")),
            signature_sha256=str(data.get("signature_sha256", "")),
            simhash64=str(data.get("simhash64", "")),
        )


@dataclass(frozen=True)
class SkillDocument:
    """A skill version: frontmatter + sectioned markdown body.

    ``sections`` keys are normalized to title case (``"Intent"``, etc.);
    unknown sections are preserved as-is to keep the format extensible.
    """

    frontmatter: SkillFrontmatter
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def skill_id(self) -> str:
        return self.frontmatter.skill_id

    @property
    def version(self) -> int:
        return self.frontmatter.version

    @property
    def status(self) -> SkillStatus:
        return self.frontmatter.status

    def with_frontmatter(self, fm: SkillFrontmatter) -> "SkillDocument":
        """Return a copy with replaced frontmatter (immutable update)."""
        return replace(self, frontmatter=fm)

    def section(self, name: str, default: str = "") -> str:
        """Read a body section by canonical title-cased name."""
        return self.sections.get(name, default)
