"""``os_agent_handler`` façade — Phase 1 thin wrapper.

The real handler is ``UnifiedToolRegistry._h_task_os_agent`` (540+ lines, in
:mod:`stable_agent.gateway.unified_tool_registry`). Phase 1 does **not** move
that code — see Phase 0 audit blocker B1 — instead this module exposes a
clean call surface that:

1. routes ``stableagent.task.os_agent`` through :class:`LocalRuntime`,
2. flattens the MCP envelope into the same 9-field CLI envelope as
   ``cli.cmd_task_run`` (Phase 0 PHASE0_CONTRACT.md §1),
3. is the only blessed import for non-CLI Python callers (tests, future
   workflow engine, etc.).

Phase 2+ may grow this into a real handler module; Phase 1 keeps it tiny so
nothing in the 540-line monolith has to move.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "stableagent.task.os_agent"


def run_os_agent(
    task_input: str,
    *,
    open_dashboard: bool = False,
    runtime: Any | None = None,
    base_url: str = "",
    extra_arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ``stableagent.task.os_agent`` in-process and return the CLI envelope.

    The shape returned here is the **9-field CLI envelope** frozen in
    ``docs/harness/PHASE0_CONTRACT.md §1`` — not the full ``structuredContent``.
    Callers that need everything should use
    :meth:`stable_agent.runtime.local_runtime.LocalRuntime.call_tool`
    directly.

    Args:
        task_input: human-readable task description. Required, non-empty.
        open_dashboard: pass-through flag; when ``False``, ``dashboard_url``
            and ``observer_url`` may come back empty.
        runtime: optional :class:`LocalRuntime` instance(mostly for tests).
            When ``None``, the module-level singleton is used.
        base_url: optional base URL prefix to prepend to dashboard/observer
            paths (CLI HTTP path does this when given a host:port). Pass an
            empty string to keep the path-only form, matching what tests and
            offline tooling expect.
        extra_arguments: forwarded into the tool ``arguments`` dict — useful
            for the V9 force_* / dry_run_learning test knobs documented in
            ``unified_tool_registry.py:976-985``.

    Returns:
        A dict with exactly these 9 keys::

            {
                "ok": bool,
                "run_id": str,
                "dashboard_url": str,
                "observer_url": str,
                "missing_required_events": list[str],
                "understanding_trace": dict | None,
                "token_report": dict | None,
                "expression_matches": list | None,
                "error": str | None,
            }

        ``ok=False`` always carries a non-empty ``error`` string (Phase 0
        contract invariant).
    """
    if not task_input or not isinstance(task_input, str):
        return _error_envelope("task_input is required and must be a non-empty string")

    if runtime is None:
        from stable_agent.runtime.local_runtime import get_default_runtime
        runtime = get_default_runtime()

    arguments: dict[str, Any] = {
        "task_input": task_input,
        "open_dashboard": open_dashboard,
    }
    if extra_arguments:
        arguments.update(extra_arguments)

    try:
        result = runtime.call_tool(TOOL_NAME, arguments)
    except Exception as exc:  # pragma: no cover — runtime guards exceptions
        logger.exception("LocalRuntime.call_tool raised — should be impossible")
        return _error_envelope(f"local runtime failure: {exc}")

    sc: dict[str, Any] = result.get("structuredContent", {}) or {}

    # Reuse the CLI envelope projection rule from cli.py:244-258 so callers
    # see one shape regardless of HTTP / local transport.
    dashboard_path = sc.get("dashboard_url", "") or ""
    observer_path = sc.get("observer_url", "") or ""
    is_error = bool(result.get("isError"))
    ok = bool(sc.get("ok", not is_error))

    error_msg: str | None = sc.get("error")
    if not ok and not error_msg:
        error_msg = sc.get("plain_text") or "工具调用失败,原因未知"

    envelope: dict[str, Any] = {
        "ok": ok,
        "run_id": sc.get("run_id", "") or "",
        "dashboard_url": _join_url(base_url, dashboard_path) if dashboard_path else "",
        "observer_url": _join_url(base_url, observer_path) if observer_path else "",
        "missing_required_events": sc.get("missing_required_events") or [],
        "understanding_trace": sc.get("understanding_trace"),
        "token_report": sc.get("token_report"),
        "expression_matches": sc.get("expression_matches"),
        "error": error_msg,
    }
    return envelope


def _error_envelope(message: str) -> dict[str, Any]:
    """Build an envelope satisfying the Phase 0 invariants for a failure."""
    return {
        "ok": False,
        "run_id": "",
        "dashboard_url": "",
        "observer_url": "",
        "missing_required_events": [],
        "understanding_trace": None,
        "token_report": None,
        "expression_matches": None,
        "error": message,
    }


def _join_url(base: str, path: str) -> str:
    """Prepend ``base`` to ``path``, or return ``path`` when ``base`` is empty."""
    if not base:
        return path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base.rstrip('/')}{path}"
