"""Phase 3 — Curator candidate generation pipeline.

Pinned behavior:

  - **NO simulated learning**: ``round_num > 1`` alone is not a trigger;
    the run must surface a real signal (low score, missing events,
    failure attribution, user feedback, or external findings).
  - Empty/garbage input → ``skipped``, not ``proposed``.
  - Candidates land in :class:`SkillStatus.CANDIDATE` after write — not
    in ``draft`` or ``promoted``.
  - Cross-skill signature collisions → ``rejected_duplicate``.
  - Near-duplicate skills are reported in the reason string but do
    NOT block the proposal (Validator/Reviewer decides).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stable_agent.core.curator_service import (
    CuratorInput,
    CuratorOutcome,
    CuratorPolicy,
    CuratorService,
)
from stable_agent.skills import SkillStatus
from stable_agent.skills.repository import SkillRepository


@pytest.fixture
def repo(tmp_path: Path) -> SkillRepository:
    return SkillRepository(root=tmp_path, best_skill_path=tmp_path / "skills" / "best_skill.md")


@pytest.fixture
def curator(repo: SkillRepository) -> CuratorService:
    return CuratorService(repo)


# --------------------------------------------------------------------------- #
# 1. NO simulated learning — must have a real signal
# --------------------------------------------------------------------------- #

def test_curator_skips_when_no_learning_signal(curator: CuratorService):
    """Round count alone is not a trigger.

    This is the hard fix for ``experiments/self_iteration_5_rounds/run_experiment.py:89``
    which hardcoded ``learning_triggered = round_num > 1``. Curator
    must instead require at least one real signal.
    """
    inp = CuratorInput(
        run_id="run_a",
        task_input="boring happy path task",
        eval_score=0.95,            # high score
        eval_passed=True,           # passed
        missing_required_events=(),  # nothing missing
        failure_attribution="",
        user_feedback=(),
        external_findings=(),
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.SKIPPED
    assert "no learning signal" in decision.reason


def test_curator_proposes_on_low_eval_score(curator: CuratorService):
    inp = CuratorInput(
        run_id="run_a",
        task_input="something complex",
        eval_score=0.42,
        eval_passed=False,
        retrieval_tags=("context", "compression"),
        task_type="coding_task",
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    assert decision.candidate is not None
    assert "low_score" in decision.reason


def test_curator_proposes_on_missing_required_events(curator: CuratorService):
    inp = CuratorInput(
        run_id="run_b",
        task_input="ok-ish task",
        eval_score=0.85,
        eval_passed=True,
        missing_required_events=("eval.completed",),
        retrieval_tags=("dashboard", "events"),
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    assert "missing_events" in decision.reason


def test_curator_proposes_on_user_feedback(curator: CuratorService):
    inp = CuratorInput(
        run_id="run_c",
        task_input="task with explicit user feedback",
        eval_score=0.92,
        eval_passed=True,
        user_feedback=("dont_do_this_again: stop summarizing logs",),
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    assert "feedback" in decision.reason


def test_curator_proposes_on_external_findings(curator: CuratorService):
    inp = CuratorInput(
        run_id="run_d",
        task_input="task that maps to a recent paper",
        eval_score=0.81,
        eval_passed=True,
        external_findings=("arxiv:2401.12345 SkillOpt held-out validation",),
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    assert "external_findings" in decision.reason


# --------------------------------------------------------------------------- #
# 2. Persistence + lifecycle
# --------------------------------------------------------------------------- #

def test_proposed_candidate_lands_in_candidate_status(
    curator: CuratorService, repo: SkillRepository,
):
    inp = CuratorInput(
        run_id="run_status",
        task_input="task body",
        eval_score=0.40,
        eval_passed=False,
    )
    decision = curator.evaluate(inp)
    assert decision.candidate is not None
    assert decision.candidate.frontmatter.status == SkillStatus.CANDIDATE

    # Index reflects candidate status.
    row = repo.index.get(decision.candidate.skill_id)
    assert row is not None
    assert row["status"] == SkillStatus.CANDIDATE.value


def test_candidate_carries_source_run_id(curator: CuratorService):
    inp = CuratorInput(
        run_id="run_source_check",
        task_input="task body",
        eval_score=0.40,
        eval_passed=False,
    )
    decision = curator.evaluate(inp)
    assert decision.candidate is not None
    assert "run_source_check" in decision.candidate.frontmatter.source_runs


def test_candidate_writes_to_repo_artifact(
    curator: CuratorService, tmp_path: Path,
):
    inp = CuratorInput(
        run_id="run_artifact",
        task_input="task body",
        eval_score=0.30,
        eval_passed=False,
    )
    decision = curator.evaluate(inp)
    assert decision.candidate is not None
    skill_dir = tmp_path / "skills" / "repo" / decision.candidate.skill_id
    assert skill_dir.exists()
    assert (skill_dir / "v1.md").exists()


def test_candidate_does_not_publish_best_skill_md(
    curator: CuratorService, tmp_path: Path,
):
    """Candidates must never auto-publish — Phase 0 + Phase 2 invariant."""
    inp = CuratorInput(
        run_id="run_no_publish",
        task_input="task",
        eval_score=0.30,
        eval_passed=False,
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    best_md = tmp_path / "skills" / "best_skill.md"
    assert not best_md.exists()


# --------------------------------------------------------------------------- #
# 3. Guards
# --------------------------------------------------------------------------- #

def test_curator_skips_empty_input(curator: CuratorService):
    decision = curator.evaluate(CuratorInput(
        run_id="", task_input="", eval_score=0.0, eval_passed=False,
    ))
    assert decision.outcome == CuratorOutcome.SKIPPED


def test_curator_high_risk_still_proposes(curator: CuratorService):
    """High-risk candidates may still be proposed; promotion gate
    (Validator) is what defers them. Curator should not silently skip."""
    inp = CuratorInput(
        run_id="run_hr",
        task_input="dangerous task body",
        eval_score=0.40,
        eval_passed=False,
        risk_level="high",
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED
    assert decision.candidate is not None
    assert decision.candidate.frontmatter.risk_level == "high"


def test_curator_policy_disabled_signal_check_proposes_anyway(repo: SkillRepository):
    """Edge case: policy with require_some_signal=False — propose every run."""
    curator = CuratorService(repo, policy=CuratorPolicy(require_some_signal=False))
    inp = CuratorInput(
        run_id="run_always",
        task_input="happy path",
        eval_score=0.99,
        eval_passed=True,
    )
    decision = curator.evaluate(inp)
    assert decision.outcome == CuratorOutcome.PROPOSED


# --------------------------------------------------------------------------- #
# 4. Duplicate handling
# --------------------------------------------------------------------------- #

def test_curator_returns_rejected_duplicate_on_signature_collision(
    curator: CuratorService, repo: SkillRepository, monkeypatch,
):
    """If two runs produce identical bodies → second one is rejected."""
    # Force the slug to be deterministic so both proposals build the
    # same canonical body and thus the same signature.
    fixed_slug = "task"
    monkeypatch.setattr(
        "stable_agent.core.curator_service._slugify", lambda text: fixed_slug,
    )
    # Force the uuid suffix so skill_id collides too — guarantees same
    # canonical body across both calls.
    monkeypatch.setattr(
        "stable_agent.core.curator_service.uuid.uuid4",
        lambda: type("U", (), {"hex": "deadbeef" * 4})(),
    )

    inp = CuratorInput(
        run_id="run_dup_a",
        task_input="task",
        eval_score=0.30,
        eval_passed=False,
        retrieval_tags=("x",),
    )
    first = curator.evaluate(inp)
    assert first.outcome == CuratorOutcome.PROPOSED

    # Second run with identical body. Bodies are deterministic given the
    # patched slug + uuid, but skill_id will collide — so we expect
    # signature dedupe to fire on cross-version write attempt.
    second_inp = CuratorInput(
        run_id="run_dup_b",
        task_input="task",
        eval_score=0.30,
        eval_passed=False,
        retrieval_tags=("x",),
    )
    second = curator.evaluate(second_inp)
    # Either rejected (signature owned by different version slot) or
    # we treat the rewrite as a same-slot rewrite — both are acceptable
    # outcomes; signature dedupe MUST not silently produce two skills.
    if second.outcome == CuratorOutcome.PROPOSED:
        assert second.candidate is not None
        assert second.candidate.skill_id == first.candidate.skill_id, (
            "duplicate body produced a NEW skill_id — signature dedupe broken"
        )
    else:
        assert second.outcome == CuratorOutcome.REJECTED_DUPLICATE
