"""Phase 2 SkillRepo v2 — public API.

Markdown + frontmatter skills with file + SQLite FTS5 index.

Module map:
  models        — SkillStatus / SkillFrontmatter / SkillDocument
  signature     — sha256 (exact dedupe) + simhash64 (near dedupe)
  lifecycle     — legal status transitions
  index_store   — SQLite FTS5 index for search / promoted-only retrieval
  repository    — file + index orchestration; ``best_skill.md`` export

The Phase 0 contract is untouched: SkillRepo lives next to (not on top of)
the V4 ``skill_optimizer`` pipeline. Phase 3 (Curator/Validator) will be
the first caller that *writes* candidates; Phase 1 only ships the storage
plumbing.
"""

from __future__ import annotations

from stable_agent.skills.lifecycle import (
    LEGAL_TRANSITIONS,
    SkillTransitionError,
    can_promote,
    transition,
)
from stable_agent.skills.models import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    Triggers,
)
from stable_agent.skills.signature import (
    canonicalize,
    content_signature_sha256,
    hamming64,
    simhash64,
)

__all__ = [
    "LEGAL_TRANSITIONS",
    "Metrics",
    "SkillDocument",
    "SkillFrontmatter",
    "SkillStatus",
    "SkillTransitionError",
    "Triggers",
    "canonicalize",
    "can_promote",
    "content_signature_sha256",
    "hamming64",
    "simhash64",
    "transition",
]
