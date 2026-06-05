"""``stable_agent.eval`` — Phase 3 validation primitives.

Distinct from :mod:`stable_agent.evals` (the V4 regression suite + rubric
judge): this package owns the **delayed-validation A/B** machinery used
by Curator → Validator → HumanReview.

  - :mod:`task_group_store`      held-out task fixtures
  - :mod:`ab_validation_runner`  baseline vs candidate runner + report

Phase 3 ships these standalone so unit tests can pin the math without
booting the Orchestrator. Phase 6 wires them into Harness CI.
"""

from stable_agent.eval.ab_validation_runner import (
    ABResult,
    ABValidationRunner,
    InMemoryRunner,
    PromotionCriteria,
    RunResult,
    TaskRunner,
    ValidationReport,
)
from stable_agent.eval.task_group_store import (
    TaskCase,
    TaskGroup,
    TaskGroupStore,
)

__all__ = [
    "ABResult",
    "ABValidationRunner",
    "InMemoryRunner",
    "PromotionCriteria",
    "RunResult",
    "TaskCase",
    "TaskGroup",
    "TaskGroupStore",
    "TaskRunner",
    "ValidationReport",
]
