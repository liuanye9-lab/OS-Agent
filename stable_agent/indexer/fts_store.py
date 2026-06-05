"""Phase 4 — ExternalArtifact / IndexChunk SQLite FTS5 store.

Same SQLite-FTS5 pattern as :mod:`stable_agent.skills.index_store`, but
on a separate file so external research and skill indexing don't share
a schema. Three operations matter:

  - :meth:`upsert_artifact` — insert/update one artifact
  - :meth:`upsert_chunk`     — index one searchable chunk
  - :meth:`search`           — BM25 over chunk text
  - :meth:`find_duplicates`  — strict (sha256) + near (simhash)

Dedupe contracts:

  - **canonical_url**: UNIQUE; second insertion of the same URL replaces.
  - **sha256(body)**:  UNIQUE; cross-URL collision rejected.
  - **simhash64**:     soft check via :meth:`find_duplicates`.

Phase 4 keeps the schema deliberately separate from
``stable_agent/skills/index.sqlite`` to avoid coupling the two indexes.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from stable_agent.external_crawler.models import ExternalArtifact, IndexChunk
from stable_agent.skills.signature import (
    content_signature_sha256,
    hamming64,
    simhash64,
    simhash64_from_hex,
    simhash64_to_hex,
)


# Word matcher for FTS5 query construction. Splits on non-alphanumeric so
# ``held-out`` becomes ``["held", "out"]`` (FTS5 reserves ``-`` as a NOT
# operator; ``"`` opens a phrase). Tokens shorter than 2 chars are dropped
# because BM25 noise floor exceeds their signal in our chunk sizes.
import re as _re_for_fts
_FTS_WORD_RE = _re_for_fts.compile(r"[A-Za-z0-9_]{2,}", _re_for_fts.UNICODE)


def _build_fts_match(query: str) -> str:
    """Turn user-facing free text into a safe FTS5 ``MATCH`` expression.

    Tokenization:
      - Split on non-alphanumeric so ``held-out`` becomes
        ``["held", "out"]`` (FTS5 reserves ``-`` as NOT, ``"`` opens a
        phrase).
      - Tokens shorter than 2 chars are dropped (BM25 noise floor).
      - Each token wrapped in double quotes individually so users can't
        smuggle FTS5 boolean operators in.
      - Tokens joined with explicit ``OR`` so partial matches still
        rank — FTS5's default is AND, which makes BM25 ranking
        useless when one keyword is absent.

    Returns empty string when there are no usable tokens.
    """
    tokens = _FTS_WORD_RE.findall(query or "")
    if not tokens:
        return ""
    quoted = []
    for tok in tokens:
        safe = tok.replace('"', '""')
        quoted.append(f'"{safe}"')
    return " OR ".join(quoted)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id     TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL,
    canonical_url   TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    authors_csv     TEXT NOT NULL DEFAULT '',
    venue           TEXT NOT NULL DEFAULT '',
    published_at    TEXT NOT NULL DEFAULT '',
    fetched_at      TEXT NOT NULL DEFAULT '',
    trust_score     REAL NOT NULL DEFAULT 0.5,
    sha256          TEXT NOT NULL DEFAULT '',
    UNIQUE (canonical_url),
    UNIQUE (sha256) ON CONFLICT FAIL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_source ON artifacts(source_type);
CREATE INDEX IF NOT EXISTS idx_artifacts_published ON artifacts(published_at);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    artifact_id     TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    section_title   TEXT NOT NULL DEFAULT '',
    text            TEXT NOT NULL DEFAULT '',
    code_snippet    TEXT NOT NULL DEFAULT '',
    language        TEXT NOT NULL DEFAULT '',
    path_hint       TEXT NOT NULL DEFAULT '',
    simhash64_hex   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_chunks_artifact ON chunks(artifact_id);
CREATE INDEX IF NOT EXISTS idx_chunks_simhash ON chunks(simhash64_hex);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    artifact_id UNINDEXED,
    section_title,
    text,
    code_snippet,
    path_hint
);
"""


