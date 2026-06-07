"""Human review gate for self-iteration."""

from __future__ import annotations

from stable_agent.self_iteration.proposal import SelfIterationProposal


class ReviewGate:
    def can_merge(self, proposal: SelfIterationProposal, *, human_approved: bool = False) -> bool:
        return proposal.status == "approved" and human_approved

    def assert_review_required(self, proposal: SelfIterationProposal) -> None:
        if proposal.status != "ready_for_human_review":
            raise ValueError("self-iteration must stop at ready_for_human_review by default")
