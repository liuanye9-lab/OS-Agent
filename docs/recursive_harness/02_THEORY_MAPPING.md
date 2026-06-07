# Theory Mapping

Progress: 0% -> 8%

| Reference | StableAgent Recursive Harness Mapping |
|---|---|
| Anthropic recursive self-improvement | Agent can suggest improvements, but all high-risk actions stop at human review. |
| SkillOS | Executor remains stable; skill curation is separated into candidate, validation, and review layers. |
| SkillOpt | `BoundedSkillEditor` supports only add/delete/replace section or rule operations under a textual learning rate. |
| RTP-LLM | Token impact is reported separately and treated as an estimated signal, not actual billing. |
| Reflexion | Failure reflections become candidates, not active long-term rules. |
| MemGPT / Letta | `memory_evidence` gates active memory with evidence, conflict detection, and decay. |
| OpenHands / SWE-agent | `self_iteration` produces branch plans and prompts; no auto-merge/deploy. |
| LangGraph | The existing RunLifecycle remains the state backbone and emits replayable events. |

## Key Product Principle

StableAgent Recursive Harness does not replace Codex, Claude Code, Cursor, or Trae. It is the personal, evidence-gated layer around them: user model, memory governance, skill curation, validation, research evidence, and human review.
