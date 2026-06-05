"""Phase 2 SkillRepo v2 — SQLite FTS5 index for promoted-only retrieval.

Two tables:

  - ``skills``       — one row per (skill_id, version) with governance
                       columns; a UNIQUE constraint on
                       ``content_signature_sha256`` enforces strict dedupe.
  - ``skills_fts``   — FTS5 virtual table mirroring intent/procedure/tags
                       for BM25 retrieval; rebuilt on every upsert.

Hard rules (mirrored by tests):

  1. Default queries return **only** ``status='promoted'`` rows. Callers
     that want all statuses must pass ``include_all_statuses=True``.
  2. ``upsert`` rejects duplicate ``content_signature_sha256`` (you must
     bump the version first).
  3. ``find_near_duplicates`` returns rows whose ``simhash64`` Hamming
     distance is ``≤ threshold`` (default 3 — roadmap recommendation).

The store is intentionally minimal: it doesn't try to be a full ORM. It
just keeps the file system (canonical artifact) and the FTS index in
sync via :mod:`stable_agent.skills.repository`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from stable_agent.skills.signature import hamming64, simhash64_from_hex


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    skill_id                  TEXT NOT NULL,
    version                   INTEGER NOT NULL,
    status                    TEXT NOT NULL,
    domain                    TEXT NOT NULL DEFAULT 'coding',
    owner                     TEXT NOT NULL DEFAULT 'curator_v1',
    risk_level                TEXT NOT NULL DEFAULT 'low',
    retrieval_tags            TEXT NOT NULL DEFAULT '',
    task_types                TEXT NOT NULL DEFAULT '',
    validations               INTEGER NOT NULL DEFAULT 0,
    win_rate                  REAL NOT NULL DEFAULT 0.0,
    avg_token_delta           REAL NOT NULL DEFAULT 0.0,
    avg_latency_delta         REAL NOT NULL DEFAULT 0.0,
    last_validation_score     REAL NOT NULL DEFAULT 0.0,
    content_signature_sha256  TEXT NOT NULL,
    simhash64_hex             TEXT NOT NULL DEFAULT '',
    file_path                 TEXT NOT NULL DEFAULT '',
    created_at                TEXT NOT NULL DEFAULT '',
    updated_at                TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (skill_id, version),
    UNIQUE (content_signature_sha256)
);

CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE INDEX IF NOT EXISTS idx_skills_simhash ON skills(simhash64_hex);

CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
    skill_id UNINDEXED,
    version UNINDEXED,
    intent,
    procedure,
    guardrails,
    tags
);
"""


