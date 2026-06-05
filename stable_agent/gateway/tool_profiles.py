"""Tool profiles — Phase 1 minimal/default/full surfaces.

Profile decides which subset of the 47 registered tools is exposed via
stdio MCP / CLI. Goal:
  - **minimal** — bounded surface for AI hosts (Claude Code, Codex, Cursor)
    so they don't accidentally call SaaS or low-level tools.
  - **default** — power-user CLI surface(adds memory/skill/eval).
  - **full** — everything registered.

Profile is **filtering only** — no tool definitions are duplicated here. The
canonical schema source remains :mod:`stable_agent.gateway.tool_schemas`.

Selection precedence(first match wins):
  1. CLI flag ``--profile``
  2. Env var ``STABLE_AGENT_TOOL_PROFILE``
  3. ``"default"``
"""

from __future__ import annotations

import os
from typing import Any, Iterable

# Profile names — keep lowercase ASCII only.
PROFILE_MINIMAL = "minimal"
PROFILE_DEFAULT = "default"
PROFILE_FULL = "full"

# Minimal profile — 12 tools.
# These are the ones AI hosts actually need to drive a complete OS-Agent
# session: run a task, give feedback, query status.
MINIMAL_TOOLS: tuple[str, ...] = (
    "stableagent.task.os_agent",
    "stableagent.task.process",
    "stableagent.feedback.remember",
    "stableagent.feedback.dont_do_this_again",
    "stableagent.feedback.correct_and_remember",
    "stableagent.understanding.trace",
    "stableagent.trace.get_run",
    "stableagent.approval.respond",
    "stableagent.token.summary",
    "stableagent.memory.health",
    "stableagent.capsule.status",
    "stableagent.eval.evaluate",
)

# Default profile — minimal + memory CRUD + skill optimization.
DEFAULT_EXTRAS: tuple[str, ...] = (
    "stableagent.context.build",
    "stableagent.context.estimate_budget",
    "stableagent.memory.retrieve",
    "stableagent.memory.write_candidate",
    "stableagent.memory.review",
    "stableagent.memory.prune",
    "stableagent.memory.promote",
    "stableagent.rag.retrieve",
    "stableagent.skillopt.status",
    "stableagent.skillopt.get_current_skill",
    "stableagent.skillopt.export_best",
    "stableagent.understanding.correct",
    "stableagent.expression.list",
    "stableagent.expression.add",
    "stableagent.expression.delete",
    "stableagent.badcase.record",
    "stableagent.eval.case.list",
    "stableagent.eval.run_ab",
    "stableagent.eval.rubric.get",
    "stableagent.token.report",
    "stableagent.token.run",
    "stableagent.capsule.doctor",
    "stableagent.memory.delete",
    "stableagent.model.profile",
    "stableagent.model.list",
    "stableagent.model.suggest",
)

ENV_VAR = "STABLE_AGENT_TOOL_PROFILE"

# Minimum tool counts as a hard contract guard. The test suite asserts
# `len(get_tool_names("minimal")) <= MINIMAL_MAX` so profile drift from
# 12 → 30 doesn't sneak in unnoticed.
MINIMAL_MAX = 12


def resolve_profile(name: str | None = None) -> str:
    """Resolve effective profile name: explicit > env > default."""
    candidate = (name or os.environ.get(ENV_VAR, "") or PROFILE_DEFAULT).lower()
    if candidate not in (PROFILE_MINIMAL, PROFILE_DEFAULT, PROFILE_FULL):
        return PROFILE_DEFAULT
    return candidate


def get_tool_names(profile: str | None = None) -> tuple[str, ...]:
    """Return tool name set for the given profile.

    Args:
        profile: profile name; ``None`` means ``resolve_profile()``.

    Returns:
        Tuple of fully-qualified tool names. ``"full"`` returns ``()`` —
        callers must interpret empty as "no filter".
    """
    name = resolve_profile(profile)
    if name == PROFILE_MINIMAL:
        return MINIMAL_TOOLS
    if name == PROFILE_DEFAULT:
        # default = minimal ∪ extras, deduped, order preserved.
        seen: set[str] = set()
        merged: list[str] = []
        for t in MINIMAL_TOOLS + DEFAULT_EXTRAS:
            if t not in seen:
                seen.add(t)
                merged.append(t)
        return tuple(merged)
    return ()  # full = no filter


def filter_tool_list(
    tools: Iterable[dict[str, Any]],
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """Filter a tool list (as returned by ``UnifiedToolRegistry.list_tools``).

    Empty allow-list (``profile="full"``) returns the input unchanged.
    """
    allowed = get_tool_names(profile)
    if not allowed:
        return list(tools)
    allow_set = set(allowed)
    return [t for t in tools if t.get("name") in allow_set]
