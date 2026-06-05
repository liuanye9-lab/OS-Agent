"""Phase 3 — Validator service.

Wires :class:`CuratorService` output through :class:`ABValidationRunner`
and the lifecycle gate. Validator is the **only** caller that should
move skills from ``candidate`` → ``validated``; promotion still requires
human review (Phase 5/6).

End-to-end flow:

    candidate ──▶ pick TaskGroups (related-task selection)
              ──▶ ABValidationRunner.run() per group
              ──▶ aggregate ValidationReports
              ──▶ if any group passes criteria + low-risk:
                       transition to validated
                  else:
                       keep as candidate; reason carried in result

High-risk skills (frontmatter ``risk_level=high``) **never** auto-validate;
they always end up requiring human review (Phase 6 review gate).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from stable_agent.eval.ab_validation_runner import (
    ABValidationRunner,
    PromotionCriteria,
    TaskRunner,
    ValidationReport,
)
from stable_agent.eval.task_group_store import TaskGroup, TaskGroupStore
from stable_agent.skills.models import SkillDocument, SkillStatus
from stable_agent.skills.repository import SkillRepository

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #

class ValidationOutcome:
    """Tag values for :attr:`ValidationDecision.outcome`."""

    VALIDATED = "validated"
    REJECTED = "rejected"
    DEFERRED_HUMAN_REVIEW = "deferred_human_review"
    NO_GROUPS = "no_groups"


@dataclass(frozen=True)
class ValidationDecision:
    """Aggregate decision across all related groups."""

    outcome: str
    reason: str
    reports: tuple[ValidationReport, ...] = field(default_factory=tuple)
    skill_id: str = ""
    version: int = 0

    @property
    def passed(self) -> bool:
        return self.outcome == ValidationOutcome.VALIDATED


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #

class ValidatorService:
    """Validate one candidate against its related task groups.

    Args:
        repo: :class:`SkillRepository` (status transitions land here).
        groups: :class:`TaskGroupStore` for related-task selection.
        runner: pre-built :class:`ABValidationRunner`. Inject the
            in-memory runner in unit tests; LocalRuntime-backed runner
            in production.
        criteria: optional override of :class:`PromotionCriteria`. Phase 3
            uses ``min_delta_score_promote=0.03`` and ``regression_rate=0``
            by default.
    """

    def __init__(
        self,
        *,
        repo: SkillRepository,
        groups: TaskGroupStore,
        runner: ABValidationRunner,
    ) -> None:
        self._repo = repo
        self._groups = groups
        self._runner = runner

    def validate(
        self,
        skill: SkillDocument,
        *,
        explicit_groups: Iterable[TaskGroup] | None = None,
        max_groups: int = 5,
    ) -> ValidationDecision:
        """Validate ``skill`` against its related groups.

        ``skill`` must be in ``status=candidate`` (Curator's job to put
        it there). Validator never re-validates promoted skills here.

        ``explicit_groups`` overrides related-task selection (used in
        unit tests + when CI fixtures already pin which groups apply).
        """
        if skill.frontmatter.status != SkillStatus.CANDIDATE:
            return ValidationDecision(
                outcome=ValidationOutcome.REJECTED,
                reason=(
                    f"skill must be in candidate status, got "
                    f"{skill.frontmatter.status.value}"
                ),
                skill_id=skill.skill_id,
                version=skill.version,
            )

        groups = list(explicit_groups) if explicit_groups else self._select_groups(skill, max_groups)
        if not groups:
            return ValidationDecision(
                outcome=ValidationOutcome.NO_GROUPS,
                reason="no related task groups found for candidate",
                skill_id=skill.skill_id,
                version=skill.version,
            )

        reports: list[ValidationReport] = [
            self._runner.run(skill, group) for group in groups
        ]

        # High-risk → mandatory human review even if all groups pass.
        if skill.frontmatter.risk_level == "high":
            return ValidationDecision(
                outcome=ValidationOutcome.DEFERRED_HUMAN_REVIEW,
                reason="high risk_level requires human review before promotion",
                reports=tuple(reports),
                skill_id=skill.skill_id,
                version=skill.version,
            )

        # All groups must pass for the candidate to advance.
        failing = [r for r in reports if not r.passed]
        if failing:
            return ValidationDecision(
                outcome=ValidationOutcome.REJECTED,
                reason=self._summarize_failures(failing),
                reports=tuple(reports),
                skill_id=skill.skill_id,
                version=skill.version,
            )

        # Update metrics from the best report (highest avg_score_delta).
        best = max(reports, key=lambda r: r.avg_score_delta)
        from stable_agent.skills.models import Metrics, SkillFrontmatter
        m = skill.frontmatter.metrics
        new_metrics = Metrics(
            validations=m.validations + len(reports),
            win_rate=1.0,
            avg_token_delta=best.avg_token_delta_ratio,
            avg_latency_delta=best.avg_latency_delta_ratio,
            last_validation_score=best.avg_score_delta,
        )
        new_fm = SkillFrontmatter(
            skill_id=skill.frontmatter.skill_id,
            version=skill.frontmatter.version,
            status=SkillStatus.VALIDATED,
            domain=skill.frontmatter.domain,
            owner=skill.frontmatter.owner,
            created_at=skill.frontmatter.created_at,
            updated_at=skill.frontmatter.updated_at,
            retrieval_tags=skill.frontmatter.retrieval_tags,
            task_types=skill.frontmatter.task_types,
            triggers=skill.frontmatter.triggers,
            metrics=new_metrics,
            source_runs=skill.frontmatter.source_runs,
            dependencies=skill.frontmatter.dependencies,
            risk_level=skill.frontmatter.risk_level,
            signature_sha256=skill.frontmatter.signature_sha256,
            simhash64=skill.frontmatter.simhash64,
        )
        updated = skill.with_frontmatter(new_fm)
        # Persist with metrics; ``allow_existing_signature=True`` because
        # the body did not change — only metrics + status.
        self._repo.write(updated, allow_existing_signature=True)

        return ValidationDecision(
            outcome=ValidationOutcome.VALIDATED,
            reason=f"all {len(reports)} group(s) passed; best avg_delta={best.avg_score_delta:.4f}",
            reports=tuple(reports),
            skill_id=skill.skill_id,
            version=skill.version,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _select_groups(
        self, skill: SkillDocument, max_groups: int,
    ) -> list[TaskGroup]:
        fm = skill.frontmatter
        return self._groups.find_related(
            task_type=fm.task_types[0] if fm.task_types else None,
            retrieval_tags=fm.retrieval_tags,
            limit=max_groups,
        )

    @staticmethod
    def _summarize_failures(failing: list[ValidationReport]) -> str:
        """Compact failure summary for the decision reason."""
        parts = [
            f"{r.group_id}: {r.reason}"
            for r in failing
        ]
        return "; ".join(parts)
