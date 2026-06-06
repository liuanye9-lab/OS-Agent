"""test_cli_effectiveness — V11.4 CLI effectiveness 命令测试。"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import pytest
CLI_MODULE = "stable_agent.cli"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestEffectivenessParser:
    def test_effectiveness_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "effectiveness", "--help"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "summary" in result.stdout
        assert "task" in result.stdout
        assert "run" in result.stdout

    def test_effectiveness_task_create_requires_args(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "effectiveness", "task", "create"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

    def test_effectiveness_run_record_requires_args(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "effectiveness", "run", "record"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

class TestEffectivenessExecution:
    def test_server_not_running_returns_error(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "effectiveness", "summary",
            "--json", "--port", "19999"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."}, timeout=10)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["ok"] is False

    @patch(f"{CLI_MODULE}._http_get")
    def test_summary_json_output(self, mock_get):
        mock_get.return_value = {"ok": True, "total_tasks": 5, "total_runs": 10}
        from stable_agent.cli import cmd_effectiveness_summary
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_effectiveness_summary(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["total_tasks"] == 5

    @patch(f"{CLI_MODULE}._http_post")
    def test_task_create_json_output(self, mock_post):
        mock_post.return_value = {"ok": True, "task": {"task_id": "T01"}}
        from stable_agent.cli import cmd_effectiveness_task_create
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(task_id="T01", description="test", category="coding", json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_effectiveness_task_create(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True

    @patch(f"{CLI_MODULE}._http_post")
    def test_run_record_json_output(self, mock_post):
        mock_post.return_value = {"ok": True, "run": {"run_id": "r01", "mode": "stableagent"}}
        from stable_agent.cli import cmd_effectiveness_run_record
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(task_id="T01", mode="stableagent", model="codex",
            stableagent_run_id="run_xxx", success=True, test_passed=True,
            intent_drift=False, over_editing=False, constraint_preserved=True,
            rework_count=1, estimated_tokens=12000, user_satisfaction=4,
            json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_effectiveness_run_record(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
