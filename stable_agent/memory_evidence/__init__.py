"""Evidence-gated memory layer."""

from stable_agent.memory_evidence.conflict_detector import ConflictDetector
from stable_agent.memory_evidence.decay_policy import DecayPolicy
from stable_agent.memory_evidence.evidence_store import EvidenceStore
from stable_agent.memory_evidence.hit_report import build_memory_hit_report
from stable_agent.memory_evidence.memory_candidate import (
    activate_candidate,
    create_memory_candidate,
)
from stable_agent.memory_evidence.models import MemoryCandidate, MemoryHitReport

__all__ = [
    "ConflictDetector",
    "DecayPolicy",
    "EvidenceStore",
    "MemoryCandidate",
    "MemoryHitReport",
    "activate_candidate",
    "build_memory_hit_report",
    "create_memory_candidate",
]
