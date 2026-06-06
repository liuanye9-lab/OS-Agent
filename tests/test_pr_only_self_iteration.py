from stable_agent.self_iteration.patch_planner import PatchPlanner
from stable_agent.self_iteration.pr_prompt_builder import PRPromptBuilder
from stable_agent.self_iteration.proposal import SelfIterationProposal


def test_self_iteration_stops_at_human_review():
    proposal = SelfIterationProposal.create(source_type="failed_run", source_ref="run_1", objective_zh="改进失败路径")
    plan = PatchPlanner().plan(proposal)
    prompt = PRPromptBuilder().build(plan)
    assert proposal.status == "ready_for_human_review"
    assert "Do not merge" in prompt
    assert "deploy" in " ".join(plan.forbidden_actions)
