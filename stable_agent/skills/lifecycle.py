"""Phase 2 SkillRepo v2 — status lifecycle.

The state machine for a skill version, with **legal transitions only**.
Curator (Phase 3) and HumanReview (Phase 6) are the only callers that
should advance status; Validator may move ``candidate → validated``.

Hard rules (enforced here, mirrored by tests):

  - You can never *re-enter* a terminal state from an arbitrary one.
  - ``promoted`` is reachable **only** from ``validated`` — Phase 3
    validation gate is the single promotion path.
  - Any status can move to ``rejected`` (curator can drop a candidate
    early; reviewer can drop a validated one).
  - ``deprecated`` and ``archived`` are end-of-life lanes for previously
    promoted skills.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from stable_agent.skills.models import SkillDocument, SkillStatus


class SkillTransitionError(ValueError):
    """Raised when a status transition is not in :data:`LEGAL_TRANSITIONS`."""


# Frozen mapping: any change here requires updating tests in
# ``test_skill_repo_v2.py::test_lifecycle_*``.
LEGAL_TRANSITIONS: Mapping[SkillStatus, frozenset[SkillStatus]] = {
    SkillStatus.DRAFT: frozenset({SkillStatus.CANDIDATE, SkillStatus.REJECTED}),
    SkillStatus.CANDIDATE: frozenset({
        SkillStatus.VALIDATED,
        SkillStatus.REJECTED,
    }),
    SkillStatus.VALIDATED: frozenset({
        SkillStatus.PROMOTED,
        SkillStatus.REJECTED,
    }),
    SkillStatus.PROMOTED: frozenset({
        SkillStatus.DEPRECATED,
    }),
    SkillStatus.DEPRECATED: frozenset({
        SkillStatus.ARCHIVED,
        SkillStatus.PROMOTED,  # un-deprecate is allowed (rare, audit-logged)
    }),
    SkillStatus.ARCHIVED: frozenset(),  # terminal
    SkillStatus.REJECTED: frozenset(),  # terminal
}


def transition(skill: SkillDocument, target: SkillStatus) -> SkillDocument:
    """Return a copy of ``skill`` with ``frontmatter.status = target``.

    Raises :class:`SkillTransitionError` if the move is not legal. Same-
    state "transitions" are a no-op (returned unchanged).
    """
    current = skill.frontmatter.status
    if current == target:
        return skill
    allowed = LEGAL_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise SkillTransitionError(
            f"illegal status transition {current.value} -> {target.value}"
            f" (allowed from {current.value}: "
            f"{sorted(s.value for s in allowed)})"
        )
    new_fm = replace(skill.frontmatter, status=target)
    return skill.with_frontmatter(new_fm)


def can_promote(skill: SkillDocument, *, min_validations: int = 2,
                min_score: float = 0.75) -> bool:
    """Pre-condition check for ``validated → promoted``.

    Phase 3 ``ValidatorService`` is the canonical caller. The thresholds
    here mirror the roadmap defaults; Phase 3 will let callers pass
    custom thresholds via :class:`stable_agent.skills.lifecycle.PromotionCriteria`
    once that exists. For Phase 2 we keep it parameterized but with safe
    defaults.
    """
    if skill.frontmatter.status != SkillStatus.VALIDATED:
        return False
    m = skill.frontmatter.metrics
    return (
        m.validations >= min_validations
        and m.last_validation_score >= min_score
    )
