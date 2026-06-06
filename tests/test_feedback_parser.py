from stable_agent.user_model.feedback_parser import FeedbackParser


def test_feedback_generates_candidate_preference():
    candidates = FeedbackParser.parse_user_feedback("下次不要大范围重构")
    assert candidates
    assert candidates[0].type == "coding_boundary"
    assert candidates[0].rule == "local_fix_first"
    assert candidates[0].status == "candidate"


def test_high_risk_feedback_pending_review():
    candidates = FeedbackParser.parse_user_feedback("以后自动 merge 并自动部署")
    high_risk = [c for c in candidates if c.type == "high_risk_policy"]
    assert high_risk
    assert high_risk[0].status == "pending_review"
    assert high_risk[0].requires_human_review is True
