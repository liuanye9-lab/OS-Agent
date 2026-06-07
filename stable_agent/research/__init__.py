"""Research watcher for evidence-only external findings."""

from stable_agent.research.arxiv_watcher import ArxivWatcher
from stable_agent.research.evidence_card import ResearchEvidenceCard
from stable_agent.research.github_watcher import GitHubWatcher
from stable_agent.research.proposal_builder import ProposalBuilder

__all__ = ["ArxivWatcher", "GitHubWatcher", "ProposalBuilder", "ResearchEvidenceCard"]
