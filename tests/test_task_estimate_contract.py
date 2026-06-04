"""
OS-Agent P2.2 — Task Estimate Contract Tests
Tests the `task estimate` CLI command and its h-agent-v1 contract output.
"""
import subprocess
import json
import sys
import os
import pytest

PYTHON = sys.executable
CLI_MODULE = "stable_agent.cli"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_estimate(task_input: str) -> dict:
    """Run task estimate and return parsed JSON output."""
    env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
    result = subprocess.run(
        [PYTHON, "-m", CLI_MODULE, "task", "estimate", "--task-input", task_input, "--json"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    return json.loads(result.stdout)


def test_estimate_normal_task():
    """Normal task should return low or medium risk."""
    data = run_estimate("检查项目结构")
    assert data["ok"] is True
    assert data["estimated_risk"] in ("low", "medium")
    assert data["contract_version"] == "h-agent-v1"


def test_estimate_dangerous_task():
    """Dangerous task should return high risk."""
    data = run_estimate("rm -rf /")
    assert data["ok"] is True
    assert data["estimated_risk"] == "high"
    assert data["requires_approval"] is True


def test_output_has_contract_version():
    """Output must include contract_version field."""
    data = run_estimate("列出文件")
    assert "contract_version" in data
    assert data["contract_version"] == "h-agent-v1"


def test_output_has_estimated_risk():
    """Output must include estimated_risk field."""
    data = run_estimate("读取配置文件")
    assert "estimated_risk" in data
    assert data["estimated_risk"] in ("low", "medium", "high")


def test_output_has_requires_approval():
    """Output must include requires_approval field."""
    data = run_estimate("更新依赖")
    assert "requires_approval" in data
    assert isinstance(data["requires_approval"], bool)
