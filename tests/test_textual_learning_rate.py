from stable_agent.skill_optimizer.textual_learning_rate import TextualLearningRate


def test_textual_learning_rate_limits_changes():
    rate = TextualLearningRate(max_lines_changed=2, max_sections_changed=1, max_rules_added=1)
    assert rate.validate(changed_lines=2, changed_sections=1, rules_added=1) == (True, "ok")
    ok, reason = rate.validate(changed_lines=3, changed_sections=1)
    assert ok is False
    assert "changed_lines" in reason
