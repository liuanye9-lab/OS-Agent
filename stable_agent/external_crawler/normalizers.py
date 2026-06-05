"""Phase 4 — URL canonicalization + content normalization.

Three-layer dedupe:

  1. **canonical_url**: same paper served at v1 / v2 / abs / pdf paths
     should map to one URL.
  2. **sha256(body)**: catches reposts under different URLs.
  3. **simhash64**: catches near-duplicates (translations, minor edits).

This module owns layer 1. Layer 2/3 reuse :mod:`stable_agent.skills.signature`
(``content_signature_sha256`` / ``simhash64``) so we have one well-tested
hash everywhere.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# Tracking params we always strip to keep canonical URLs stable.
_STRIP_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_src",  # twitter / x.com style
    "ab", "context",   # arxiv context tracking
})

# arXiv version suffix matcher: /abs/2401.12345v3 → /abs/2401.12345
_ARXIV_VERSION_RE = re.compile(r"^(/abs/[0-9]+\.[0-9]+)v[0-9]+$")
_ARXIV_PDF_RE = re.compile(r"^(/pdf/[0-9]+\.[0-9]+)(?:v[0-9]+)?(?:\.pdf)?$")


def canonicalize_url(url: str) -> str:
    """Normalize a URL so cosmetically-different forms collapse to one.

    Rules:
      1. lowercase scheme + host
      2. strip default ports
      3. strip tracking params (utm_*, ref, etc.)
      4. drop URL fragments
      5. arXiv: ``/abs/X.Yv3`` → ``/abs/X.Y``; ``/pdf/X.Y.pdf`` → ``/abs/X.Y``
      6. GitHub: trailing slash removed
      7. GitHub blob URLs:
         ``/owner/repo/blob/main/path`` keeps the form (path matters)

    Returns empty string for unparseable input.
    """
    if not url or not isinstance(url, str):
        return ""

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return ""

    if not parsed.scheme or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return ""
    # Always upgrade to https for canonicalization (mirrors GitHub / arxiv default).
    scheme = "https"

    netloc = parsed.netloc.lower()
    # Strip default ports.
    if netloc.endswith(":80") or netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]

    path = parsed.path or ""
    # arXiv version → abstract canonical form.
    if "arxiv.org" in netloc:
        m = _ARXIV_VERSION_RE.match(path)
        if m:
            path = m.group(1)
        m2 = _ARXIV_PDF_RE.match(path)
        if m2:
            # /pdf/X.Y(.pdf|v3) → /abs/X.Y so paper-as-pdf and paper-as-abs match.
            path = m2.group(1).replace("/pdf/", "/abs/", 1)
    # Trailing slash removal (preserve root "/" as-is).
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter tracking params; sort for stability.
    if parsed.query:
        kept = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in _STRIP_PARAMS
        ]
        kept.sort()
        query = urlencode(kept)
    else:
        query = ""

    # Drop fragment; preserve params (rarely used).
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace; trim. Used before hashing artifact bodies."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()
