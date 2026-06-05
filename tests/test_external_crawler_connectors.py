"""Phase 4 — connector contract tests.

All three connectors are tested with :class:`StubFetcher` injection
so the suite runs **completely offline**. The test responses are
captured from real API shapes (trimmed) so a future API drift will
flip these tests, not silently swallow it.
"""

from __future__ import annotations

import json

import pytest

from stable_agent.external_crawler import (
    ArxivConnector,
    GitHubConnector,
    GitHubRepoRef,
    OpenReviewConnector,
    SourceType,
    StubFetcher,
    canonicalize_url,
)
from stable_agent.external_crawler.fetcher import FetchError


# --------------------------------------------------------------------------- #
# arXiv
# --------------------------------------------------------------------------- #

ARXIV_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2026-05-30T12:00:00Z</updated>
    <published>2026-05-15T00:00:00Z</published>
    <title>SkillOpt: Held-Out Validation for Skill Curators</title>
    <summary>We propose a held-out validation harness for skill editing
    in agent systems. By rejecting edits that fail on N=5 holdout
    cases we measurably reduce regression rate.</summary>
    <author><name>Alice Researcher</name></author>
    <author><name>Bob Thinker</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2401.12345v2"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.99999v1</id>
    <updated>2026-04-01T00:00:00Z</updated>
    <published>2026-04-01T00:00:00Z</published>
    <title>Unrelated Paper Title</title>
    <summary>Lorem ipsum dolor sit amet.</summary>
    <author><name>Carol Bystander</name></author>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2402.99999v1"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG"/>
  </entry>
