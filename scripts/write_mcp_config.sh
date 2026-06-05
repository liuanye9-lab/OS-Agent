#!/usr/bin/env bash
# Phase 6 — emit a .mcp.json snippet wired to the in-process LocalRuntime.
#
# Usage:
#   ./scripts/write_mcp_config.sh <venv_dir> <project_root> [profile]
#
# Prints to stdout. The output is the JSON block users paste into their
# Claude Code / Codex / Cursor `.mcp.json`. We deliberately do NOT write
# the file ourselves — the user owns their host config.

set -euo pipefail

VENV_DIR="${1:?usage: write_mcp_config.sh <venv_dir> <project_root> [profile]}"
ROOT="${2:?missing project_root}"
PROFILE="${3:-minimal}"

PYTHON="$VENV_DIR/bin/python"

cat <<JSON
{
  "mcpServers": {
    "stableagent": {
      "type": "stdio",
      "command": "$PYTHON",
      "args": [
        "-m", "stable_agent.mcp_stdio",
        "--local",
        "--profile", "$PROFILE"
      ],
      "env": {
        "PYTHONPATH": "$ROOT",
        "STABLE_AGENT_RUNTIME_MODE": "local",
        "STABLE_AGENT_TOOL_PROFILE": "$PROFILE",
        "STABLE_AGENT_HARNESS_MODE": "1"
      }
    }
  }
}
JSON
