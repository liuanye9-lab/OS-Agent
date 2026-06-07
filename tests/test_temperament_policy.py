from stable_agent.user_model.temperament_policy import default_temperament_policy


def test_high_risk_requires_review():
    policy = default_temperament_policy()
    assert policy.high_risk_requires_review is True
    assert policy.requires_review("delete files", risk_level="high") is True
    assert policy.requires_review("auto merge best_skill") is True
    assert policy.requires_review("small typo fix", risk_level="low") is False
