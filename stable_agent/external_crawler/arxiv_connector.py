"""Phase 4 — arXiv connector.

Wraps the official arXiv query API:

    GET https://export.arxiv.org/api/query
        ?search_query=all:<query>
        &start=<offset>
        &max_results=<n>

Returns Atom XML which we parse with stdlib ``xml.etree.ElementTree``
(no ``feedparser`` dep — staying within Phase 0's "no new deps" rule).

Per arXiv API ToU we honor a 3s rate limit; that's enforced at the
:class:`UrllibFetcher` layer via ``ARXIV_RATE_LIMIT_SECONDS`` so individual
connectors don't have to remember.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from stable_agent.external_crawler.fetcher import FetchError, HttpFetcher
from stable_agent.external_crawler.models import ExternalArtifact, SourceType
from stable_agent.external_crawler.normalizers import canonicalize_url

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# arXiv ID matchers — we want the canonical YYMM.NNNNN form.
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


class ArxivConnector:
    """Search arXiv by free-text query, return :class:`ExternalArtifact` rows.

    Args:
        fetcher: any :class:`HttpFetcher`. Production should pass
            :class:`UrllibFetcher` so the 3-second rate limit applies.
    """

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        start: int = 0,
    ) -> list[ExternalArtifact]:
        """Search ``query`` and return parsed artifacts (newest first).

        ``query`` is sent as ``search_query=all:<query>``. Phase 4 keeps
        it simple — power users can pass arXiv's boolean operators
        (``ti:``, ``au:``, etc.) directly inside ``query``.
        """
        if not query or not query.strip():
            return []

        params = {
            "search_query": f"all:{query.strip()}",
            "start": str(int(start)),
            "max_results": str(int(max_results)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"
        body = self._fetcher.get(url, as_json=False, timeout=20.0)
        return self._parse_atom(body if isinstance(body, str) else body.decode("utf-8", "replace"))

    # ------------------------------------------------------------------ #
    # Parser
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_atom(xml_text: str) -> list[ExternalArtifact]:
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise FetchError(f"arxiv: malformed atom feed: {exc}") from exc

        out: list[ExternalArtifact] = []
        for entry in root.findall(f"{_ATOM_NS}entry"):
            arxiv_id = _text(entry, f"{_ATOM_NS}id")
            arxiv_id_short = ""
            m = _ARXIV_ID_RE.search(arxiv_id)
            if m:
                arxiv_id_short = m.group(1)
            title = _normalize_ws(_text(entry, f"{_ATOM_NS}title"))
            summary = _normalize_ws(_text(entry, f"{_ATOM_NS}summary"))
            published = _text(entry, f"{_ATOM_NS}published")
            html_url = ""
            for link in entry.findall(f"{_ATOM_NS}link"):
                rel = link.attrib.get("rel", "")
                href = link.attrib.get("href", "")
                if rel == "alternate" and href:
                    html_url = href
                    break
            if not html_url and arxiv_id_short:
                html_url = f"https://arxiv.org/abs/{arxiv_id_short}"

            authors = tuple(
                _text(a, f"{_ATOM_NS}name")
                for a in entry.findall(f"{_ATOM_NS}author")
                if _text(a, f"{_ATOM_NS}name")
            )
            primary_cat = ""
            cat_el = entry.find(f"{_ARXIV_NS}primary_category")
            if cat_el is not None:
                primary_cat = cat_el.attrib.get("term", "")

            artifact_id = f"arxiv:{arxiv_id_short}" if arxiv_id_short else f"arxiv:raw:{arxiv_id}"
            out.append(ExternalArtifact(
                artifact_id=artifact_id,
                source_type=SourceType.ARXIV_PAPER,
                canonical_url=canonicalize_url(html_url),
                title=title,
                authors=authors,
                venue=primary_cat,
                published_at=published or "",
                fetched_at=_now_iso(),
                trust_score=0.85,  # peer-review-adjacent
                raw_metadata={
                    "summary": summary,
                    "primary_category": primary_cat,
                    "arxiv_id": arxiv_id_short,
                },
            ))
        return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    found = el.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
