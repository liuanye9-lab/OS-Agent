"""Phase 4 — OpenReview connector (API v2).

OpenReview deprecated v1 in favor of v2 (``https://api2.openreview.net``).
Phase 4 only needs keyword search, which API v2 exposes via:

    GET https://api2.openreview.net/notes/search
        ?term=<query>
        &limit=<n>
        &offset=<o>

The response is JSON. Phase 4 doesn't try to be clever about venue / year
filtering — Curator/ResearchBridge can filter post-hoc on
:attr:`ExternalArtifact.venue` if needed.
"""

from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from stable_agent.external_crawler.fetcher import FetchError, HttpFetcher
from stable_agent.external_crawler.models import ExternalArtifact, SourceType
from stable_agent.external_crawler.normalizers import canonicalize_url

logger = logging.getLogger(__name__)

OPENREVIEW_API_BASE = "https://api2.openreview.net"
OPENREVIEW_HTML_BASE = "https://openreview.net"


class OpenReviewConnector:
    """Search OpenReview by free-text query, return :class:`ExternalArtifact`s."""

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        offset: int = 0,
    ) -> list[ExternalArtifact]:
        if not query or not query.strip():
            return []
        params = {
            "term": query.strip(),
            "limit": str(int(max_results)),
            "offset": str(int(offset)),
        }
        url = f"{OPENREVIEW_API_BASE}/notes/search?{urllib.parse.urlencode(params)}"
        body = self._fetcher.get(url, as_json=True, timeout=20.0)

        notes = body.get("notes", []) if isinstance(body, dict) else []
        if not isinstance(notes, list):
            raise FetchError(f"openreview: unexpected notes payload type: {type(notes)}")

        out: list[ExternalArtifact] = []
        for note in notes:
            if not isinstance(note, dict):
                continue
            note_id = note.get("id") or ""
            content = note.get("content") or {}

            title = _content_value(content, "title")
            abstract = _content_value(content, "abstract")
            authors_raw = _content_value(content, "authors")
            authors = tuple(authors_raw) if isinstance(authors_raw, list) else ()
            venue = _content_value(content, "venue") or _content_value(content, "venueid")

            published_at = ""
            ts_ms = note.get("cdate")  # creation date in ms
            if isinstance(ts_ms, (int, float)) and ts_ms > 0:
                published_at = datetime.fromtimestamp(
                    ts_ms / 1000, tz=timezone.utc,
                ).strftime("%Y-%m-%dT%H:%M:%SZ")

            html_url = f"{OPENREVIEW_HTML_BASE}/forum?id={note_id}" if note_id else ""

            out.append(ExternalArtifact(
                artifact_id=f"openreview:{note_id}" if note_id else "openreview:unknown",
                source_type=SourceType.OPENREVIEW_SUBMISSION,
                canonical_url=canonicalize_url(html_url),
                title=title or "(untitled openreview note)",
                authors=authors,
                venue=str(venue) if venue else "",
                published_at=published_at,
                fetched_at=_now_iso(),
                trust_score=0.75,  # peer-review platform
                raw_metadata={
                    "abstract": abstract,
                    "openreview_id": note_id,
                },
            ))
        return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _content_value(content: dict[str, Any], key: str) -> Any:
    """OpenReview API v2 wraps each field in ``{"value": ...}``.

    We tolerate both wrapped (``{"value": "x"}``) and bare (``"x"``)
    forms because some endpoints return raw values.
    """
    raw = content.get(key)
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value", "")
    return raw if raw is not None else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
