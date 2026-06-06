"""Plan draft patches without applying or pushing them."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from stable_agent.self_iteration.proposal import SelfIterationProposal


@dataclass
class DraftPatchPlan:
    proposal_id: str
    branch_name: str
    patch_summary: str
    allowed_actions: list[str]
    forbidden_actions: list[str]
    status: str = "ready_for_human_review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PatchPlanner:
    def plan(self, proposal: SelfIterationProposal) -> DraftPatchPlan:
        return DraftPatchPlan(
            proposal_id=proposal.proposal_id,
            branch_name=f"codex/{proposal.proposal_id}",
            patch_summary=proposal.objective_zh,
            allowed_actions=["create_branch_plan", "generate_patch_summary", "build_codex_prompt"],
            forbidden_actions=["push", "merge", "deploy", "promote_best_skill"],
        )
