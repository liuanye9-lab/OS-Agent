import json
import os
import subprocess
import sys


def test_integration_doctor_contract():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, "-m", "stable_agent.cli", "integration", "doctor", "--json"],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": project_root},
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(result.stdout)
    assert data["contract_version"] == "h-agent-v1"
    assert data["os_agent_tool"]["ok"] is True
    assert data["contract_normalize"]["ok"] is True
