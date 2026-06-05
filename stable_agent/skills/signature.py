"""Phase 2 SkillRepo v2 — content signatures (sha256 + simhash64).

Two-layer dedupe primitive:

  - ``content_signature_sha256`` — strict exact-equality. Used to reject
    re-submission of an identical skill body.
  - ``simhash64`` — locality-sensitive 64-bit hash. Used to flag
    near-duplicates whose Hamming distance is small (roadmap recommends
    ``≤ 3`` triggers a duplicate review).

Canonicalization rules (must match :func:`canonicalize`):

  1. Whitespace inside each section is collapsed to single spaces.
  2. Sections are joined with the literal sentinel ``\\n---\\n``.
  3. ``retrieval_tags`` are lowercased, stripped, deduped, sorted, then
     joined with ``,``.
  4. Empty inputs collapse to empty strings — *not* dropped — so absence
     remains semantically distinct from presence.

Why locally implemented (no third-party simhash dep): the algorithm is
~30 lines, the upstream libraries vary in tokenizer + bit width, and we
want bit-stable signatures across Python versions. We use ``blake2b``
with 8-byte digests for the per-token hash.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

# Public sentinel — exposed so tests can build the same canonical string.
SECTION_SEPARATOR: str = "\n---\n"

# Word tokenizer: alnum runs ≥ 2 chars. Punctuation is dropped because
# it adds noise without semantic content for skill text.
_WORD_RE = re.compile(r"[\w]{2,}", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    """Collapse whitespace and strip; preserve case (case-sensitive bodies)."""
    return _WS_RE.sub(" ", (text or "").strip())


def _normalize_tags(tags: Iterable[str]) -> str:
    """Lowercase, strip, dedupe, sort, comma-join."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in tags or ():
        t = raw.strip().lower()
        if t and t not in seen:
            seen.add(t)
            cleaned.append(t)
    cleaned.sort()
    return ",".join(cleaned)


def canonicalize(
    intent: str,
    procedure: str,
    guardrails: str,
    retrieval_tags: Iterable[str] = (),
) -> str:
    """Build the canonical signature string for a skill.

    The four parts are *positionally* concatenated with
    :data:`SECTION_SEPARATOR` between them. Reordering inputs to
    :func:`canonicalize` is a contract break — same with renaming any
    section here — because it would invalidate all stored signatures.
    """
    parts = [
        _normalize_text(intent),
        _normalize_text(procedure),
        _normalize_text(guardrails),
        _normalize_tags(retrieval_tags),
    ]
    return SECTION_SEPARATOR.join(parts)


def content_signature_sha256(canonical: str) -> str:
    """Hex-encoded SHA-256 of the canonical string (64 hex chars)."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _token_hash64(token: str) -> int:
    """Stable 64-bit hash of a token via blake2b-8byte digest."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def simhash64(canonical: str) -> int:
    """Compute a 64-bit simhash over the canonical string.

    Algorithm: tokenize → hash each token to 64 bits → for each bit
    position accumulate +1 (bit set) or -1 (bit clear) → final bit is 1
    iff the accumulator is positive.

    Returns 0 for empty input (a degenerate but stable value; callers
    should treat ``simhash64("") == simhash64("")`` as a true match,
    which it is).
    """
    tokens = _WORD_RE.findall(canonical)
    if not tokens:
        return 0
    bits = [0] * 64
    for tok in tokens:
        h = _token_hash64(tok)
        for i in range(64):
            if (h >> i) & 1:
                bits[i] += 1
            else:
                bits[i] -= 1
    out = 0
    for i in range(64):
        if bits[i] > 0:
            out |= (1 << i)
    return out


def hamming64(a: int, b: int) -> int:
    """Hamming distance between two 64-bit ints (popcount of XOR)."""
    return (a ^ b).bit_count()


def simhash64_to_hex(value: int) -> str:
    """Render simhash64 as zero-padded 16-char lowercase hex string.

    Frontmatter stores hex (not int) so YAML round-trips don't cast it
    to an exotic numeric type.
    """
    return f"{value & 0xFFFFFFFFFFFFFFFF:016x}"


def simhash64_from_hex(text: str) -> int:
    """Inverse of :func:`simhash64_to_hex`. Empty / malformed → ``0``."""
    if not text:
        return 0
    try:
        return int(text, 16) & 0xFFFFFFFFFFFFFFFF
    except ValueError:
        return 0
