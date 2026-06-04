"""stable_agent/impact/models.py — Learning Impact Report 数据模型。

定义每次 os_agent 运行结束后展示给用户的学习收益数据结构。
所有字段均为只读快照，不包含用户隐私原文。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryImpact:
    """单条记忆命中记录。

    Attributes:
        memory_id: 记忆标识 (不包含完整内容)。
        content_preview: 内容预览 (最多 80 字符，脱敏)。
        reason_zh: 为什么选择这条记忆。
        used_in_stage: 在哪个执行阶段使用。
        confidence: 命中置信度 0.0~1.0。
    """
    memory_id: str = ""
    content_preview: str = ""
    reason_zh: str = ""
    used_in_stage: str = ""
    confidence: float = 0.0


@dataclass
class TokenImpact:
    """Token 预算影响。

    Attributes:
        baseline_tokens_estimated: 基线 token 估算。
        injected_tokens: 实际注入 token。
        dropped_tokens: 丢弃的 token。
        saved_tokens_estimated: 节省的 token。
        saving_ratio: 节省比例 0.0~1.0。
        summary_zh: 中文摘要。
        is_estimated: 是否为估算值。
    """
    baseline_tokens_estimated: int = 0
    injected_tokens: int = 0
    dropped_tokens: int = 0
    saved_tokens_estimated: int = 0
    saving_ratio: float = 0.0
    summary_zh: str = ""
    is_estimated: bool = True


@dataclass
class SkillImpact:
    """单条 Skill 影响记录。

    Attributes:
        skill_id: 技能标识。
        status: 状态 (promoted/candidate/validated/deprecated)。
        reason_zh: 使用或生成原因。
        used: 是否被使用。
        generated_this_run: 本次是否新生成。
        needs_validation: 是否需要后续验证。
        needs_human_review: 是否需要人工审核。
    """
    skill_id: str = ""
    status: str = ""
    reason_zh: str = ""
    used: bool = False
    generated_this_run: bool = False
    needs_validation: bool = False
    needs_human_review: bool = False


@dataclass
class LearningImpactReport:
    """Learning Impact Report — 本次运行的学习收益报告。

    每次 stableagent.task.os_agent 运行结束后生成，
    清晰展示记忆、token、skill 带来的体感收益。

    Attributes:
        run_id: 运行标识。
        overall_impact_score: 综合提升分数 0.0~1.0。
        memory_impact_score: 记忆命中分数 0.0~1.0。
        token_impact_score: Token 节省分数 0.0~1.0。
        skill_impact_score: Skill 使用/生成分数 0.0~1.0。
        personalization_score: 个性化提升分数 0.0~1.0。
        memory_hits: 记忆命中列表。
        token_impact: Token 影响详情。
        skills_used: 使用的 Skill 列表。
        skill_candidates_created: 本次生成的候选 Skill。
        what_improved_zh: 本次哪些地方变好了。
        what_did_not_improve_zh: 本次哪些地方没有提升。
        next_learning_actions_zh: 下一步学习动作。
        user_visible_summary_zh: 面向用户的摘要。
    """
    run_id: str = ""
    overall_impact_score: float = 0.0
    memory_impact_score: float = 0.0
    token_impact_score: float = 0.0
    skill_impact_score: float = 0.0
    personalization_score: float = 0.0
    memory_hits: list[MemoryImpact] = field(default_factory=list)
    token_impact: TokenImpact | None = None
    skills_used: list[SkillImpact] = field(default_factory=list)
    skill_candidates_created: list[SkillImpact] = field(default_factory=list)
    what_improved_zh: list[str] = field(default_factory=list)
    what_did_not_improve_zh: list[str] = field(default_factory=list)
    next_learning_actions_zh: list[str] = field(default_factory=list)
    user_visible_summary_zh: str = ""

    def to_dict(self) -> dict:
        """转换为字典格式 (用于 JSON 序列化)。"""
        return {
            "run_id": self.run_id,
            "overall_impact_score": round(self.overall_impact_score, 4),
            "memory_impact_score": round(self.memory_impact_score, 4),
            "token_impact_score": round(self.token_impact_score, 4),
            "skill_impact_score": round(self.skill_impact_score, 4),
            "personalization_score": round(self.personalization_score, 4),
            "memory_hits": [
                {
                    "memory_id": m.memory_id,
                    "content_preview": m.content_preview,
                    "reason_zh": m.reason_zh,
                    "used_in_stage": m.used_in_stage,
                    "confidence": round(m.confidence, 4),
                }
                for m in self.memory_hits
            ],
            "token_impact": {
                "baseline_tokens_estimated": self.token_impact.baseline_tokens_estimated,
                "injected_tokens": self.token_impact.injected_tokens,
                "dropped_tokens": self.token_impact.dropped_tokens,
                "saved_tokens_estimated": self.token_impact.saved_tokens_estimated,
                "saving_ratio": round(self.token_impact.saving_ratio, 4),
                "summary_zh": self.token_impact.summary_zh,
                "is_estimated": self.token_impact.is_estimated,
            } if self.token_impact else None,
            "skills_used": [
                {
                    "skill_id": s.skill_id,
                    "status": s.status,
                    "reason_zh": s.reason_zh,
                    "used": s.used,
                    "generated_this_run": s.generated_this_run,
                    "needs_validation": s.needs_validation,
                    "needs_human_review": s.needs_human_review,
                }
                for s in self.skills_used
            ],
            "skill_candidates_created": [
                {
                    "skill_id": s.skill_id,
                    "status": s.status,
                    "reason_zh": s.reason_zh,
                    "used": s.used,
                    "generated_this_run": s.generated_this_run,
                    "needs_validation": s.needs_validation,
                    "needs_human_review": s.needs_human_review,
                }
                for s in self.skill_candidates_created
            ],
            "what_improved_zh": self.what_improved_zh,
            "what_did_not_improve_zh": self.what_did_not_improve_zh,
            "next_learning_actions_zh": self.next_learning_actions_zh,
            "user_visible_summary_zh": self.user_visible_summary_zh,
        }
