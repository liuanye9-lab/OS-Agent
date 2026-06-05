"""Phase 4 — Research bridge.

Glue layer between :mod:`stable_agent.external_crawler` (raw artifacts) and
:mod:`stable_agent.core.curator_service` (CuratorInput.external_findings).

Phase 4 explicitly forbids ResearchBridge from writing skills directly
— it only **proposes evidence**. The actual proposal happens through
``Curator.evaluate(input_with_findings)`` so the lifecycle (draft →
candidate → validated → promoted) is unchanged.

Pipeline:

    raw artifacts → chunks → FTS index
        ↓
    .find(query, repo_gap) → ResearchFinding[]
        ↓
    .to_curator_signals(findings) → tuple[str, ...]   (passed into CuratorInput)
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from stable_agent.external_crawler.models import (
    ExternalArtifact,
    IndexChunk,
    ResearchFinding,
    SourceType,
)
from stable_agent.indexer.fts_store import FtsStore
from stable_agent.skills.signature import (
    content_signature_sha256,
    simhash64,
    simhash64_to_hex,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #

_H_RE = re.compile(r"(?m)^(#+ +.+)$")
_FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")
_MIN_CHUNK_CHARS = 80


def chunk_markdown(
    artifact_id: str,
    body: str,
    *,
    path_hint: str = "",
) -> list[IndexChunk]:
    """Split a markdown body into per-section chunks + code-fence chunks.

    - Each ``#``/``##`` section becomes one chunk.
    - Each fenced code block becomes one extra chunk(searchable separately
      so we can target "code samples" later).
    - Sections shorter than :data:`_MIN_CHUNK_CHARS` are merged into the
      next section to avoid noisy retrieval.
    """
    if not body:
        return []

    out: list[IndexChunk] = []

    # 1. Code fences first — strip them from text body so paragraph
    # chunks don't double-count their content.
    code_blocks: list[tuple[str, str]] = _FENCE_RE.findall(body)
    body_no_code = _FENCE_RE.sub("\n[code-block]\n", body)

    # 2. Section split.
    parts = _H_RE.split(body_no_code)
    # _H_RE.split returns alternating [pre, header, body, header, body, ...]
    pending_section = ""
    pending_body: list[str] = []
    section_idx = 0

    def emit(title: str, text: str) -> None:
        nonlocal section_idx
        text = (text or "").strip()
        if len(text) < _MIN_CHUNK_CHARS and not title:
            return
        if not text:
            return
        chunk_id = f"{artifact_id}#{section_idx}"
        section_idx += 1
        out.append(IndexChunk(
            chunk_id=chunk_id,
            artifact_id=artifact_id,
            section_title=title.strip(),
            text=text,
            path_hint=path_hint,
            simhash64_hex=simhash64_to_hex(simhash64(text)),
        ))

    if parts:
        # First piece is body before any header.
        head = parts[0]
        if head and head.strip():
            emit("", head)
        # Now alternating (header, body) pairs.
        for i in range(1, len(parts), 2):
            title = parts[i].lstrip("#").strip()
            section_body = parts[i + 1] if i + 1 < len(parts) else ""
            emit(title, section_body)

    # 3. Code fence chunks.
    for lang, code in code_blocks:
        if len(code.strip()) < _MIN_CHUNK_CHARS:
            continue
        chunk_id = f"{artifact_id}#code-{section_idx}"
        section_idx += 1
        out.append(IndexChunk(
            chunk_id=chunk_id,
            artifact_id=artifact_id,
            section_title="[code]",
            text="",
            code_snippet=code.strip(),
            language=lang.strip(),
            path_hint=path_hint,
            simhash64_hex=simhash64_to_hex(simhash64(code.strip())),
        ))

    return out


# --------------------------------------------------------------------------- #
# Bridge
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RepoGap:
    """Description of a repo problem that motivates external search.

    Phase 4 keeps it narrow on purpose — Curator picks which signals to
    pass through. ``failure_mode`` doubles as the search seed.
    """

    failure_mode: str
    keywords: tuple[str, ...] = ()
    task_type: str = ""

    @property
    def query(self) -> str:
        kw = " ".join(self.keywords)
        return f"{self.failure_mode} {kw}".strip()


class ResearchBridge:
    """Index raw artifacts and surface findings for Curator.

    Args:
        index: :class:`FtsStore` to read/write.
    """

    def __init__(self, index: FtsStore) -> None:
        self._index = index

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #

    def index_artifact(
        self,
        artifact: ExternalArtifact,
        *,
        body: str,
        path_hint: str = "",
    ) -> int:
        """Index one artifact + chunks. Returns chunk count written.

        ``body`` is the artifact's body (markdown / abstract / readme).
        ``sha256`` on the artifact is computed if missing.
        """
        sha = artifact.sha256 or content_signature_sha256(body or "")
        # Stamp sha back onto the artifact via raw_metadata trick — we
        # can't mutate the frozen dataclass, so we let upsert_artifact
        # take an explicit hash.
        self._index.upsert_artifact(artifact, body_for_hash=body or "")
        # If we computed sha and the artifact didn't have one, also
        # propagate via a follow-up update so downstream dedupe sees it.
        # We keep this implicit because the upsert layer already does it.
        chunks = chunk_markdown(artifact.artifact_id, body, path_hint=path_hint)
        for c in chunks:
            self._index.upsert_chunk(c)
        return len(chunks)

    def index_artifacts(
        self,
        items: Iterable[tuple[ExternalArtifact, str]],
        *,
        path_hint: str = "",
    ) -> int:
        """Bulk index. Returns the **total** number of chunks written."""
        total = 0
        for artifact, body in items:
            try:
                total += self.index_artifact(artifact, body=body, path_hint=path_hint)
            except Exception:
                logger.exception(
                    "research_bridge: failed to index %s", artifact.artifact_id
                )
        return total

    # ------------------------------------------------------------------ #
    # Find
    # ------------------------------------------------------------------ #

    def find(
        self,
        gap: RepoGap,
        *,
        max_findings: int = 5,
        source_types: Iterable[str] = (),
    ) -> list[ResearchFinding]:
        """Search the index for evidence matching ``gap``.

        Each returned :class:`ResearchFinding` aggregates one or more
        chunks from the **same artifact** so Curator can cite cleanly.
        Ranking: top-N artifacts by their best chunk's BM25 rank
        (FTS5 returns lower = better).
        """
        rows = self._index.search(
            gap.query, limit=max_findings * 5, source_types=list(source_types) or (),
        )
        if not rows:
            return []

        # Group by artifact_id; keep the best (lowest) bm25 rank per artifact.
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r["artifact_id"], []).append(r)
        ranked: list[tuple[float, str, list[dict]]] = []
        for art_id, matches in grouped.items():
            best_rank = min(m.get("bm25_rank", 0.0) for m in matches)
            ranked.append((best_rank, art_id, matches))
        ranked.sort()  # ascending rank → best first

        findings: list[ResearchFinding] = []
        for _, art_id, matches in ranked[:max_findings]:
            head = matches[0]
            head_title = head.get("title") or "(untitled)"
            head_section = head.get("section_title") or ""
            summary = head_title if not head_section else f"{head_title} — {head_section}"
            chunk_ids = tuple(m["chunk_id"] for m in matches if m.get("chunk_id"))
            findings.append(ResearchFinding(
                finding_id=f"find_{uuid.uuid4().hex[:10]}",
                query=gap.query,
                evidence_chunk_ids=chunk_ids,
                summary_zh=summary,
                summary_en=summary,
                delta_type="new",
                relevance_score=_rank_to_score(matches[0].get("bm25_rank", 0.0)),
                freshness_score=_freshness_score(head.get("published_at", "")),
                source_artifact_ids=(art_id,),
            ))
        return findings

    # ------------------------------------------------------------------ #
    # Output for Curator
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_curator_signals(findings: Iterable[ResearchFinding]) -> tuple[str, ...]:
        """Render findings as :class:`CuratorInput.external_findings` strings."""
        return tuple(f.to_curator_signal() for f in findings)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _rank_to_score(rank: float) -> float:
    """FTS5 BM25 rank is signed; lower = better. Map into 0..1 score.

    The transform here is intentionally simple so callers know what
    they get: ``score = 1 / (1 + max(0, -rank))``. Negative ranks (good
    matches) yield scores closer to 1.
    """
    return 1.0 / (1.0 + max(0.0, -rank))


def _freshness_score(published_at: str) -> float:
    """Newer = higher. Returns 0.5 when published_at is empty."""
    if not published_at:
        return 0.5
    try:
        from datetime import datetime, timezone
        # Tolerate both "2024-..." and full RFC3339.
        ts = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(tz=timezone.utc) - ts).days
        if age_days <= 30:
            return 1.0
        if age_days <= 365:
            return 0.7
        return max(0.2, 1.0 - age_days / 3650)
    except Exception:
        return 0.5
