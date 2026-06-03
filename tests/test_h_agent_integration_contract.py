"""H-Agent Integration Contract Tests."""
import json
import subprocess
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_normalize_success():
    from stable_agent.cli import normalize_h_agent_output
    data = {"ok": True, "run_id": "run_123", "output_text": "hello", "eval_passed": True, "eval_score": 0.9}
    result = normalize_h_agent_output(data)
    assert result["ok"] is True
    assert result["contract_version"] == "h-agent-v1"
    assert result["output_text"] == "hello"
    assert result["error"] is None


def test_normalize_failure():
    from stable_agent.cli import normalize_h_agent_output
    data = {"ok": False, "error": "something broke"}
    result = normalize_h_agent_output(data)
    assert result["ok"] is False
    assert result["contract_version"] == "h-agent-v1"
    assert result["error"] == "something broke"
    # output_text auto-fill only happens on success; on failure it stays ""
    assert result["output_text"] == ""


def test_normalize_auto_fill_error():
    from stable_agent.cli import normalize_h_agent_output
    data = {"ok": False}
    result = normalize_h_agent_output(data)
    assert result["error"] == "工具调用失败，原因未知"


def test_normalize_output_text_always_exists():
    from stable_agent.cli import normalize_h_agent_output
    data = {"ok": True}
    result = normalize_h_agent_output(data)
    assert "output_text" in result
    assert isinstance(result["output_text"], str)


def test_normalize_legacy_fields():
    from stable_agent.cli import normalize_h_agent_output
    data = {"ok": True, "text": "legacy text output", "raw": {"foo": "bar"}}
    result = normalize_h_agent_output(data)
    assert result["output_text"] == "legacy text output"
