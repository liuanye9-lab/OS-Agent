"""Phase 6 — `harness validate` CLI helper.

Thin wrapper that the operator (or CI) calls to **re-run validation** on
an existing candidate skill without re-running Curator. This is the
"second look" path: a candidate was proposed days ago, you want to
verify it still passes A/B before approving.

Not used by :class:`HarnessFlow` directly — it's an out-of-band tool.
Phase 6 keeps it small (~40 lines of behavior) so the same logic can be
re-used by future ``harness review`` workflows.
"""

from __future__ import annotations

from typing import Iterable

from stable_agent.api.validation_store import ValidationReportStore
from stable_agent.core.validator_service import ValidationDecision, ValidatorService
from stable_agent.eval.task_group_store import TaskGroup
from stable_agent.skills.models import SkillStatus
from stable_agent.skills.repository import SkillRepository


class CandidateNotFound(LookupError):
    """Raised when ``revalidate`` can't find ``(skill_id, version)``."""


class CandidateNotInValidatableState(ValueError):
    """Raised when a skill is past the candidate stage."""


def revalidate(
    *,
    repo: SkillRepository,
    validator: ValidatorService,
    validation_store: ValidationReportStore,
    skill_id: str,
    version: int,
    related_groups: Iterable[TaskGroup] | None = None,
    run_id: str = "",
) -> tuple[ValidationDecision, str | None]:
    """Re-run Validator on an existing candidate; persist the report.

    Returns ``(decision, validation_id)`` — ``validation_id`` is ``None``
    when the validator produced no reports (e.g. NO_GROUPS).

    Raises :class:`CandidateNotFound` if the skill is missing,
    :class:`CandidateNotInValidatableState` if it's past candidate.
    """
    try:
        skill = repo.get(skill_id, version)
    except Exception as exc:
        raise CandidateNotFound(f"{skill_id}@v{version}") from exc

    if skill.frontmatter.status not in (SkillStatus.CANDIDATE,):
        raise CandidateNotInValidatableState(
            f"{skill_id}@v{version} is in status "
            f"{skill.frontmatter.status.value}; revalidate only works on "
            f"candidates"
        )

    decision = validator.validate(skill, explicit_groups=related_groups)
    validation_id: str | None = None
    if decision.reports:
        # Use the best report by avg_score_delta (mirrors HarnessFlow).
        best = max(decision.reports, key=lambda r: r.avg_score_delta)
        validation_id = validation_store.save(best, run_id=run_id)

    return decision, validation_id
