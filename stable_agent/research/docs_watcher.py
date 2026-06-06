"""Official documentation watcher."""

from __future__ import annotations

from stable_agent.external_crawler.fetcher import UrllibFetcher
from stable_agent.research.allowlist import is_allowed_url
from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.finding_extractor import extract_claims, modules_for_claims, proposed_changes_for_claims


class DocsWatcher:
    def __init__(self, fetcher: UrllibFetcher | None = None) -> None:
        self.fetcher = fetcher or UrllibFetcher()

    def scan(self, url: str, *, max_results: int = 1) -> list[ResearchEvidenceCard]:
        if not is_allowed_url(url):
            return [ResearchEvidenceCard.create(
                source_type="docs",
                source_url=url,
                title="Blocked documentation source",
                claims=["URL is not in the official-docs allowlist."],
                evidence_summary="Blocked by allowlist; no candidate created.",
                applicable_modules=["stable_agent.research"],
                risks=["source_not_allowlisted"],
                proposed_changes=["Add source to allowlist only after human review."],
                status="rejected",
            )]
        try:
            body = self.fetcher.get(url, as_json=False, timeout=10.0)
        except Exception as exc:
            body = f"Fetch failed: {exc}"
        claims = extract_claims(str(body))
        return [ResearchEvidenceCard.create(
            source_type="docs",
            source_url=url,
            title=f"Documentation evidence: {url}",
            claims=claims[:max_results],
            evidence_summary=str(body)[:500],
            applicable_modules=modules_for_claims(claims),
            risks=["official docs still require implementation review"],
            proposed_changes=proposed_changes_for_claims(claims),
        )]
