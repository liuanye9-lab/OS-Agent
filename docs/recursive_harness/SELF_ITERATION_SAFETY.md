# Self-Iteration Safety

Self-iteration is PR-only by default.

Flow:

1. ResearchFinding, FailedRun, or RejectedEdit creates an improvement proposal.
2. PatchPlanner creates a branch plan and patch summary.
3. PRPromptBuilder creates a Codex prompt.
4. SandboxRunner can run tests or benchmarks.
5. ReviewGate stops at `ready_for_human_review`.

Default forbidden actions:

- `git push`
- merge
- deploy
- promote best skill

No self-iteration path automatically changes production state.
