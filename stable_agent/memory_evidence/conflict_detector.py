"""Conflict detection for memory candidates."""

from __future__ import annotations

import re

from stable_agent.memory_evidence.models import MemoryCandidate


class ConflictDetector:
    NEGATION = ("不要", "别", "never", "do not", "don't", "禁止")
    AFFIRMATION = ("必须", "总是", "always", "should", "要")

    def detect(self, candidates: list[MemoryCandidate]) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        for i, left in enumerate(candidates):
            for right in candidates[i + 1:]:
                if self._conflicts(left.content_summary, right.content_summary):
                    conflicts.append({
                        "left": left.memory_id,
                        "right": right.memory_id,
                        "reason_zh": "两条候选记忆对同一行为给出相反偏好。",
                    })
        return conflicts

    def mark_conflicts(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        conflict_ids = {c["left"] for c in self.detect(candidates)} | {c["right"] for c in self.detect(candidates)}
        return [c.mark_conflict() if c.memory_id in conflict_ids else c for c in candidates]

    def _conflicts(self, a: str, b: str) -> bool:
        a_norm = self._normalize_subject(a)
        b_norm = self._normalize_subject(b)
        if not a_norm or not b_norm:
            return False
        overlaps = len(set(a_norm.split()) & set(b_norm.split())) >= 1
        polarity_diff = self._polarity(a) * self._polarity(b) == -1
        return overlaps and polarity_diff

    def _polarity(self, text: str) -> int:
        lowered = text.lower()
        if any(word in lowered for word in self.NEGATION):
            return -1
        if any(word in lowered for word in self.AFFIRMATION):
            return 1
        return 0

    @staticmethod
    def _normalize_subject(text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^\w\u4e00-\u9fff]+", " ", lowered)
        for word in ("不要", "别", "never", "do", "not", "don't", "必须", "总是", "always", "should", "要"):
            lowered = lowered.replace(word, " ")
        return " ".join(lowered.split())
