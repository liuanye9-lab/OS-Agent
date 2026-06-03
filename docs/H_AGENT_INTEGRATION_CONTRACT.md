# H-Agent Integration Contract

StableAgent Capsule can serve as the execution layer of H.Agent.
All CLI output with `--json` follows the `h-agent-v1` JSON contract defined below.

## Contract Version

`h-agent-v1`

## Success Response

```json
{
  "ok": true,
  "run_id": "run_xxx",
  "dashboard_url": "...",
  "observer_url": "...",
  "output_text": "...",
  "eval_passed": true,
  "eval_score": 0.82,
  "missing_required_events": [],
  "understanding_trace": {},
  "token_report": {},
  "error": null,
  "suggestion": null,
  "contract_version": "h-agent-v1"
}
```

### Field Descriptions (Success)

| Field | Type | Description |
|---|---|---|
| `ok` | `bool` | Always `true` on success. |
| `run_id` | `string` | Unique run identifier (e.g. `run_xxx`). |
| `dashboard_url` | `string` | URL to the run dashboard page. |
| `observer_url` | `string` | URL to the observer/replay page. |
| `output_text` | `string` | Human-readable output text of the task. |
| `eval_passed` | `bool` | Whether the evaluation gate passed. |
| `eval_score` | `float \| null` | Evaluation score (0.0 - 1.0). |
| `missing_required_events` | `array` | List of required events that were not emitted. |
| `understanding_trace` | `object \| null` | The understanding trace generated at task start. |
| `token_report` | `object \| null` | Token budget report for the run. |
| `error` | `null` | Always `null` on success. |
| `suggestion` | `null` | Always `null` on success. |
| `contract_version` | `string` | Always `"h-agent-v1"`. |

## Failure Response

```json
{
  "ok": false,
  "run_id": "run_xxx",
  "dashboard_url": "",
  "observer_url": "",
  "output_text": "",
  "eval_passed": false,
  "eval_score": null,
  "missing_required_events": [],
  "understanding_trace": null,
  "token_report": null,
  "error": "...",
  "suggestion": "...",
  "contract_version": "h-agent-v1"
}
```

### Field Descriptions (Failure)

| Field | Type | Description |
|---|---|---|
| `ok` | `bool` | Always `false` on failure. |
| `run_id` | `string` | Run ID if available, otherwise empty string. |
| `dashboard_url` | `string` | Empty string on failure. |
| `observer_url` | `string` | Empty string on failure. |
| `output_text` | `string` | Empty string on failure. |
| `eval_passed` | `bool` | Always `false` on failure. |
| `eval_score` | `null` | Always `null` on failure. |
| `missing_required_events` | `array` | Empty array on failure. |
| `understanding_trace` | `null` | Always `null` on failure. |
| `token_report` | `null` | Always `null` on failure. |
| `error` | `string` | Human-readable error description. |
| `suggestion` | `string` | Suggested fix steps. |
| `contract_version` | `string` | Always `"h-agent-v1"`. |

## Backward Compatibility

The normalizer preserves any extra fields from the upstream response that are not part of the contract. This ensures backward compatibility with consumers that may rely on additional fields.

## Usage

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "your task description" \
  --json
```

The output JSON will always conform to the `h-agent-v1` contract.
