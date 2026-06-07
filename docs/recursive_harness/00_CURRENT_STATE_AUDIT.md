# Phase 0 Current State Audit

Progress: 0% -> 8%

## Baseline Commands

- `git status --short --branch`: on `codex/recursive-harness`, with pre-existing untracked `OS-Agent/` nested copy.
- `find . -maxdepth 4 -type f | sort`: completed; repo contains root project plus untracked nested `OS-Agent/`.
- `PYTHONPATH=. ./.venv/bin/python -m pytest -q || true`: collection failed because the local venv lacked `httpx2/httpx`.
- `bash scripts/integration_test.sh || true`: failed before running Python because the script used bare `python`, which is absent in this shell.
- `PYTHONPATH=. ./.venv/bin/python tools/check_closed_loop.py || true`: passed all structural checks.

## Existing Memory Modules

- `stable_agent/memory/`: temporal memory candidate and router.
- `stable_agent/capsule/memory_lifecycle.py`: capsule memory review, promote, prune, delete.
- `.stableagent-capsule/memory/`: existing runtime capsule memory store.
- Added in this upgrade: `stable_agent/memory_evidence/` for evidence-gated candidates, conflict detection, decay, and hit reports.

## Existing Skill Modules

- `stable_agent/skill_optimizer/`: existing optimizer, patch applier/merger/ranker, validation gate, rejected edit buffer, document store.
- `stable_agent/skills/`: skill repository, lifecycle, signatures.
- `stable_agent/self_improvement/`: proof loop, validation report, skill patch candidates, human review queue.
- Added in this upgrade: bounded edit language files under `stable_agent/skill_optimizer/`.

## Current Chain Findings

- Curator is present through `skill_optimizer` and `self_improvement`, but not all new Recursive Harness concepts were explicit by name.
- ValidationGate exists and is structurally checked by `tools/check_closed_loop.py`.
- CLI has `task run --local`, so local runtime can avoid HTTP, but default CLI path still uses HTTP MCP for compatibility.
- Dashboard Observer already shows event replay, sync status, learning/self-improvement data, and avoids hidden chain-of-thought fields.
- User expression profile existed under `stable_agent/understanding/`; explicit `user_model` layer was missing before this upgrade.
- Research bridge/external crawler existed; explicit evidence-card workflow was missing before this upgrade.
- PR-only self-iteration existed as safety intent in docs/self-improvement; explicit `self_iteration` proposal harness was missing before this upgrade.

## Biggest Technical Debt

The largest technical debt is split transport/runtime behavior: HTTP MCP is still the default CLI path, while `--local` is the path that proves stdio/CLI does not need the server. A second issue is environment drift: required test dependencies existed in `pyproject.toml` but not `requirements.txt` or the local venv.
