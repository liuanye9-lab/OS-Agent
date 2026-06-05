"""Phase 4 — ExternalCrawler / Indexer data models.

Three core entities:

  - :class:`ExternalArtifact` — one paper / release / README / issue thread
  - :class:`IndexChunk` — searchable fragment of an artifact
  - :class:`ResearchFinding` — Curator-/Validator-facing summary of relevant
    evidence; never modifies a skill directly

Phase 4 keeps these immutable (frozen dataclasses) so connectors → indexer
→ research bridge can pass values without worrying about hidden mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SourceType:
    """Tag values for :attr:`ExternalArtifact.source_type`."""

    GITHUB_REPO = "github_repo"
    GITHUB_RELEASE = "github_release"
    GITHUB_README = "github_readme"
    ARXIV_PAPER = "arxiv_paper"
    OPENREVIEW_SUBMISSION = "openreview_submission"
    HTML_DOC = "html_doc"  # generic fallback


@dataclass(frozen=True)
class ExternalArtifact:
    """One external resource — paper, release, README, issue, etc.

    ``canonical_url`` is the deduped form of the source URL after applying
    :func:`stable_agent.external_crawler.normalizers.canonicalize_url`.
    ``sha256`` is over the *body text* (not the URL) so we catch reposts
    of the same content under different URLs.

    ``trust_score`` is a Phase 4 stub (0.0–1.0). Phase 6 may grow it into
    something connector-aware (e.g. arXiv > random HTML).
    """

    artifact_id: str
    source_type: str
    canonical_url: str
    title: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    venue: str = ""
    published_at: str = ""  # ISO 8601 date or empty
    fetched_at: str = ""
    trust_score: float = 0.5
    sha256: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexChunk:
    """Searchable fragment of an :class:`ExternalArtifact`.

    For papers: typically one chunk per section (abstract / contributions
    / method). For READMEs / releases: one chunk per top-level header.

    ``language`` is set when ``code_snippet`` is the chunk content (e.g.
    a fenced block from a README); otherwise empty.
    """

    chunk_id: str
    artifact_id: str
    section_title: str
    text: str
    code_snippet: str = ""
    language: str = ""
    path_hint: str = ""
    simhash64_hex: str = ""


@dataclass(frozen=True)
class ResearchFinding:
    """Curator-facing summary of relevant evidence.

    Phase 4 explicitly forbids findings from directly modifying skills;
    they only become :attr:`CuratorInput.external_findings` strings the
    Curator can use as a learning signal.

    ``delta_type`` is one of ``new``, ``update``, ``contradiction`` —
    used by Phase 5 Observer to color-code research-driven candidates.
    """

    finding_id: str
    query: str
    evidence_chunk_ids: tuple[str, ...]
    summary_zh: str
    summary_en: str = ""
    delta_type: str = "new"
    relevance_score: float = 0.0
    freshness_score: float = 0.0
    source_artifact_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_curator_signal(self) -> str:
        """Render as a one-line string for ``CuratorInput.external_findings``."""
        head = self.summary_en or self.summary_zh
        cite = ",".join(self.source_artifact_ids[:2]) if self.source_artifact_ids else ""
        return f"[{self.delta_type}] {head} ({cite})" if cite else f"[{self.delta_type}] {head}"
