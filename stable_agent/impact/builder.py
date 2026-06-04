"""stable_agent/impact/builder.py — LearningImpactBuilder。

从 events / token_report / si_report / curator_report 构建
LearningImpactReport。

职责：
- 从事件流提取 memory impact
- 从 token_report 提取 token impact
- 从 si_report / curator_report 提取 skill impact
- 计算 personalization score
- 调用 ImpactScorer 计算综合分

不负责：
- 修改事件
- 修改 RunStore
- 展示 (由前端/CLI 负责)
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.impact.models import (
    LearningImpactReport,
    MemoryImpact,
    TokenImpact,
    SkillImpact,
)
from stable_agent.impact.scoring import ImpactScorer

logger = logging.getLogger(__name__)


class LearningImpactBuilder:
    """从运行数据构建 LearningImpactReport。

    构建失败不影响主任务 — 外层应 catch 异常并返回 error 字段。
    """

    def __init__(self) -> None:
        self._scorer = ImpactScorer()

    def build(
        self,
        run_id: str,
        events: list[dict[str, Any]],
        token_report: dict[str, Any] | None = None,
        si_report: dict[str, Any] | None = None,
        curator_report: dict[str, Any] | None = None,
    ) -> LearningImpactReport:
        """构建 LearningImpactReport。

        Args:
            run_id: 运行标识。
            events: 本次运行发出的事件列表。
            token_report: Token 预算报告 (可选)。
            si_report: Self-Improvement 报告 (可选)。
            curator_report: Curator 分析报告 (可选)。

        Returns:
            完整的 LearningImpactReport。
        """
        report = LearningImpactReport(run_id=run_id)

        # 1. Memory Impact
        self._build_memory_impact(report, events)

        # 2. Token Impact
        self._build_token_impact(report, token_report)

        # 3. Skill Impact
        self._build_skill_impact(report, si_report, curator_report)

        # 4. Personalization Score
        self._compute_personalization(report)

        # 5. Score and summarize
        report = self._scorer.score(report)

        return report

    # ── Memory Impact ─────────────────────────────────────────

    def _build_memory_impact(
        self, report: LearningImpactReport, events: list[dict[str, Any]]
    ) -> None:
        """从 temporal_memory.retrieved 事件提取记忆命中。

        逻辑：
        - 找到 event_type == "temporal_memory.retrieved" 的事件
        - 提取 selected_memories 列表
        - 构建 MemoryImpact 记录
        - 计算 memory_impact_score
        """
        memory_event = self._find_event(events, "temporal_memory.retrieved")
        if not memory_event:
            report.memory_impact_score = 0.0
            return

        selected = memory_event.get("selected_memories", [])
        count = memory_event.get("count", len(selected))

        if count == 0 or not selected:
            report.memory_impact_score = 0.0
            report.what_did_not_improve_zh.append(
                "本次没有命中历史记忆，不会产生明显个性化提升。"
            )
            return

        for mem in selected[:5]:  # 最多展示 5 条
            impact = MemoryImpact(
                memory_id=str(mem.get("memory_id", "")),
                content_preview=self._truncate(str(mem.get("content_preview", mem.get("reason_zh", ""))), 80),
                reason_zh=str(mem.get("reason_zh", "相关性匹配")),
                used_in_stage="temporal_memory_retrieving",
                confidence=float(mem.get("confidence", 0.7)),
            )
            report.memory_hits.append(impact)

        # 分数: min(1.0, count / 5)
        report.memory_impact_score = min(1.0, count / 5.0)

        if count > 0:
            report.what_improved_zh.append(
                f"本次命中 {count} 条历史记忆，提升了任务个性化程度。"
            )

    # ── Token Impact ──────────────────────────────────────────

    def _build_token_impact(
        self, report: LearningImpactReport, token_report: dict[str, Any] | None
    ) -> None:
        """从 token_report 提取 token 节省情况。

        逻辑：
        - 如果 token_report 为空，token_impact_score = 0
        - 否则提取 baseline/injected/dropped/saved/saving_ratio
        - 根据 saving_ratio 计算 token_impact_score
        """
        if not token_report or not isinstance(token_report, dict):
            report.token_impact_score = 0.0
            return

        impact = TokenImpact(
            baseline_tokens_estimated=int(token_report.get("baseline_tokens_estimated", 0)),
            injected_tokens=int(token_report.get("injected_tokens", 0)),
            dropped_tokens=int(token_report.get("dropped_tokens", 0)),
            saved_tokens_estimated=int(token_report.get("saved_tokens_estimated", 0)),
            saving_ratio=float(token_report.get("saving_ratio", 0.0)),
            summary_zh=str(token_report.get("summary_zh", "")),
            is_estimated=bool(token_report.get("is_estimated", True)),
        )
        report.token_impact = impact

        # 分数: saving_ratio 映射到 0~1，但 cap 在 0.8
        if impact.saving_ratio > 0.0:
            report.token_impact_score = min(0.8, impact.saving_ratio)
            report.what_improved_zh.append(
                f"本次通过上下文压缩节省了约 {int(impact.saving_ratio * 100)}% token。"
            )
        else:
            report.token_impact_score = 0.0
            if impact.baseline_tokens_estimated < 500:
                report.what_did_not_improve_zh.append(
                    "本次上下文较短，token 优化体感不明显。"
                )

    # ── Skill Impact ──────────────────────────────────────────

    def _build_skill_impact(
        self,
        report: LearningImpactReport,
        si_report: dict[str, Any] | None,
        curator_report: dict[str, Any] | None,
    ) -> None:
        """从 si_report 和 curator_report 提取 skill 影响。

        逻辑：
        - 从 si_report 读取 learning_triggered, skill_patches, validation_passed, human_review_required
        - 从 curator_report 读取 candidates_created
        - 如果生成了 candidate: skill_impact_score += 0.4
        - 如果有 skill_patches: skill_impact_score += 0.3
        - 如果 validation_passed: skill_impact_score += 0.3
        """
        score = 0.0

        # 从 curator_report 提取候选 skill
        if curator_report and isinstance(curator_report, dict):
            candidates_created = curator_report.get("candidates_created", 0)
            if candidates_created > 0:
                score += 0.4
                for i in range(candidates_created):
                    report.skill_candidates_created.append(SkillImpact(
                        skill_id=f"candidate_{i + 1}",
                        status="candidate",
                        reason_zh="Curator 从本次运行中提炼出改进规则",
                        used=False,
                        generated_this_run=True,
                        needs_validation=True,
                        needs_human_review=False,
                    ))
                report.next_learning_actions_zh.append(
                    "已生成 candidate skill，需要后续相关任务验证。"
                )

        # 从 si_report 提取 skill patches
        if si_report and isinstance(si_report, dict):
            learning_triggered = si_report.get("learning_triggered", False)
            skill_patches = si_report.get("skill_patches", [])
            validation_passed = si_report.get("validation_passed", False)
            human_review_required = si_report.get("human_review_required", False)
            best_skill_exported = si_report.get("best_skill_exported", False)

            if learning_triggered:
                score += 0.2

            if skill_patches:
                score += 0.2
                for patch in skill_patches:
                    patch_id = patch.get("patch_id", "") if isinstance(patch, dict) else str(patch)
                    report.skill_candidates_created.append(SkillImpact(
                        skill_id=patch_id,
                        status="candidate",
                        reason_zh=f"针对 {patch.get('failure_mode', '未知')} 模式生成的改进规则" if isinstance(patch, dict) else "Skill patch 提案",
                        used=False,
                        generated_this_run=True,
                        needs_validation=not validation_passed,
                        needs_human_review=human_review_required,
                    ))

            if validation_passed:
                score += 0.2
                report.what_improved_zh.append("Skill 验证通过，改进已确认有效。")

            if human_review_required:
                report.next_learning_actions_zh.append(
                    "有 skill patch 等待人工审核。"
                )

            if best_skill_exported:
                score += 0.1
                report.what_improved_zh.append("最佳 skill 已导出。")

        report.skill_impact_score = min(1.0, score)

        if score == 0.0:
            report.what_did_not_improve_zh.append(
                "本次未使用 promoted skill，也未触发技能更新。"
            )

    # ── Personalization Score ─────────────────────────────────

    def _compute_personalization(self, report: LearningImpactReport) -> None:
        """综合计算个性化分数。

        personalization_score = weighted average of:
        - memory_impact_score (0.4)
        - skill_impact_score (0.3)
        - feedback_hit_score (0.3) — 暂用 0.0，后续接入反馈数据
        """
        feedback_hit_score = 0.0  # TODO: 从 feedback 事件提取

        report.personalization_score = round(
            0.4 * report.memory_impact_score
            + 0.3 * report.skill_impact_score
            + 0.3 * feedback_hit_score,
            4,
        )

    # ── 辅助方法 ──────────────────────────────────────────────

    @staticmethod
    def _find_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
        """在事件列表中查找指定类型的事件。"""
        for evt in events:
            if isinstance(evt, dict) and evt.get("event_type") == event_type:
                return evt
        return None

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """截断文本，超过 max_len 则加省略号。"""
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."
