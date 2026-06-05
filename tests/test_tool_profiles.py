"""Phase 1 — tool profile filter.

Profiles cap the tool surface exposed via stdio MCP / CLI so AI hosts
don't accidentally call SaaS or low-level tools. This file pins:

  - minimal ≤ 12 tools (hard ceiling — `MINIMAL_MAX`)
  - default ⊇ minimal
  - full = no filter (`get_tool_names("full") == ()`)
  - env var resolution
  - filter never duplicates / loses tools

These guards exist because profile drift(creeping a new SaaS tool into
"minimal") is hard to spot in code review.
"""

from __future__ import annotations

import os

import pytest

from stable_agent.gateway.tool_profiles import (
    DEFAULT_EXTRAS,
    ENV_VAR,
    MINIMAL_MAX,
    MINIMAL_TOOLS,
    PROFILE_DEFAULT,
    PROFILE_FULL,
    PROFILE_MINIMAL,
    filter_tool_list,
    get_tool_names,
    resolve_profile,
)


def test_minimal_under_hard_cap():
    assert len(MINIMAL_TOOLS) <= MINIMAL_MAX, (
        f"minimal profile exceeded the {MINIMAL_MAX}-tool cap: "
        f"{len(MINIMAL_TOOLS)} tools registered."
    )


def test_minimal_includes_os_agent_and_feedback():
    """The whole point of the minimal profile is the H.Agent surface."""
    must_have = {
        "stableagent.task.os_agent",
        "stableagent.feedback.remember",
        "stableagent.feedback.dont_do_this_again",
    }
    assert must_have.issubset(set(MINIMAL_TOOLS))


def test_default_is_superset_of_minimal():
    default = set(get_tool_names(PROFILE_DEFAULT))
    assert set(MINIMAL_TOOLS).issubset(default)


def test_full_is_unfiltered():
    """`get_tool_names("full")` returns empty tuple — interpreted as no filter."""
    assert get_tool_names(PROFILE_FULL) == ()


def test_resolve_profile_env_var(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "minimal")
    assert resolve_profile() == PROFILE_MINIMAL

    monkeypatch.setenv(ENV_VAR, "GIBBERISH")
    assert resolve_profile() == PROFILE_DEFAULT  # invalid → default

    monkeypatch.delenv(ENV_VAR, raising=False)
    assert resolve_profile() == PROFILE_DEFAULT


def test_resolve_profile_explicit_wins_over_env(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "full")
    assert resolve_profile("minimal") == PROFILE_MINIMAL


def test_filter_tool_list_minimal_keeps_only_allowed():
    fake_tools = [
        {"name": "stableagent.task.os_agent"},
        {"name": "stableagent.skill.review"},  # not in minimal
        {"name": "stableagent.token.summary"},
    ]
    out = filter_tool_list(fake_tools, profile=PROFILE_MINIMAL)
    out_names = {t["name"] for t in out}
    assert "stableagent.task.os_agent" in out_names
    assert "stableagent.skill.review" not in out_names
    assert "stableagent.token.summary" in out_names


def test_filter_tool_list_full_returns_all():
    fake_tools = [
        {"name": "a"},
        {"name": "b"},
        {"name": "stableagent.task.os_agent"},
    ]
    out = filter_tool_list(fake_tools, profile=PROFILE_FULL)
    assert {t["name"] for t in out} == {"a", "b", "stableagent.task.os_agent"}


def test_get_tool_names_default_no_duplicates():
    """Default = minimal ∪ extras — must not list the same tool twice."""
    names = get_tool_names(PROFILE_DEFAULT)
    assert len(names) == len(set(names))


def test_default_extras_disjoint_from_minimal():
    """Sanity: extras shouldn't restate minimal tools (the merge handles it,
    but if a duplicate sneaks in we want a louder signal)."""
    overlap = set(MINIMAL_TOOLS) & set(DEFAULT_EXTRAS)
    assert not overlap, f"extras overlap minimal: {overlap}"
