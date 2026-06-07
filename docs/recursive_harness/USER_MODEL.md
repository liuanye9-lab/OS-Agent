# User Model

The user model is stored under `.stableagent/user_model/`:

- `expression_profile.yaml`: language, explanation, formatting, and Codex prompt preferences.
- `cognitive_profile.yaml`: thinking models, decision preferences, risk preferences, evidence requirements.
- `temperament_policy.yaml`: stable behavior rules and pause conditions.

Feedback parsing generates `PreferenceCandidate` records. Low-risk feedback remains `candidate`. High-risk changes, such as automatic merge, deploy, promotion, or best skill overwrite, become `pending_review`.
