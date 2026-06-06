# Phase 0 Contract Freeze

Progress: 0% -> 8%

## Frozen Contract

`stableagent.task.os_agent` must keep these surfaces backward compatible:

- CLI envelope: `ok`, `run_id`, `dashboard_url`, `observer_url`, `missing_required_events`, `understanding_trace`, `token_report`, `expression_matches`, `error`.
- MCP `structuredContent`: existing top-level fields remain additive-only.
- `structuredContent.data`: existing V9/V10 sync fields remain present.
- Dashboard event fields must continue to include `run_id`, `event_type`, `stage`, `progress_pct`, `status_text_zh`, `decision_summary_zh`, `why_zh`, `next_step_zh`, `avatar_state`, `timestamp`.

## Additive Fields

This upgrade adds only additive fields:

- `profile_hits`
- `memory_hit_report`
- `learning_impact_report`
- `research_findings`
- `validation_ab`
- `human_review_queue`
- `self_iteration_proposal`

## Safety Freeze

- No automatic main-branch edits.
- No automatic merge, deploy, or best skill export.
- No direct promotion of external research into active memory or promoted skill.
- No active memory without `evidence_refs`.
- No hidden chain-of-thought in Dashboard or MCP top-level projection.
