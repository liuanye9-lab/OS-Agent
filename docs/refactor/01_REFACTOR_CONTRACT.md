# 01_REFACTOR_CONTRACT.md — 重构契约

> 本轮重构的不可变约束。

## 外部契约 (不可变)

### stableagent.task.os_agent 返回字段

以下字段在重构前后必须始终存在:

```
ok: bool
run_id: str
dashboard_url: str
observer_url: str
event_sync_ok: bool
event_api_ok: bool
dashboard_replay_ok: bool
api_event_count: int
emitted_event_count: int
missing_required_events: list[str]
api_missing_required_events: list[str]
eval_passed: bool
eval_score: float | None
si_report: dict | None
progress_pct: int
current_stage: str
```

### Required Events (正常路径)

```
task.received
intent.parsed
context.budgeted
temporal_memory.retrieved
rag.retrieved
context.compression_guard.checked
context.built
workflow.plan.created
workflow.step.started
workflow.step.completed
eval.completed
self_improvement.checked
task.completed
```

### Required Events (失败学习路径)

```
regression.generated
memory.update.candidate
skill.patch.proposed
validation.checked
```

### Tool Name

- `stableagent.task.os_agent` 不可更改

### Dashboard/Observer URL 格式

- `/runs/{run_id}`
- `/observe/{run_id}`

## 内部契约 (可优化)

| 组件 | 当前行为 | 重构后行为 |
|---|---|---|
| _h_task_os_agent | 620 行含回退 | ≤80 行，只做参数转发 |
| CuratorService | 未接入 | 接入主链路 |
| ValidationGate.validate_delayed | stub | 真实实现 |
| CLI task run | 依赖 HTTP | 默认 local runtime |
| stdio MCP tools/call | 依赖 HTTP | 默认 local runtime |

## 禁止事项

1. 不重写整个项目
2. 不删除现有可运行能力
3. 不破坏 `stableagent.task.os_agent` 外部行为
4. 不破坏 MCP HTTP 现有入口
5. 不自动覆盖 best_skill.md
6. 不把失败经验直接写入 promoted skill
7. 不继续增加 MCP 工具数量
8. 不引入重型依赖 (向量数据库、复杂任务队列、外部 SaaS)
