from pathlib import Path


def test_dashboard_recursive_panels_do_not_render_cot_fields():
    js = Path("web/static/run_observer.js").read_text(encoding="utf-8")
    whitelist_function = js[js.index("function pickPublicDecisionFields"):js.index("function renderPublicDecision")]
    assert "chain_of_thought" not in whitelist_function
    assert "hidden" not in whitelist_function.lower()
    assert "decision_summary_zh" in whitelist_function
    assert "why_zh" in whitelist_function
    assert "next_step_zh" in whitelist_function
