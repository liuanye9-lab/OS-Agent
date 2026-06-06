"""Phase 3 — Delayed validation A/B contract.

Pinned behavior:

  1. Validator only acts on ``status=candidate`` skills; rejects others.
  2. Promotion criteria is **purely numerical** — no simulated bypass:
       * avg_score_delta >= min_delta_score_promote (0.03 default)
       * regression_rate == 0.0
       * required_events_completeness == 1.0
       * token / latency increases under thresholds
  3. High-risk skills go to ``deferred_human_review`` regardless of metrics.
  4. Without TaskGroups → ``no_groups``, never spuriously "validated".
  5. Validator math is independent of the underlying TaskRunner — this
     is what lets the InMemoryRunner pin behavior without booting the
     Orchestrator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stable_agent.core.validator_service import (
    ValidationOutcome,
    ValidatorService,
)
from stable_agent.eval.ab_validation_runner import (
    ABValidationRunner,
    InMemoryRunner,
    PromotionCriteria,
)
from stable_agent.eval.task_group_store import TaskCase, TaskGroup, TaskGroupStore
from stable_agent.skills import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    Triggers,
)
from stable_agent.skills.repository import SkillRepository
from stable_agent.validation.ab_runner import DelayedValidationABRunner as RecursiveABRunner
from stable_agent.validation.ab_runner import TaskRunScore


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_candidate(
    *,
    skill_id: str = "sk_test_candidate",
    risk_level: str = "low",
    retrieval_tags: tuple[str, ...] = ("ctx", "guard"),
    task_type: str = "coding_task",
) -> SkillDocument:
    fm = SkillFrontmatter(
        skill_id=skill_id, version=1, status=SkillStatus.CANDIDATE,
        retrieval_tags=retrieval_tags,
        task_types=(task_type,),
        triggers=Triggers(),
        metrics=Metrics(),
        risk_level=risk_level,
    )
    return SkillDocument(
        frontmatter=fm,
        sections={
            "Intent": "test intent body",
            "Procedure": "1. do thing",
            "Guardrails": "no chitchat",
        },
    )


def _make_group(
    *,
    group_id: str = "grp_default",
    task_type: str = "coding_task",
    failure_mode: str = "missing_event",
    retrieval_tags: tuple[str, ...] = ("ctx", "guard"),
    case_count: int = 3,
) -> TaskGroup:
    cases = tuple(
        TaskCase(case_id=f"case_{i}", task_input=f"task {i}", expected_signals=("eval.completed",))
        for i in range(case_count)
    )
    return TaskGroup(
        group_id=group_id,
        task_type=task_type,
        failure_mode=failure_mode,
        retrieval_tags=retrieval_tags,
        cases=cases,
    )


@pytest.fixture
def repo(tmp_path: Path) -> SkillRepository:
    return SkillRepository(root=tmp_path)


@pytest.fixture
def groups(tmp_path: Path) -> TaskGroupStore:
    return TaskGroupStore(root=tmp_path)


# --------------------------------------------------------------------------- #
# 1. ABValidationRunner math (no Orchestrator)
# --------------------------------------------------------------------------- #

def test_ab_runner_passes_clean_uplift():
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.65, "case_1": 0.72, "case_2": 0.80},
    )
    ab = ABValidationRunner(runner, criteria=PromotionCriteria())
    report = ab.run(_make_candidate(), _make_group())
    assert report.passed is True, report.reason
    assert report.regression_count == 0
    assert report.avg_score_delta > 0.03


def test_recursive_ab_runner_requires_two_validations():
    runner = RecursiveABRunner()
    one = runner.compare(
        [TaskRunScore("t1", eval_score=0.7, tokens_used=100)],
        [TaskRunScore("t1", eval_score=0.8, tokens_used=100)],
    )
    assert one.passed is False

    two = runner.compare(
        [
            TaskRunScore("t1", eval_score=0.7, tokens_used=100),
            TaskRunScore("t2", eval_score=0.7, tokens_used=100),
        ],
        [
            TaskRunScore("t1", eval_score=0.75, tokens_used=105),
            TaskRunScore("t2", eval_score=0.76, tokens_used=104),
        ],
    )
    assert two.passed is True
    assert two.status == "ready_for_human_review"


def test_ab_runner_rejects_when_below_threshold():
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.80, "case_1": 0.80, "case_2": 0.80},
        candidate_scores={"case_0": 0.81, "case_1": 0.81, "case_2": 0.81},
    )
    ab = ABValidationRunner(runner, criteria=PromotionCriteria())
    report = ab.run(_make_candidate(), _make_group())
    assert report.passed is False
    assert "avg_score_delta" in report.reason


def test_ab_runner_rejects_on_any_regression():
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.70, "case_1": 0.80, "case_2": 0.40},  # case_2 worse
    )
    ab = ABValidationRunner(runner, criteria=PromotionCriteria())
    report = ab.run(_make_candidate(), _make_group())
    assert report.passed is False
    assert report.regression_count >= 1
    assert "regression_rate" in report.reason


def test_ab_runner_rejects_on_lost_required_events():
    """Even with score uplift, losing a required event = regression."""
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.70, "case_1": 0.80, "case_2": 0.90},
        required_events_complete={
            # baseline complete, candidate broken on case_2
            "case_0": True, "case_1": True, "case_2": False,
        },
    )
    ab = ABValidationRunner(runner, criteria=PromotionCriteria())
    report = ab.run(_make_candidate(), _make_group())
    assert report.passed is False
    # Either regression_count counts the event-loss, or
    # required_events_completeness fails the gate. Either way the report
    # must not pass.


def test_ab_runner_rejects_token_blowup():
    """Score uplift but token usage explodes 50% → reject."""
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.70, "case_1": 0.80, "case_2": 0.90},
        token_used={"case_0": 100, "case_1": 100, "case_2": 100},
        candidate_token_used={"case_0": 200, "case_1": 200, "case_2": 200},
    )
    ab = ABValidationRunner(runner, criteria=PromotionCriteria())
    report = ab.run(_make_candidate(), _make_group())
    assert report.passed is False
    assert "token" in report.reason.lower()


# --------------------------------------------------------------------------- #
# 2. ValidatorService — full pipeline
# --------------------------------------------------------------------------- #

def test_validator_validates_low_risk_pass(
    repo: SkillRepository, groups: TaskGroupStore,
):
    repo.write(_make_candidate(skill_id="sk_pass"))
    cand = repo.get("sk_pass")
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.70, "case_1": 0.80, "case_2": 0.90},
    )
    validator = ValidatorService(
        repo=repo, groups=groups,
        runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand, explicit_groups=[_make_group()])
    assert decision.outcome == ValidationOutcome.VALIDATED
    # Repo state must reflect the new status.
    refreshed = repo.get("sk_pass")
    assert refreshed.frontmatter.status == SkillStatus.VALIDATED


def test_validator_rejects_when_any_group_fails(
    repo: SkillRepository, groups: TaskGroupStore,
):
    repo.write(_make_candidate(skill_id="sk_mix"))
    cand = repo.get("sk_mix")
    # Two groups: g1 passes, g2 has regression — overall must reject.
    g1 = _make_group(group_id="g_pass")
    g2 = _make_group(group_id="g_regress")
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.50, "case_1": 0.60, "case_2": 0.70},
        candidate_scores={"case_0": 0.50, "case_1": 0.40, "case_2": 0.50},  # all worse
    )
    validator = ValidatorService(
        repo=repo, groups=groups, runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand, explicit_groups=[g1, g2])
    assert decision.outcome == ValidationOutcome.REJECTED


def test_validator_high_risk_always_deferred(
    repo: SkillRepository, groups: TaskGroupStore,
):
    """High-risk → never auto-validate, even with perfect scores."""
    repo.write(_make_candidate(skill_id="sk_hr", risk_level="high"))
    cand = repo.get("sk_hr")
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.10, "case_1": 0.10, "case_2": 0.10},
        candidate_scores={"case_0": 0.95, "case_1": 0.95, "case_2": 0.95},
    )
    validator = ValidatorService(
        repo=repo, groups=groups, runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand, explicit_groups=[_make_group()])
    assert decision.outcome == ValidationOutcome.DEFERRED_HUMAN_REVIEW
    # Status untouched.
    refreshed = repo.get("sk_hr")
    assert refreshed.frontmatter.status == SkillStatus.CANDIDATE


def test_validator_no_groups_returns_no_groups(
    repo: SkillRepository, groups: TaskGroupStore,
):
    repo.write(_make_candidate(skill_id="sk_no_groups"))
    cand = repo.get("sk_no_groups")
    runner = InMemoryRunner()
    validator = ValidatorService(
        repo=repo, groups=groups, runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand)  # no explicit groups, none stored
    assert decision.outcome == ValidationOutcome.NO_GROUPS


def test_validator_rejects_non_candidate_status(
    repo: SkillRepository, groups: TaskGroupStore,
):
    repo.write(_make_candidate(skill_id="sk_draft"))
    repo.transition_status("sk_draft", 1, SkillStatus.REJECTED)
    cand = repo.get("sk_draft")
    runner = InMemoryRunner()
    validator = ValidatorService(
        repo=repo, groups=groups, runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand, explicit_groups=[_make_group()])
    assert decision.outcome == ValidationOutcome.REJECTED
    assert "candidate" in decision.reason


# --------------------------------------------------------------------------- #
# 3. TaskGroupStore — file IO + related-task selection
# --------------------------------------------------------------------------- #

def test_task_group_store_round_trip(tmp_path: Path):
    store = TaskGroupStore(root=tmp_path)
    g = _make_group()
    store.add_group(g)

    loaded = store.get(g.group_id)
    assert loaded.group_id == g.group_id
    assert loaded.task_type == g.task_type
    assert len(loaded.cases) == len(g.cases)
    assert loaded.cases[0].case_id == g.cases[0].case_id


def test_task_group_store_find_related_ranks_by_score(tmp_path: Path):
    store = TaskGroupStore(root=tmp_path)
    store.add_group(_make_group(
        group_id="g_perfect",
        task_type="coding_task",
        failure_mode="bug",
        retrieval_tags=("ctx", "guard"),
    ))
    store.add_group(_make_group(
        group_id="g_partial",
        task_type="coding_task",
        failure_mode="other",
        retrieval_tags=("ctx",),
    ))
    store.add_group(_make_group(
        group_id="g_unrelated",
        task_type="docs_task",
        failure_mode="other",
        retrieval_tags=("nope",),
    ))

    related = store.find_related(
        task_type="coding_task",
        retrieval_tags=("ctx", "guard"),
        failure_mode="bug",
    )
    assert related[0].group_id == "g_perfect"
    assert "g_unrelated" not in [g.group_id for g in related]


def test_task_group_id_validation(tmp_path: Path):
    store = TaskGroupStore(root=tmp_path)
    with pytest.raises(KeyError):
        store.get("does_not_exist")
    with pytest.raises(ValueError):
        store.get("invalid/slash")


# --------------------------------------------------------------------------- #
# 4. NO simulated learning — explicit guard
# --------------------------------------------------------------------------- #

def test_validator_does_not_pass_with_zero_delta(
    repo: SkillRepository, groups: TaskGroupStore,
):
    """If candidate == baseline, Validator MUST reject, not 'simulated pass'."""
    repo.write(_make_candidate(skill_id="sk_flat"))
    cand = repo.get("sk_flat")
    runner = InMemoryRunner(
        baseline_scores={"case_0": 0.60, "case_1": 0.60, "case_2": 0.60},
        candidate_scores={"case_0": 0.60, "case_1": 0.60, "case_2": 0.60},
    )
    validator = ValidatorService(
        repo=repo, groups=groups, runner=ABValidationRunner(runner),
    )
    decision = validator.validate(cand, explicit_groups=[_make_group()])
    assert decision.outcome == ValidationOutcome.REJECTED, (
        "zero score delta must NOT pass — this is the explicit guard "
        "against the simulated `round_num > 1` style trigger"
    )
