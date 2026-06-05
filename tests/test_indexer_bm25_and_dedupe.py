"""Phase 4 — Indexer + ResearchBridge contract tests.

Two layers:

  - :class:`FtsStore` — BM25 + sha256/simhash dedupe
  - :class:`ResearchBridge` — chunking, indexing, finding → CuratorInput signal

Tests use ``:memory:`` SQLite + StubFetcher so the suite runs offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from stable_agent.external_crawler import (
    ExternalArtifact,
    SourceType,
    canonicalize_url,
)
from stable_agent.indexer.fts_store import FtsStore
from stable_agent.research_bridge import RepoGap, ResearchBridge, chunk_markdown
from stable_agent.skills.signature import (
    content_signature_sha256,
    simhash64,
    simhash64_to_hex,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_artifact(
    artifact_id: str,
    *,
    canonical_url: str,
    title: str,
    body: str,
    source_type: str = SourceType.ARXIV_PAPER,
) -> tuple[ExternalArtifact, str]:
    art = ExternalArtifact(
        artifact_id=artifact_id,
        source_type=source_type,
        canonical_url=canonical_url,
        title=title,
        fetched_at=_now_iso(),
        sha256=content_signature_sha256(body),
    )
    return art, body


@pytest.fixture
def store() -> FtsStore:
    return FtsStore(":memory:")


@pytest.fixture
def bridge(store: FtsStore) -> ResearchBridge:
    return ResearchBridge(store)


# --------------------------------------------------------------------------- #
# 1. FtsStore basics
# --------------------------------------------------------------------------- #

def test_fts_store_upsert_and_get(store: FtsStore):
    art, body = _make_artifact(
        "arxiv:2401.12345",
        canonical_url="https://arxiv.org/abs/2401.12345",
        title="Skill Optimization",
        body="abstract body",
    )
    written = store.upsert_artifact(art, body_for_hash=body)
    assert written == "arxiv:2401.12345"
    assert store.count_artifacts() == 1

    row = store.get_artifact("arxiv:2401.12345")
    assert row is not None
    assert row["title"] == "Skill Optimization"


def test_fts_store_dedupes_by_canonical_url(store: FtsStore):
    body_a = "abstract one"
    body_b = "abstract two — different content but same URL"
    art_a, _ = _make_artifact(
        "arxiv:dup", canonical_url="https://arxiv.org/abs/2401.0001",
        title="Old Title", body=body_a,
    )
    art_b, _ = _make_artifact(
        "arxiv:other_id", canonical_url="https://arxiv.org/abs/2401.0001",
        title="New Title", body=body_b,
    )
    store.upsert_artifact(art_a, body_for_hash=body_a)
    written = store.upsert_artifact(art_b, body_for_hash=body_b)
    # URL collision → kept original artifact_id, updated mutable fields.
    assert written == "arxiv:dup"
    assert store.count_artifacts() == 1
    row = store.get_artifact("arxiv:dup")
    assert row["title"] == "New Title"


def test_fts_store_search_returns_bm25_ranked(store: FtsStore, bridge: ResearchBridge):
    art1, body1 = _make_artifact(
        "arxiv:a", canonical_url="https://arxiv.org/abs/a.1",
        title="Skill optimization with held-out validation",
        body="# Abstract\nWe propose held-out validation for skill editing in agent systems.",
    )
    art2, body2 = _make_artifact(
        "arxiv:b", canonical_url="https://arxiv.org/abs/b.1",
        title="Cooking recipes for stew",
        body="# Abstract\nWe present recipes for beef stew.",
    )
    bridge.index_artifact(art1, body=body1)
    bridge.index_artifact(art2, body=body2)

    rows = store.search("skill validation", limit=5)
    assert rows
    # Top hit should be arxiv:a, not arxiv:b.
    assert rows[0]["artifact_id"] == "arxiv:a", (
        f"BM25 ranking broken — got {rows[0]['artifact_id']} on top"
    )


# --------------------------------------------------------------------------- #
# 2. Dedupe — sha256 + simhash
# --------------------------------------------------------------------------- #

def test_fts_store_finds_exact_duplicate_by_sha256(store: FtsStore):
    body = "exact match body"
    art, _ = _make_artifact(
        "arxiv:exact", canonical_url="https://arxiv.org/abs/exact.1",
        title="Exact", body=body,
    )
    store.upsert_artifact(art, body_for_hash=body)

    sha = content_signature_sha256(body)
    dups = store.find_duplicates(sha256=sha)
    assert dups
    assert dups[0]["match_type"] == "sha256"
    assert dups[0]["artifact_id"] == "arxiv:exact"


def test_fts_store_finds_near_duplicate_by_simhash(
    store: FtsStore, bridge: ResearchBridge,
):
    """Two papers with near-identical wording should hit the simhash threshold."""
    body_a = (
        "We propose held-out validation for skill editing in agent systems. "
        "By rejecting edits that fail on holdout cases we reduce regression rate."
    )
    body_b = (
        "We propose held-out validation for skill editing in agent systems. "
        "By rejecting edits that fail on N=5 holdout cases we reduce regression rate, "
        "with one extra clarifying sentence appended."
    )
    art_a, _ = _make_artifact(
        "arxiv:close_a", canonical_url="https://arxiv.org/abs/close_a.1",
        title="Paper A", body=body_a,
    )
    art_b, _ = _make_artifact(
        "arxiv:close_b", canonical_url="https://arxiv.org/abs/close_b.1",
        title="Paper B", body=body_b,
    )
    bridge.index_artifact(art_a, body=body_a)
    bridge.index_artifact(art_b, body=body_b)

    sim_a = simhash64_to_hex(simhash64(body_a))
    near = store.find_duplicates(simhash_hex=sim_a, threshold=20)
    art_ids = {row["artifact_id"] for row in near}
    assert "arxiv:close_b" in art_ids


# --------------------------------------------------------------------------- #
# 3. Chunking
# --------------------------------------------------------------------------- #

def test_chunk_markdown_emits_per_section_chunks():
    body = (
        "# Title\n"
        "Intro paragraph that is more than eighty characters long so it survives the minimum chunk filter.\n\n"
        "## Section One\n"
        "Body for section one. Long enough to survive the minimum chunk filter — eighty plus chars here.\n\n"
        "## Section Two\n"
        "Body for section two. Long enough too to survive minimum chunk filter, definitely more than 80.\n"
    )
    chunks = chunk_markdown("artifact:1", body)
    titles = [c.section_title for c in chunks]
    assert "Title" in titles
    assert "Section One" in titles
    assert "Section Two" in titles


def test_chunk_markdown_extracts_code_fences_separately():
    body = (
        "# Setup\n"
        "Plain text discussion that goes long enough to survive the minimum chunk size filter please.\n\n"
        "```python\n"
        "def hello():\n"
        "    print('hi')\n"
        "    return 42  # extra line so we beat the 80-char chunk filter inside the fence\n"
        "```\n"
    )
    chunks = chunk_markdown("artifact:2", body)
    code_chunks = [c for c in chunks if c.code_snippet]
    assert code_chunks, "code fence should produce its own chunk"
    assert code_chunks[0].language == "python"
    assert "def hello" in code_chunks[0].code_snippet


# --------------------------------------------------------------------------- #
# 4. ResearchBridge — find findings + Curator signal
# --------------------------------------------------------------------------- #

def test_research_bridge_find_returns_relevant_findings(bridge: ResearchBridge):
    art_a, body_a = _make_artifact(
        "arxiv:relevant", canonical_url="https://arxiv.org/abs/rel.1",
        title="Held-out validation for skill curators",
        body="# Method\nWe use held-out validation to reject regressing skills in agent systems.",
    )
    art_b, body_b = _make_artifact(
        "arxiv:noise", canonical_url="https://arxiv.org/abs/noise.1",
        title="Cooking recipes",
        body="# Recipe\nBrown the beef and add onions for stew.",
    )
    bridge.index_artifact(art_a, body=body_a)
    bridge.index_artifact(art_b, body=body_b)

    findings = bridge.find(RepoGap(
        failure_mode="missing_validation",
        keywords=("held-out", "skill"),
    ))
    assert findings
    assert findings[0].source_artifact_ids[0] == "arxiv:relevant"


def test_research_bridge_to_curator_signals(bridge: ResearchBridge):
    art, body = _make_artifact(
        "arxiv:cite",
        canonical_url="https://arxiv.org/abs/cite.1",
        title="Citation paper",
        body="# Method\nWe present a held-out validation scheme for skill optimization.",
    )
    bridge.index_artifact(art, body=body)

    findings = bridge.find(RepoGap(
        failure_mode="missing_validation",
        keywords=("held-out", "skill"),
    ))
    signals = ResearchBridge.to_curator_signals(findings)
    assert signals
    assert "[new]" in signals[0]
    assert "arxiv:cite" in signals[0]


def test_research_bridge_does_not_modify_skills(bridge: ResearchBridge):
    """Phase 4 invariant: bridge only proposes, never writes a skill."""
    # Bridge has no SkillRepo dependency. Just assert by signature.
    assert not hasattr(bridge, "_repo")
    assert not hasattr(bridge, "skill_repository")


def test_research_bridge_find_empty_query_returns_empty(bridge: ResearchBridge):
    findings = bridge.find(RepoGap(failure_mode=""))
    assert findings == []
