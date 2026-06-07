from stable_agent.research.evidence_card import ResearchEvidenceCard


def test_research_card_defaults_to_evidence_only():
    card = ResearchEvidenceCard.create(
        source_type="arxiv",
        source_url="https://arxiv.org/abs/0000.00000",
        title="Test",
        claims=["claim"],
        evidence_summary="summary",
    )
    assert card.status == "evidence_only"
    assert card.finding_id.startswith("finding_")
