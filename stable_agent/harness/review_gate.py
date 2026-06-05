"""Phase 6 — Review gate.

The governance heart of the harness. Three guarantees, all enforced by
tests in ``test_review_gate_and_rollback.py``:

  1. **`ReviewGate.evaluate()` never promotes a skill.** The only path
     from `validated → promoted` runs through :meth:`ReviewGate.approve`
     which requires an explicit `reviewer` argument.
  2. **High-risk skills always require human review** regardless of the
     numeric ValidationDecision outcome.
  3. **Rollback ≠ demote**. When a regression is detected against an
     existing promoted version of the same skill, the new candidate is
     marked `rejected`. The promoted version is *not* changed — there
     is nothing to demote because nothing was auto-promoted in the
     first place.

Outcomes(:attr:`ReviewGateDecision.outcome`):

  ``SKIPPED_NO_PROPOSAL``       Curator skipped — nothing to do
  ``DUPLICATE_REJECTED``        Curator rejected a duplicate body
  ``VALIDATION_FAILED``         Validator rejected — candidate stays
  ``READY_FOR_HUMAN_REVIEW``    low-risk pass — queued for review
  ``HIGH_RISK_HUMAN_REVIEW``    high-risk — queued, flagged
  ``ROLLBACK_REQUIRED``         regression vs promoted — candidate rejected
  ``NO_GROUPS``                 Validator could not find related tasks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stable_agent.core.curator_service import CuratorDecision, CuratorOutcome
from stable_agent.core.validator_service import ValidationDecision, ValidationOutcome
from stable_agent.harness.review_queue import ReviewQueueStore
from stable_agent.skills import SkillStatus
from stable_agent.skills.repository import SkillRepository


class ReviewGateOutcome:
    """Tag values for :attr:`ReviewGateDecision.outcome`."""

    SKIPPED_NO_PROPOSAL = "skipped_no_proposal"
    DUPLICATE_REJECTED = "duplicate_rejected"
    VALIDATION_FAILED = "validation_failed"
    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"
    HIGH_RISK_HUMAN_REVIEW = "high_risk_human_review"
    ROLLBACK_REQUIRED = "rollback_required"
    NO_GROUPS = "no_groups"
    PROMOTED = "promoted"
    REJECTED = "rejected"


# Outcomes that mean "operator action needed" (queue must have a row).
QUEUED_OUTCOMES = frozenset({
    ReviewGateOutcome.READY_FOR_HUMAN_REVIEW,
    ReviewGateOutcome.HIGH_RISK_HUMAN_REVIEW,
})


@dataclass(frozen=True)
class ReviewGateDecision:
    outcome: str
    reason: str
    review_id: str | None = None
    skill_id: str = ""
    skill_version: int = 0
    risk_level: str = "low"

    @property
    def needs_human_review(self) -> bool:
        return self.outcome in QUEUED_OUTCOMES

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "review_id": self.review_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "risk_level": self.risk_level,
            "needs_human_review": self.needs_human_review,
        }


class ReviewGate:
    """Governance layer between Validator and skill promotion.

    Args:
        repo: shared :class:`SkillRepository` — gate transitions skill
            status here on ``approve``/``reject``.
        review_queue: :class:`ReviewQueueStore` for pending items.
    """

    def __init__(
        self,
        *,
        repo: SkillRepository,
        review_queue: ReviewQueueStore,
    ) -> None:
        self._repo = repo
        self._queue = review_queue

    # ------------------------------------------------------------------ #
    # evaluate — main entry point from HarnessFlow
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        curator: CuratorDecision,
        validation: ValidationDecision | None,
        *,
        validation_id: str | None = None,
    ) -> ReviewGateDecision:
        """Decide what happens next; queue if a human is needed."""
        # Curator skipped or rejected.
        if curator.outcome == CuratorOutcome.SKIPPED:
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.SKIPPED_NO_PROPOSAL,
                reason=curator.reason,
            )
        if curator.outcome == CuratorOutcome.REJECTED_DUPLICATE:
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.DUPLICATE_REJECTED,
                reason=curator.reason,
            )

        candidate = curator.candidate
        if candidate is None:
            # Defensive: Curator marked PROPOSED but no candidate. Treat
            # as skip; never auto-promote.
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.SKIPPED_NO_PROPOSAL,
                reason="curator marked proposed but produced no candidate",
            )

        skill_id = candidate.skill_id
        skill_version = candidate.version
        risk = candidate.frontmatter.risk_level

        # Validator absent → defensive skip.
        if validation is None:
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.SKIPPED_NO_PROPOSAL,
                reason="no validation decision (curator may have failed early)",
                skill_id=skill_id, skill_version=skill_version, risk_level=risk,
            )

        # No related task groups → can't validate; surface that.
        if validation.outcome == ValidationOutcome.NO_GROUPS:
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.NO_GROUPS,
                reason=validation.reason,
                skill_id=skill_id, skill_version=skill_version, risk_level=risk,
            )

        # High-risk: ALWAYS human review (regardless of numeric pass/fail).
        if validation.outcome == ValidationOutcome.DEFERRED_HUMAN_REVIEW or risk == "high":
            review_id = self._queue.submit(
                skill_id=skill_id,
                skill_version=skill_version,
                risk_level=risk,
                review_kind="HIGH_RISK",
                validation_id=validation_id,
                run_id=_run_id_from_source(candidate),
                reason=validation.reason,
            )
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.HIGH_RISK_HUMAN_REVIEW,
                reason=validation.reason,
                review_id=review_id,
                skill_id=skill_id, skill_version=skill_version, risk_level=risk,
            )

        # Validation failed at the numeric gate.
        if validation.outcome == ValidationOutcome.REJECTED:
            # Rollback case: there's an existing PROMOTED version of this
            # same skill_id and the new candidate regressed. We mark the
            # candidate REJECTED so it doesn't sit forever — the
            # already-promoted version is **untouched** (rollback ≠ demote).
            existing_promoted = self._existing_promoted_version(skill_id)
            if existing_promoted is not None:
                self._safe_reject_candidate(skill_id, skill_version)
                return ReviewGateDecision(
                    outcome=ReviewGateOutcome.ROLLBACK_REQUIRED,
                    reason=(
                        f"new candidate v{skill_version} regressed against "
                        f"promoted v{existing_promoted}; candidate rejected"
                    ),
                    skill_id=skill_id, skill_version=skill_version, risk_level=risk,
                )
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.VALIDATION_FAILED,
                reason=validation.reason,
                skill_id=skill_id, skill_version=skill_version, risk_level=risk,
            )

        # Validation passed AND low-risk → queue for human review.
        # ReviewGate.evaluate() NEVER promotes — that's the explicit
        # Phase 6 governance invariant.
        if validation.outcome == ValidationOutcome.VALIDATED:
            review_id = self._queue.submit(
                skill_id=skill_id,
                skill_version=skill_version,
                risk_level=risk,
                review_kind="READY",
                validation_id=validation_id,
                run_id=_run_id_from_source(candidate),
                reason=validation.reason,
            )
            return ReviewGateDecision(
                outcome=ReviewGateOutcome.READY_FOR_HUMAN_REVIEW,
                reason=validation.reason,
                review_id=review_id,
                skill_id=skill_id, skill_version=skill_version, risk_level=risk,
            )

        # Catch-all defensive — shouldn't reach here.
        return ReviewGateDecision(
            outcome=ReviewGateOutcome.VALIDATION_FAILED,
            reason=f"unhandled validation outcome: {validation.outcome}",
            skill_id=skill_id, skill_version=skill_version, risk_level=risk,
        )

    # ------------------------------------------------------------------ #
    # Operator-facing actions (only path to PROMOTED)
    # ------------------------------------------------------------------ #

    def approve(
        self,
        review_id: str,
        *,
        reviewer: str,
        reason: str = "approved by reviewer",
    ) -> ReviewGateDecision:
        """Promote the queued candidate. THE ONLY path to ``status=promoted``."""
        rec = self._queue.record_decision(
            review_id, verdict="approved", reviewer=reviewer, reason=reason,
        )
        skill_id = rec["skill_id"]
        skill_version = rec["skill_version"]

        # Walk lifecycle: candidate → validated → promoted.
        # If skill is already validated (Validator wrote it), skip the
        # candidate→validated jump.
        skill = self._repo.get(skill_id, skill_version)
        if skill.frontmatter.status == SkillStatus.CANDIDATE:
            self._repo.transition_status(skill_id, skill_version, SkillStatus.VALIDATED)
        promoted = self._repo.transition_status(skill_id, skill_version, SkillStatus.PROMOTED)

        return ReviewGateDecision(
            outcome=ReviewGateOutcome.PROMOTED,
            reason=reason,
            review_id=review_id,
            skill_id=skill_id,
            skill_version=skill_version,
            risk_level=promoted.frontmatter.risk_level,
        )

    def reject(
        self,
        review_id: str,
        *,
        reviewer: str,
        reason: str,
    ) -> ReviewGateDecision:
        """Reject the queued candidate (terminal status REJECTED)."""
        rec = self._queue.record_decision(
            review_id, verdict="rejected", reviewer=reviewer, reason=reason,
        )
        skill_id = rec["skill_id"]
        skill_version = rec["skill_version"]
        self._safe_reject_candidate(skill_id, skill_version)
        return ReviewGateDecision(
            outcome=ReviewGateOutcome.REJECTED,
            reason=reason,
            review_id=review_id,
            skill_id=skill_id,
            skill_version=skill_version,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _existing_promoted_version(self, skill_id: str) -> int | None:
        """Highest promoted version of ``skill_id``, or None."""
        for row in self._repo.index.list_promoted():
            if row["skill_id"] == skill_id:
                return int(row["version"])
        return None

    def _safe_reject_candidate(self, skill_id: str, version: int) -> None:
        """Move candidate → rejected; ignore if already terminal.

        Lifecycle (Phase 2): rejected is terminal, archived is terminal.
        Trying to transition from a terminal state would raise; this
        helper makes the gate idempotent.
        """
        try:
            skill = self._repo.get(skill_id, version)
        except Exception:
            return
        if skill.frontmatter.status in (SkillStatus.REJECTED, SkillStatus.ARCHIVED):
            return
        try:
            # candidate → rejected and validated → rejected are both legal
            # per Phase 2 lifecycle. Promoted → rejected is NOT legal,
            # which is exactly the rollback-≠-demote invariant.
            self._repo.transition_status(skill_id, version, SkillStatus.REJECTED)
        except Exception:
            # If something else is wrong (e.g. promoted state) we leave
            # the skill alone rather than silently demoting a promoted
            # version — that's the Phase 6 governance rule.
            pass


def _run_id_from_source(candidate: Any) -> str:
    """Best-effort run_id extraction from candidate's frontmatter."""
    try:
        runs = candidate.frontmatter.source_runs
        if runs:
            return runs[0]
    except AttributeError:
        pass
    return ""
