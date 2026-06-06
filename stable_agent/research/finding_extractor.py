"""Extract evidence-card claims from external artifacts."""

from __future__ import annotations

from typing import Any


def extract_claims(summary: str, *, max_claims: int = 3) -> list[str]:
    chunks = [part.strip() for part in summary.replace("\n", " ").split(".") if part.strip()]
    return chunks[:max_claims] or [summary[:160] or "No claim extracted"]


def modules_for_claims(claims: list[str]) -> list[str]:
    text = " ".join(claims).lower()
    modules: list[str] = []
    if "memory" in text or "记忆" in text:
        modules.append("stable_agent.memory_evidence")
    if "skill" in text:
        modules.append("stable_agent.skill_optimizer")
    if "validation" in text or "eval" in text:
        modules.append("stable_agent.validation")
    if "agent" in text or not modules:
        modules.append("stable_agent.research")
    return modules


def proposed_changes_for_claims(claims: list[str]) -> list[str]:
    return [f"Review evidence before creating candidate: {claim[:120]}" for claim in claims]
