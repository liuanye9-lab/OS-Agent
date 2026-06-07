from stable_agent.skill_optimizer.bounded_editor import BoundedSkillEditor
from stable_agent.skill_optimizer.edit_models import BoundedSkillEdit
from stable_agent.skill_optimizer.heldout_validator import HeldoutValidationResult
from stable_agent.skill_optimizer.rejected_buffer import RejectedBuffer


def test_bounded_editor_accepts_small_add_rule(tmp_path):
    editor = BoundedSkillEditor(rejected_buffer=RejectedBuffer(tmp_path / "rejected.jsonl"))
    result = editor.apply(
        "## Procedure\n\n- Existing rule\n",
        [BoundedSkillEdit(operation="ADD_RULE", target="Procedure", content="Run focused pytest.")],
        validation=HeldoutValidationResult(True, 0.8, 0.84, 0.04, 0, 1.0, "ok"),
    )
    assert result.accepted is True
    assert "Run focused pytest" in result.content


def test_bounded_editor_rejects_safety_delete(tmp_path):
    editor = BoundedSkillEditor(rejected_buffer=RejectedBuffer(tmp_path / "rejected.jsonl"))
    result = editor.apply(
        "## Safety\n\n- Human review required\n",
        [BoundedSkillEdit(operation="DELETE_SECTION", target="Safety")],
    )
    assert result.accepted is False
    assert result.rejected is True
