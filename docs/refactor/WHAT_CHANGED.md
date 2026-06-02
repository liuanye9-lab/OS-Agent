# WHAT_CHANGED.md — 本轮重构变更清单

> V12.0: StableAgent Capsule 收敛式精简重构

## 文件变更

### 新增文件 (7)

| 文件 | 用途 |
|---|---|
| `stable_agent/core/os_agent_handler.py` | 薄编排层 (Executor → Curator → ContractBuilder) |
| `stable_agent/eval/related_task_store.py` | Related Task Store (Delayed Validation 数据源) |
| `stable_agent/runtime/local_runtime.py` | Local Runtime (CLI/stdio 脱离 HTTP) |
| `tests/test_os_agent_contract.py` | 契约冻结测试 (17 tests) |
| `tests/test_os_agent_handler_slim.py` | Handler 瘦身测试 (13 tests) |
| `tests/test_delayed_validation_v1.py` | Delayed Validation v1 测试 (8 tests) |
| `tests/test_promotion_policy.py` | Promotion Policy 测试 (17 tests) |
| `tests/test_local_runtime.py` | Local Runtime 测试 (4 tests) |
| `tests/test_mcp_stdio_without_http.py` | stdio MCP 脱离 HTTP 测试 (5 tests) |
| `tests/test_cli_without_http.py` | CLI 脱离 HTTP 测试 (2 tests) |
| `docs/refactor/00_CURRENT_PROGRESS_AUDIT.md` | 审计报告 |
| `docs/refactor/01_REFACTOR_CONTRACT.md` | 重构契约 |
| `docs/refactor/02_RISK_AND_ROLLBACK.md` | 风险与回滚策略 |
| `UPDATED_README.md` | 新 README (StableAgent Capsule 定位) |

### 修改文件 (5)

| 文件 | 变更 |
|---|---|
| `stable_agent/gateway/unified_tool_registry.py` | 2519→1937 行 (-582)。_h_task_os_agent 从 620 行瘦身到 39 行。删除内联回退。 |
| `stable_agent/core/validator.py` | `validate_delayed()` 从 stub 变为真实实现。新增 `_estimate_improvement()`。 |
| `stable_agent/mcp_stdio.py` | `_handle_tools_call()` 默认使用 local runtime，HTTP 作为回退。新增 `_use_http_mode()`, `_call_via_local_runtime()`。 |
| `stable_agent/cli.py` | `cmd_task_run()` 默认使用 local runtime。新增 `_call_local_runtime()`, `--http` 参数。 |
| `tests/test_v9_final_hardening.py` | 更新 `test_sync_health_fields_in_tool_result` 以检查 ContractBuilder 而非内联代码。 |

### 未修改

- `stable_agent/core/models.py` — 已有完整模型
- `stable_agent/core/contracts.py` — 已有 ContractBuilder
- `stable_agent/core/curator.py` — 已有 CuratorService
- `stable_agent/core/executor.py` — 已有 OSAgentExecutor
- `stable_agent/core/delayed_validation.py` — 已有 DelayedValidationGate
- `stable_agent/skills/repository.py` — 已有 SkillRepository
- `stable_agent/gateway/tool_profiles.py` — 已有三级 profile

## 关键指标变化

| 指标 | 重构前 | 重构后 |
|---|---|---|
| unified_tool_registry.py 行数 | 2519 | **1937** (-23%) |
| _h_task_os_agent 行数 | 620 | **39** (-94%) |
| CuratorService 接入主链路 | 否 | **是** |
| validate_delayed | stub | **真实实现** |
| CLI 依赖 HTTP | 是 | **否 (默认 local)** |
| stdio MCP 依赖 HTTP | 是 | **否 (默认 local)** |
| 测试数量 | 1680 passed | **1742 passed** (+62) |
