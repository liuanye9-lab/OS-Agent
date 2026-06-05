"""Phase 3 — A/B validation runner.

Pipeline:

    1. Caller picks a related :class:`TaskGroup` for a candidate skill.
    2. For each :class:`TaskCase`:
         a. ``runner.run(case, candidate_skill=None)``     → baseline
         b. ``runner.run(case, candidate_skill=skill)``    → candidate
       (We always run baseline first to keep a sane reference.)
    3. Aggregate per-case deltas → :class:`ValidationReport`.
    4. Optional gate: :class:`PromotionCriteria.passes` decides whether
       the report meets the bar for ``validated → promoted``.

Why a Protocol-based ``TaskRunner``:

  - Phase 3 unit tests inject a :class:`InMemoryRunner` so we can pin
    the math without spinning the real Orchestrator.
  - Phase 6 wires the production runner to :class:`LocalRuntime` —
    same interface, real eval scores.

This separation is the only way to keep the **simulated pass / real
pass** distinction honest: tests are explicitly fake (and labelled as
such); the production path runs the real OS-Agent loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Protocol

from stable_agent.eval.task_group_store import TaskCase, TaskGroup
from stable_agent.skills.models import SkillDocument

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Per-run signal
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RunResult:
    """Outcome of one Validator-driven case run.

    ``required_events_complete`` is ``True`` iff the run emitted every
    event listed in ``case.expected_signals`` (Phase 0 contract uses 13;
    Validator can pass a tighter list per case).
    """

    case_id: str
    eval_score: float
    token_used: int
    latency_ms: int
    required_events_complete: bool
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class TaskRunner(Protocol):
    """Anything that can execute one held-out case in baseline / candidate mode.

    Phase 3 unit tests inject :class:`InMemoryRunner`. Production wires
    the real OS-Agent (LocalRuntime) — see ``docs/harness/PHASE3_CURATOR_VALIDATION.md``.
    """

    def run(
        self,
        case: TaskCase,
        *,
        candidate_skill: SkillDocument | None,
    ) -> RunResult:
        ...


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ABResult:
    """Single-case A/B comparison."""

    case_id: str
    baseline: RunResult
    candidate: RunResult

    @property
    def score_delta(self) -> float:
        return self.candidate.eval_score - self.baseline.eval_score

    @property
    def token_delta_ratio(self) -> float:
        """Relative token change: 0.10 = candidate uses 10% more tokens."""
        if self.baseline.token_used <= 0:
            return 0.0
        return (self.candidate.token_used - self.baseline.token_used) / self.baseline.token_used

    @property
    def latency_delta_ratio(self) -> float:
        if self.baseline.latency_ms <= 0:
            return 0.0
        return (
            (self.candidate.latency_ms - self.baseline.latency_ms)
            / self.baseline.latency_ms
        )

    @property
    def regression(self) -> bool:
        """Candidate strictly worse on score OR lost required events."""
        if self.candidate.error is not None and self.baseline.error is None:
            return True
        if self.candidate.eval_score < self.baseline.eval_score - 1e-6:
            return True
        # Lost required events that baseline had → regression.
        if self.baseline.required_events_complete and not self.candidate.required_events_complete:
            return True
        return False


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate report for one (candidate, group) pair.

    Phase 3 ``passes`` is set by :meth:`PromotionCriteria.passes` — the
    runner itself does not decide. This keeps the data and the policy
    independent.
    """

    candidate_skill_id: str
    candidate_version: int
    group_id: str
    cases: tuple[ABResult, ...]
    avg_score_delta: float
    avg_token_delta_ratio: float
    avg_latency_delta_ratio: float
    regression_count: int
    required_events_completeness: float
    passed: bool = False
    reason: str = ""

    @property
    def case_count(self) -> int:
        return len(self.cases)

    @property
    def regression_rate(self) -> float:
        if not self.cases:
            return 0.0
        return self.regression_count / len(self.cases)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly view (Observer / API consumers)."""
        return {
            "candidate_skill_id": self.candidate_skill_id,
            "candidate_version": self.candidate_version,
            "group_id": self.group_id,
            "case_count": self.case_count,
            "avg_score_delta": round(self.avg_score_delta, 4),
            "avg_token_delta_ratio": round(self.avg_token_delta_ratio, 4),
            "avg_latency_delta_ratio": round(self.avg_latency_delta_ratio, 4),
            "regression_count": self.regression_count,
            "regression_rate": round(self.regression_rate, 4),
            "required_events_completeness": round(self.required_events_completeness, 4),
            "passed": self.passed,
            "reason": self.reason,
            "cases": [
                {
                    "case_id": ab.case_id,
                    "baseline_score": ab.baseline.eval_score,
                    "candidate_score": ab.candidate.eval_score,
                    "score_delta": round(ab.score_delta, 4),
                    "regression": ab.regression,
                }
                for ab in self.cases
            ],
        }


# --------------------------------------------------------------------------- #
# Promotion criteria
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PromotionCriteria:
    """Defaults from the deep-research roadmap (§3.6 reward proxy)."""

    min_delta_score_promote: float = 0.03
    max_token_increase_promote: float = 0.10
    max_latency_increase_promote: float = 0.15
    max_regression_rate: float = 0.0
    min_required_events_completeness: float = 1.0
    require_high_risk_human_review: bool = True

    def passes(self, report: ValidationReport, *, risk_level: str = "low") -> tuple[bool, str]:
        """Apply gate. Returns ``(passed, reason)``.

        Reason is the **first** failing condition; this matches
        Curator/Reviewer expectations of a clear single-cause rejection.
        """
        if report.case_count == 0:
            return False, "no cases in validation group"

        if report.avg_score_delta < self.min_delta_score_promote:
            return False, (
                f"avg_score_delta {report.avg_score_delta:.4f} < threshold "
                f"{self.min_delta_score_promote}"
            )
        if report.regression_rate > self.max_regression_rate:
            return False, (
                f"regression_rate {report.regression_rate:.4f} > threshold "
                f"{self.max_regression_rate}"
            )
        if report.required_events_completeness < self.min_required_events_completeness:
            return False, (
                f"required_events_completeness "
                f"{report.required_events_completeness:.4f} < threshold "
                f"{self.min_required_events_completeness}"
            )
        if report.avg_token_delta_ratio > self.max_token_increase_promote:
            return False, (
                f"avg_token_delta {report.avg_token_delta_ratio:.4f} > threshold "
                f"{self.max_token_increase_promote}"
            )
        if report.avg_latency_delta_ratio > self.max_latency_increase_promote:
            return False, (
                f"avg_latency_delta {report.avg_latency_delta_ratio:.4f} > threshold "
                f"{self.max_latency_increase_promote}"
            )
        if self.require_high_risk_human_review and risk_level == "high":
            return False, "high_risk skill requires human review before promotion"
        return True, "ok"


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

class ABValidationRunner:
    """Drive baseline + candidate runs through any :class:`TaskRunner`.

    The runner is intentionally dumb about *how* the underlying TaskRunner
    actually executes — it only owns the loop and aggregation math. This
    means the math itself is unit-testable without the Orchestrator.
    """

    def __init__(
        self,
        runner: TaskRunner,
        *,
        criteria: PromotionCriteria | None = None,
    ) -> None:
        self._runner = runner
        self._criteria = criteria or PromotionCriteria()

    @property
    def criteria(self) -> PromotionCriteria:
        return self._criteria

    def run(
        self,
        candidate: SkillDocument,
        group: TaskGroup,
    ) -> ValidationReport:
        """Run the full A/B over one group; return a fresh report.

        The report is stamped with ``passed`` according to ``criteria`` and
        the candidate's frontmatter ``risk_level``.
        """
        ab_results: list[ABResult] = []
        for case in group.cases:
            baseline = self._safe_run(case, candidate_skill=None)
            cand = self._safe_run(case, candidate_skill=candidate)
            ab_results.append(ABResult(
                case_id=case.case_id,
                baseline=baseline,
                candidate=cand,
            ))

        report = self._aggregate(
            candidate=candidate,
            group=group,
            cases=ab_results,
        )

        passed, reason = self._criteria.passes(
            report,
            risk_level=candidate.frontmatter.risk_level,
        )
        return replace(report, passed=passed, reason=reason)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _safe_run(
        self, case: TaskCase, *, candidate_skill: SkillDocument | None,
    ) -> RunResult:
        """Wrap the runner so a thrown exception becomes an error :class:`RunResult`."""
        try:
            return self._runner.run(case, candidate_skill=candidate_skill)
        except Exception as exc:  # pragma: no cover — defensive only
            logger.exception("TaskRunner.run failed for case=%s", case.case_id)
            return RunResult(
                case_id=case.case_id,
                eval_score=0.0,
                token_used=0,
                latency_ms=0,
                required_events_complete=False,
                error=f"runner exception: {exc}",
            )

    @staticmethod
    def _aggregate(
        *,
        candidate: SkillDocument,
        group: TaskGroup,
        cases: list[ABResult],
    ) -> ValidationReport:
        if not cases:
            return ValidationReport(
                candidate_skill_id=candidate.skill_id,
                candidate_version=candidate.version,
                group_id=group.group_id,
                cases=(),
                avg_score_delta=0.0,
                avg_token_delta_ratio=0.0,
                avg_latency_delta_ratio=0.0,
                regression_count=0,
                required_events_completeness=0.0,
            )

        n = len(cases)
        avg_score = sum(c.score_delta for c in cases) / n
        avg_tok = sum(c.token_delta_ratio for c in cases) / n
        avg_lat = sum(c.latency_delta_ratio for c in cases) / n
        regress = sum(1 for c in cases if c.regression)
        complete = sum(1 for c in cases if c.candidate.required_events_complete) / n
        return ValidationReport(
            candidate_skill_id=candidate.skill_id,
            candidate_version=candidate.version,
            group_id=group.group_id,
            cases=tuple(cases),
            avg_score_delta=avg_score,
            avg_token_delta_ratio=avg_tok,
            avg_latency_delta_ratio=avg_lat,
            regression_count=regress,
            required_events_completeness=complete,
        )


# --------------------------------------------------------------------------- #
# Test runner — explicitly fake, so production code never accidentally
# uses it.
# --------------------------------------------------------------------------- #

@dataclass
class InMemoryRunner:
    """Deterministic :class:`TaskRunner` for unit tests.

    Behavior:

      - ``baseline_scores[case_id]`` returns the baseline ``eval_score``
      - ``candidate_scores[case_id]`` returns the candidate ``eval_score``
      - any case_id missing from the maps returns 0.0 (treated as "no signal")
      - ``token_used`` / ``latency_ms`` configurable via ``token_used`` /
        ``latency_ms`` dicts; default 100 / 100

    NOTE: this class is **fake by design** — it lives in production code
    so prod callers can't accidentally `from .ab_validation_runner import
    InMemoryRunner` thinking it's the real thing. Phase 6 may move it to
    ``tests/_helpers/`` once the harness CI is in place.
    """

    baseline_scores: dict[str, float] = field(default_factory=dict)
    candidate_scores: dict[str, float] = field(default_factory=dict)
    token_used: dict[str, int] = field(default_factory=dict)
    latency_ms: dict[str, int] = field(default_factory=dict)
    required_events_complete: dict[str, bool] = field(default_factory=dict)
    candidate_token_used: dict[str, int] = field(default_factory=dict)
    candidate_latency_ms: dict[str, int] = field(default_factory=dict)
    raise_on: tuple[str, ...] = ()

    def run(
        self, case: TaskCase, *, candidate_skill: SkillDocument | None,
    ) -> RunResult:
        if case.case_id in self.raise_on:
            raise RuntimeError(f"InMemoryRunner injected failure for {case.case_id}")
        if candidate_skill is None:
            score = self.baseline_scores.get(case.case_id, 0.0)
            tokens = self.token_used.get(case.case_id, 100)
            latency = self.latency_ms.get(case.case_id, 100)
        else:
            score = self.candidate_scores.get(case.case_id, 0.0)
            tokens = self.candidate_token_used.get(
                case.case_id, self.token_used.get(case.case_id, 100)
            )
            latency = self.candidate_latency_ms.get(
                case.case_id, self.latency_ms.get(case.case_id, 100)
            )
        return RunResult(
            case_id=case.case_id,
            eval_score=score,
            token_used=tokens,
            latency_ms=latency,
            required_events_complete=self.required_events_complete.get(
                case.case_id, True
            ),
        )
