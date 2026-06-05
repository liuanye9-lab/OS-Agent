"""Phase 4 — public API for the ExternalCrawler subsystem.

Re-exports the three connectors, the data models, and the fetcher layer.
The Indexer + ResearchBridge live in their own packages because they are
orthogonal — see :mod:`stable_agent.indexer` and
:mod:`stable_agent.research_bridge`.

Roadmap step §4 explicitly requires that no test depends on real network;
all connector tests must inject :class:`StubFetcher`.
"""

from stable_agent.external_crawler.arxiv_connector import ArxivConnector
from stable_agent.external_crawler.fetcher import (
    ARXIV_RATE_LIMIT_SECONDS,
    FetchError,
    HttpFetcher,
    StubFetcher,
    UrllibFetcher,
)
from stable_agent.external_crawler.github_connector import (
    GitHubConnector,
    GitHubRepoRef,
)
from stable_agent.external_crawler.models import (
    ExternalArtifact,
    IndexChunk,
    ResearchFinding,
    SourceType,
)
from stable_agent.external_crawler.normalizers import (
    canonicalize_url,
    collapse_whitespace,
)
from stable_agent.external_crawler.openreview_connector import (
    OpenReviewConnector,
)

__all__ = [
    "ARXIV_RATE_LIMIT_SECONDS",
    "ArxivConnector",
    "ExternalArtifact",
    "FetchError",
    "GitHubConnector",
    "GitHubRepoRef",
    "HttpFetcher",
    "IndexChunk",
    "OpenReviewConnector",
    "ResearchFinding",
    "SourceType",
    "StubFetcher",
    "UrllibFetcher",
    "canonicalize_url",
    "collapse_whitespace",
]
