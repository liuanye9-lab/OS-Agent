"""Phase 6 — Review queue (JSON-on-disk).

One :class:`ReviewQueueItem` per skill that's awaiting human review.
Items are immutable on disk; ``approve``/``reject`` writes a new
``decision`` field but the rest of the record is preserved for audit.

Schema (kept minimal to dodge YAML / Pydantic dependencies)::

    {
      "review_id": "rev_<12hex>",
      "validation_id": "val_<12hex>" | null,
      "run_id": "...",
      "skill_id": "...",
      "skill_version": 1,
      "risk_level": "low" | "high",
      "review_kind": "READY" | "HIGH_RISK" | "ROLLBACK",
      "submitted_at": "<iso8601>",
      "submitted_reason": "...",
      "decision": null
        | {"verdict": "approved" | "rejected", "reviewer": "...",
           "reason": "...", "decided_at": "<iso8601>"}
    }

Why JSON files (not SQLite): operators audit this manually, and the
small volume (review queue rarely has > 100 pending items) doesn't
justify a second DB. ``data/review_queue/`` is also git-archivable
for compliance.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Same path-traversal guard as ValidationReportStore.
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _validate_id(review_id: str) -> None:
    if not _ID_RE.match(review_id):
        raise ValueError(
            f"invalid review_id {review_id!r}: must match {_ID_RE.pattern}"
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReviewQueueStore:
    """File-backed pending-review queue.

    Layout::

        {root}/data/review_queue/
        ├── rev_<id>.json
        └── ...

    Pending = ``decision is None``. ``approve``/``reject`` mutate decision
    in place (the rest of the file is preserved for audit).
    """

    def __init__(self, root: str | Path) -> None:
        self._dir = Path(root) / "data" / "review_queue"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def submit(
        self,
        *,
        skill_id: str,
        skill_version: int,
        risk_level: str,
        review_kind: str,
        validation_id: str | None,
        run_id: str,
        reason: str,
        review_id: str | None = None,
    ) -> str:
        """Create a pending review item and return ``review_id``."""
        if review_id is None:
            review_id = f"rev_{uuid.uuid4().hex[:12]}"
        _validate_id(review_id)

        record: dict[str, Any] = {
            "review_id": review_id,
            "validation_id": validation_id,
            "run_id": run_id,
            "skill_id": skill_id,
            "skill_version": skill_version,
            "risk_level": risk_level,
            "review_kind": review_kind,
            "submitted_at": _now_iso(),
            "submitted_reason": reason,
            "decision": None,
        }
        path = self._dir / f"{review_id}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return review_id

    def record_decision(
        self,
        review_id: str,
        *,
        verdict: str,
        reviewer: str,
        reason: str,
    ) -> dict[str, Any]:
        """Stamp a decision onto a pending item.

        Raises :class:`KeyError` if the item doesn't exist;
        :class:`ValueError` if the item is not pending (already decided).
        """
        if verdict not in ("approved", "rejected"):
            raise ValueError(f"verdict must be approved/rejected, got {verdict!r}")
        rec = self.get(review_id)
        if rec is None:
            raise KeyError(f"review_id not found: {review_id}")
        if rec.get("decision") is not None:
            raise ValueError(f"review {review_id} already decided")

        rec["decision"] = {
            "verdict": verdict,
            "reviewer": reviewer,
            "reason": reason,
            "decided_at": _now_iso(),
        }
        path = self._dir / f"{review_id}.json"
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        return rec

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get(self, review_id: str) -> dict[str, Any] | None:
        _validate_id(review_id)
        path = self._dir / f"{review_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_pending(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self._dir.glob("rev_*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("decision") is None:
                out.append(rec)
        return out

    def list_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted(self._dir.glob("rev_*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out
