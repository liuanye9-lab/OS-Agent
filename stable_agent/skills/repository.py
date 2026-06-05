"""Phase 2 SkillRepo v2 — file + index orchestration.

The single entry point that callers (Phase 3 Curator/Validator,
Phase 6 Harness CLI) should import. Wraps:

  - markdown + frontmatter file I/O on disk
  - signature canonicalization + dedupe checks
  - SQLite index keep-in-sync
  - ``best_skill.md`` export from promoted skills

Layout:
    {root}/skills/
    ├── index.sqlite              ← :class:`IndexStore`
    └── repo/
        └── {skill_id}/
            ├── v1.md             ← canonical artifact
            ├── v2.md
            └── ...

The legacy ``skills/best_skill.md`` is **derived**, never the source of
truth. Phase 2 does not modify it during candidate writes; only
``export_best_skill()`` may overwrite it (callers like Phase 3 Validator
should call that explicitly after a successful promotion).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from stable_agent.skills.index_store import IndexStore
from stable_agent.skills.lifecycle import (
    SkillTransitionError,
    transition,
)
from stable_agent.skills.models import (
    SECTION_ORDER,
    SkillDocument,
    SkillFrontmatter,
    SkillStatus,
)
from stable_agent.skills.signature import (
    canonicalize,
    content_signature_sha256,
    simhash64,
    simhash64_to_hex,
)

logger = logging.getLogger(__name__)


class SkillRepoError(Exception):
    """Base class for repo-level failures."""


class DuplicateSkillError(SkillRepoError):
    """A skill body identical to an existing one was submitted."""


class SkillNotFoundError(SkillRepoError):
    """No matching (skill_id, version) exists."""


# Pre-compiled patterns for the markdown parser.
_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<fm>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL
)
# H1 sections — matches ``# Title`` at line start.
_H1_RE = re.compile(r"^# (?P<title>[^\n]+)\n", re.MULTILINE)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_markdown(text: str) -> SkillDocument:
    """Parse one of our markdown skill files into a :class:`SkillDocument`.

    Tolerant of:
      - missing trailing newlines
      - sections in any order
      - extra unknown sections (they're preserved)
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise SkillRepoError("missing or malformed YAML frontmatter")
    fm_yaml = m.group("fm")
    body = m.group("body")

    fm_dict = yaml.safe_load(fm_yaml) or {}
    if not isinstance(fm_dict, dict):
        raise SkillRepoError("frontmatter must be a YAML mapping")
    fm = SkillFrontmatter.from_yaml_dict(fm_dict)

    sections: dict[str, str] = {}
    matches = list(_H1_RE.finditer(body))
    for i, mm in enumerate(matches):
        title = mm.group("title").strip()
        start = mm.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()

    return SkillDocument(frontmatter=fm, sections=sections)


def _serialize_markdown(skill: SkillDocument) -> str:
    """Inverse of :func:`_parse_markdown`. Stable section ordering."""
    fm_yaml = yaml.safe_dump(
        skill.frontmatter.to_yaml_dict(),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()

    parts: list[str] = ["---", fm_yaml, "---", ""]

    # Known sections first, in canonical order.
    used: set[str] = set()
    for title in SECTION_ORDER:
        body_text = skill.sections.get(title, "")
        used.add(title)
        parts.append(f"# {title}")
        if body_text:
            parts.append(body_text)
        parts.append("")  # spacer

    # Unknown sections preserved tail-end (extension-friendly).
    for title, body_text in skill.sections.items():
        if title in used:
            continue
        parts.append(f"# {title}")
        if body_text:
            parts.append(body_text)
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


class SkillRepository:
    """File + SQLite skill repository.

    Args:
        root: directory under which ``skills/index.sqlite`` and
            ``skills/repo/{skill_id}/v{n}.md`` live.
        best_skill_path: where ``export_best_skill()`` writes the
            promoted artifact for legacy consumers. ``None`` disables
            export entirely.
    """

    def __init__(
        self,
        root: str | Path,
        best_skill_path: str | Path | None = None,
    ) -> None:
        self._root = Path(root)
        self._repo_dir = self._root / "skills" / "repo"
        self._db_path = self._root / "skills" / "index.sqlite"
        self._repo_dir.mkdir(parents=True, exist_ok=True)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._index = IndexStore(self._db_path)
        self._best_skill_path = (
            Path(best_skill_path) if best_skill_path else None
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def index(self) -> IndexStore:
        """Direct access to :class:`IndexStore` for read queries."""
        return self._index

    def write(
        self,
        skill: SkillDocument,
        *,
        allow_existing_signature: bool = False,
    ) -> SkillDocument:
        """Persist a skill version to disk and the SQLite index.

        Computes ``signature_sha256`` + ``simhash64`` from the canonical
        body so callers don't have to.

        Raises :class:`DuplicateSkillError` when the *exact* body has been
        seen before (different ``skill_id`` or different ``version``)
        unless ``allow_existing_signature=True``.
        """
        intent = skill.section("Intent")
        procedure = skill.section("Procedure")
        guardrails = skill.section("Guardrails")
        canonical = canonicalize(
            intent, procedure, guardrails,
            skill.frontmatter.retrieval_tags,
        )
        sha = content_signature_sha256(canonical)
        sim_hex = simhash64_to_hex(simhash64(canonical))

        existing = self._index.find_by_signature(sha)
        if existing and not allow_existing_signature:
            same_slot = (
                existing["skill_id"] == skill.skill_id
                and existing["version"] == skill.version
            )
            if not same_slot:
                raise DuplicateSkillError(
                    f"signature {sha[:12]} already owned by "
                    f"{existing['skill_id']}@v{existing['version']}"
                )

        now = _now_utc_iso()
        fm = skill.frontmatter
        fm = SkillFrontmatter(
            skill_id=fm.skill_id,
            version=fm.version,
            status=fm.status,
            domain=fm.domain,
            owner=fm.owner,
            created_at=fm.created_at or now,
            updated_at=now,
            retrieval_tags=fm.retrieval_tags,
            task_types=fm.task_types,
            triggers=fm.triggers,
            metrics=fm.metrics,
            source_runs=fm.source_runs,
            dependencies=fm.dependencies,
            risk_level=fm.risk_level,
            signature_sha256=sha,
            simhash64=sim_hex,
        )
        new_skill = skill.with_frontmatter(fm)

        # Persist canonical artifact.
        skill_dir = self._repo_dir / new_skill.skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = skill_dir / f"v{new_skill.version}.md"
        artifact_path.write_text(_serialize_markdown(new_skill), encoding="utf-8")

        # Mirror to SQLite index.
        self._index.upsert(
            skill_id=new_skill.skill_id,
            version=new_skill.version,
            status=new_skill.status.value,
            domain=fm.domain,
            owner=fm.owner,
            risk_level=fm.risk_level,
            retrieval_tags=list(fm.retrieval_tags),
            task_types=list(fm.task_types),
            validations=fm.metrics.validations,
            win_rate=fm.metrics.win_rate,
            avg_token_delta=fm.metrics.avg_token_delta,
            avg_latency_delta=fm.metrics.avg_latency_delta,
            last_validation_score=fm.metrics.last_validation_score,
            content_signature_sha256=sha,
            simhash64_hex=sim_hex,
            file_path=str(artifact_path.relative_to(self._root)),
            created_at=fm.created_at,
            updated_at=fm.updated_at,
            intent_text=intent,
            procedure_text=procedure,
            guardrails_text=guardrails,
        )
        return new_skill

    def get(self, skill_id: str, version: int | None = None) -> SkillDocument:
        """Load one version's full SkillDocument from disk.

        ``version=None`` → latest version on disk. Raises
        :class:`SkillNotFoundError` if missing.
        """
        row = self._index.get(skill_id, version)
        if not row:
            raise SkillNotFoundError(f"{skill_id}@v{version}")
        path = self._root / row["file_path"]
        if not path.exists():
            raise SkillNotFoundError(
                f"index references missing file: {path}"
            )
        return _parse_markdown(path.read_text(encoding="utf-8"))

    def transition_status(
        self,
        skill_id: str,
        version: int,
        target: SkillStatus,
    ) -> SkillDocument:
        """Move a skill version to a new status (lifecycle-checked)."""
        skill = self.get(skill_id, version)
        try:
            updated = transition(skill, target)
        except SkillTransitionError:
            raise
        # Re-write artifact + index with the new status.
        return self.write(updated, allow_existing_signature=True)

    def search(
        self,
        query: str,
        *,
        include_all_statuses: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """BM25 search via the FTS5 index."""
        return self._index.search(
            query,
            include_all_statuses=include_all_statuses,
            limit=limit,
        )

    def find_near_duplicates(
        self,
        skill: SkillDocument,
        *,
        threshold: int = 3,
    ) -> list[dict]:
        """Hamming-bounded simhash neighbourhood, *excluding* exact self.

        Useful when Curator wants to ask "is this candidate already
        covered?" before writing a new version.
        """
        intent = skill.section("Intent")
        procedure = skill.section("Procedure")
        guardrails = skill.section("Guardrails")
        canonical = canonicalize(
            intent, procedure, guardrails,
            skill.frontmatter.retrieval_tags,
        )
        sim_hex = simhash64_to_hex(simhash64(canonical))
        sha = content_signature_sha256(canonical)

        rows = self._index.find_near_duplicates(sim_hex, threshold=threshold)
        return [r for r in rows if r["content_signature_sha256"] != sha]

    def list_promoted(self) -> list[SkillDocument]:
        """Materialize all currently promoted skills (latest version each)."""
        # Group by skill_id, take the most recent version per skill.
        rows = self._index.list_promoted()
        seen: dict[str, dict] = {}
        for row in rows:
            sid = row["skill_id"]
            if sid not in seen or seen[sid]["version"] < row["version"]:
                seen[sid] = row
        out: list[SkillDocument] = []
        for row in seen.values():
            try:
                out.append(self.get(row["skill_id"], row["version"]))
            except SkillNotFoundError:
                logger.warning(
                    "promoted skill %s@v%s missing on disk — skipping",
                    row["skill_id"], row["version"],
                )
        return out

    def export_best_skill(self) -> Path | None:
        """Concatenate all promoted skills into ``best_skill.md``.

        Phase 2 keeps the legacy export simple: a header per skill
        followed by its body sections. Phase 3+ may add ranking, but
        for now alphabetical order on ``skill_id`` is enough.

        Returns the path written, or ``None`` if no destination is set.
        """
        if self._best_skill_path is None:
            return None

        promoted = sorted(self.list_promoted(), key=lambda s: s.skill_id)
        if not promoted:
            self._best_skill_path.write_text(
                "<!-- skill_repo_v2: no promoted skills -->\n",
                encoding="utf-8",
            )
            return self._best_skill_path

        lines: list[str] = [
            "<!-- skill_repo_v2: derived export — do not edit by hand -->",
            f"<!-- generated_at: {_now_utc_iso()} -->",
            "",
        ]
        for skill in promoted:
            lines.append(
                f"## {skill.skill_id} @ v{skill.version} "
                f"(score={skill.frontmatter.metrics.last_validation_score:.2f})"
            )
            for section in SECTION_ORDER:
                body = skill.section(section)
                if body:
                    lines.append(f"### {section}")
                    lines.append(body)
            lines.append("")

        self._best_skill_path.parent.mkdir(parents=True, exist_ok=True)
        self._best_skill_path.write_text("\n".join(lines), encoding="utf-8")
        return self._best_skill_path
