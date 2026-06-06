from stable_agent.impact.builder import LearningImpactReportBuilder


def test_no_memory_hit_no_memory_improvement_claim():
    report = LearningImpactReportBuilder.build(run_id="run_weak")
    assert report.memory_impact_score == 0
    assert any("没有 memory hit" in item for item in report.what_did_not_improve_zh)
    assert any("没有 promoted skill hit" in item for item in report.what_did_not_improve_zh)
    assert any("没有 A/B validation" in item for item in report.what_did_not_improve_zh)
