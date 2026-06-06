"""Build Codex prompts for PR-only self-iteration."""

from __future__ import annotations

from stable_agent.self_iteration.patch_planner import DraftPatchPlan


class PRPromptBuilder:
    def build(self, plan: DraftPatchPlan) -> str:
        return (
            "You are preparing a PR-only improvement.\n"
            f"Branch plan: {plan.branch_name}\n"
            f"Patch summary: {plan.patch_summary}\n"
            "Do not merge, push, deploy, or promote. Stop at human review.\n"
            "Run pytest/benchmark before presenting the PR summary."
        )
