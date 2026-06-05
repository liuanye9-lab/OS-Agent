"""Phase 6 — Review gate governance + rollback contract.

The hard invariants in this file are the **whole point of Phase 6**:

  1. ``ReviewGate.evaluate()`` MUST NEVER return ``PROMOTED``. The only
     legal path to promoted is ``ReviewGate.approve(review_id, ...)``,
     which requires an explicit ``reviewer`` argument and a queue item.
  2. High-risk skills ALWAYS go through human review, regardless of
     numeric ValidationDecision outcome.
  3. Rollback ≠ demote. When a regressing candidate appears against an
     existing promoted version, the candidate is marked rejected;
     the promoted version is **untouched**.
  4. ``approve``/``reject`` are idempotent + auditable: each writes to
     the review queue with reviewer / reason / timestamp; double-deciding
     a queue item raises ``ValueError`` instead of silently overwriting.

These guarantees are what separate "Phase 6 harness" from "Phase 0–5
loose pieces wired together".
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from stable_agent.core.curator_service import CuratorDecision, CuratorOutcome
from stable_agent.core.validator_service import (
    ValidationDecision,
    ValidationOutcome,
)
from stable_agent.harness.review_gate import (
    ReviewGate,
    ReviewGateOutcome,
)
from stable_agent.harness.review_queue import ReviewQueueStore
from stable_agent.skills import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    Triggers,
)
from stable_agent.skills.repository import SkillRepository


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_skill(
    *,
    skill_id: str = "sk_demo",
    version: int = 1,
    risk_level: str = "low",
    intent: str = "default intent body that is long enough",
) -> SkillDocument:
    fm = SkillFrontmatter(
        skill_id=skill_id, version=version, status=SkillStatus.DRAFT,
        retrieval_tags=("ctx",), task_types=("coding_task",),
        triggers=Triggers(),
        metrics=Metrics(),
        risk_level=risk_level,
        source_runs=("run_demo",),
    )
    return SkillDocument(
        frontmatter=fm,
        sections={
            "Intent": intent,
            "Procedure": "1. do thing for skill " + skill_id,
            "Guardrails": "no chitchat",
        },
    )


def _validation(outcome: str, *, reason: str = "") -> ValidationDecision:
    return ValidationDecision(
        outcome=outcome,
        reason=reason or f"forged {outcome}",
        reports=(),
    )


def _curator_proposed(skill: SkillDocument, *, reason: str = "low_score") -> CuratorDecision:
    return CuratorDecision(
        outcome=CuratorOutcome.PROPOSED,
        reason=reason,
        candidate=skill,
    )


@pytest.fixture
def repo(tmp_path: Path) -> SkillRepository:
    return SkillRepository(root=tmp_path)


@pytest.fixture
def queue(tmp_path: Path) -> ReviewQueueStore:
    return ReviewQueueStore(root=tmp_path)


@pytest.fixture
def gate(repo: SkillRepository, queue: ReviewQueueStore) -> ReviewGate:
    return ReviewGate(repo=repo, review_queue=queue)


# --------------------------------------------------------------------------- #
# 1. HARD INVARIANT: evaluate() never returns PROMOTED
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("validation_outcome", [
    ValidationOutcome.VALIDATED,
    ValidationOutcome.REJECTED,
    ValidationOutcome.DEFERRED_HUMAN_REVIEW,
    ValidationOutcome.NO_GROUPS,
])
def test_evaluate_never_returns_promoted(gate: ReviewGate, repo: SkillRepository, validation_outcome: str):
    """Phase 6 hard invariant — only ``approve()`` can yield PROMOTED."""
    skill = _make_skill()
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(validation_outcome),
    )

    assert decision.outcome != ReviewGateOutcome.PROMOTED, (
        f"evaluate() returned PROMOTED on validation {validation_outcome} — "
        "Phase 6 governance broken: skills must only promote via approve()"
    )


def test_evaluate_validated_queues_for_review_but_does_not_promote(
    gate: ReviewGate, repo: SkillRepository, queue: ReviewQueueStore,
):
    skill = _make_skill()
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.VALIDATED),
    )

    assert decision.outcome == ReviewGateOutcome.READY_FOR_HUMAN_REVIEW
    assert decision.review_id is not None
    assert decision.needs_human_review is True

    # Skill still in candidate (Validator may have moved it to validated
    # before reaching the gate, but we never touch it here).
    refreshed = repo.get(skill.skill_id, 1)
    assert refreshed.frontmatter.status == SkillStatus.CANDIDATE

    # Queue holds the item, decision still pending.
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0]["review_id"] == decision.review_id
    assert pending[0]["decision"] is None


# --------------------------------------------------------------------------- #
# 2. HARD INVARIANT: high-risk always queued
# --------------------------------------------------------------------------- #

def test_high_risk_skill_always_queued_even_with_perfect_validation(
    gate: ReviewGate, repo: SkillRepository,
):
    skill = _make_skill(risk_level="high")
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.VALIDATED),
    )

    assert decision.outcome == ReviewGateOutcome.HIGH_RISK_HUMAN_REVIEW
    assert decision.review_id is not None
    assert decision.risk_level == "high"


def test_high_risk_deferred_validation_also_queued(
    gate: ReviewGate, repo: SkillRepository,
):
    """Both signal sources (risk_level + Validator deferral) trigger the queue."""
    skill = _make_skill(risk_level="high")
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.DEFERRED_HUMAN_REVIEW),
    )

    assert decision.outcome == ReviewGateOutcome.HIGH_RISK_HUMAN_REVIEW


# --------------------------------------------------------------------------- #
# 3. HARD INVARIANT: rollback ≠ demote
# --------------------------------------------------------------------------- #

def _promote_skill(repo: SkillRepository, skill: SkillDocument) -> None:
    """Helper: walk the lifecycle to land ``skill`` in PROMOTED."""
    repo.write(skill)
    sid, ver = skill.skill_id, skill.version
    repo.transition_status(sid, ver, SkillStatus.CANDIDATE)
    repo.transition_status(sid, ver, SkillStatus.VALIDATED)
    repo.transition_status(sid, ver, SkillStatus.PROMOTED)


def test_regressing_candidate_against_promoted_v1_does_not_demote_v1(
    gate: ReviewGate, repo: SkillRepository,
):
    # v1 promoted.
    v1 = _make_skill(skill_id="sk_rollback", version=1, intent="version 1 intent body, useful")
    _promote_skill(repo, v1)
    assert repo.get("sk_rollback", 1).frontmatter.status == SkillStatus.PROMOTED

    # v2 candidate, validation says REJECTED (regression).
    v2 = _make_skill(skill_id="sk_rollback", version=2, intent="version 2 intent body, broken")
    repo.write(v2)
    repo.transition_status("sk_rollback", 2, SkillStatus.CANDIDATE)

    decision = gate.evaluate(
        _curator_proposed(repo.get("sk_rollback", 2)),
        _validation(ValidationOutcome.REJECTED, reason="regressed on case_2"),
    )

    assert decision.outcome == ReviewGateOutcome.ROLLBACK_REQUIRED
    # v1 untouched.
    assert repo.get("sk_rollback", 1).frontmatter.status == SkillStatus.PROMOTED, (
        "rollback demoted the previously promoted v1 — Phase 6 governance broken"
    )
    # v2 marked rejected.
    assert repo.get("sk_rollback", 2).frontmatter.status == SkillStatus.REJECTED


def test_validation_failed_without_promoted_version_yields_validation_failed(
    gate: ReviewGate, repo: SkillRepository,
):
    """If no prior promoted version exists, validation rejection is just a
    VALIDATION_FAILED — not a rollback (nothing to roll back to)."""
    v1 = _make_skill(skill_id="sk_first_try", version=1)
    repo.write(v1)
    repo.transition_status("sk_first_try", 1, SkillStatus.CANDIDATE)

    decision = gate.evaluate(
        _curator_proposed(repo.get("sk_first_try", 1)),
        _validation(ValidationOutcome.REJECTED, reason="bad numbers"),
    )

    assert decision.outcome == ReviewGateOutcome.VALIDATION_FAILED


# --------------------------------------------------------------------------- #
# 4. approve() / reject() — auditable, single-shot
# --------------------------------------------------------------------------- #

def test_approve_promotes_skill_via_explicit_action(
    gate: ReviewGate, repo: SkillRepository, queue: ReviewQueueStore,
):
    skill = _make_skill()
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.VALIDATED),
    )
    rid = decision.review_id
    assert rid is not None

    # Out-of-band approval — THE only path to PROMOTED.
    promoted = gate.approve(rid, reviewer="alice", reason="passed manual review")
    assert promoted.outcome == ReviewGateOutcome.PROMOTED
    assert repo.get(skill.skill_id, 1).frontmatter.status == SkillStatus.PROMOTED

    # Queue entry now decided + auditable.
    rec = queue.get(rid)
    assert rec is not None
    assert rec["decision"]["verdict"] == "approved"
    assert rec["decision"]["reviewer"] == "alice"
    assert rec["decision"]["reason"] == "passed manual review"
    assert rec["decision"]["decided_at"]


def test_reject_marks_candidate_terminal(
    gate: ReviewGate, repo: SkillRepository, queue: ReviewQueueStore,
):
    skill = _make_skill()
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.VALIDATED),
    )
    rid = decision.review_id

    rejected = gate.reject(rid, reviewer="bob", reason="not safe enough")
    assert rejected.outcome == ReviewGateOutcome.REJECTED
    assert repo.get(skill.skill_id, 1).frontmatter.status == SkillStatus.REJECTED


def test_double_decide_same_review_raises(gate: ReviewGate, repo: SkillRepository):
    skill = _make_skill()
    repo.write(skill)
    repo.transition_status(skill.skill_id, 1, SkillStatus.CANDIDATE)
    cand = repo.get(skill.skill_id, 1)

    decision = gate.evaluate(
        _curator_proposed(cand),
        _validation(ValidationOutcome.VALIDATED),
    )
    rid = decision.review_id
    gate.approve(rid, reviewer="alice")

    # Second decision on the same review_id must fail loudly.
    with pytest.raises(ValueError):
        gate.reject(rid, reviewer="alice", reason="changed my mind")
    with pytest.raises(ValueError):
        gate.approve(rid, reviewer="alice")


def test_approve_unknown_review_id_raises(gate: ReviewGate):
    with pytest.raises(KeyError):
        gate.approve("rev_does_not_exist", reviewer="alice")


# --------------------------------------------------------------------------- #
# 5. Curator skip / duplicate paths — no queue, no skill churn
# --------------------------------------------------------------------------- #

def test_curator_skipped_does_not_queue(
    gate: ReviewGate, queue: ReviewQueueStore,
):
    decision = gate.evaluate(
        CuratorDecision(outcome=CuratorOutcome.SKIPPED, reason="no signal"),
        validation=None,
    )
    assert decision.outcome == ReviewGateOutcome.SKIPPED_NO_PROPOSAL
    assert decision.review_id is None
    assert queue.list_all() == []


def test_curator_duplicate_does_not_queue(
    gate: ReviewGate, queue: ReviewQueueStore,
):
    decision = gate.evaluate(
        CuratorDecision(
            outcome=CuratorOutcome.REJECTED_DUPLICATE,
            reason="signature 0x123 owned by sk_other@v1",
        ),
        validation=None,
    )
    assert decision.outcome == ReviewGateOutcome.DUPLICATE_REJECTED
    assert queue.list_all() == []


# --------------------------------------------------------------------------- #
# 6. ReviewQueueStore basics (path traversal + persistence)
# --------------------------------------------------------------------------- #

def test_review_queue_path_traversal_rejected(queue: ReviewQueueStore):
    with pytest.raises(ValueError):
        queue.submit(
            skill_id="sk", skill_version=1, risk_level="low",
            review_kind="READY", validation_id=None, run_id="r",
            reason="x", review_id="../../etc/passwd",
        )


def test_review_queue_pending_filtering(queue: ReviewQueueStore):
    rid_a = queue.submit(
        skill_id="sk_a", skill_version=1, risk_level="low",
        review_kind="READY", validation_id=None, run_id="r1", reason="a",
    )
    rid_b = queue.submit(
        skill_id="sk_b", skill_version=1, risk_level="low",
        review_kind="READY", validation_id=None, run_id="r2", reason="b",
    )

    queue.record_decision(rid_a, verdict="approved", reviewer="alice", reason="ok")
    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0]["review_id"] == rid_b

    all_items = queue.list_all()
    assert len(all_items) == 2
