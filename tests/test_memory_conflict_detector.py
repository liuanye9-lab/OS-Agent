from stable_agent.memory_evidence.conflict_detector import ConflictDetector
from stable_agent.memory_evidence.memory_candidate import create_memory_candidate


def test_conflict_detector_finds_opposite_preferences():
    left = create_memory_candidate("必须小范围修改", evidence_refs=["r1"])
    right = create_memory_candidate("不要小范围修改", evidence_refs=["r2"])

    conflicts = ConflictDetector().detect([left, right])

    assert len(conflicts) == 1
    assert conflicts[0]["left"] == left.memory_id
