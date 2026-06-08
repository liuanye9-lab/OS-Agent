"""Dashboard 页面路由 — /, /dashboard/*, /runs/{id}, /login, /connect."""
from __future__ import annotations

import os
from fastapi.responses import HTMLResponse


def _serve_html(path: str) -> HTMLResponse:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Page not found</h1>", status_code=404)


def _standalone_page(title: str, subtitle: str, active: str, body: str) -> HTMLResponse:
    """Render lightweight standalone dashboard pages with the observer visual shell."""
    nav_items = [
        ("overview", "/observer", "▦", "Overview"),
        ("effectiveness", "/effectiveness", "☑", "Effectiveness"),
        ("timeline", "/dashboard/timeline", "◷", "Timeline"),
        ("analytics", "/dashboard/analytics", "↗", "Analytics"),
        ("review", "/dashboard/review", "◎", "Review"),
    ]
    general_items = [
        ("connect", "/connect", "⚙", "Connect"),
        ("help", "/help", "?", "Help"),
    ]
    nav_html = "\n".join(
        f'<a class="nav-item{" active" if key == active else ""}" href="{href}"><span class="nav-icon">{icon}</span> {label}</a>'
        for key, href, icon, label in nav_items
    )
    general_html = "\n".join(
        f'<a class="nav-item{" active" if key == active else ""}" href="{href}"><span class="nav-icon">{icon}</span> {label}</a>'
        for key, href, icon, label in general_items
    )
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — StableAgent OS</title>
<link rel="stylesheet" href="/static/run_observer.css?v=20260608-readme-visual">
</head>
<body>
<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">S</div>
      <div>
        <div class="brand-title">StableAgent</div>
        <div class="brand-subtitle">Recursive Suite</div>
      </div>
    </div>
    <nav>
      <div class="nav-section-title">Menu</div>
      <div class="nav-list">{nav_html}</div>
    </nav>
    <nav class="sidebar-footer">
      <div class="nav-section-title">General</div>
      <div class="nav-list">{general_html}</div>
      <div class="mcp-status">已连接</div>
    </nav>
  </aside>
  <main class="workspace">
    <header class="top-bar">
      <label class="search-box" aria-label="Search">
        <span>⌕</span>
        <input type="search" placeholder="Search dashboard" />
        <span class="search-kbd">⌘F</span>
      </label>
      <div></div>
      <div class="header-actions">
        <a class="secondary-action" href="/observer">Back to Overview</a>
      </div>
    </header>
    <section class="hero-row">
      <div>
        <h1 class="task-name">{title}</h1>
        <div class="run-id">{subtitle}</div>
      </div>
    </section>
    {body}
  </main>
