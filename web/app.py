"""StableAgent Cloud — 主应用工厂。

模块化架构：
- routes/dashboard.py: 页面路由
- routes/auth.py: 认证 API
- routes/workspaces.py: 工作区 API
- routes/projects.py: 项目 API
- routes/runs.py: 运行 API
- routes/approvals.py: 审批 API
- routes/reviews.py: 审核 API
- routes/api.py: 通用 API (usage/audit/skills/keys/eval/connect)
- dependencies.py: 权限 Guard

Usage:
    uvicorn web.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logger = logging.getLogger("uvicorn")


def create_app() -> FastAPI:
    """创建完整的 StableAgent Cloud 应用。"""
    # ------------------------------------------------------------------
    # 0. LLM Client — 全局注入，所有模块共享
    # ------------------------------------------------------------------
    from stable_agent.llm_factory import get_llm_client
    llm_client = get_llm_client()
    logger.info("LLM 客户端: %s", type(llm_client).__name__)

    # ------------------------------------------------------------------
    # 1. Core modules
    # ------------------------------------------------------------------
    from stable_agent.context_decision_engine import ContextDecisionEngine
    from stable_agent.context_budget_manager import ContextBudgetManager
    from stable_agent.memory_router import MemoryBank, MemoryRouter
    from stable_agent.eval_and_bad_case import BadCaseManager, Evaluator
    from stable_agent.workflow_state_machine import WorkflowEngine
    from stable_agent.trace_event_bus import EventBus
    # V6.0: MCPServer import removed — /mcp/legacy deprecated

    event_bus = EventBus()
    decision_engine = ContextDecisionEngine()
    budget_manager = ContextBudgetManager()
    memory_router = MemoryRouter(MemoryBank())
    evaluator = Evaluator(llm_client=llm_client)
    bad_case_manager = BadCaseManager()
    workflow_engine = WorkflowEngine(
        decision_engine=decision_engine, budget_manager=budget_manager,
        memory_router=memory_router, evaluator=evaluator,
        bad_case_manager=bad_case_manager, event_bus=event_bus,
        llm_client=llm_client,  # 注入真实 LLM 客户端
    )

    orchestrator = None
    try:
        from stable_agent.orchestrator import StableAgentOrchestrator
        orchestrator = StableAgentOrchestrator(
            evaluator=evaluator,
            llm_client=llm_client,
        )
        logger.info("Orchestrator 已创建 (LLM: %s)", type(llm_client).__name__)
    except Exception as e:
        logger.warning("Orchestrator 创建失败 (网关模式): %s", e)

    # V6.0: MCPToolRegistry (V3) 不再需要，V5 UnifiedToolRegistry 在 gateway 中使用    # ------------------------------------------------------------------
    # 2. FastAPI app
    # ------------------------------------------------------------------
    app = FastAPI(title="StableAgent Cloud", version="2.2.0",
                  docs_url="/docs", redoc_url="/redoc")

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # 3. MCP Gateway mounts
    # ------------------------------------------------------------------
    gateway_run_store = None
    dash_sync = None
    try:
        from stable_agent.gateway.mcp_gateway import MCPGateway
        from stable_agent.observation.dashboard_sync import DashboardSync
        # V11.5: 注入 SQLite db_path 到 RunStore
        from pathlib import Path
        _db_path = str(Path.cwd() / "data" / "run_events.sqlite")
        os.makedirs(os.path.dirname(_db_path), exist_ok=True)
        gateway = MCPGateway(orchestrator=orchestrator, db_path=_db_path)
        gateway_run_store = gateway.run_store
        app.mount("/mcp", gateway.create_fastapi_app())
        dash_sync = DashboardSync(gateway.event_stream)
        app.mount("/dashboard-sync", dash_sync.create_app())
    except Exception as e:
        logger.warning(f"V5 MCP Gateway mount skipped: {e}")

    # V6.2: V3/V4 MCP 已物理删除（mcp_server.py, mcp_tools.py, mcp/skillopt_tools.py）
    logger.info("V6.2: /mcp/legacy 及相关 V3/V4 MCP 已物理删除")

    # ------------------------------------------------------------------
    # 4. Static files + templates
    # ------------------------------------------------------------------
    web_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(web_dir, "static")
    templates_dir = os.path.join(web_dir, "templates")

    _404_html = os.path.join(templates_dir, "404.html")

    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc):
        if os.path.exists(_404_html):
            with open(_404_html, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=404)
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)

    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ------------------------------------------------------------------
    # 5. Register all module routes
    # ------------------------------------------------------------------
    from web.routes.dashboard import register_pages
    from web.routes.auth import register_auth_routes
    from web.routes.workspaces import register_workspace_routes
    from web.routes.projects import register_project_routes
    from web.routes.runs import register_run_routes
    from web.routes.approvals import register_approval_routes
    from web.routes.reviews import register_review_routes
    from web.routes.api import register_api_routes

    # Pages (must be before Dashboard mount)
    register_pages(app, templates_dir)

    # Dashboard mount (after pages)
    from stable_agent.dashboard import Dashboard
    dashboard = Dashboard(event_bus, orchestrator=orchestrator)
    dashboard.mount_to(app, prefix="/dashboard")

    # API routes
    register_auth_routes(app)
    register_workspace_routes(app)
    register_project_routes(app)
    register_run_routes(app, gateway_run_store, dash_sync)
    register_approval_routes(app)
    register_review_routes(app, orchestrator) if orchestrator else None

    # V11.2: Wire FeedbackLearningService for real feedback closed loop
    feedback_service = None
    try:
        from stable_agent.feedback.feedback_learning_service import FeedbackLearningService
        feedback_service = FeedbackLearningService()
        logger.info("FeedbackLearningService initialized")
    except Exception as exc:
        logger.warning("FeedbackLearningService init failed: %s", exc)

    register_api_routes(app, dash_sync, gateway_run_store=gateway_run_store, feedback_service=feedback_service)

    # V11.3: Wire Effectiveness Dashboard
    effectiveness_store = None
    try:
        from stable_agent.effectiveness import ExperimentStore
        from web.routes.effectiveness import register_effectiveness_routes
        effectiveness_store = ExperimentStore()
        register_effectiveness_routes(app, effectiveness_store)
        logger.info("Effectiveness Dashboard routes registered")
    except Exception as exc:
        logger.warning("Effectiveness Dashboard init failed: %s", exc)

    # V11.3: Effectiveness page route — 已在 register_pages 中注册，此处跳过避免重复
    logger.info("Effectiveness page route registered via register_pages")

    return app
