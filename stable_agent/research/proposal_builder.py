"""Build improvement proposals from evidence cards."""

from __future__ import annotations

import uuid

from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.source_models import ImprovementProposal


class ProposalBuilder:
    def build(self, card: ResearchEvidenceCard) -> ImprovementProposal:
        return ImprovementProposal(
            proposal_id=f"proposal_{uuid.uuid4().hex[:12]}",
            finding_id=card.finding_id,
            status="ready_for_human_review",
            summary_zh="外部证据只能生成改进提案，不能直接写入 skill 或 active memory。",
            proposed_changes=list(card.proposed_changes),
            requires_validation=True,
            requires_human_review=True,
        )
