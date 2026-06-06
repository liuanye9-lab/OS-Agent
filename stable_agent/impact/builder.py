"""Learning Impact Report builder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stable_agent.impact.models import LearningImpactReport
from stable_agent.impact.scoring import clamp_score, score_memory, score_profiles, score_skills, score_tokens


class LearningImpactReportBuilder:
    @staticmethod
    def build(
        *,
        run_id: str,
        memory_hits: list[dict[str, Any]] | None = None,
        skill_hits: list[dict[str, Any]] | None = None,
        profile_hits: list[dict[str, Any]] | None = None,
        candidate_created: list[dict[str, Any]] | None = None,
        token_report: dict[str, Any] | None = None,
        has_ab_validation: bool = False,
    ) -> LearningImpactReport:
        memories = list(memory_hits or [])
        skills = list(skill_hits or [])
        profiles = list(profile_hits or [])
        candidates = list(candidate_created or [])

        personalization_score = score_profiles(profiles)
        memory_impact_score = score_memory(memories)
        skill_impact_score = score_skills(skills)
        token_impact_score = score_tokens(token_report)
        evidence_score = clamp_score(0.2 + (0.2 if memories else 0.0) + (0.2 if profiles else 0.0) + (0.2 if has_ab_validation else 0.0))

        improved: list[str] = []
        not_improved: list[str] = []
        next_actions: list[str] = []

        if profiles:
            improved.append("使用了表达/思维偏好来约束任务理解。")
        else:
            not_improved.append("没有命中 user profile，不能声称个性化提升。")

        if memories:
            improved.append(f"命中 {len(memories)} 条记忆，并说明了使用原因。")
        else:
            not_improved.append("没有 memory hit，不能声称记忆提升。")
            next_actions.append("继续收集有证据的候选记忆。")

        if any(s.get("status") == "promoted" for s in skills):
            improved.append("使用了 promoted skill。")
        else:
            not_improved.append("没有 promoted skill hit，不能声称 skill 提升。")

        if not has_ab_validation:
            not_improved.append("没有 A/B validation，不能声称自进化已经有效。")
            next_actions.append("为 candidate skill 安排 baseline-vs-candidate A/B 验证。")

        if candidates:
            next_actions.append("新 candidate 处于等待验证状态，不能直接沉淀。")

        overall = clamp_score(
            0.25 * personalization_score
            + 0.25 * memory_impact_score
            + 0.2 * skill_impact_score
            + 0.15 * token_impact_score
            + 0.15 * evidence_score
        )

        summary = "本次有个性化信号，但仍需验证后才能声称自我进化有效。"
        if overall < 0.25:
            summary = "本次学习信号较弱：缺少记忆命中、promoted skill 或 A/B 证据。"
        elif candidates and not has_ab_validation:
            summary = "本次生成了候选学习项，状态是等待验证，不会直接写入长期规则。"

        return LearningImpactReport(
            run_id=run_id,
            overall_impact_score=overall,
            personalization_score=personalization_score,
            memory_impact_score=memory_impact_score,
            skill_impact_score=skill_impact_score,
            token_impact_score=token_impact_score,
            evidence_score=evidence_score,
            memory_hits=memories,
            skill_hits=skills,
            profile_hits=profiles,
            candidate_created=candidates,
            what_improved_zh=improved,
            what_did_not_improve_zh=not_improved,
            next_learning_actions_zh=next_actions,
            user_visible_summary_zh=summary,
        )

    @staticmethod
    def save_latest(report: LearningImpactReport, root: str | Path = ".stableagent/impact") -> Path:
        path = Path(root) / "latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def load_latest(root: str | Path = ".stableagent/impact") -> LearningImpactReport | None:
        path = Path(root) / "latest.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return LearningImpactReport(**data)
