"""Scoring helpers for Learning Impact Report v2."""

from __future__ import annotations

from typing import Any


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def score_memory(memory_hits: list[dict[str, Any]]) -> float:
    return clamp_score(min(len(memory_hits), 5) / 5.0) if memory_hits else 0.0


def score_skills(skill_hits: list[dict[str, Any]]) -> float:
    promoted = [s for s in skill_hits if s.get("status") == "promoted"]
    return clamp_score(min(len(promoted), 3) / 3.0) if promoted else 0.0


def score_profiles(profile_hits: list[dict[str, Any]]) -> float:
    return clamp_score(min(len(profile_hits), 4) / 4.0) if profile_hits else 0.0


def score_tokens(token_report: dict[str, Any] | None) -> float:
    if not token_report:
        return 0.0
    return clamp_score(float(token_report.get("saving_ratio") or 0.0))
