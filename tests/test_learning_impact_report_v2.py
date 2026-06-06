from stable_agent.impact.builder import LearningImpactReportBuilder


def test_learning_impact_report_scores_profile_and_memory():
    report = LearningImpactReportBuilder.build(
        run_id="run_1",
        profile_hits=[{"rule": "audit_before_refactor"}],
        memory_hits=[{"memory_id": "m1"}],
        skill_hits=[{"skill": "best_skill", "status": "promoted"}],
        token_report={"saving_ratio": 0.5},
        has_ab_validation=True,
    )
    assert report.overall_impact_score > 0
    assert report.memory_impact_score > 0
    assert report.skill_impact_score > 0
    assert "没有 memory hit" not in " ".join(report.what_did_not_improve_zh)
