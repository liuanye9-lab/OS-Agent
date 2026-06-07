from stable_agent.memory_evidence.hit_report import build_memory_hit_report


def test_memory_hit_report_lists_hits_and_stage():
    report = build_memory_hit_report(
        hits=[{"memory_id": "m1", "reason_zh": "匹配用户约束", "source": "temporal_memory"}],
        stage="temporal_memory_retrieving",
    )
    data = report.to_dict()
    assert data["memory_hits"][0]["memory_id"] == "m1"
    assert data["memory_used_in_stage"] == "temporal_memory_retrieving"
    assert data["why_this_memory_zh"] == ["匹配用户约束"]
