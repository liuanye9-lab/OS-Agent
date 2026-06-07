from stable_agent.user_model.repository import UserModelRepository


def test_profile_files_initialize(tmp_path):
    repo = UserModelRepository(tmp_path / "user_model")
    paths = repo.initialize_defaults()

    assert paths["expression_profile"].exists()
    assert paths["cognitive_profile"].exists()
    assert paths["temperament_policy"].exists()
    assert repo.load_expression_profile().preferred_language == "zh-CN"
    assert "第一性原理" in repo.load_cognitive_profile().thinking_models


def test_profile_hits_include_audit_preference(tmp_path):
    repo = UserModelRepository(tmp_path / "user_model")
    hits = repo.profile_hits_for_task("请先审计再重构，并运行 pytest 验收")
    rules = {hit["rule"] for hit in hits}
    assert "audit_before_refactor" in rules
    assert "show_verification_evidence" in rules
