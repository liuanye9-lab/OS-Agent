from stable_agent.impact.builder import LearningImpactReportBuilder


def test_impact_report_does_not_need_raw_private_text():
    report = LearningImpactReportBuilder.build(
        run_id="run_privacy",
        memory_hits=[{"memory_id": "m1", "reason_zh": "命中偏好"}],
    )
    payload = report.to_dict()
    assert "user_original_input" not in payload
    assert "chain_of_thought" not in payload
