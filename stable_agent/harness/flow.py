"""Phase 6 — Harness flow orchestration.

Composes Phase 3 Curator → Validator → Phase 5 ValidationReportStore →
Phase 6 ReviewGate into a single deterministic pipeline. The flow is
the **only** entry point that should drive the candidate lifecycle in
production — direct calls to Curator/Validator are still allowed but
unsafe (they skip the review queue).

Design choices:

  - **Pure composition**: HarnessFlow has no Orchestrator / LLM / FastAPI
    dependency. It accepts services in the constructor; tests inject
    fakes (InMemoryRunner) and production injects LocalRuntime-backed.
  - **Side-effect order is fixed**: write candidate skill → run validation →
    persist report → write review queue item. Each step is observable
    from the returned :class:`HarnessReport`.
  - **PR-only**: HarnessFlow never modifies git. It writes skills /
    reports / queue items to disk; an external Phase 6 CLI / CI step
    bundles those into a PR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from stable_agent.api.validation_store import ValidationReportStore
from stable_agent.core.curator_service import CuratorDecision, CuratorInput, CuratorService
from stable_agent.core.validator_service import ValidationDecision, ValidatorService
from stable_agent.eval.task_group_store import TaskGroup
from stable_agent.harness.review_gate import ReviewGate, ReviewGateDecision
from stable_agent.skills.repository import SkillRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HarnessReport:
    """Aggregate output of one :meth:`HarnessFlow.run` call.

    Designed to be JSON-friendly so :mod:`stable_agent.harness.__main__`
    can pretty-print it for the operator.
    """

    run_id: str
    curator: CuratorDecision
    validation: ValidationDecision | None = None
    validation_id: str | None = None
    review: ReviewGateDecision | None = None

    @property
    def outcome(self) -> str:
        """One-word summary used by CI / log lines.

        Resolution priority: review > validation > curator. The first
        non-null layer's outcome wins, because earlier layers never see
        rejection from later layers.
        """
        if self.review is not None:
            return self.review.outcome
        if self.validation is not None:
            return f"validator:{self.validation.outcome}"
        return f"curator:{self.curator.outcome}"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "outcome": self.outcome,
            "curator": {
                "outcome": self.curator.outcome,
                "reason": self.curator.reason,
                "candidate_skill_id": (
                    self.curator.candidate.skill_id if self.curator.candidate else None
                ),
                "candidate_version": (
                    self.curator.candidate.version if self.curator.candidate else None
                ),
            },
            "validation": {
                "outcome": self.validation.outcome,
                "reason": self.validation.reason,
                "report_count": len(self.validation.reports),
            } if self.validation is not None else None,
            "validation_id": self.validation_id,
            "review": self.review.to_dict() if self.review is not None else None,
        }


class HarnessFlow:
    """End-to-end candidate pipeline: Curator → Validator → ReviewGate.

    Args:
        curator: configured :class:`CuratorService`.
        validator: configured :class:`ValidatorService`.
        validation_store: :class:`ValidationReportStore` for persistence.
        review_gate: :class:`ReviewGate` for governance + queue writes.
        repo: shared :class:`SkillRepository` (already used by curator/
            validator) — kept here for consistency assertions during
            tests, not used at runtime.
    """

    def __init__(
        self,
        *,
        curator: CuratorService,
        validator: ValidatorService,
        validation_store: ValidationReportStore,
        review_gate: ReviewGate,
        repo: SkillRepository | None = None,
    ) -> None:
        self._curator = curator
        self._validator = validator
        self._validation_store = validation_store
        self._review_gate = review_gate
        self._repo = repo

    def run(
        self,
        inp: CuratorInput,
        *,
        related_groups: Iterable[TaskGroup] | None = None,
    ) -> HarnessReport:
        """Run the full pipeline once.

        ``related_groups`` overrides Validator's automatic
        related-task selection (matches Phase 3 ValidatorService API).
        Use it in CI / harness fixture runs where you want determinism.
        """
        curator_decision = self._curator.evaluate(inp)

        # Curator skipped or rejected — nothing to validate.
        if not curator_decision.proposed or curator_decision.candidate is None:
            review = self._review_gate.evaluate(curator_decision, validation=None)
            return HarnessReport(
                run_id=inp.run_id,
                curator=curator_decision,
                review=review,
            )

        # Validate.
        validation = self._validator.validate(
            curator_decision.candidate,
            explicit_groups=related_groups,
        )

        # Persist the validation report set so Phase 5 Compare API and
        # Phase 6 review queue can look it up.
        validation_id = self._validation_store.save(
            _aggregate_report(validation),
            run_id=inp.run_id,
        ) if validation.reports else None

        review = self._review_gate.evaluate(
            curator_decision,
            validation=validation,
            validation_id=validation_id,
        )

        return HarnessReport(
            run_id=inp.run_id,
            curator=curator_decision,
            validation=validation,
            validation_id=validation_id,
            review=review,
        )


def _aggregate_report(validation: ValidationDecision):
    """Pick the report best representing the candidate's overall result.

    Strategy: highest avg_score_delta wins. When all reports have the
    same delta, first one wins (deterministic).
    """
    return max(validation.reports, key=lambda r: r.avg_score_delta)
