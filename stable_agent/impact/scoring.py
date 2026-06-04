"""stable_agent/impact/scoring.py — Impact 评分逻辑。

计算记忆、token、skill、个性化四个维度的分数，
以及综合 overall_impact_score。
"""

from __future__ import annotations

from stable_agent.impact.models import (
    LearningImpactReport,
    MemoryImpact,
    TokenImpact,
    SkillImpact,
)


class ImpactScorer:
    """Impact 评分器。

    根据报告的各维度数据计算分数。
    评分规则：
    - 不伪造提升：没有数据就不给分
    - 低分时诚实解释原因
    - 综合分 = 加权平均
    """

    # 各维度权重
    WEIGHTS = {
        "memory": 0.25,
        "token": 0.25,
        "skill": 0.30,
        "personalization": 0.20,
    }

    def score(self, report: LearningImpactReport) -> LearningImpactReport:
        """计算并填充报告的分数字段。

        Args:
            report: 待评分的报告 (各维度数据已填充)。

        Returns:
            评分后的报告 (原地修改并返回)。
        """
        # 各维度分数已在 builder 中计算，这里计算综合分
        report.overall_impact_score = self._weighted_score(
            report.memory_impact_score,
            report.token_impact_score,
            report.skill_impact_score,
            report.personalization_score,
        )

        # 补充"没有提升"的原因
        self._fill_no_improvement_reasons(report)

        # 生成用户摘要
        report.user_visible_summary_zh = self._build_summary(report)

        return report

    def _weighted_score(
        self,
        memory_score: float,
        token_score: float,
        skill_score: float,
        personalization_score: float,
    ) -> float:
        """加权综合分数。"""
        return round(
            self.WEIGHTS["memory"] * memory_score
            + self.WEIGHTS["token"] * token_score
            + self.WEIGHTS["skill"] * skill_score
            + self.WEIGHTS["personalization"] * personalization_score,
            4,
        )

    def _fill_no_improvement_reasons(self, report: LearningImpactReport) -> None:
        """当分数低时，诚实解释为什么体感弱。"""
        existing = set(report.what_did_not_improve_zh)

        if report.memory_impact_score == 0.0 and "本次没有命中历史记忆，不会产生明显个性化提升。" not in existing:
            report.what_did_not_improve_zh.append(
                "本次没有命中历史记忆，不会产生明显个性化提升。"
            )

        if report.token_impact_score == 0.0 and "本次上下文较短或无 token 压缩数据，token 优化体感不明显。" not in existing:
            report.what_did_not_improve_zh.append(
                "本次上下文较短或无 token 压缩数据，token 优化体感不明显。"
            )

        if report.skill_impact_score == 0.0 and "本次未使用 promoted skill，也未触发技能更新。" not in existing:
            report.what_did_not_improve_zh.append(
                "本次未使用 promoted skill，也未触发技能更新。"
            )

        if report.overall_impact_score < 0.3:
            low_reasons = []
            if report.memory_impact_score < 0.2:
                low_reasons.append("历史记忆不足")
            if report.skill_impact_score < 0.2:
                low_reasons.append("未命中已验证 skill")
            if report.token_impact_score < 0.2:
                low_reasons.append("token 优化不明显")
            if not low_reasons:
                low_reasons.append("任务较简单或缺少用户反馈")
            reason_str = "、".join(low_reasons)
            summary = f"本次个性化提升较弱，原因可能是：{reason_str}。"
            if summary not in existing:
                report.what_did_not_improve_zh.append(summary)

    def _build_summary(self, report: LearningImpactReport) -> str:
        """构建面向用户的摘要。"""
        score_pct = int(report.overall_impact_score * 100)
        parts = [f"本次学习提升: {score_pct}%"]

        if report.memory_hits:
            parts.append(f"命中 {len(report.memory_hits)} 条记忆")
        if report.token_impact and report.token_impact.saved_tokens_estimated > 0:
            parts.append(f"节省约 {report.token_impact.saved_tokens_estimated} token")
        if report.skill_candidates_created:
            parts.append(f"生成 {len(report.skill_candidates_created)} 个候选 skill")

        if report.overall_impact_score < 0.3:
            parts.append("体感提升较弱，建议继续积累历史数据。")

        return " | ".join(parts)
