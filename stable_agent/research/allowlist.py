"""Allowlist for external research sources."""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_DOMAINS = {
    "arxiv.org",
    "export.arxiv.org",
    "github.com",
    "api.github.com",
    "docs.python.org",
    "platform.openai.com",
    "docs.anthropic.com",
}


def is_allowed_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)
