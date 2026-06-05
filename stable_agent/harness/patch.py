"""Phase 6 — `harness patch` skill-patch descriptor.

A "skill patch" in OS-Agent is **not** a code patch. It's a structured
description of the (skill_id, version) the harness wants the operator
to commit to git as a PR. Phase 6 keeps `patch` small because the
actual content lives in the skill artifact on disk; this module is
just the metadata wrapper.

Used by ``stable_agent.harness.__main__`` to produce JSON descriptors
that fit into PR bodies / change logs / audit logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stable_agent.harness.flow import HarnessReport
from stable_agent.skills.repository import SkillRepository


@dataclass(frozen=True)
class SkillPatchDescriptor:
    """A patch the harness suggests committing to git via PR.

    Phase 6 is **PR-only** — the harness never touches git. The
    descriptor exists so an external tool (gh CLI, GitHub Action) can
    produce a PR.
    """

    skill_id: str
    skill_version: int
    artifact_path: str
    review_id: str | None
    validation_id: str | None
    review_required: bool
    risk_level: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "artifact_path": self.artifact_path,
            "review_id": self.review_id,
            "validation_id": self.validation_id,
            "review_required": self.review_required,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def build_patch(
    report: HarnessReport,
    *,
    repo: SkillRepository,
) -> SkillPatchDescriptor | None:
    """Translate a :class:`HarnessReport` into a :class:`SkillPatchDescriptor`.

    Returns ``None`` if the harness did not produce a candidate (skipped,
    duplicate, no_groups, etc.). The PR-builder should treat that as
    "nothing to commit".
    """
    candidate = report.curator.candidate
    if candidate is None:
        return None

    artifact_rel = Path("skills") / "repo" / candidate.skill_id / f"v{candidate.version}.md"

    review = report.review
    summary_parts = [
        f"skill {candidate.skill_id}@v{candidate.version}",
        f"outcome={report.outcome}",
    ]
    if report.validation is not None and report.validation.reports:
        best = max(report.validation.reports, key=lambda r: r.avg_score_delta)
        summary_parts.append(f"avg_score_delta={best.avg_score_delta:.4f}")
    summary = "; ".join(summary_parts)

    return SkillPatchDescriptor(
        skill_id=candidate.skill_id,
        skill_version=candidate.version,
        artifact_path=str(artifact_rel),
        review_id=review.review_id if review else None,
        validation_id=report.validation_id,
        review_required=bool(review and review.needs_human_review),
        risk_level=candidate.frontmatter.risk_level,
        summary=summary,
    )