class FtsStore:
    """SQLite + FTS5 store for ExternalArtifact / IndexChunk.

    Args:
        db_path: file path; ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path: str = str(db_path)
        # ``:memory:`` databases are connection-local — each
        # ``sqlite3.connect(":memory:")`` returns a *different* empty DB.
        # Pin a single shared connection for in-memory mode so writes
        # actually persist across :meth:`_connect` calls.
        self._shared_memory_conn: sqlite3.Connection | None = None
        if self._db_path == ":memory:":
            self._shared_memory_conn = sqlite3.connect(":memory:")
            self._shared_memory_conn.row_factory = sqlite3.Row
            self._shared_memory_conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._shared_memory_conn is not None:
            # In-memory mode: yield the shared connection without
            # closing it on exit. We still commit so call sites don't
            # need to remember.
            try:
                yield self._shared_memory_conn
                self._shared_memory_conn.commit()
            except Exception:
                self._shared_memory_conn.rollback()
                raise
            return

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def upsert_artifact(self, art: ExternalArtifact, *, body_for_hash: str = "") -> str:
        """Insert/replace one artifact.

        Returns the ``artifact_id`` actually persisted (may differ from
        ``art.artifact_id`` if the canonical_url collides — we keep the
        existing artifact and return its id so the caller can dedupe).

        Raises :class:`sqlite3.IntegrityError` on cross-URL sha256 collision
        (same content under a different canonical_url) — let callers
        decide policy.
        """
        sha = art.sha256 or content_signature_sha256(body_for_hash) if body_for_hash else art.sha256

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT artifact_id FROM artifacts WHERE canonical_url = ?",
                (art.canonical_url,),
            ).fetchone()
            if existing:
                # URL already known — update mutable fields, keep id.
                conn.execute(
                    """
                    UPDATE artifacts SET
                        source_type = ?, title = ?, authors_csv = ?, venue = ?,
                        published_at = ?, fetched_at = ?, trust_score = ?,
                        sha256 = COALESCE(NULLIF(?, ''), sha256)
                    WHERE artifact_id = ?
                    """,
                    (
                        art.source_type, art.title, ",".join(art.authors),
                        art.venue, art.published_at, art.fetched_at,
                        art.trust_score, sha, existing["artifact_id"],
                    ),
                )
                return existing["artifact_id"]

            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, source_type, canonical_url, title,
                    authors_csv, venue, published_at, fetched_at,
                    trust_score, sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    art.artifact_id, art.source_type, art.canonical_url,
                    art.title, ",".join(art.authors), art.venue,
                    art.published_at, art.fetched_at, art.trust_score, sha,
                ),
            )
            return art.artifact_id

    def upsert_chunk(self, chunk: IndexChunk) -> None:
        """Insert/replace one chunk + its FTS row."""
        sim_hex = chunk.simhash64_hex
        if not sim_hex and chunk.text:
            sim_hex = simhash64_to_hex(simhash64(chunk.text))

        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk.chunk_id,))
            conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, artifact_id, section_title, text,
                    code_snippet, language, path_hint, simhash64_hex
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id, chunk.artifact_id, chunk.section_title,
                    chunk.text, chunk.code_snippet, chunk.language,
                    chunk.path_hint, sim_hex,
                ),
            )
            conn.execute(
                "DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,),
            )
            conn.execute(
                """
                INSERT INTO chunks_fts (chunk_id, artifact_id, section_title, text, code_snippet, path_hint)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id, chunk.artifact_id, chunk.section_title,
                    chunk.text, chunk.code_snippet, chunk.path_hint,
                ),
            )

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_artifact_by_url(self, canonical_url: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE canonical_url = ?", (canonical_url,),
            ).fetchone()
            return dict(row) if row else None

    def list_artifacts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts ORDER BY fetched_at DESC, artifact_id"
            ).fetchall()
            return [dict(r) for r in rows]

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        source_types: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        """BM25 search joined with artifacts metadata + bm25_rank.

        Tokenization rules (mirrored by :mod:`stable_agent.skills.index_store.search`):

          - Split on non-alphanumeric so ``held-out`` becomes
            ``"held" "out"`` rather than ``held NOT out`` (FTS5 reserves
            ``-`` as a negation operator).
          - Each token is wrapped in double quotes individually so
            users can't smuggle FTS5 boolean operators in.
          - Tokens are AND'd together (FTS5's default).
        """
        if not query or not query.strip():
            return []
        safe_query = _build_fts_match(query)
        if not safe_query:
            return []
        type_clause = ""
        params: list[Any] = [safe_query]
        types = list(source_types)
        if types:
            placeholders = ",".join(["?"] * len(types))
            type_clause = f" AND a.source_type IN ({placeholders}) "
            params.extend(types)
        params.append(limit)

        sql = f"""
            SELECT a.*, c.section_title, c.text, c.path_hint, c.chunk_id, fts.rank AS bm25_rank
            FROM chunks_fts fts
            JOIN chunks c ON c.chunk_id = fts.chunk_id
            JOIN artifacts a ON a.artifact_id = c.artifact_id
            WHERE chunks_fts MATCH ?
              {type_clause}
            ORDER BY fts.rank
            LIMIT ?
        """
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def find_duplicates(
        self,
        *,
        sha256: str = "",
        simhash_hex: str = "",
        threshold: int = 3,
    ) -> list[dict[str, Any]]:
        """Return artifacts matching exact sha256 OR near simhash."""
        results: list[dict[str, Any]] = []
        with self._connect() as conn:
            if sha256:
                row = conn.execute(
                    "SELECT * FROM artifacts WHERE sha256 = ?", (sha256,),
                ).fetchone()
                if row:
                    d = dict(row)
                    d["match_type"] = "sha256"
                    d["hamming_distance"] = 0
                    results.append(d)

            if simhash_hex:
                target = simhash64_from_hex(simhash_hex)
                rows = conn.execute(
                    "SELECT artifact_id, c.simhash64_hex AS chunk_simhash, c.chunk_id, a.* "
                    "FROM artifacts a JOIN chunks c USING(artifact_id) "
                    "WHERE c.simhash64_hex != ''"
                ).fetchall()
                seen: set[str] = {r.get("artifact_id", "") for r in results}
                for row in rows:
                    other = simhash64_from_hex(row["chunk_simhash"])
                    distance = hamming64(target, other)
                    if distance <= threshold and row["artifact_id"] not in seen:
                        d = dict(row)
                        d["match_type"] = "simhash"
                        d["hamming_distance"] = distance
                        results.append(d)
                        seen.add(row["artifact_id"])
        return results

    def count_artifacts(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]

    def count_chunks(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
