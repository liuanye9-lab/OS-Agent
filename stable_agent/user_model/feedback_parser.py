"""Turn user feedback into reviewable preference candidates."""

from __future__ import annotations

import re

from stable_agent.user_model.models import PreferenceCandidate


class FeedbackParser:
    """Small deterministic parser for first-pass feedback candidates."""

    HIGH_RISK_PATTERNS = (
        "自动 merge",
        "自动合并",
        "自动 deploy",
        "自动部署",
        "自动 promote",
        "自动晋升",
        "覆盖 best_skill",
        "删除 safety",
        "删除安全",
        "绕过 review",
        "绕过审核",
    )

    @classmethod
    def parse_user_feedback(cls, text: str) -> list[PreferenceCandidate]:
        if not text or not text.strip():
            return []

        cleaned = " ".join(text.strip().split())
        lowered = cleaned.lower()
        candidates: list[PreferenceCandidate] = []

        if any(p in cleaned for p in ("不要大范围重构", "别大范围重构", "不要乱改", "少改文件")):
            candidates.append(cls._candidate(
                preference_type="coding_boundary",
                rule="local_fix_first",
                text=cleaned,
                confidence=0.86,
            ))

        if any(p in cleaned for p in ("先审计", "先检查", "先看现状")):
            candidates.append(cls._candidate(
                preference_type="workflow",
                rule="audit_before_refactor",
                text=cleaned,
                confidence=0.78,
            ))

        if any(p in cleaned for p in ("小白", "大白话", "讲人话")):
            candidates.append(cls._candidate(
                preference_type="communication",
                rule="plain_language_first",
                text=cleaned,
                confidence=0.8,
            ))

        if any(p in lowered for p in ("evidence", "证据", "pytest", "验收")):
            candidates.append(cls._candidate(
                preference_type="evidence",
                rule="show_verification_evidence",
                text=cleaned,
                confidence=0.72,
            ))

        if any(pattern in cleaned for pattern in cls.HIGH_RISK_PATTERNS):
            candidates.append(PreferenceCandidate(
                type="high_risk_policy",
                rule="requires_human_review_before_enablement",
                evidence="user_feedback",
                status="pending_review",
                confidence=0.9,
                requires_human_review=True,
                source_text_summary=cls._summarize(cleaned),
                metadata={"risk": "high"},
            ))

        if not candidates:
            candidates.append(cls._candidate(
                preference_type="general_preference",
                rule="review_before_activation",
                text=cleaned,
                confidence=0.5,
            ))

        return candidates

    @classmethod
    def _candidate(
        cls,
        *,
        preference_type: str,
        rule: str,
        text: str,
        confidence: float,
    ) -> PreferenceCandidate:
        return PreferenceCandidate(
            type=preference_type,
            rule=rule,
            evidence="user_feedback",
            status="candidate",
            confidence=confidence,
            requires_human_review=False,
            source_text_summary=cls._summarize(text),
        )

    @staticmethod
    def _summarize(text: str) -> str:
        sanitized = re.sub(r"[\w.+-]+@[\w.-]+", "[redacted-email]", text)
        sanitized = re.sub(r"(sk-|ghp_|xoxb-)[A-Za-z0-9_-]+", "[redacted-secret]", sanitized)
        return sanitized[:120]
