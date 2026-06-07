from stable_agent.self_iteration.sandbox_runner import SandboxRunner


def test_sandbox_blocks_auto_merge_or_push():
    result = SandboxRunner().run(["git", "push"], timeout=1)
    assert result.ok is False
    assert "forbidden" in result.stderr_tail
