"""test_cli_task_run — V11.4 CLI task run 命令测试。"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import pytest

CLI_MODULE = "stable_agent.cli"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestTaskRunParser:
    def test_task_run_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "task", "run", "--help"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "task-input" in result.stdout or "task_input" in result.stdout

    def test_task_run_requires_task_input(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "task", "run"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

    def test_task_run_short_flag(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "task", "run", "-t", "test", "--help"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0

class TestTaskRunExecution:
    def test_server_not_running_returns_error(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "task", "run",
            "-t", "test task", "--json", "--port", "19999"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."}, timeout=10)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert "error" in data

    @patch(f"{CLI_MODULE}._http_post")
    def test_json_output_valid(self, mock_post):
        mock_post.return_value = {"result": {"ok": True, "isError": False, "structuredContent": {
            "run_id": "run_test123", "dashboard_url": "/runs/run_test123",
            "observer_url": "/observe/run_test123", "missing_required_events": [],
            "understanding_trace": {"interpreted_goal": "test"},
            "token_report": {"baseline_tokens_estimated": 100}, "expression_matches": []}}}
        from stable_agent.cli import cmd_task_run
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(task_input="test task", open_dashboard=False, json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_task_run(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["run_id"] == "run_test123"
        assert data["dashboard_url"].endswith("/runs/run_test123")

    @patch(f"{CLI_MODULE}._http_post")
    def test_run_id_parsed(self, mock_post):
        mock_post.return_value = {"result": {"ok": True, "isError": False, "structuredContent": {
            "run_id": "run_abc", "dashboard_url": "/runs/run_abc", "observer_url": "/observe/run_abc"}}}
        from stable_agent.cli import cmd_task_run
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(task_input="test", open_dashboard=False, json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_task_run(args)
        data = json.loads(f.getvalue())
        assert data["run_id"] == "run_abc"

    @patch(f"{CLI_MODULE}._http_post")
    def test_dashboard_url_parsed(self, mock_post):
        mock_post.return_value = {"result": {"ok": True, "isError": False, "structuredContent": {
            "run_id": "run_xyz", "dashboard_url": "/runs/run_xyz", "observer_url": "/observe/run_xyz"}}}
        from stable_agent.cli import cmd_task_run
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(task_input="test", open_dashboard=False, json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_task_run(args)
        data = json.loads(f.getvalue())
        assert data["dashboard_url"].endswith("/runs/run_xyz")
