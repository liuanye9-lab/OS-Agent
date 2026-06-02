"""stable_agent/eval/related_task_store.py — Related Task Store。

存储和检索与 skill candidate 相关的历史任务。
用于 Delayed Validation v1 的 holdout task 来源。

数据源：
- .skills/validation/related_tasks.jsonl
- 已有 eval cases
- 历史 failed runs
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RelatedTaskStore:
    """Related Task 存储。

    JSONL 文件 + 内存缓存。
    """

    def __init__(self, base_path: str | Path | None = None):
        if base_path is None:
            base_path = Path.cwd() / ".skills"
        self._base_path = Path(base_path)
        self._validation_dir = self._base_path / "validation"
        self._validation_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self._validation_dir / "related_tasks.jsonl"
        self._cache: list[dict[str, Any]] = []
        self._loaded = False

    def add_task(self, task: dict[str, Any]) -> None:
        """添加相关任务。

        Args:
            task: 任务定义，至少包含 task_input。
        """
        entry = {
            "task_id": task.get("task_id", f"task_{int(time.time() * 1000)}"),
            "task_input": task.get("task_input", ""),
            "domain": task.get("domain", "general"),
            "failure_mode": task.get("failure_mode", ""),
            "eval_score": task.get("eval_score"),
            "source_run_id": task.get("source_run_id", ""),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._cache.append(entry)
        self._append_to_file(entry)

    def find_related(
        self,
        domain: str = "",
        failure_mode: str = "",
        skill_tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """查找相关任务。

        Args:
            domain: 领域过滤。
            failure_mode: 失败模式过滤。
            skill_tags: 技能标签过滤。
            limit: 最大返回数。

        Returns:
            相关任务列表。
        """
        self._ensure_loaded()

        scored: list[tuple[float, dict[str, Any]]] = []
        for task in self._cache:
            score = self._compute_relevance(task, domain, failure_mode, skill_tags)
            if score > 0:
                scored.append((score, task))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:limit]]

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有相关任务。"""
        self._ensure_loaded()
        return list(self._cache)

    def count(self) -> int:
        """返回任务数量。"""
        self._ensure_loaded()
        return len(self._cache)

    # ── 内部方法 ──────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """确保从文件加载。"""
        if self._loaded:
            return
        self._loaded = True
        self._cache = []
        if self._tasks_file.exists():
            for line in self._tasks_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        self._cache.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    def _append_to_file(self, entry: dict[str, Any]) -> None:
        """追加到 JSONL 文件。"""
        try:
            with open(self._tasks_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Failed to append to related_tasks.jsonl: %s", exc)

    def _compute_relevance(
        self,
        task: dict[str, Any],
        domain: str,
        failure_mode: str,
        skill_tags: list[str] | None,
    ) -> float:
        """计算任务相关性分数。"""
        score = 0.0

        if domain and task.get("domain") == domain:
            score += 0.4

        if failure_mode and task.get("failure_mode") == failure_mode:
            score += 0.4

        if skill_tags:
            task_input = task.get("task_input", "").lower()
            for tag in skill_tags:
                if tag.lower() in task_input:
                    score += 0.2
                    break

        return min(1.0, score)
