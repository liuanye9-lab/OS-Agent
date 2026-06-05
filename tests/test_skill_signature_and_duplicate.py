"""Phase 2 — SkillRepo v2 signature + duplicate detection.

Three layers:

  1. SHA-256 of canonical body — *exact* dedupe (PK + UNIQUE constraint).
  2. simhash64 / Hamming distance — near-dedupe; threshold 3 by default.
  3. Lifecycle: same signature is allowed only inside the same
     (skill_id, version) slot.

This file pins:

  - canonical sigantures are stable across whitespace / tag-order tweaks
    that should be considered "the same skill"
  - DIFFERENT bodies do NOT collide
  - duplicate-rejection on cross-skill signature collision
  - near-duplicate detection actually returns near misses, not exact ones
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stable_agent.skills.signature import (
    canonicalize,
    content_signature_sha256,
    hamming64,
    simhash64,
    simhash64_from_hex,
    simhash64_to_hex,
)
from stable_agent.skills.repository import (
    DuplicateSkillError,
    SkillRepository,
)
from stable_agent.skills import (
    Metrics,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
    Triggers,
)


# --------------------------------------------------------------------------- #
# canonicalize() — order, whitespace, tag-order invariants
# --------------------------------------------------------------------------- #

def test_canonicalize_collapses_whitespace():
    a = canonicalize(
        intent="Compress context  safely",
        procedure="Drop noise.",
        guardrails="Keep paths.",
        retrieval_tags=("context",),
    )
    b = canonicalize(
        intent="Compress\tcontext\nsafely",
        procedure="Drop noise.",  # NBSP is whitespace.
        guardrails="Keep   paths.",
        retrieval_tags=("context",),
    )
    assert a == b, "whitespace differences must canonicalize to the same string"


def test_canonicalize_tag_order_invariant():
    a = canonicalize("i", "p", "g", retrieval_tags=("alpha", "beta", "gamma"))
    b = canonicalize("i", "p", "g", retrieval_tags=("gamma", "alpha", "beta"))
    c = canonicalize("i", "p", "g", retrieval_tags=("beta", "ALPHA", "Gamma"))
    assert a == b == c, "retrieval_tags ordering / case must not matter"


def test_canonicalize_section_order_NOT_invariant():
    """Reordering inputs to canonicalize() *must* change the signature.

    This is intentional: section position carries semantic meaning
    (intent vs procedure vs guardrails). If it didn't, a malicious tag
    swap could collide with an unrelated skill.
    """
    a = canonicalize("a", "b", "c")
    b = canonicalize("c", "b", "a")
    assert a != b


def test_canonicalize_empty_inputs_collapse_to_separators():
    """Empty inputs are preserved (not dropped) so absence stays distinct."""
    out = canonicalize("", "", "", ())
    # Three sections + tag-list = three separators.
    assert out.count("\n---\n") == 3


# --------------------------------------------------------------------------- #
# SHA-256 signatures
# --------------------------------------------------------------------------- #

def test_content_signature_sha256_is_64_hex():
    sig = content_signature_sha256(canonicalize("a", "b", "c"))
    assert len(sig) == 64
    int(sig, 16)  # valid hex


def test_content_signature_changes_on_content_change():
    sig1 = content_signature_sha256(canonicalize("a", "b", "c"))
    sig2 = content_signature_sha256(canonicalize("a", "b", "c2"))
    assert sig1 != sig2


# --------------------------------------------------------------------------- #
# simhash64 — basic stability
# --------------------------------------------------------------------------- #

def test_simhash64_identical_inputs_match():
    s = canonicalize("compress safely", "drop noise", "keep paths", ("context",))
    assert simhash64(s) == simhash64(s)


def test_simhash64_close_inputs_have_low_distance():
    """Adding ~1 sentence should not blow the Hamming distance past 16."""
    base = canonicalize(
        intent="Compress context safely while keeping cited paths intact.",
        procedure="Step 1: identify protected items. Step 2: drop noise.",
        guardrails="Never drop user-cited file paths.",
        retrieval_tags=("context", "compression"),
    )
    near = canonicalize(
        intent="Compress context safely while keeping cited paths intact, then verify.",
        procedure="Step 1: identify protected items. Step 2: drop noise.",
        guardrails="Never drop user-cited file paths.",
        retrieval_tags=("context", "compression"),
    )
    distance = hamming64(simhash64(base), simhash64(near))
    assert 0 < distance <= 16, (
        f"close inputs should have low Hamming distance; got {distance}"
    )


def test_simhash64_distant_inputs_have_high_distance():
    a = canonicalize(
        "Compress context safely.",
        "Drop noise.",
        "Keep paths.",
        ("context", "compression"),
    )
    b = canonicalize(
        "Cook a beef stew tonight.",
        "Brown the meat first.",
        "Don't burn the onions.",
        ("recipe", "stew"),
    )
    distance = hamming64(simhash64(a), simhash64(b))
    # 64-bit simhash on unrelated inputs typically lands >= 20.
    assert distance >= 12, (
        f"unrelated inputs should be far apart; got distance={distance}"
    )


def test_simhash64_hex_round_trip():
    s = canonicalize("alpha", "beta", "gamma", ("x",))
    h = simhash64(s)
    hx = simhash64_to_hex(h)
    assert len(hx) == 16
    assert simhash64_from_hex(hx) == h


def test_simhash64_from_hex_tolerates_garbage():
    assert simhash64_from_hex("") == 0
    assert simhash64_from_hex("not-hex") == 0


# --------------------------------------------------------------------------- #
# Repository — duplicate enforcement
# --------------------------------------------------------------------------- #

def _make_minimal(skill_id: str, version: int = 1, intent: str = "i", procedure: str = "p", guardrails: str = "g") -> SkillDocument:
    fm = SkillFrontmatter(
        skill_id=skill_id, version=version, status=SkillStatus.DRAFT,
        retrieval_tags=("x",), task_types=("t",),
        triggers=Triggers(), metrics=Metrics(),
    )
    return SkillDocument(
        frontmatter=fm,
        sections={
            "Intent": intent,
            "Procedure": procedure,
            "Guardrails": guardrails,
        },
    )


def test_repository_rejects_cross_skill_signature_collision(tmp_path: Path):
    repo = SkillRepository(root=tmp_path)
    repo.write(_make_minimal("sk_a"))
    # Same body → same signature → owned by sk_a → sk_b should be rejected.
    with pytest.raises(DuplicateSkillError):
        repo.write(_make_minimal("sk_b"))


def test_repository_allows_same_slot_rewrite(tmp_path: Path):
    """(skill_id, version) is the natural slot — re-writing it is fine."""
    repo = SkillRepository(root=tmp_path)
    first = repo.write(_make_minimal("sk_a", version=1))
    again = repo.write(_make_minimal("sk_a", version=1))
    assert first.frontmatter.signature_sha256 == again.frontmatter.signature_sha256


def test_repository_finds_near_duplicates(tmp_path: Path):
    repo = SkillRepository(root=tmp_path)
    repo.write(_make_minimal(
        "sk_base",
        intent="Compress context safely while keeping cited paths intact.",
        procedure="Step 1: identify protected items. Step 2: drop noise.",
        guardrails="Never drop user-cited file paths.",
    ))

    # Almost-the-same skill — should show up as near-duplicate.
    candidate = _make_minimal(
        "sk_candidate",
        intent="Compress context safely while keeping cited paths intact, then verify.",
        procedure="Step 1: identify protected items. Step 2: drop noise.",
        guardrails="Never drop user-cited file paths.",
    )

    near = repo.find_near_duplicates(candidate, threshold=20)
    near_ids = {r["skill_id"] for r in near}
    assert "sk_base" in near_ids
    # Should NOT find itself (candidate isn't written yet — list excludes
    # exact matches anyway).
    assert "sk_candidate" not in near_ids


def test_repository_near_duplicates_excludes_exact(tmp_path: Path):
    repo = SkillRepository(root=tmp_path)
    sk = _make_minimal("sk_base")
    repo.write(sk)
    near = repo.find_near_duplicates(sk, threshold=3)
    # Exact-match (same canonical) is excluded — only true *near* hits.
    assert all(r["skill_id"] != "sk_base" for r in near)
