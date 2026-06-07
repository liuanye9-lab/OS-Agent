"""test_agent_rule_files_cli_fallback — V11.4 AGENTS.md/CLAUDE.md CLI fallback 规则测试。"""
from __future__ import annotations
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestAgentRulesCliFallback:
    def _read_file(self, name: str) -> str:
        path = PROJECT_ROOT / name
        assert path.exists(), f"{name} 不存在"
        return path.read_text(encoding="utf-8")

    def test_agents_md_has_calling_priority_section(self):
        assert "StableAgent Calling Priority" in self._read_file("AGENTS.md")

    def test_agents_md_prefers_mcp(self):
        assert "Prefer MCP" in self._read_file("AGENTS.md")

    def test_agents_md_has_cli_fallback(self):
        assert "python -m stable_agent.cli task run" in self._read_file("AGENTS.md")

    def test_agents_md_cli_uses_task_input(self):
        assert "--task-input" in self._read_file("AGENTS.md")

    def test_agents_md_cli_json_flag(self):
        assert "--json" in self._read_file("AGENTS.md")

    def test_agents_md_cli_open_dashboard(self):
        assert "--open-dashboard" in self._read_file("AGENTS.md")

    def test_claude_md_has_calling_priority_section(self):
        assert "StableAgent Calling Priority" in self._read_file("CLAUDE.md")

    def test_claude_md_prefers_mcp(self):
        assert "Prefer MCP" in self._read_file("CLAUDE.md")

    def test_claude_md_has_cli_fallback(self):
        assert "python -m stable_agent.cli task run" in self._read_file("CLAUDE.md")

    def test_claude_md_cli_uses_task_input(self):
        assert "--task-input" in self._read_file("CLAUDE.md")

    def test_claude_md_cli_json_flag(self):
        assert "--json" in self._read_file("CLAUDE.md")

    def test_claude_md_cli_open_dashboard(self):
        assert "--open-dashboard" in self._read_file("CLAUDE.md")
