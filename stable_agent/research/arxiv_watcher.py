"""arXiv research watcher."""

from __future__ import annotations

from stable_agent.external_crawler.arxiv_connector import ArxivConnector
from stable_agent.external_crawler.fetcher import FetchError, UrllibFetcher
from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.finding_extractor import extract_claims, modules_for_claims, proposed_changes_for_claims


class ArxivWatcher:
    def __init__(self, fetcher: UrllibFetcher | None = None) -> None:
        self.fetcher = fetcher or UrllibFetcher(rate_limit_per_host={"export.arxiv.org": 0.0})

    def scan(self, query: str, *, max_results: int = 3) -> list[ResearchEvidenceCard]:
        try:
            artifacts = ArxivConnector(self.fetcher).search(query, max_results=max_results)
        except Exception as exc:
            return [ResearchEvidenceCard.create(
                source_type="arxiv",
                source_url="https://arxiv.org/search/",
                title=f"arXiv scan fallback: {query}",
                claims=[f"arXiv scan could not fetch live results: {exc}"],
                evidence_summary="Fallback evidence card created without promoting memory or skill.",
                applicable_modules=["stable_agent.research"],
                risks=["network_unavailable", "evidence_only"],
                proposed_changes=["Retry scan later; do not promote from fallback card."],
            )]

        cards: list[ResearchEvidenceCard] = []
        for artifact in artifacts[:max_results]:
            summary = str(artifact.raw_metadata.get("summary", ""))
            claims = extract_claims(summary)
            cards.append(ResearchEvidenceCard.create(
                source_type="arxiv",
                source_url=artifact.canonical_url,
                title=artifact.title,
                claims=claims,
                evidence_summary=summary[:500],
                applicable_modules=modules_for_claims(claims),
                risks=["external paper is evidence only", "requires validation before candidate"],
                proposed_changes=proposed_changes_for_claims(claims),
            ))
        return cards
