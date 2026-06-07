from stable_agent.self_iteration.proposal import SelfIterationProposal
from stable_agent.self_iteration.review_gate import ReviewGate


def test_review_gate_default_no_merge():
    proposal = SelfIterationProposal.create(source_type="research", source_ref="finding_1", objective_zh="生成提案")
    gate = ReviewGate()
    gate.assert_review_required(proposal)
    assert gate.can_merge(proposal, human_approved=False) is False
