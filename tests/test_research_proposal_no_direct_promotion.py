from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.proposal_builder import ProposalBuilder


def test_research_proposal_requires_validation_and_review():
    card = ResearchEvidenceCard.create(
        source_type="github",
        source_url="https://github.com/example/repo",
        title="Repo",
        claims=["claim"],
        evidence_summary="summary",
    )
    proposal = ProposalBuilder().build(card)
    assert proposal.status == "ready_for_human_review"
    assert proposal.requires_validation is True
    assert proposal.requires_human_review is True
