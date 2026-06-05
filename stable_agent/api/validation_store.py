"""Phase 5 — ValidationReport persistence.

Phase 3 produces :class:`ValidationReport` in memory but never writes
them anywhere — Phase 5 fixes that with a tiny JSON-on-disk store keyed
by ``validation_id``. The store is shared by:

  - Compare API (``/api/runs/{run_id}/compare``)
  - Validation detail API (``/api/validations/{validation_id}``)
  - Phase 6 Harness CI (rollback decisions need historical reports)

We keep the format JSON-flat (one file per report) so:

  - Phase 5 tests can assert artifacts on disk
  - operators can ``cat`` a report without booting the app
  - Phase 6 can git-archive `data/validations/` for audit
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stable_agent.eval.ab_validation_runner import ValidationReport


_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _validate_id(validation_id: str) -> None:
    if not _ID_RE.match(validation_id):
        raise ValueError(
            f"invalid validation_id {validation_id!r}: "
            f"must match {_ID_RE.pattern}"
        )


class ValidationReportStore:
    """File-backed validation report store.

    Layout::

        {root}/
        └── data/
            └── validations/
                ├── val_<id>.json
                └── ...

    Args:
        root: directory under which ``data/validations/`` lives.
            Created on first write.
    """

    def __init__(self, root: str | Path) -> None:
        self._dir = Path(root) / "data" / "validations"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def save(
        self,
        report: ValidationReport,
        *,
        run_id: str = "",
        validation_id: str | None = None,
    ) -> str:
        """Persist ``report`` and return the assigned ``validation_id``.

        ``run_id`` is the OS-Agent run that produced the candidate. We
        keep it as a sidecar field so the Compare API can find the right
        report for a given run.
        """
        if validation_id is None:
            validation_id = f"val_{uuid.uuid4().hex[:12]}"
        _validate_id(validation_id)

        record: dict[str, Any] = {
            "validation_id": validation_id,
            "run_id": run_id,
            "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "report": report.to_dict(),
        }
        path = self._dir / f"{validation_id}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return validation_id

    def delete(self, validation_id: str) -> bool:
        _validate_id(validation_id)
        path = self._dir / f"{validation_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get(self, validation_id: str) -> dict[str, Any] | None:
        _validate_id(validation_id)
        path = self._dir / f"{validation_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def find_by_run(self, run_id: str) -> list[dict[str, Any]]:
        """Return all saved reports tagged with ``run_id`` (newest first)."""
        if not run_id:
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self._dir.glob("val_*.json"), reverse=True):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("run_id") == run_id:
                out.append(rec)
        return out

    def list_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self._dir.glob("val_*.json"), reverse=True):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out
