# Phase 0 — `stableagent.task.os_agent` 契约冻结

> **Scope**: 这份文档冻结的是 OS-Agent 当前对外契约的 **真实形状**,作为 Phase 1+ 重构(`os_agent_handler.py`、`LocalRuntime`、tool profile)的不可破坏基线。
> 任何字段的删除、重命名、类型变更 = 契约破坏 = 必须随版本号 bump 与迁移说明一起发布。
> 字段新增(additive)是允许的,但必须更新 `tests/golden/os_agent_response_shape.json`。

## 0. 三个返回面

调用 `stableagent.task.os_agent` 会同时产生 **三个** 返回面,各有不同的稳定性承诺。这是 [deep-research-report (5).md](../../README.md) 路线图未明确区分但实际存在的事实,**所有 Phase 1+ 重构必须保留这三层投影关系**:

| 层 | 来源 | 稳定性 | 形状 |
|---|---|---|---|
| **CLI envelope (9 字段)** | `stable_agent/cli.py:244-254` `cmd_task_run` | **最高** — 是 H.Agent / Claude Code / Codex / 外部脚本依赖的对外契约 | 见 §1 |
| **MCP `structuredContent` 顶层 (26 字段)** | `_make_result()` @ `unified_tool_registry.py:178-224` | 高 — MCP host 直接消费,改字段会同时影响 stdio / HTTP MCP | 见 §2 |
| **`structuredContent.data` 内层 (27 字段)** | `_h_task_os_agent` data block @ `unified_tool_registry.py:1469-1503` | 高 — Dashboard / Observer / V9 健康检查依赖 | 见 §3 |

> **CLI envelope 是 sc 顶层与 sc.data 的子集投影**,见 §1 末尾的字段映射表。

## 1. CLI envelope — 9 字段(最稳定面)

来源:`stable_agent/cli.py:244-254`,由 `cmd_task_run` 显式装配。

```json
{
  "ok": true,
  "run_id": "run_xxxxxxxxxxxx",
  "dashboard_url": "http://127.0.0.1:8000/runs/run_xxx",
  "observer_url": "http://127.0.0.1:8000/observe/run_xxx",
  "missing_required_events": [],
  "understanding_trace": { ... },
  "token_report": { ... },
  "expression_matches": null,
  "error": null
}
```

| 字段 | 类型 | 语义 | 缺省 | 失败时取值 |
|---|---|---|---|---|
| `ok` | `bool` | 工具调用是否成功 | — | `false` |
| `run_id` | `str` | 本次运行 ID;失败时空串 | `""` | `""` |
| `dashboard_url` | `str` | Dashboard 完整 URL(含 base);失败时空串 | `""` | `""` |
| `observer_url` | `str` | Observer 完整 URL(含 base);失败时空串 | `""` | `""` |
| `missing_required_events` | `list[str]` | 必需事件中缺失的列表;成功时 `[]` | `[]` | `[]` |
| `understanding_trace` | `dict \| None` | 语义理解轨迹(13 字段) | `None` | `None` |
| `token_report` | `dict \| None` | Token 节省报告(20 字段) | `None` | `None` |
| `expression_matches` | `list \| None` | 表达匹配命中(可选) | `None` | `None` |
| `error` | `str \| None` | 失败原因;成功时 `None` | `None` | 必须为非空字符串 |

**契约不变量**:
- `ok=false` → `error` 必须为非空字符串(强约束,见 `cli.py:257-258`)
- `dashboard_url` / `observer_url` 总是含 base;空串表示失败或 `open_dashboard=False`
- `missing_required_events` 永远是 list,不会是 `None`

**CLI envelope ↔ `structuredContent` 投影关系**:

| CLI 字段 | 来自 |
|---|---|
| `ok` | `sc.ok ∨ ¬rpc_result.isError` |
| `run_id` | `sc.run_id` |
| `dashboard_url` | `base + sc.dashboard_url`(若非空) |
| `observer_url` | `base + sc.observer_url`(若非空) |
| `missing_required_events` | `sc.missing_required_events` |
| `understanding_trace` | `sc.understanding_trace` |
| `token_report` | `sc.token_report` |
| `expression_matches` | `sc.expression_matches` |
| `error` | `sc.error \|\| sc.plain_text \|\| rpc_result.plain_text` |

## 2. MCP `structuredContent` 顶层 — 26 字段

来源:`StableAgentToolResult` @ `_make_result()`(`unified_tool_registry.py:178-224`)。

