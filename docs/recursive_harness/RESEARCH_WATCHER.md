# Research Watcher

Research Watcher scans arXiv, GitHub, and allowlisted documentation sources into `ResearchEvidenceCard` records.

Rules:

- External evidence starts as `evidence_only`.
- Evidence cards do not modify skills.
- Proposals require validation.
- Candidate creation still requires review.
- Promotion requires delayed A/B validation and human approval.

CLI:

```bash
python -m stable_agent.cli research scan --source arxiv --query "self evolving agents"
python -m stable_agent.cli research scan --source github --query "agent memory skill repo"
python -m stable_agent.cli research propose --finding-id FINDING_ID
```
