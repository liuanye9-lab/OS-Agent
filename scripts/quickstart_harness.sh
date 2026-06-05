#!/usr/bin/env bash
# Phase 6 — Harness quickstart.
#
# Usage:
#   ./scripts/quickstart_harness.sh
#
# What it does (idempotent, safe to re-run):
#   1. Detect / create the project venv at ./.venv
#   2. Install dependencies from requirements.txt
#   3. Run the doctor suite — Phase 0–6 contract tests in `--co` (collection)
#      mode so we don't spin the LocalRuntime if Python isn't ready yet
#   4. Print recommended `.mcp.json` block for Claude Code / Codex
#
# This is intentionally a thin shell wrapper, not a Python entry point —
# the goal is "user runs one command and sees concrete output", which
# shell handles better than argparse.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
PROFILE="${STABLE_AGENT_TOOL_PROFILE:-minimal}"

echo "==> OS-Agent Harness quickstart"
echo "    project root: $ROOT"
echo "    venv:         $VENV_DIR"
echo "    profile:      $PROFILE"
echo

# ---------------------------------------------------------------------------
# 1. venv
# ---------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    echo "==> creating venv at $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------------------
# 2. deps
# ---------------------------------------------------------------------------
echo "==> installing dependencies"
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ---------------------------------------------------------------------------
# 3. doctor — collection-only run of all Phase 0–6 tests
# ---------------------------------------------------------------------------
echo
echo "==> doctor: collecting harness tests"
PYTHONPATH="$ROOT" pytest --collect-only -q \
    tests/test_os_agent_contract_snapshot.py \
    tests/test_required_events_snapshot.py \
    tests/test_local_runtime_contract.py \
    tests/test_tool_profiles.py \
    tests/test_skill_repo_v2.py \
    tests/test_skill_signature_and_duplicate.py \
    tests/test_curator_candidate_pipeline.py \
    tests/test_delayed_validation_ab.py \
    tests/test_external_crawler_connectors.py \
    tests/test_indexer_bm25_and_dedupe.py \
    tests/test_observer_impact_compare.py \
    tests/test_harness_end_to_end.py \
    tests/test_review_gate_and_rollback.py \
    > /tmp/quickstart_collect.log 2>&1 || {
        echo "!! doctor failed — see /tmp/quickstart_collect.log"
        tail -40 /tmp/quickstart_collect.log
        exit 1
    }
collected="$(grep -c '::test_' /tmp/quickstart_collect.log || true)"
echo "    collected $collected tests"

# ---------------------------------------------------------------------------
# 4. Emit .mcp.json suggestion
# ---------------------------------------------------------------------------
echo
echo "==> recommended .mcp.json (Claude Code / Codex)"
"$ROOT/scripts/write_mcp_config.sh" "$VENV_DIR" "$ROOT" "$PROFILE"
echo
echo "Done. Next steps:"
echo "  • Run real harness:  PYTHONPATH=. $VENV_DIR/bin/python -m pytest -q"
echo "  • Start CLI server:  PYTHONPATH=. $VENV_DIR/bin/python -m stable_agent.cli serve"
echo "  • Use --local CLI:   PYTHONPATH=. $VENV_DIR/bin/python -m stable_agent.cli task run --task-input '...' --local"
