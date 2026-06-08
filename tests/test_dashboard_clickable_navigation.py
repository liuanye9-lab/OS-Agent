from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routes.dashboard import register_pages


def test_observer_sidebar_uses_clickable_navigation_targets():
    html = Path("web/templates/run_observer.html").read_text(encoding="utf-8")

    assert 'id="navDashboardLink"' in html
    assert 'id="navTasksLink"' in html
    assert 'href="/observer"' in html
    assert 'href="/effectiveness"' in html
    assert 'href="/dashboard/timeline"' in html
    assert 'href="/dashboard/analytics"' in html
    assert 'href="/dashboard/review"' in html
    assert 'href="/connect"' in html
    assert 'href="/help"' in html
    assert 'onclick="exportRunSnapshot()"' in html
    assert 'src="/static/run_observer.js?v=20260608-readme-visual"' in html


def test_observer_script_reads_path_injected_run_id():
    js = Path("web/static/run_observer.js").read_text(encoding="utf-8")

    assert 'document.querySelector(\'meta[name="run-id"]\')' in js
    assert 'params.get("run_id") || (runMeta ? runMeta.content : "")' in js
    assert 'navDashboardLink.href = `/observe/${encodeURIComponent(runId)}`' in js
    assert 'navTasksLink.href = `/effectiveness?run_id=${encodeURIComponent(runId)}`' in js
    assert 'effLink.href = `/effectiveness?run_id=${encodeURIComponent(runId)}`' in js
    assert "function loadEffectivenessLayer" in js
    assert 'fetch("/api/effectiveness/summary")' in js


def test_observer_contains_unified_dashboard_layers():
    html = Path("web/templates/run_observer.html").read_text(encoding="utf-8")

    assert 'id="overviewSection"' in html
    assert 'id="effectivenessSection"' in html
    assert 'id="reviewSection"' in html
    assert 'id="connectSection"' in html
    assert 'id="effectivenessRows"' in html
    assert 'id="mcpConfigBlock"' in html


def test_dashboard_navigation_targets_render_standalone_pages():
    app = FastAPI()
    register_pages(app, "web/templates")
    client = TestClient(app, follow_redirects=False)

    expected = {
        "/effectiveness": "Effectiveness Dashboard",
        "/effectiveness?run_id=run_123": "Effectiveness Dashboard",
        "/dashboard/timeline": "Timeline",
        "/dashboard/analytics": "Analytics",
        "/dashboard/review": "Review",
        "/connect": "Connect",
        "/help": "Help",
    }
    for path, marker in expected.items():
        resp = client.get(path)
        assert resp.status_code == 200
        assert marker in resp.text
        assert "#effectivenessSection" not in str(resp.url)
