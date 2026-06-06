# StableAgent Recursive Harness Architecture

Progress: 98% -> 100%

StableAgent Recursive Harness is a personal, evidence-gated self-evolution layer for AI Coding Agents.

It is not an Executor replacement. Codex, Claude Code, Cursor, Trae, and other coding agents still do the work. StableAgent adds the layer around them:

- User Model: expression, cognitive preferences, temperament policy.
- Evidence-Gated Memory: candidate-first memory with evidence refs, conflict detection, and decay.
- Learning Impact Report: honest report of what improved and what was not proven.
- SkillOpt-style Editor: bounded textual edits, rejected buffer, held-out validation.
- Delayed Validation A/B: baseline-vs-candidate comparison before promotion.
- Research Watcher: external sources become evidence cards first.
- PR-only Self Iteration: proposals and prompts stop at human review.
- Dashboard Observer: user-visible summaries, evidence, next steps, no hidden chain-of-thought.
