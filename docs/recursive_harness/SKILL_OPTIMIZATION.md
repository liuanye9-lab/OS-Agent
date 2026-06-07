# Skill Optimization

Skill optimization uses bounded edits:

- `ADD_SECTION`
- `DELETE_SECTION`
- `REPLACE_SECTION`
- `ADD_RULE`
- `REPLACE_RULE`
- `DELETE_RULE`

The `TextualLearningRate` defaults to at most 12 changed lines, one changed section, two added rules, and no deletion. Safety and human-review sections cannot be deleted or replaced by default. Failed validation writes to `.skills/rejected_edits.jsonl` so the same failed idea is not repeated.