class IndexStore:
    """SQLite-backed index for SkillRepo v2.

    Args:
        db_path: SQLite file path. Pass ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path: str = str(db_path)
        self._init_schema()

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        # FTS5 ships with stock SQLite on Python 3.11+; absence is a hard
        # failure we want to surface loudly rather than silently fallback.
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

    def upsert(
        self,
        *,
        skill_id: str,
        version: int,
        status: str,
        domain: str,
        owner: str,
        risk_level: str,
        retrieval_tags: list[str],
        task_types: list[str],
        validations: int,
        win_rate: float,
        avg_token_delta: float,
        avg_latency_delta: float,
        last_validation_score: float,
        content_signature_sha256: str,
        simhash64_hex: str,
        file_path: str,
        created_at: str,
        updated_at: str,
        intent_text: str = "",
        procedure_text: str = "",
        guardrails_text: str = "",
    ) -> None:
        """Insert or replace a (skill_id, version) row + FTS row.

        Raises :class:`sqlite3.IntegrityError` if a *different* skill
        already owns the same ``content_signature_sha256`` — the caller
        (Repository) translates that into a duplicate-rejection error.
        """
        tags_csv = ",".join(retrieval_tags or ())
        task_csv = ",".join(task_types or ())

        with self._connect() as conn:
            # Use INSERT OR REPLACE for the (skill_id, version) PK so
            # version bumps work; the UNIQUE on content_signature_sha256
            # still catches cross-skill duplicates.
            conn.execute(
                """
                INSERT INTO skills (
                    skill_id, version, status, domain, owner, risk_level,
                    retrieval_tags, task_types,
                    validations, win_rate, avg_token_delta,
                    avg_latency_delta, last_validation_score,
                    content_signature_sha256, simhash64_hex, file_path,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(skill_id, version) DO UPDATE SET
                    status=excluded.status,
                    domain=excluded.domain,
                    owner=excluded.owner,
                    risk_level=excluded.risk_level,
                    retrieval_tags=excluded.retrieval_tags,
                    task_types=excluded.task_types,
                    validations=excluded.validations,
                    win_rate=excluded.win_rate,
                    avg_token_delta=excluded.avg_token_delta,
                    avg_latency_delta=excluded.avg_latency_delta,
                    last_validation_score=excluded.last_validation_score,
                    content_signature_sha256=excluded.content_signature_sha256,
                    simhash64_hex=excluded.simhash64_hex,
                    file_path=excluded.file_path,
                    updated_at=excluded.updated_at
                """,
                (
                    skill_id, version, status, domain, owner, risk_level,
                    tags_csv, task_csv,
                    validations, win_rate, avg_token_delta,
                    avg_latency_delta, last_validation_score,
                    content_signature_sha256, simhash64_hex, file_path,
                    created_at, updated_at,
                ),
            )

            # Refresh FTS row — easier than maintaining triggers.
            conn.execute(
                "DELETE FROM skills_fts WHERE skill_id = ? AND version = ?",
                (skill_id, version),
            )
            conn.execute(
                "INSERT INTO skills_fts (skill_id, version, intent, procedure, guardrails, tags) VALUES (?,?,?,?,?,?)",
                (skill_id, version, intent_text, procedure_text, guardrails_text, tags_csv),
            )

    def delete(self, skill_id: str, version: int | None = None) -> int:
        """Delete one version (``version`` given) or all versions of a skill.

        Returns number of rows deleted. Used by tests; production should
        prefer status transitions to ``archived``.
        """
        with self._connect() as conn:
            if version is None:
                cur = conn.execute(
                    "DELETE FROM skills WHERE skill_id = ?", (skill_id,)
                )
                conn.execute(
                    "DELETE FROM skills_fts WHERE skill_id = ?", (skill_id,)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM skills WHERE skill_id = ? AND version = ?",
                    (skill_id, version),
                )
                conn.execute(
                    "DELETE FROM skills_fts WHERE skill_id = ? AND version = ?",
                    (skill_id, version),
                )
            return cur.rowcount

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get(self, skill_id: str, version: int | None = None) -> dict[str, Any] | None:
        """Fetch a single row. ``version=None`` returns the latest version."""
        with self._connect() as conn:
            if version is None:
                row = conn.execute(
                    "SELECT * FROM skills WHERE skill_id = ? ORDER BY version DESC LIMIT 1",
                    (skill_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM skills WHERE skill_id = ? AND version = ?",
                    (skill_id, version),
                ).fetchone()
            return dict(row) if row else None

    def list_promoted(self) -> list[dict[str, Any]]:
        """All ``status='promoted'`` rows. Default retrieval surface."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skills WHERE status = 'promoted' ORDER BY skill_id, version DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def list_all(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skills ORDER BY skill_id, version DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def search(
        self,
        query: str,
        *,
        include_all_statuses: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """BM25 FTS5 search — promoted-only by default.

        Returns rows joined with ``skills`` table so callers see governance
        metadata + bm25 score.
        """
        if not query or not query.strip():
            return []

        # Phase 2 sanitization: FTS5 reserves a few characters (`"` and
        # the ``-`` operator). Quote the query as a single phrase to keep
        # callers from accidentally building boolean expressions.
        safe = '"' + query.replace('"', '""') + '"'

        status_clause = "" if include_all_statuses else " AND s.status = 'promoted' "
        sql = f"""
            SELECT s.*, fts.rank AS bm25_rank
            FROM skills_fts fts
            JOIN skills s
              ON s.skill_id = fts.skill_id AND s.version = fts.version
            WHERE skills_fts MATCH ?
              {status_clause}
            ORDER BY fts.rank
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (safe, limit)).fetchall()
            return [dict(r) for r in rows]

    def find_near_duplicates(
        self,
        simhash_hex: str,
        *,
        threshold: int = 3,
    ) -> list[dict[str, Any]]:
        """Return all skills whose simhash64 is within ``threshold`` Hamming bits.

        Threshold defaults to ``3`` (roadmap recommendation). Phase 2
        scans every row — fine up to ~10⁴ skills; Phase 3+ may add an
        LSH bucket if scale demands.
        """
        target = simhash64_from_hex(simhash_hex)
        results: list[dict[str, Any]] = []
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM skills").fetchall()
        for row in rows:
            other = simhash64_from_hex(row["simhash64_hex"])
            distance = hamming64(target, other)
            if distance <= threshold:
                d = dict(row)
                d["hamming_distance"] = distance
                results.append(d)
        results.sort(key=lambda r: r["hamming_distance"])
        return results

    def find_by_signature(self, sha256: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skills WHERE content_signature_sha256 = ?",
                (sha256,),
            ).fetchone()
            return dict(row) if row else None

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
