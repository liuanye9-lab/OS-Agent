"""GitHub research watcher."""

from __future__ import annotations

import re

from stable_agent.external_crawler.fetcher import UrllibFetcher
from stable_agent.external_crawler.github_connector import GitHubConnector, GitHubRepoRef
from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.finding_extractor import extract_claims, modules_for_claims, proposed_changes_for_claims


class GitHubWatcher:
    def __init__(self, fetcher: UrllibFetcher | None = None) -> None:
        self.fetcher = fetcher or UrllibFetcher()

    def scan(self, query: str, *, max_results: int = 3) -> list[ResearchEvidenceCard]:
        repo = _extract_repo_slug(query)
        if not repo:
            return [ResearchEvidenceCard.create(
                source_type="github",
                source_url=f"https://github.com/search?q={query.replace(' ', '+')}",
                title=f"GitHub search evidence: {query}",
                claims=["GitHub search query captured as evidence-only card."],
                evidence_summary="A GitHub search needs human triage before becoming a candidate change.",
                applicable_modules=["stable_agent.research"],
                risks=["search_result_not_validated"],
                proposed_changes=["Pick an allowlisted repo, then fetch README or releases for evidence."],
            )]

        connector = GitHubConnector(self.fetcher)
        cards: list[ResearchEvidenceCard] = []
        try:
            readme = connector.fetch_readme(GitHubRepoRef.parse(repo))
            if readme:
                body = str(readme.raw_metadata.get("body", ""))
                claims = extract_claims(body)
                cards.append(ResearchEvidenceCard.create(
                    source_type="github",
                    source_url=readme.canonical_url,
                    title=readme.title,
                    claims=claims,
                    evidence_summary=body[:500],
                    applicable_modules=modules_for_claims(claims),
                    risks=["external repo is evidence only"],
                    proposed_changes=proposed_changes_for_claims(claims),
                ))
        except Exception as exc:
            cards.append(ResearchEvidenceCard.create(
                source_type="github",
                source_url=f"https://github.com/{repo}",
                title=f"GitHub scan fallback: {repo}",
                claims=[f"GitHub fetch failed: {exc}"],
                evidence_summary="Fallback card only; no memory or skill promotion.",
                applicable_modules=["stable_agent.research"],
                risks=["network_unavailable", "evidence_only"],
                proposed_changes=["Retry with authenticated GitHub access if needed."],
            ))
        return cards[:max_results]


def _extract_repo_slug(query: str) -> str:
    match = re.search(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", query or "")
    return match.group(1) if match else ""