</div>
</body>
</html>""")


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
        # V6.2: 默认首页重定向到 run_observer（推荐入口）
        if os.path.exists(_observer):
            with open(_observer, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return _serve_html(_dash)

    @app.get("/dashboard")
    async def dashboard_legacy(): return _serve_html(_observer)

    @app.get("/dashboard/v2")
    async def dashboard_v2():
        # V6.2: 已收敛到 observer，302 重定向
        return HTMLResponse(
            content='<html><head><meta http-equiv="refresh" content="0;url=/observer"></head>'
            '<body><p>重定向到 <a href="/observer">实时观察器</a>...</p></body></html>',
            status_code=302,
            headers={"Location": "/observer"},
        )

    @app.get("/runs/{run_id}")
    async def run_page(run_id: str):
        # V6.2: /runs/{id} 改为 redirect 到 observer
        return HTMLResponse(
            content=f'<html><head><meta http-equiv="refresh" content="0;url=/observe/{run_id}"></head>'
            f'<body><p>重定向到 <a href="/observe/{run_id}">实时观察器</a>...</p></body></html>',
            status_code=302,
            headers={"Location": f"/observe/{run_id}"},
        )

    @app.get("/dashboard/v3")
    async def dashboard_v3():
        # V6.2: 重定向到 observer
        return HTMLResponse(
            content='<html><head><meta http-equiv="refresh" content="0;url=/observer"></head>'
            '<body><p>重定向到 <a href="/observer">实时观察器</a>...</p></body></html>',
            status_code=302,
            headers={"Location": "/observer"},
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
    async def connect_page():
        return _standalone_page(
            "Connect",
            "MCP endpoint, dashboard health, and local setup",
            "connect",
            """
            <section class="unified-section">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Connect</h2>
                  <p class="panel-subtitle">StableAgent 本地连接配置和 Dashboard 健康入口。</p>
                </div>
              </div>
              <div class="unified-grid two-up">
                <article class="unified-card"><div class="card-kicker">MCP endpoint</div><h3>HTTP MCP</h3><pre class="code-block">{"mcpServers":{"stableagent":{"type":"http","url":"http://127.0.0.1:8000/mcp"}}}</pre></article>
                <article class="unified-card"><div class="card-kicker">Dashboard</div><h3>Observer URL</h3><pre class="code-block">http://127.0.0.1:8000/observer</pre></article>
              </div>
            </section>
            """,
        )

    @app.get("/dashboard/timeline")
    async def timeline_page():
        return _standalone_page(
            "Timeline",
            "Run event replay and live observer history",
            "timeline",
            """
            <section class="unified-section">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Timeline</h2>
                  <p class="panel-subtitle">独立页面入口，用于查看 run 事件、回放状态和同步健康。</p>
                </div>
              </div>
              <div class="unified-grid three-up">
                <article class="unified-card"><div class="card-kicker">Replay</div><h3>API history</h3><p>通过 /api/runs/{run_id}/events 回放历史事件。</p></article>
                <article class="unified-card"><div class="card-kicker">Live</div><h3>WebSocket channel</h3><p>实时事件仍在 Observer 页面中持续更新。</p></article>
                <article class="unified-card"><div class="card-kicker">Fallback</div><h3>Refresh safety</h3><p>刷新页面后使用历史事件恢复可见状态。</p></article>
              </div>
            </section>
            """,
        )

    @app.get("/dashboard/analytics")
    async def analytics_page():
        return _standalone_page(
            "Analytics",
            "Project analytics and activity summary",
            "analytics",
            """
            <section class="unified-section">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Analytics</h2>
                  <p class="panel-subtitle">StableAgent 运行趋势、效率指标和项目活动总览。</p>
                </div>
              </div>
              <div class="unified-grid four-up">
                <article class="unified-stat"><div class="stat-label">Runs</div><div class="stat-value">--</div></article>
                <article class="unified-stat"><div class="stat-label">Events</div><div class="stat-value">--</div></article>
                <article class="unified-stat"><div class="stat-label">Validated</div><div class="stat-value good">--</div></article>
                <article class="unified-stat"><div class="stat-label">Needs Data</div><div class="stat-value muted">--</div></article>
              </div>
            </section>
            """,
        )

    @app.get("/help")
    async def help_page():
        return _standalone_page(
            "Help",
            "Default OSAgent command and dashboard entry points",
            "help",
            """
            <section class="unified-section">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Help</h2>
                  <p class="panel-subtitle">常用调用方式和本地 Dashboard 入口。</p>
                </div>
              </div>
              <div class="unified-grid two-up">
                <article class="unified-card"><div class="card-kicker">Task command</div><h3>Run OSAgent</h3><pre class="code-block">PYTHONPATH=. ./.venv/bin/python -m stable_agent.cli task run --task-input "你的任务" --open-dashboard --json</pre></article>
                <article class="unified-card"><div class="card-kicker">Dashboard</div><h3>Open observer</h3><pre class="code-block">http://127.0.0.1:8000/observer</pre></article>
              </div>
            </section>
            """,
        )

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
    async def effectiveness_page():
        return _serve_html(_effectiveness)
