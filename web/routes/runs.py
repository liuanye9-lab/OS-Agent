"""Run API 路由 — /api/runs/*"""
from __future__ import annotations

import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("uvicorn")


def register_run_routes(app: FastAPI, gateway_run_store=None, dash_sync=None) -> None:
    @app.get("/api/runs/recent")
    async def api_recent_runs(limit: int = 10):
        """V6.3: 列出最近 runs（含已完成/失败），首页着陆页使用。"""
        try:
            store = gateway_run_store
            if store is None:
                return {"total": 0, "runs": [], "success_rate": 0}
            if hasattr(store, 'list_recent_runs'):
                return store.list_recent_runs(limit=limit)
            # fallback: 使用 list_active_runs
            if hasattr(store, 'list_active_runs'):
                runs = store.list_active_runs(limit=limit)
                return {"total": len(runs), "runs": runs, "success_rate": 0}
            return {"total": 0, "runs": [], "success_rate": 0}
        except Exception as e:
            return {"total": 0, "runs": [], "success_rate": 0, "error": str(e)}

    @app.post("/api/runs")
    async def api_create_run(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.create_run(body.get("workspace_id", ""), body.get("project_id", ""),
                agent_id=body.get("agent_id", ""), user_task=body.get("user_task", ""))
            return {"run_id": run.run_id, "status": run.status, "dashboard_url": run.dashboard_url}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}")
    async def api_get_run(run_id: str):
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.get_run(run_id)
            if run is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {"run_id": run.run_id, "status": run.status, "progress_pct": run.progress_pct,
                    "overall_score": run.overall_score, "token_used": run.token_used,
                    "dashboard_url": run.dashboard_url, "user_task": run.user_task}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}/detail")
    async def api_get_run_detail(run_id: str):
        try:
            from stable_agent.saas import RunService, SaasRepository
            svc = RunService(SaasRepository())
            run = svc.get_run(run_id)
            if run is None:
                return JSONResponse({"error": "not found"}, status_code=404)
            return {
                "run_id": run.run_id, "status": run.status,
                "progress_pct": run.progress_pct, "overall_score": run.overall_score,
                "intent_alignment_score": run.intent_alignment_score,
                "token_used": run.token_used, "cost_estimate": run.cost_estimate,
                "dashboard_url": run.dashboard_url, "trace_url": run.trace_url,
                "user_task": run.user_task, "started_at": run.started_at,
                "ended_at": run.ended_at, "workspace_id": run.workspace_id,
                "project_id": run.project_id, "agent_id": run.agent_id,
            }
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str):
        try:
            store = gateway_run_store
            if store is None:
                return JSONResponse(
                    {"error": "gateway_run_store unavailable", "run_id": run_id},
                    status_code=503,
                )
            import dataclasses
            events = store.get_events(run_id)
            # V9.2: run_id 不存在于 RunStore → 返回 404
            run_status = store.get_run_status(run_id)
            if run_status is None:
                return JSONResponse(
                    {"error": "run not found", "run_id": run_id},
                    status_code=404,
                )
            result = []
            for e in events:
                if dataclasses.is_dataclass(e):
                    result.append(dataclasses.asdict(e))
                elif isinstance(e, dict):
                    result.append(e)
                else:
                    result.append({"raw": str(e)})
            # V10: 结构化返回，含 event_count
            return {
                "run_id": run_id,
                "event_count": len(result),
                "events": result,
            }
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").exception("get_run_events failed: %s", e)
            return JSONResponse(
                {"error": str(e), "run_id": run_id},
                status_code=500,
            )

    @app.get("/api/runs/{run_id}/summary")
    async def get_run_summary(run_id: str):
        try:
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "error": "gateway run store unavailable"}
            return store.get_run_summary(run_id)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"get_run_summary failed: {e}")
            return {"run_id": run_id, "error": str(e)}

    @app.post("/api/runs/{run_id}/feedback")
    async def submit_run_feedback(run_id: str, request: Request):
        try:
            body = await request.json()
            from stable_agent.observation.user_feedback_signal import UserFeedbackSignal
            import uuid
            fb = UserFeedbackSignal(
                feedback_id=str(uuid.uuid4()), run_id=run_id,
                signal_type=body.get("label", body.get("signal_type", "")),
                comment=body.get("comment", ""),
            )
            if dash_sync:
                try:
                    dash_sync.sync_feedback(fb.to_dict())
                except Exception as exc:
                    logger.warning("dash_sync.sync_feedback failed: %s", exc)
            return {"ok": True, "feedback_id": fb.feedback_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ===================================================================
    # V11.1: Run 级 API — understanding / token / learning / badcases
    # ===================================================================

    def _find_event_by_type(events: list, event_type: str) -> dict | None:
        """从事件列表中查找最新匹配类型的事件。"""
        for e in reversed(events):
            if isinstance(e, dict) and e.get("event_type") == event_type:
                return e
        return None

    @app.get("/api/runs/{run_id}/understanding")
    async def get_run_understanding(run_id: str):
        """获取 Understanding Trace — 从 RunStore events 中提取。"""
        try:
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "ok": False, "error": "store unavailable"}
            events = store.get_events(run_id)
            if not events:
                return {"run_id": run_id, "ok": False, "understanding_trace": None, "event_found": False}
            evt = _find_event_by_type(events, "understanding.trace.created")
            if evt is None:
                return {"run_id": run_id, "ok": False, "understanding_trace": None, "event_found": False}
            return {
                "run_id": run_id,
                "ok": True,
                "understanding_trace": evt.get("understanding_trace"),
                "event_found": True,
            }
        except Exception as e:
            logger.warning("get_run_understanding failed: %s", e)
            return {"run_id": run_id, "ok": False, "error": str(e)}

    @app.get("/api/runs/{run_id}/token")
    async def get_run_token(run_id: str):
        """获取 Token Report — 优先从 BudgetLedger，fallback 从 events。"""
        try:
            # 先尝试 BudgetLedger
            try:
                from stable_agent.token.budget_ledger import BudgetLedger
                from stable_agent.capsule.capsule_manager import ensure_capsule
                capsule_path = ensure_capsule()
                db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
                ledger = BudgetLedger(db_path=db_path)
                record = ledger.get_run_record(run_id)
                if record:
                    return {"run_id": run_id, "ok": True, "token_report": record.to_dict()}
            except Exception as exc:
                logger.debug("BudgetLedger lookup failed, falling back to events: %s", exc)
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "ok": False, "token_report": None}
            events = store.get_events(run_id)
            evt = _find_event_by_type(events, "token.budget.estimated")
            if evt and "token_report" in evt:
                return {"run_id": run_id, "ok": True, "token_report": evt["token_report"]}
            return {"run_id": run_id, "ok": False, "token_report": None}
        except Exception as e:
            logger.warning("get_run_token failed: %s", e)
            return {"run_id": run_id, "ok": False, "error": str(e)}

    @app.get("/api/runs/{run_id}/learning")
    async def get_run_learning(run_id: str):
        """获取 Learning Events — 从 RunStore 提取自我优化相关事件。"""
        try:
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "ok": False, "learning_events": []}
            events = store.get_events(run_id)
            learning_types = {
                "self_improvement.checked", "regression.generated",
                "memory.update.candidate", "skill.patch.proposed",
                "validation.checked", "human_review.required",
                # V11.2: feedback events
                "feedback.received", "bad_case.recorded",
                "eval_case.generated", "expression.rule.candidate",
            }
            learning_events = [
                e for e in events
                if isinstance(e, dict) and e.get("event_type") in learning_types
            ]
            # 生成摘要
            si_evt = _find_event_by_type(events, "self_improvement.checked")
            summary = {}
            if si_evt:
                summary = {
                    "learning_triggered": si_evt.get("learning_triggered", False),
                    "validation_passed": si_evt.get("validation_passed"),
                    "regression_cases": si_evt.get("regression_cases", 0),
                    "memory_candidates": si_evt.get("memory_candidates", 0),
                    "skill_patches": si_evt.get("skill_patches", 0),
                    "human_review_status": si_evt.get("human_review_status", "none"),
                }
            return {
                "run_id": run_id,
                "ok": True,
                "learning_events": learning_events,
                "summary": summary,
            }
        except Exception as e:
            logger.warning("get_run_learning failed: %s", e)
            return {"run_id": run_id, "ok": False, "learning_events": [], "error": str(e)}

    @app.get("/api/runs/{run_id}/badcases")
    async def get_run_badcases(run_id: str):
        """获取 Bad Cases — 从 learning events 中提取。"""
        try:
            store = gateway_run_store
            if store is None:
                return {"run_id": run_id, "ok": True, "badcases": []}
            events = store.get_events(run_id)
            badcases = [
                e for e in events
                if isinstance(e, dict) and e.get("event_type") in ("regression.generated", "bad_case.recorded")
            ]
            return {"run_id": run_id, "ok": True, "badcases": badcases}
        except Exception as e:
            logger.warning("get_run_badcases failed: %s", e)
            return {"run_id": run_id, "ok": True, "badcases": []}