| 字段 | 类型 | 备注 |
|---|---|---|
| `ok` | `bool` | |
| `run_id` | `str` | |
| `tool_call_id` | `str` | MCP tool call 跟踪 ID |
| `tool_name` | `str` | 固定 `"stableagent.task.os_agent"` |
| `data` | `dict` | **27 个内层字段,见 §3** |
| `plain_text` | `str` | 默认人类可读文本 |
| `plain_text_zh` | `str` | 中文版本 |
| `plain_text_en` | `str` | 英文版本 |
| `dashboard_url` | `str` | Dashboard 路径(无 base) |
| `observer_url` | `str` | Observer 路径(无 base) |
| `trace_url` | `str` | `/runs/{run_id}` |
| `warnings` | `list[str]` | |
| `next_actions` | `list[str]` | |
| `current_stage` | `str` | 终态 `"completed"` |
| `progress_pct` | `int` | 终态 `100` |
| `status_text_zh` | `str` | 状态短语(中) |
| `status_text_en` | `str` | 状态短语(英) |
| `avatar_state` | `str` | UI 头像状态(终态 `"done"`) |
| `decision_summary_zh` | `str \| None` | |
| `decision_summary_en` | `str \| None` | |
| `why_zh` | `str \| None` | |
| `why_en` | `str \| None` | |
| `error` | `str \| None` | |
| `missing_required_events` | `list[str]` | **顶层副本**;真值在 `data.missing_required_events` |
| `understanding_trace` | `dict \| None` | **顶层副本**;真值同名 |
| `token_report` | `dict \| None` | **顶层副本**;真值同名 |
| `expression_matches` | `list \| None` | |

> 标"顶层副本"的字段是为了让 CLI / 简单 host 不必下钻 `sc.data` 即可拿到关键值,**它们与 `data` 内同名字段必须保持一致**。

## 3. `structuredContent.data` 内层 — 27 字段(健康检查面)

来源:`_h_task_os_agent` 终态 data block(`unified_tool_registry.py:1469-1503`)。
**Phase 1+ 重构(handler 拆分)绝不能更改这 27 个字段的名字与类型,因为 V9 健康检查、Dashboard 重放、Observer 投影直接依赖这些值。**

### 3.1 任务状态(7 字段)

| 字段 | 类型 | 终态值 |
|---|---|---|
| `run_id` | `str` | |
| `dashboard_url` | `str` | `/runs/{run_id}` 或 `""` |
| `current_stage` | `str` | `"completed"` |
| `progress_pct` | `int` | `100` |
| `status_text_zh` | `str` | |
| `status_text_en` | `str` | |
| `avatar_state` | `str` | `"done"` |

### 3.2 任务结果(4 字段)

| 字段 | 类型 | 备注 |
|---|---|---|
| `task_type` | `str` | |
| `workflow_state` | `str` | |
| `eval_score` | `float` | |
| `eval_passed` | `bool` | |

### 3.3 自我改进(2 字段)

| 字段 | 类型 | 备注 |
|---|---|---|
| `si_report` | `dict \| None` | 17 字段 self-improvement 报告 |
| `mode` | `str` | `auto` / `force_*` 等 |

### 3.4 V9 事件同步健康检查(8 字段)— **核心契约**

| 字段 | 类型 | 语义 |
|---|---|---|
| `emitted_event_count` | `int` | 本次 run emit 事件总数 |
| `emitted_events` | `list[dict]` | `[{event_type, stage, progress_pct, _emit_ok}, ...]` |
| `event_sync_ok` | `bool` | `len(sync_errors)==0 ∧ len(missing_required_events)==0 ∧ event_api_ok` |
| `sync_errors` | `list[str]` | EventStream/RunStore emit 失败列表 |
| `missing_required_events` | `list[str]` | 客户端侧检查:13 个 `REQUIRED_NORMAL_EVENTS` 中未发出的 |
| `required_events` | `list[str]` | 13 个必需事件类型常量回显(见 §4) |
| `event_api_ok` | `bool` | 服务端侧从 RunStore 回读校验通过 |
| `api_event_count` | `int` | 服务端侧 RunStore 中事件数 |
| `api_missing_required_events` | `list[str]` | 服务端侧缺失事件 |
| `dashboard_replay_ok` | `bool` | `event_api_ok` 的别名(供 Dashboard UI 读) |

**契约不变量**(全部已在 `unified_tool_registry.py:1421-1460` 实现):
- `event_sync_ok ⇒ event_api_ok`
- `event_sync_ok ⇒ missing_required_events == []`
- `event_sync_ok ⇒ sync_errors == []`
- `dashboard_replay_ok ≡ event_api_ok`

### 3.5 实验/学习模式(2 字段)

| 字段 | 类型 |
|---|---|
| `dry_run_learning` | `bool` |
| `force_validation_passed` | `bool \| None` |

### 3.6 V11.1 理解 / Token 报告(2 字段)

