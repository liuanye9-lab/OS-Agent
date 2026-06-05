"""Phase 4 — HTTP fetcher Protocol + fixture-friendly defaults.

Connectors take a :class:`HttpFetcher` (just a callable) so tests inject
fakes and production injects a real urllib-backed client. The fetcher
returns one of two shapes:

  - bytes / str         → raw response body
  - dict / list         → parsed JSON

This is intentionally tiny — Phase 4 doesn't need a full requests/httpx
abstraction, and pulling in a new dep would violate the "no new deps"
rule from Phase 0+.

The default :class:`UrllibFetcher` enforces:

  - **strict-https only**: refuses http://
  - polite per-source rate limit (3 s for arXiv per their guidance)
  - bounded timeout (default 15 s)
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# arXiv API explicitly recommends ≥ 3s between calls
# (https://info.arxiv.org/help/api/tou.html).
ARXIV_RATE_LIMIT_SECONDS: float = 3.0


class HttpFetcher(Protocol):
    """Anything that can fetch ``url`` and return body / JSON.

    Implementations should:
      - raise on non-2xx
      - raise on timeout
      - return ``str`` / ``bytes`` for non-JSON, ``dict``/``list`` for JSON
    """

    def get(
        self,
        url: str,
        *,
        as_json: bool = False,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        ...


class UrllibFetcher:
    """Default urllib-backed fetcher. Production-safe.

    Args:
        rate_limit_per_host: minimum seconds between calls per host
            (overrides per-host defaults like arXiv's 3s only when
            explicitly set; arXiv host falls back to ``ARXIV_RATE_LIMIT_SECONDS``).
        user_agent: User-Agent string sent with every request.
    """

    def __init__(
        self,
        *,
        rate_limit_per_host: dict[str, float] | None = None,
        user_agent: str = "OS-Agent-Phase4/1.0 (+https://github.com/liuanye9-lab/OS-Agent)",
    ) -> None:
        self._user_agent = user_agent
        self._last_call_at: dict[str, float] = {}
        defaults = {"export.arxiv.org": ARXIV_RATE_LIMIT_SECONDS}
        if rate_limit_per_host:
            defaults.update(rate_limit_per_host)
        self._rate_limits = defaults

    def get(
        self,
        url: str,
        *,
        as_json: bool = False,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        if not url.lower().startswith("https://"):
            raise ValueError(f"refused non-https URL: {url}")

        host = urllib.parse.urlparse(url).netloc.lower()
        self._honor_rate_limit(host)

        merged_headers = {"User-Agent": self._user_agent}
        if headers:
            merged_headers.update(headers)

        req = urllib.request.Request(url, headers=merged_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} on {url}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise FetchError(f"URL error for {url}: {exc.reason}") from exc

        self._last_call_at[host] = time.monotonic()
        if as_json:
            return json.loads(body.decode("utf-8"))
        return body.decode("utf-8", errors="replace")

    def _honor_rate_limit(self, host: str) -> None:
        delay = self._rate_limits.get(host, 0.0)
        if delay <= 0:
            return
        last = self._last_call_at.get(host, 0.0)
        wait = (last + delay) - time.monotonic()
        if wait > 0:
            time.sleep(wait)


class FetchError(RuntimeError):
    """Raised on any HTTP / URL-level failure inside a connector."""


# --------------------------------------------------------------------------- #
# Fixture-friendly fakes — explicitly named so production code can't import
# them by accident expecting "the" fetcher.
# --------------------------------------------------------------------------- #

class StubFetcher:
    """In-memory fixture fetcher for tests.

    Map ``url → response`` ahead of time, and the fetcher returns it
    verbatim. Unknown URLs raise :class:`FetchError`.
    """

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self._responses = dict(responses or {})
        self.calls: list[tuple[str, bool]] = []

    def add(self, url: str, response: Any) -> None:
        self._responses[url] = response

    def get(
        self,
        url: str,
        *,
        as_json: bool = False,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        self.calls.append((url, as_json))
        if url not in self._responses:
            raise FetchError(f"StubFetcher: no response registered for {url!r}")
        body = self._responses[url]
        if as_json:
            if isinstance(body, (dict, list)):
                return body
            return json.loads(body) if isinstance(body, str) else body
        return body
