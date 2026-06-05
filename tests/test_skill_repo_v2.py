"""Phase 2 — SkillRepo v2 file + index orchestration tests.

Pinned behavior:

  - markdown round-trip is loss-less for known sections
  - SQLite index stays in sync with disk artifacts
  - default search returns **only** promoted skills
  - lifecycle transitions are enforced
  - ``best_skill.md`` is derived, not the source of truth
  - candidate writes do NOT clobber ``best_skill.md``

Tests use a per-test ``tmp_path`` so the live ``skills/`` tree on disk
stays untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stable_agent.skills import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    SkillTransitionError,
    Triggers,
)
from stable_agent.skills.repository import (
    DuplicateSkillError,
    SkillNotFoundError,
    SkillRepository,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_skill(
    skill_id: str = "sk_demo",
    version: int = 1,
    status: SkillStatus = SkillStatus.DRAFT,
    intent: str = "Help the agent compress context safely.",
    procedure: str = "Step 1: identify protected items.\nStep 2: drop noise.",
    guardrails: str = "Never drop user-cited file paths.",
    retrieval_tags: tuple[str, ...] = ("context", "compression"),
    last_validation_score: float = 0.0,
    validations: int = 0,
) -> SkillDocument:
    fm = SkillFrontmatter(
        skill_id=skill_id,
        version=version,
        status=status,
        domain="coding",
        owner="curator_v1",
        retrieval_tags=retrieval_tags,
        task_types=("coding_task",),
        triggers=Triggers(
            must_contain=("context",),
            should_contain=("compression",),
            must_avoid=("chitchat",),
        ),
        metrics=Metrics(
            validations=validations,
            last_validation_score=last_validation_score,
        ),
        risk_level="low",
    )
    return SkillDocument(
        frontmatter=fm,
        sections={
            "Intent": intent,
            "Procedure": procedure,
            "Guardrails": guardrails,
            "Positive examples": "When user pastes a long log, keep paths.",
            "Negative examples": "Don't drop the asked file path.",
            "Patch history": "v1: initial draft.",
        },
    )


@pytest.fixture
def repo(tmp_path: Path) -> SkillRepository:
    best = tmp_path / "skills" / "best_skill.md"
    return SkillRepository(root=tmp_path, best_skill_path=best)


# --------------------------------------------------------------------------- #
# 1. Round-trip + signature
# --------------------------------------------------------------------------- #

def test_write_creates_artifact_on_disk(repo: SkillRepository, tmp_path: Path):
    skill = _make_skill()
    written = repo.write(skill)

    artifact = tmp_path / "skills" / "repo" / "sk_demo" / "v1.md"
    assert artifact.exists()

    content = artifact.read_text(encoding="utf-8")
    assert content.startswith("---\n")  # frontmatter fence
    assert "skill_id: sk_demo" in content
    assert "# Intent" in content

    # Signature must be populated by write().
    assert written.frontmatter.signature_sha256
    assert len(written.frontmatter.signature_sha256) == 64
    assert written.frontmatter.simhash64
    assert len(written.frontmatter.simhash64) == 16


def test_write_then_get_round_trip(repo: SkillRepository):
    skill = _make_skill()
    written = repo.write(skill)

    loaded = repo.get("sk_demo", 1)
    assert loaded.frontmatter.skill_id == written.frontmatter.skill_id
    assert loaded.frontmatter.signature_sha256 == written.frontmatter.signature_sha256
    assert loaded.section("Intent") == skill.section("Intent")
    assert loaded.section("Procedure") == skill.section("Procedure")
    assert loaded.section("Patch history") == skill.section("Patch history")


def test_get_unknown_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.get("sk_does_not_exist", 1)


# --------------------------------------------------------------------------- #
# 2. Index sync
# --------------------------------------------------------------------------- #

def test_index_count_tracks_writes(repo: SkillRepository):
    assert repo.index.count() == 0
    repo.write(_make_skill())
    assert repo.index.count() == 1
    repo.write(_make_skill(version=2, intent="A different intent."))
    assert repo.index.count() == 2


def test_index_get_returns_latest_when_version_omitted(repo: SkillRepository):
    repo.write(_make_skill(version=1))
    repo.write(_make_skill(version=2, intent="Second draft different intent."))
    row = repo.index.get("sk_demo")
    assert row is not None
    assert row["version"] == 2


# --------------------------------------------------------------------------- #
# 3. Lifecycle
# --------------------------------------------------------------------------- #

def test_lifecycle_legal_path_to_promoted(repo: SkillRepository):
    repo.write(_make_skill())
    repo.transition_status("sk_demo", 1, SkillStatus.CANDIDATE)
    repo.transition_status("sk_demo", 1, SkillStatus.VALIDATED)
    promoted = repo.transition_status("sk_demo", 1, SkillStatus.PROMOTED)
    assert promoted.frontmatter.status == SkillStatus.PROMOTED


def test_lifecycle_illegal_skip_raises(repo: SkillRepository):
    repo.write(_make_skill())
    # draft → promoted (skipping candidate / validated) is illegal.
    with pytest.raises(SkillTransitionError):
        repo.transition_status("sk_demo", 1, SkillStatus.PROMOTED)


def test_lifecycle_archived_is_terminal(repo: SkillRepository):
    repo.write(_make_skill())
    repo.transition_status("sk_demo", 1, SkillStatus.CANDIDATE)
    repo.transition_status("sk_demo", 1, SkillStatus.VALIDATED)
    repo.transition_status("sk_demo", 1, SkillStatus.PROMOTED)
    repo.transition_status("sk_demo", 1, SkillStatus.DEPRECATED)
    repo.transition_status("sk_demo", 1, SkillStatus.ARCHIVED)
    with pytest.raises(SkillTransitionError):
        repo.transition_status("sk_demo", 1, SkillStatus.PROMOTED)


# --------------------------------------------------------------------------- #
# 4. Search — promoted-only by default
# --------------------------------------------------------------------------- #

def test_search_default_excludes_non_promoted(repo: SkillRepository):
    repo.write(_make_skill(skill_id="sk_a", intent="alpha context"))
    # sk_b is candidate, must NOT appear in default search.
    repo.write(_make_skill(skill_id="sk_b", intent="beta context"))
    repo.transition_status("sk_b", 1, SkillStatus.CANDIDATE)

    rows = repo.search("context")
    names = {r["skill_id"] for r in rows}
    assert "sk_b" not in names, "candidate skill leaked into default search"


def test_search_include_all_statuses_returns_drafts(repo: SkillRepository):
    repo.write(_make_skill(skill_id="sk_a", intent="alpha context"))
    rows = repo.search("alpha", include_all_statuses=True)
    assert any(r["skill_id"] == "sk_a" for r in rows)


def test_search_promoted_finds_promoted(repo: SkillRepository):
    repo.write(_make_skill(skill_id="sk_a", intent="alpha context"))
    repo.transition_status("sk_a", 1, SkillStatus.CANDIDATE)
    repo.transition_status("sk_a", 1, SkillStatus.VALIDATED)
    repo.transition_status("sk_a", 1, SkillStatus.PROMOTED)

    rows = repo.search("alpha")
    assert any(r["skill_id"] == "sk_a" for r in rows)


# --------------------------------------------------------------------------- #
# 5. best_skill.md export
# --------------------------------------------------------------------------- #

def test_candidate_write_does_not_touch_best_skill_md(
    repo: SkillRepository, tmp_path: Path,
):
    """Candidates must NOT auto-publish — Phase 0 contract invariant."""
    repo.write(_make_skill())
    repo.transition_status("sk_demo", 1, SkillStatus.CANDIDATE)
    best = tmp_path / "skills" / "best_skill.md"
    assert not best.exists(), (
        "candidate write created best_skill.md — Phase 2 contract break"
    )


def test_export_best_skill_emits_promoted_only(
    repo: SkillRepository, tmp_path: Path,
):
    repo.write(_make_skill(skill_id="sk_promoted", intent="promoted intent"))
    repo.transition_status("sk_promoted", 1, SkillStatus.CANDIDATE)
    repo.transition_status("sk_promoted", 1, SkillStatus.VALIDATED)
    repo.transition_status("sk_promoted", 1, SkillStatus.PROMOTED)

    repo.write(_make_skill(skill_id="sk_candidate", intent="candidate intent"))
    repo.transition_status("sk_candidate", 1, SkillStatus.CANDIDATE)

    out = repo.export_best_skill()
    assert out is not None
    text = out.read_text(encoding="utf-8")

    assert "sk_promoted" in text
    assert "sk_candidate" not in text


def test_export_best_skill_empty_when_nothing_promoted(
    repo: SkillRepository, tmp_path: Path,
):
    repo.write(_make_skill(skill_id="sk_a"))
    out = repo.export_best_skill()
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "no promoted skills" in text


# --------------------------------------------------------------------------- #
# 6. list_promoted
# --------------------------------------------------------------------------- #

def test_list_promoted_returns_only_promoted(repo: SkillRepository):
    repo.write(_make_skill(skill_id="sk_a", intent="alpha-only intent"))  # draft
    repo.write(_make_skill(skill_id="sk_b", intent="beta-only intent"))
    repo.transition_status("sk_b", 1, SkillStatus.CANDIDATE)
    repo.transition_status("sk_b", 1, SkillStatus.VALIDATED)
    repo.transition_status("sk_b", 1, SkillStatus.PROMOTED)

    promoted = repo.list_promoted()
    assert len(promoted) == 1
    assert promoted[0].skill_id == "sk_b"
    assert promoted[0].status == SkillStatus.PROMOTED
