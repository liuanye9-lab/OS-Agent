"""Score comparison helper."""

from __future__ import annotations

from stable_agent.validation.ab_runner import TaskRunScore, ValidationResult


def compare_scores(baseline: list[TaskRunScore], candidate: list[TaskRunScore]) -> ValidationResult:
    from stable_agent.validation.ab_runner import DelayedValidationABRunner

    return DelayedValidationABRunner().compare(baseline, candidate)
