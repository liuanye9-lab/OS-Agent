"""Phase 4 — GitHub connector.

Implements two endpoints from the GitHub REST API v3:

  - ``GET /repos/{owner}/{repo}/releases`` — release metadata + notes
  - ``GET /repos/{owner}/{repo}/readme`` — README in raw form

GitHub-Contents-API caveat (per the official docs): a directory listing
is capped at 1000 entries, and the recommended way to walk a large repo
recursively is the Trees API. Phase 4 sticks to the two endpoints above
because they cover the OS-Agent research use case (latest release notes,
README highlights). Trees API is left as a Phase 6 follow-up.

All HTTP goes through :class:`HttpFetcher` so tests can inject
:class:`StubFetcher` and run completely offline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from stable_agent.external_crawler.fetcher import FetchError, HttpFetcher
from stable_agent.external_crawler.models import ExternalArtifact, SourceType
from stable_agent.external_crawler.normalizers import canonicalize_url

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_HTML_BASE = "https://github.com"

# Spec-stable artifact_id prefixes.
_ARTIFACT_RELEASE = "gh_release"
_ARTIFACT_README = "gh_readme"


@dataclass(frozen=True)
class GitHubRepoRef:
    """Lightweight ``owner/repo[@ref]`` pointer."""

    owner: str
    repo: str
    ref: str = ""  # branch / tag / sha — empty = default branch

    @classmethod
    def parse(cls, slug: str) -> "GitHubRepoRef":
        """Parse ``owner/repo`` or ``owner/repo@ref``."""
        if not slug or "/" not in slug:
            raise ValueError(f"invalid github slug: {slug!r}")
        ref = ""
        body = slug
        if "@" in slug:
            body, ref = slug.split("@", 1)
        owner, repo = body.split("/", 1)
        if not owner or not repo:
            raise ValueError(f"invalid github slug: {slug!r}")
        return cls(owner=owner, repo=repo, ref=ref)


class GitHubConnector:
    """Fetch release notes + README from a public GitHub repo.

    Args:
        fetcher: any :class:`HttpFetcher`. Default behavior is unauthenticated
            (sufficient for public repos); pass a fetcher that injects an
            ``Authorization`` header to use a token.
        token: optional PAT — convenience shortcut, fetcher header takes
            precedence if both are present.
    """

    def __init__(
        self,
        fetcher: HttpFetcher,
        *,
        token: str | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._token = token

    def list_releases(
        self,
        repo: GitHubRepoRef,
        *,
        per_page: int = 10,
    ) -> list[ExternalArtifact]:
        """Return ``per_page`` newest releases as :class:`ExternalArtifact`.

        Uses ``GET /repos/{owner}/{repo}/releases`` (sorted newest first
        by GitHub's default).
        """
        url = (
            f"{GITHUB_API_BASE}/repos/{repo.owner}/{repo.repo}/releases"
            f"?per_page={int(per_page)}"
        )
        body = self._fetch_json(url)
        if not isinstance(body, list):
            raise FetchError(f"unexpected releases payload for {repo.owner}/{repo.repo}")

        out: list[ExternalArtifact] = []
        for r in body:
            if not isinstance(r, dict):
                continue
            tag = r.get("tag_name") or ""
            html_url = r.get("html_url") or f"{GITHUB_HTML_BASE}/{repo.owner}/{repo.repo}/releases/tag/{tag}"
            published = r.get("published_at") or r.get("created_at") or ""
            artifact_id = f"{_ARTIFACT_RELEASE}:{repo.owner}/{repo.repo}@{tag}" if tag else f"{_ARTIFACT_RELEASE}:{repo.owner}/{repo.repo}"
            title = r.get("name") or tag or "(unnamed release)"
            out.append(ExternalArtifact(
                artifact_id=artifact_id,
                source_type=SourceType.GITHUB_RELEASE,
                canonical_url=canonicalize_url(html_url),
                title=title,
                authors=(r.get("author", {}).get("login", ""),) if r.get("author") else (),
                venue=f"github:{repo.owner}/{repo.repo}",
                published_at=published,
                fetched_at=_now_iso(),
                trust_score=0.7,  # official repo releases are higher-trust
                raw_metadata={
                    "body": r.get("body") or "",
                    "tag_name": tag,
                    "draft": bool(r.get("draft")),
                    "prerelease": bool(r.get("prerelease")),
                },
            ))
        return out

    def fetch_readme(self, repo: GitHubRepoRef) -> ExternalArtifact | None:
        """Return the repo README as a single :class:`ExternalArtifact`.

        Uses ``GET /repos/{owner}/{repo}/readme`` with the
        ``application/vnd.github.raw`` accept header.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo.owner}/{repo.repo}/readme"
        if repo.ref:
            url += f"?ref={repo.ref}"

        try:
            body = self._fetch_text(
                url,
                headers={"Accept": "application/vnd.github.raw"},
            )
        except FetchError as exc:
            logger.info("README fetch failed for %s/%s: %s", repo.owner, repo.repo, exc)
            return None

        title = _extract_first_h1(body) or f"{repo.owner}/{repo.repo} README"
        artifact_id = f"{_ARTIFACT_README}:{repo.owner}/{repo.repo}"
        if repo.ref:
            artifact_id += f"@{repo.ref}"
        html_url = f"{GITHUB_HTML_BASE}/{repo.owner}/{repo.repo}#readme"
        return ExternalArtifact(
            artifact_id=artifact_id,
            source_type=SourceType.GITHUB_README,
            canonical_url=canonicalize_url(html_url),
            title=title,
            venue=f"github:{repo.owner}/{repo.repo}",
            fetched_at=_now_iso(),
            trust_score=0.6,
            raw_metadata={"body": body, "ref": repo.ref},
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if extra:
            h.update(extra)
        return h

    def _fetch_json(self, url: str) -> Any:
        return self._fetcher.get(url, as_json=True, headers=self._build_headers())

    def _fetch_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        return self._fetcher.get(url, as_json=False, headers=self._build_headers(headers))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_H1_RE = re.compile(r"^#\s+(?P<title>[^\n]+)", re.MULTILINE)


def _extract_first_h1(text: str) -> str:
    m = _H1_RE.search(text or "")
    return m.group("title").strip() if m else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
