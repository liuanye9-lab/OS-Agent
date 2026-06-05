"""Phase 3 — Curator service.

Decides **whether** a run is worth learning from, and if so produces a
candidate :class:`SkillDocument`. Does *not* promote — that's Validator
+ HumanReview territory.

Inputs (`CuratorInput`):
  - run trace summary (eval score, missing events, retrieval_tags)
  - failure attribution (from `eval_and_bad_case`)
  - user feedback (`feedback_learning_service`)
  - optional external findings (Phase 4 ExternalCrawler bridge)

Output (`CuratorDecision`):
  - decision: ``proposed`` | ``skipped`` | ``rejected_duplicate``
  - candidate skill (when proposed)
  - reason string

Hard rules (mirrored by tests):

  1. ``round_num > 1`` is **not** a learning trigger — runs must surface
     a real signal (low score, attribution, feedback, missing events).
     This explicitly fixes the simulated trigger documented in
     ``experiments/self_iteration_5_rounds/run_experiment.py:89``.
  2. Candidates are written with ``status=draft``; Curator immediately
     moves them to ``candidate`` only after de-dup check passes.
  3. The skill body length cap (``compression_ratio_max``) is enforced
     so we don't propose monster skills that just dump the trace.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from stable_agent.skills import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    Triggers,
)
from stable_agent.skills.repository import (
    DuplicateSkillError,
    SkillRepository,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CuratorInput:
    """Snapshot of one run that Curator inspects.

    Designed so Phase 3 unit tests can construct it directly without
    booting the Orchestrator. Phase 6 will wire a real builder that maps
    OS-Agent run output → :class:`CuratorInput`.
    """

    run_id: str
    task_input: str
    eval_score: float
    eval_passed: bool
    missing_required_events: tuple[str, ...] = field(default_factory=tuple)
    failure_mode: str = ""
    failure_attribution: str = ""
    user_feedback: tuple[str, ...] = field(default_factory=tuple)
    retrieval_tags: tuple[str, ...] = field(default_factory=tuple)
    task_type: str = "coding_task"
    risk_level: str = "low"
    external_findings: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CuratorPolicy:
    """Defaults from the deep-research roadmap (§3.6 reward proxy)."""

    min_eval_score_to_learn: float = 0.75
    # Absolute max body size for a candidate skill. Replaces the roadmap's
    # ``compression_ratio_max`` because that ratio only makes sense when we
    # have an explicit source-trace size; Phase 3 callers don't, so we cap
    # the absolute body instead. 8 KiB is plenty for a structured skill —
    # anything larger smells like a trace dump.
    max_candidate_body_chars: int = 8192
    require_some_signal: bool = True

    def should_propose(self, inp: CuratorInput) -> tuple[bool, str]:
        """Decide whether this run is worth learning from.

        Returns ``(propose, reason)``. ``reason`` is a short label so
        ``CuratorDecision.reason`` reads cleanly on Observer.
        """
        if not self.require_some_signal:
            return True, "policy: require_some_signal=False (always propose)"

        signals: list[str] = []
        if inp.eval_score < self.min_eval_score_to_learn:
            signals.append(f"low_score({inp.eval_score:.2f})")
        if inp.missing_required_events:
            signals.append(f"missing_events({len(inp.missing_required_events)})")
        if inp.failure_attribution:
            signals.append("has_attribution")
        if inp.user_feedback:
            signals.append(f"feedback({len(inp.user_feedback)})")
        if inp.external_findings:
            signals.append(f"external_findings({len(inp.external_findings)})")

        if not signals:
            return False, "no learning signal — score ok, no failure, no feedback"
        return True, "+".join(signals)


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #

class CuratorOutcome:
    """Tag values for :attr:`CuratorDecision.outcome` (string for logs/JSON)."""

    PROPOSED = "proposed"
    SKIPPED = "skipped"
    REJECTED_DUPLICATE = "rejected_duplicate"


@dataclass(frozen=True)
class CuratorDecision:
    outcome: str
    reason: str
    candidate: SkillDocument | None = None
    duplicate_of: str | None = None  # "skill_id@v{n}" when rejected_duplicate

    @property
    def proposed(self) -> bool:
        return self.outcome == CuratorOutcome.PROPOSED


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_SAFE_ID_RE = re.compile(r"[^a-z0-9_]+")


def _slugify(text: str) -> str:
    """ASCII-safe lowercased slug for skill_id construction."""
    s = (text or "").lower()
    # ASCII transliteration is overkill for Phase 3; just keep [a-z0-9_].
    s = _SAFE_ID_RE.sub("_", s).strip("_")
    return s[:32] or "task"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Curator
# --------------------------------------------------------------------------- #

class CuratorService:
    """Generates candidate skills from real run signals.

    Args:
        repo: :class:`SkillRepository` to write candidates into.
        policy: optional override of :class:`CuratorPolicy` defaults.
    """

    def __init__(
        self,
        repo: SkillRepository,
        *,
        policy: CuratorPolicy | None = None,
    ) -> None:
        self._repo = repo
        self._policy = policy or CuratorPolicy()

    @property
    def policy(self) -> CuratorPolicy:
        return self._policy

    def evaluate(self, inp: CuratorInput) -> CuratorDecision:
        """Decide and (when proposing) persist a candidate skill.

        Returns :class:`CuratorDecision`. The candidate, when present,
        is already written through :meth:`SkillRepository.write` and
        transitioned to ``candidate`` status — no further action needed
        before Validator picks it up.
        """
        # Guard: empty / nonsense input is always a skip.
        if not inp.run_id or not inp.task_input:
            return CuratorDecision(
                outcome=CuratorOutcome.SKIPPED,
                reason="missing run_id or task_input",
            )

        propose, reason = self._policy.should_propose(inp)
        if not propose:
            return CuratorDecision(outcome=CuratorOutcome.SKIPPED, reason=reason)

        draft = self._build_draft(inp)

        # Body-size cap: protects against runaway proposals that just dump
        # the whole trace as a "skill". Phase 3 uses an absolute char cap
        # (8 KiB by default) — see CuratorPolicy.max_candidate_body_chars.
        body_size = sum(len(v) for v in draft.sections.values())
        if body_size > self._policy.max_candidate_body_chars:
            return CuratorDecision(
                outcome=CuratorOutcome.SKIPPED,
                reason=(
                    f"candidate body too large "
                    f"({body_size} > {self._policy.max_candidate_body_chars})"
                ),
            )

        # Strict + near-duplicate check.
        near = self._repo.find_near_duplicates(draft, threshold=3)
        try:
            written = self._repo.write(draft)
        except DuplicateSkillError as exc:
            # Find the cross-skill collision to label the dup target.
            return CuratorDecision(
                outcome=CuratorOutcome.REJECTED_DUPLICATE,
                reason=str(exc),
                duplicate_of=str(exc).split("owned by ")[-1],
            )

        # Move draft → candidate immediately; Curator is the gate before
        # the candidate enters Validator.
        candidate = self._repo.transition_status(
            written.skill_id, written.version, SkillStatus.CANDIDATE,
        )

        decision_reason = reason
        if near:
            near_ids = ", ".join(
                f"{n['skill_id']}@v{n['version']}(d={n['hamming_distance']})"
                for n in near[:3]
            )
            decision_reason += f" [near_duplicates: {near_ids}]"

        return CuratorDecision(
            outcome=CuratorOutcome.PROPOSED,
            reason=decision_reason,
            candidate=candidate,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _build_draft(self, inp: CuratorInput) -> SkillDocument:
        """Assemble a draft :class:`SkillDocument` from the input signals.

        Phase 3 uses a deterministic template — no LLM. Phase 6 may add
        an optional LLM rephrase step gated behind a feature flag.
        """
        slug = _slugify(inp.task_input.split()[0] if inp.task_input.strip() else "task")
        # Append a short uuid suffix so skill_id is stable per run but
        # collision-free across runs hitting the same slug.
        skill_id = f"sk_{slug}_{uuid.uuid4().hex[:6]}"

        intent_lines: list[str] = [f"Improve handling of: {inp.task_input.strip()[:140]}"]
        if inp.failure_mode:
            intent_lines.append(f"Failure mode: {inp.failure_mode}")
        if inp.user_feedback:
            intent_lines.append("User feedback signals:")
            intent_lines.extend(f"- {f}" for f in inp.user_feedback)

        procedure_lines: list[str] = ["Suggested procedure:"]
        if inp.failure_attribution:
            procedure_lines.append(f"1. Address attribution: {inp.failure_attribution}")
        else:
            procedure_lines.append("1. Re-read protected constraints before reasoning.")
        if inp.missing_required_events:
            procedure_lines.append(
                "2. Ensure these events are emitted: "
                + ", ".join(inp.missing_required_events)
            )
        else:
            procedure_lines.append("2. Verify required-event chain completes.")
        if inp.external_findings:
            procedure_lines.append("3. Consider external findings:")
            procedure_lines.extend(f"   - {f}" for f in inp.external_findings)

        guardrails = "Do not skip Phase 0 contract events. Reject the run if eval_score < 0.5."

        triggers = Triggers(
            must_contain=tuple(inp.retrieval_tags[:2]) if inp.retrieval_tags else (),
            should_contain=tuple(inp.retrieval_tags[2:5]),
            must_avoid=("chitchat",),
        )

        fm = SkillFrontmatter(
            skill_id=skill_id,
            version=1,
            status=SkillStatus.DRAFT,
            domain="coding",
            owner="curator_v1",
            created_at=_now_utc_iso(),
            updated_at=_now_utc_iso(),
            retrieval_tags=tuple(inp.retrieval_tags),
            task_types=(inp.task_type,) if inp.task_type else (),
            triggers=triggers,
            metrics=Metrics(),
            source_runs=(inp.run_id,),
            risk_level=inp.risk_level,
        )

        sections = {
            "Intent": "\n".join(intent_lines),
            "Procedure": "\n".join(procedure_lines),
            "Guardrails": guardrails,
            "Positive examples": "",
            "Negative examples": "",
            "Patch history": f"v1: proposed by curator_v1 from run {inp.run_id}.",
        }
        return SkillDocument(frontmatter=fm, sections=sections)
