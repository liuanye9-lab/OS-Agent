"""test_cli_feedback — V11.4 CLI feedback 命令测试。"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from unittest.mock import patch
import pytest
CLI_MODULE = "stable_agent.cli"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestFeedbackParser:
    def test_feedback_command_exists(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "feedback", "--help"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode == 0
        assert "remember" in result.stdout
        assert "dont" in result.stdout
        assert "correct" in result.stdout

    def test_remember_requires_run_id_and_note(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "feedback", "remember"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

    def test_dont_requires_run_id_and_note(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "feedback", "dont"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

    def test_correct_requires_run_id_phrase_meaning(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "feedback", "correct"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."})
        assert result.returncode != 0

class TestFeedbackExecution:
    def test_server_not_running_returns_error(self):
        result = subprocess.run([sys.executable, "-m", "stable_agent.cli", "feedback", "remember",
            "--run-id", "run_test", "--note", "test", "--json", "--port", "19999"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "."}, timeout=10)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["ok"] is False

    @patch(f"{CLI_MODULE}._http_post")
    def test_remember_json_output(self, mock_post):
        mock_post.return_value = {"ok": True, "action": "remember", "run_id": "run_test", "generated": {"memory_update_candidate": True}}
        from stable_agent.cli import cmd_feedback_remember
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(run_id="run_test", note="test", json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_feedback_remember(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["action"] == "remember"

    @patch(f"{CLI_MODULE}._http_post")
    def test_dont_json_output(self, mock_post):
        mock_post.return_value = {"ok": True, "action": "dont_do_this_again", "run_id": "run_test", "generated": {"bad_case": True}}
        from stable_agent.cli import cmd_feedback_dont
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(run_id="run_test", note="dont", json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_feedback_dont(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["action"] == "dont_do_this_again"

    @patch(f"{CLI_MODULE}._http_post")
    def test_correct_json_output(self, mock_post):
        mock_post.return_value = {"ok": True, "action": "correct_and_remember", "run_id": "run_test", "generated": {"expression_rule_candidate": True}}
        from stable_agent.cli import cmd_feedback_correct
        import argparse, io
        from contextlib import redirect_stdout
        args = argparse.Namespace(run_id="run_test", phrase="不要AI味", meaning="避免模板化表达", json=True, host="127.0.0.1", port=8000)
        f = io.StringIO()
        with redirect_stdout(f): cmd_feedback_correct(args)
        data = json.loads(f.getvalue())
        assert data["ok"] is True
        assert data["action"] == "correct_and_remember"
