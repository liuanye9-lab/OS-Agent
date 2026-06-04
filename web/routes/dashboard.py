"""Dashboard 页面路由 — /, /dashboard/*, /runs/{id}, /login, /connect."""
from __future__ import annotations

import os
from fastapi import Request
from fastapi.responses import HTMLResponse


def _serve_html(path: str) -> HTMLResponse:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Page not found</h1>", status_code=404)


def register_pages(app, templates_dir: str) -> None:
    """注册所有页面路由。"""
    _dash = os.path.join(templates_dir, "dashboard.html")
    _dash_v2 = os.path.join(templates_dir, "dashboard_v2.html")
    _dash_v3 = os.path.join(templates_dir, "dashboard_v3.html")
    _usage = os.path.join(templates_dir, "usage.html")
    _apikeys = os.path.join(templates_dir, "apikeys.html")
    _billing = os.path.join(templates_dir, "billing.html")
    _team = os.path.join(templates_dir, "team.html")
    _skills = os.path.join(templates_dir, "skills.html")
    _review = os.path.join(templates_dir, "review.html")
    _login = os.path.join(templates_dir, "login.html")
    _connect = os.path.join(templates_dir, "connect.html")
    _observer = os.path.join(templates_dir, "run_observer.html")

    @app.get("/")
    async def root():
        # V6.3: 首页展示系统状态着陆页（而非空 observer）
        _home = os.path.join(templates_dir, "home.html")
        if os.path.exists(_home):
            with open(_home, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        # fallback: 直接提供 observer
        if os.path.exists(_observer):
            with open(_observer, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return _serve_html(_dash)

    @app.get("/dashboard")
    async def dashboard_legacy(): return _serve_html(_dash)

    @app.get("/dashboard/v2")
    async def dashboard_v2():
        # V6.3: 已收敛到首页着陆
        return HTMLResponse(
            content='<html><head><meta http-equiv="refresh" content="0;url=/"></head>'
            '<body><p>重定向到 <a href="/">StableAgent</a>...</p></body></html>',
            status_code=302,
            headers={"Location": "/"},
        )

    @app.get("/runs/{run_id}")
    async def run_page(run_id: str):
        # V6.3: /runs/{id} 改为 redirect 到 observer 详情页
        return HTMLResponse(
            content=f'<html><head><meta http-equiv="refresh" content="0;url=/observe/{run_id}"></head>'
            f'<body><p>重定向到 <a href="/observe/{run_id}">实时观察器</a>...</p></body></html>',
            status_code=302,
            headers={"Location": f"/observe/{run_id}"},
        )

    @app.get("/dashboard/v3")
    async def dashboard_v3():
        # V6.3: 重定向到首页着陆
        return HTMLResponse(
            content='<html><head><meta http-equiv="refresh" content="0;url=/"></head>'
            '<body><p>重定向到 <a href="/">StableAgent</a>...</p></body></html>',
            status_code=302,
            headers={"Location": "/"},
        )

    # SaaS pages
    @app.get("/dashboard/usage")
    async def saas_usage(): return _serve_html(_usage)
    @app.get("/dashboard/apikeys")
    async def saas_apikeys(): return _serve_html(_apikeys)
    @app.get("/dashboard/billing")
    async def saas_billing(): return _serve_html(_billing)
    @app.get("/dashboard/team")
    async def saas_team(): return _serve_html(_team)
    @app.get("/dashboard/skills")
    async def saas_skills(): return _serve_html(_skills)
    @app.get("/dashboard/review")
    async def saas_review(): return _serve_html(_review)
    @app.get("/login")
    async def login_page(): return _serve_html(_login)
    @app.get("/connect")
    async def connect_page(): return _serve_html(_connect)

    @app.get("/observe/{run_id}")
    async def observe_run(run_id: str):
        if os.path.exists(_observer):
            with open(_observer, "r", encoding="utf-8") as f:
                html = f.read()
            html = html.replace("<head>", f'<head>\n    <meta name="run-id" content="{run_id}">')
            return HTMLResponse(content=html)
        return HTMLResponse(content="<h1>Observer page not found</h1>", status_code=404)

    @app.get("/observer")
    async def observer_page(): return _serve_html(_observer)

    # V11.3: Effectiveness Dashboard page
    _effectiveness = os.path.join(templates_dir, "effectiveness.html")
    @app.get("/effectiveness")
    async def effectiveness_page(): return _serve_html(_effectiveness)
