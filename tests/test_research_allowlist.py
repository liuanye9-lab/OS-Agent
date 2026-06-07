from stable_agent.research.allowlist import is_allowed_url


def test_research_allowlist_blocks_unknown_domains():
    assert is_allowed_url("https://arxiv.org/abs/1234.5678") is True
    assert is_allowed_url("https://evil.example.com/paper") is False
