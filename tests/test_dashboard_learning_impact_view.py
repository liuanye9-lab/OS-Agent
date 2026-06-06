from pathlib import Path


def test_dashboard_has_recursive_harness_panels():
    html = Path("web/templates/run_observer.html").read_text(encoding="utf-8")
    for panel_id in [
        "rhProfileContent",
        "rhMemoryContent",
        "rhSkillContent",
        "rhImpactContent",
        "rhResearchContent",
        "rhCandidateContent",
        "rhValidationContent",
        "rhReviewContent",
        "rhSelfIterationContent",
    ]:
        assert panel_id in html

    js = Path("web/static/run_observer.js").read_text(encoding="utf-8")
    assert "function updateRecursiveHarnessPanels" in js
    assert "learning_impact_report" in js
