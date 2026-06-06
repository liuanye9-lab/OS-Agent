import pytest

from stable_agent.memory_evidence.memory_candidate import activate_candidate, create_memory_candidate
from stable_agent.memory_evidence.models import MemoryCandidate


def test_no_evidence_cannot_be_active():
    candidate = create_memory_candidate("用户偏好: 先审计")
    with pytest.raises(ValueError):
        activate_candidate(candidate)


def test_evidence_refs_allow_activation():
    candidate = create_memory_candidate("用户偏好: 先审计", evidence_refs=["run_1"])
    active = activate_candidate(candidate)
    assert active.status == "active"
    assert active.evidence_refs == ["run_1"]


def test_private_text_is_sanitized():
    candidate = MemoryCandidate.create(
        content_summary="email a@example.com id 123-45-6789",
        source_type="user_feedback",
        source_ref="ref 123-45-6789",
        evidence_refs=[],
    )
    assert "a@example.com" not in candidate.content_summary
    assert "123-45-6789" not in candidate.content_summary
    assert "123-45-6789" not in candidate.source_ref
