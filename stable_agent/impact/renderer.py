"""Render Learning Impact Report for users."""

from __future__ import annotations

from stable_agent.impact.models import LearningImpactReport


def render_user_summary_zh(report: LearningImpactReport) -> str:
    lines = [
        f"run_id: {report.run_id}",
        f"overall_impact_score: {report.overall_impact_score:.2f}",
        f"personalization_score: {report.personalization_score:.2f}",
        f"memory_impact_score: {report.memory_impact_score:.2f}",
        f"skill_impact_score: {report.skill_impact_score:.2f}",
        report.user_visible_summary_zh,
    ]
    if report.what_did_not_improve_zh:
        lines.append("未证明的提升: " + "；".join(report.what_did_not_improve_zh))
    if report.next_learning_actions_zh:
        lines.append("下一步: " + "；".join(report.next_learning_actions_zh))
    return "\n".join(lines)