| 字段 | 类型 |
|---|---|
| `understanding_trace` | `dict \| None`(13 字段:`trace_id`/`run_id`/`user_original_input`/`interpreted_goal`/`task_type`/`assumptions`/`protected_constraints`/`uncertainties`/`expression_matches`/`semantic_risk_flags`/`confidence`/`needs_user_confirmation`/`created_at`) |
| `token_report` | `dict \| None`(20 字段:`record_id`/`run_id`/`created_at`/`baseline_tokens_estimated`/`raw_context_tokens`/`candidate_context_tokens`/`deduped_tokens`/`retrieved_tokens`/`protected_tokens`/`injected_tokens`/`dropped_tokens`/`output_tokens_estimated`/`saved_tokens_estimated`/`saving_ratio`/`estimation_method`/`is_estimated`/`risk_level`/`protected_items`/`dropped_items`/`summary_zh`) |

## 4. Required Events — 实际 13 个,不是 6 个

来源:`REQUIRED_NORMAL_EVENTS` @ `unified_tool_registry.py:1387-1400`。

> **路线图勘误**:[deep-research-report (5).md](../../README.md) Phase 0 提示词列出 6 个必需事件 (`task.received` / `intent.parsed` / `context.budgeted` / `context.built` / `eval.completed` / `task.completed`),但**仓库实际硬约束 13 个**。Phase 0 必须冻结全部 13 个,否则 `event_sync_ok` 会假阳性。

### 13 个 `REQUIRED_NORMAL_EVENTS`(完整 happy-path 链)

| # | 事件 | 阶段 | 必需性 | emit 位置 |
|---:|---|---|---|---|
| 1 | `task.received` | received | 路线图列出 | `unified_tool_registry.py:1067` |
| 2 | `intent.parsed` | intent_parsing | 路线图列出 | `:1107` |
| 3 | `context.budgeted` | context_budgeting | 路线图列出 | `:1113` |
| 4 | `temporal_memory.retrieved` | temporal_memory_retrieving | **路线图未列** | `:1145` |
| 5 | `rag.retrieved` | rag_retrieving | **路线图未列** | `:1148` |
| 6 | `context.compression_guard.checked` | — | **路线图未列** | (compression guard 链) |
| 7 | `context.built` | context_building | 路线图列出 | `:1264` |
| 8 | `workflow.plan.created` | — | **路线图未列** | (workflow 链) |
| 9 | `workflow.step.started` | — | **路线图未列** | (workflow 链) |
| 10 | `workflow.step.completed` | — | **路线图未列** | (workflow 链) |
| 11 | `eval.completed` | evaluating | 路线图列出 | `:1304` |
| 12 | `self_improvement.checked` | — | **路线图未列** | (self-improvement 链) |
| 13 | `task.completed` | completed | 路线图列出 | `:1374` |

### `REQUIRED_FAILURE_EVENTS`(失败学习链额外要求)

仅当本次 run 触发 failure-learning(出现 `regression.generated` 或 `skill.patch.proposed`)时,这 4 个事件**也必须**出现:

- `regression.generated`
- `memory.update.candidate`
- `skill.patch.proposed`
- `validation.checked`

## 5. 兼容性承诺(Phase 1+ 重构边界)

| 操作 | 是否允许 |
|---|---|
| **新增** CLI envelope 字段 | ✅ additive,但需更新 golden snapshot |
| **新增** `sc` 顶层字段 | ✅ additive |
| **新增** `sc.data` 内层字段 | ✅ additive |
| **新增** required event(扩到 14+) | ⚠️ 重大变更,需 Phase 进度文档同步说明 |
| **重命名 / 删除** 任何已冻结字段 | ❌ 契约破坏 |
| **改类型** 任何已冻结字段(例 `bool → str`) | ❌ 契约破坏 |
| **改 `event_sync_ok` 计算口径** | ❌ 契约破坏(下游 V9 健康检查依赖) |
| **`required_events` 顺序变化** | ✅ 顺序非语义;但事件 emit 顺序应保持单调流 |
| **`run_id` 格式从 `run_xxx` 变更** | ⚠️ 重大;Dashboard URL/路径 hardcode 该前缀 |
| **`open_dashboard=false` 时返回空串还是 `None`** | 维持空串(`""`),不要切换到 `None` |

## 6. 验证

- 形状 snapshot:`tests/golden/os_agent_response_shape.json`
- 契约测试:`tests/test_os_agent_contract_snapshot.py`
- 必需事件测试:`tests/test_required_events_snapshot.py`

跑这两条命令验证契约未破:

```bash
PYTHONPATH=. /Users/Zhuanz/OS-Agent/OS-Agent/.venv/bin/python -m stable_agent.cli serve  # 终端 A
pytest tests/test_os_agent_contract_snapshot.py tests/test_required_events_snapshot.py -q  # 终端 B
```

未启动 server 时这两套测试会 `skip`(而不是 fail),保持 CI 友好。
