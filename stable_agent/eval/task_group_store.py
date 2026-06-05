"""Phase 3 — Task group store for delayed validation.

A *task group* is a small set of related tasks Curator/Validator use as
held-out fixtures when comparing baseline vs candidate runs.

Storage model (Phase 3 keeps it dumb on purpose):

  - one JSONL file per group at ``{root}/eval/task_groups/{group_id}.jsonl``
  - frontmatter line(``__meta__``) carries ``task_type`` /
    ``failure_mode`` / ``retrieval_tags``
  - subsequent lines are :class:`TaskCase` records

This is enough for Phase 3 (CI fixtures, local dev). Phase 5/6 may move
this to SQLite once the corpus is large enough to justify indexing.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

# Group IDs are file names — keep them filesystem-safe.
_GROUP_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _validate_group_id(group_id: str) -> None:
    if not _GROUP_ID_RE.match(group_id):
        raise ValueError(
            f"invalid group_id {group_id!r}: must match {_GROUP_ID_RE.pattern}"
        )


@dataclass(frozen=True)
class TaskCase:
    """One held-out task fixture.

    ``expected_signals`` lists event types or keywords the run must emit
    for the case to count as "complete". For Phase 3 the Validator only
    uses it to compute ``required_events_completeness``.
    """

    case_id: str
    task_input: str
    expected_signals: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class TaskGroup:
    """A bundle of related-task cases used for Validator A/B runs.

    The group's ``failure_mode`` / ``retrieval_tags`` are the keys the
    Curator uses to pick **which** group fits a given candidate skill.
    """

    group_id: str
    task_type: str
    failure_mode: str
    retrieval_tags: tuple[str, ...]
    cases: tuple[TaskCase, ...]
    description: str = ""

    def __post_init__(self) -> None:
        _validate_group_id(self.group_id)
        if not self.cases:
            raise ValueError("TaskGroup must have at least one case")


class TaskGroupStore:
    """File-backed store for :class:`TaskGroup` fixtures.

    Args:
        root: directory under which ``eval/task_groups/{group_id}.jsonl``
            files are kept. Created on first write.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root) / "eval" / "task_groups"
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def add_group(self, group: TaskGroup) -> Path:
        """Persist a :class:`TaskGroup`. Overwrites existing file."""
        _validate_group_id(group.group_id)
        path = self._root / f"{group.group_id}.jsonl"
        meta = {
            "__meta__": True,
            "group_id": group.group_id,
            "task_type": group.task_type,
            "failure_mode": group.failure_mode,
            "retrieval_tags": list(group.retrieval_tags),
            "description": group.description,
        }
        lines = [json.dumps(meta, ensure_ascii=False)]
        for case in group.cases:
            lines.append(json.dumps(asdict(case), ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def remove_group(self, group_id: str) -> bool:
        path = self._root / f"{group_id}.jsonl"
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get(self, group_id: str) -> TaskGroup:
        _validate_group_id(group_id)
        path = self._root / f"{group_id}.jsonl"
        if not path.exists():
            raise KeyError(f"task group not found: {group_id}")
        return self._parse(path)

    def list_all(self) -> list[TaskGroup]:
        out: list[TaskGroup] = []
        for path in sorted(self._root.glob("*.jsonl")):
            try:
                out.append(self._parse(path))
            except Exception:
                # Skip malformed groups; production should add a logger.
                continue
        return out

    def find_related(
        self,
        *,
        task_type: str | None = None,
        retrieval_tags: Iterable[str] = (),
        failure_mode: str | None = None,
        limit: int = 5,
    ) -> list[TaskGroup]:
        """Score-rank groups by tag/type/failure_mode overlap.

        Scoring (Phase 3 keeps it transparent — no learned ranker):

          + 2 if ``task_type`` matches
          + 2 if ``failure_mode`` matches
          + 1 per overlapping retrieval_tag

        Returns at most ``limit`` groups, highest score first. Ties broken
        by ``group_id`` for stability.
        """
        wanted_tags = {t.lower() for t in retrieval_tags}
        scored: list[tuple[float, TaskGroup]] = []
        for group in self.list_all():
            score = 0.0
            if task_type and group.task_type == task_type:
                score += 2.0
            if failure_mode and group.failure_mode == failure_mode:
                score += 2.0
            score += len(wanted_tags & {t.lower() for t in group.retrieval_tags})
            if score > 0:
                scored.append((score, group))
        scored.sort(key=lambda x: (-x[0], x[1].group_id))
        return [g for _, g in scored[:limit]]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse(path: Path) -> TaskGroup:
        meta: dict | None = None
        cases: list[TaskCase] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("__meta__"):
                meta = obj
            else:
                cases.append(TaskCase(
                    case_id=obj["case_id"],
                    task_input=obj["task_input"],
                    expected_signals=tuple(obj.get("expected_signals") or ()),
                    notes=obj.get("notes", ""),
                ))
        if meta is None:
            raise ValueError(f"task group missing meta line: {path}")
        if not cases:
            raise ValueError(f"task group has no cases: {path}")
        return TaskGroup(
            group_id=meta["group_id"],
            task_type=meta["task_type"],
            failure_mode=meta["failure_mode"],
            retrieval_tags=tuple(meta.get("retrieval_tags") or ()),
            cases=tuple(cases),
            description=meta.get("description", ""),
        )