</feed>
"""


def test_arxiv_search_parses_atom_feed():
    fetcher = StubFetcher()
    fetcher.add(
        "https://export.arxiv.org/api/query"
        "?search_query=all%3Askill+optimization&start=0&max_results=10"
        "&sortBy=submittedDate&sortOrder=descending",
        ARXIV_FIXTURE,
    )

    conn = ArxivConnector(fetcher)
    arts = conn.search("skill optimization")
    assert len(arts) == 2

    head = arts[0]
    assert head.source_type == SourceType.ARXIV_PAPER
    assert head.title.startswith("SkillOpt")
    assert "Alice Researcher" in head.authors
    assert head.canonical_url.endswith("/abs/2401.12345"), (
        f"version stripping failed: {head.canonical_url}"
    )
    assert head.venue == "cs.AI"
    assert head.trust_score >= 0.8


def test_arxiv_empty_query_returns_empty_list():
    conn = ArxivConnector(StubFetcher())
    assert conn.search("") == []
    assert conn.search("   ") == []


def test_arxiv_handles_malformed_xml():
    fetcher = StubFetcher()
    fetcher.add(
        "https://export.arxiv.org/api/query"
        "?search_query=all%3Atest&start=0&max_results=10"
        "&sortBy=submittedDate&sortOrder=descending",
        "<not></valid>",
    )
    conn = ArxivConnector(fetcher)
    with pytest.raises(FetchError):
        conn.search("test")


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #

def test_github_releases_parsed():
    fetcher = StubFetcher()
    fetcher.add(
        "https://api.github.com/repos/anthropics/anthropic-sdk-python/releases?per_page=2",
        json.dumps([
            {
                "tag_name": "v0.40.0",
                "name": "v0.40.0 — Streaming improvements",
                "html_url": "https://github.com/anthropics/anthropic-sdk-python/releases/tag/v0.40.0",
                "published_at": "2026-05-30T00:00:00Z",
                "body": "## Highlights\n- New streaming API\n- Bug fixes",
                "draft": False,
                "prerelease": False,
                "author": {"login": "octobot"},
            },
            {
                "tag_name": "v0.39.0",
                "name": "v0.39.0",
                "html_url": "https://github.com/anthropics/anthropic-sdk-python/releases/tag/v0.39.0",
                "published_at": "2026-05-01T00:00:00Z",
                "body": "Older release.",
                "draft": False,
                "prerelease": False,
                "author": {"login": "octobot"},
            },
        ]),
    )

    conn = GitHubConnector(fetcher)
    repo = GitHubRepoRef.parse("anthropics/anthropic-sdk-python")
    rels = conn.list_releases(repo, per_page=2)

    assert len(rels) == 2
    head = rels[0]
    assert head.source_type == SourceType.GITHUB_RELEASE
    assert "v0.40.0" in head.artifact_id
    assert head.title.startswith("v0.40.0")
    assert "Streaming" in head.raw_metadata["body"] or head.raw_metadata.get("body")


def test_github_readme_parsed():
    fetcher = StubFetcher()
    fetcher.add(
        "https://api.github.com/repos/foo/bar/readme",
        "# Foo Bar\n\nSome documentation.",
    )

    conn = GitHubConnector(fetcher)
    art = conn.fetch_readme(GitHubRepoRef.parse("foo/bar"))

    assert art is not None
    assert art.source_type == SourceType.GITHUB_README
    assert art.title == "Foo Bar"
    assert art.raw_metadata["body"].startswith("# Foo Bar")


def test_github_readme_returns_none_on_404():
    """README endpoint failure should not raise — caller treats as missing."""
    fetcher = StubFetcher()  # no responses registered
    conn = GitHubConnector(fetcher)
    art = conn.fetch_readme(GitHubRepoRef.parse("ghost/repo"))
    assert art is None


def test_github_repo_ref_parser_validates_input():
    with pytest.raises(ValueError):
        GitHubRepoRef.parse("missing-slash")
    with pytest.raises(ValueError):
        GitHubRepoRef.parse("/empty-owner")
    ref = GitHubRepoRef.parse("foo/bar@feature-x")
    assert ref.owner == "foo" and ref.repo == "bar" and ref.ref == "feature-x"


# --------------------------------------------------------------------------- #
# OpenReview
# --------------------------------------------------------------------------- #

def test_openreview_search_parses_v2_response():
    fetcher = StubFetcher()
    payload = {
        "notes": [
            {
                "id": "abc123",
                "cdate": 1717200000000,  # ~2024-06-01 — but used to test parser
                "content": {
                    "title": {"value": "Skill State Optimization"},
                    "abstract": {"value": "We propose ..."},
                    "authors": {"value": ["Dana", "Eve"]},
                    "venue": {"value": "ICLR 2026 Conference"},
                },
            }
        ]
    }
    fetcher.add(
        "https://api2.openreview.net/notes/search?term=skill+optimization&limit=5&offset=0",
        json.dumps(payload),
    )

    conn = OpenReviewConnector(fetcher)
    arts = conn.search("skill optimization", max_results=5)
    assert len(arts) == 1
    head = arts[0]
    assert head.title == "Skill State Optimization"
    assert head.authors == ("Dana", "Eve")
    assert head.venue == "ICLR 2026 Conference"
    assert "openreview" in head.canonical_url


def test_openreview_handles_bare_content_values():
    """API v2 sometimes returns bare strings instead of {"value": ...}."""
    fetcher = StubFetcher()
    fetcher.add(
        "https://api2.openreview.net/notes/search?term=x&limit=10&offset=0",
        json.dumps({"notes": [{
            "id": "n1",
            "cdate": 0,
            "content": {
                "title": "Bare Title",
                "abstract": "raw abstract",
                "authors": ["Alice"],
            },
        }]}),
    )
    conn = OpenReviewConnector(fetcher)
    arts = conn.search("x")
    assert arts[0].title == "Bare Title"
    assert arts[0].authors == ("Alice",)


# --------------------------------------------------------------------------- #
# URL canonicalization
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw, expected", [
    ("HTTPS://Arxiv.org/abs/2401.12345v3?utm_source=tw",
     "https://arxiv.org/abs/2401.12345"),
    ("https://arxiv.org/pdf/2401.12345v2.pdf",
     "https://arxiv.org/abs/2401.12345"),
    ("https://github.com/foo/bar/",
     "https://github.com/foo/bar"),
    ("http://example.com/page#fragment",
     "https://example.com/page"),
    ("javascript:alert(1)", ""),  # rejected
    ("not-a-url", ""),
    ("", ""),
])
def test_canonicalize_url_collapses_known_variants(raw, expected):
    assert canonicalize_url(raw) == expected
