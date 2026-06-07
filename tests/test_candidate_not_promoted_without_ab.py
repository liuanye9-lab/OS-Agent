from stable_agent.validation.ab_runner import DelayedValidationABRunner


def test_candidate_not_promoted_without_ab():
    result = DelayedValidationABRunner().compare([], [])
    assert result.passed is False
    assert result.status == "waiting_for_related_tasks"
