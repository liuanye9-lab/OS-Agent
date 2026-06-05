"""Phase 5 — public surface for the Observer / Evidence Console.

Three Phase-5-specific routes (importable as ``include_router(...)``):

  - ``GET /api/runs/{run_id}/detail``       — run lifecycle + V9 health
  - ``GET /api/runs/{run_id}/impact``       — memory hits + skill hits + token / event impact
  - ``GET /api/runs/{run_id}/compare``      — baseline vs candidate validation comparison
  - ``GET /api/validations/{validation_id}`` — full ValidationReport detail

These endpoints intentionally **do not** depend on SaaS / RunService —
they read from :class:`stable_agent.observation.run_store.RunStore` and
:class:`stable_agent.api.validation_store.ValidationReportStore`. That
keeps the Observer console runnable in CLI / LocalRuntime mode.

Phase 0 contract is preserved: callers that just want CLI envelope keep
hitting :func:`stable_agent.core.os_agent_handler.run_os_agent`. These
APIs are additive (read-only).
"""

from stable_agent.api.compare_api import build_compare_router
from stable_agent.api.impact_api import build_impact_router, build_impact_report
from stable_agent.api.run_detail_api import build_run_detail_router
from stable_agent.api.validation_store import ValidationReportStore

__all__ = [
    "ValidationReportStore",
    "build_compare_router",
    "build_impact_report",
    "build_impact_router",
    "build_run_detail_router",
]
