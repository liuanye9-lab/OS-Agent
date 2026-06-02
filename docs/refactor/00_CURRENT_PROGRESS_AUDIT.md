# 00_CURRENT_PROGRESS_AUDIT.md — 收敛式精简重构审计

> 生成时间: 2026-06-02
> 审计范围: OS-Agent/ (git repo at commit 23fee20)

## 1. 项目概况

| 指标 | 值 |
|---|---|
| Git 最新提交 | `23fee20 V11.5: SkillOS Convergence Refactor` |
| Python 文件数 | 669 |
| 总文件数 | 1317 |
| 测试文件数 | ~120 |
| unified_tool_registry.py 行数 | 2519 |
| _h_task_os_agent 行数 | **620** (L970-L1589, 含内联回退) |
| handler 方法数 | 55 |

## 2. MCP 工具数量

| Profile | 工具数 | 说明 |
|---|---|---|
| minimal | 10 | 核心闭环工具 |
| default | 20 | minimal + eval/skill 调试 |
| full | 55 | 所有旧工具 (含 SaaS) |

**minimal 工具清单:**
1. stableagent.task.os_agent
2. stableagent.trace.get_run
3. stableagent.feedback.correct_and_remember
4. stableagent.feedback.remember
5. stableagent.feedback.dont_do_this_again
6. stableagent.token.report
7. stableagent.capsule.status
8. stableagent.capsule.doctor
9. stableagent.memory.health
10. stableagent.token.summary

## 3. _h_task_os_agent 职责分析

当前 `_h_task_os_agent` (L970-L1589) 承担以下职责:

| 职责 | 行范围 | 是否已提取到独立模块 |
|---|---|---|
| TaskSpec 解析 | L977 | ✓ models.py |
| OSAgentExecutor 委托 | L981-1008 | ✓ executor.py (但有回退) |
| 事件发布 (_emit) | L1049-1100 | ✗ 内联 |
| RunStore 注册 | L1111-1118 | ✗ 内联 |
| Understanding Trace | L1124-1159 | ✗ 内联 |
| Temporal Memory 检索 | L1172-1199 | ✗ 内联 |
| RAG 检索 | L1201-1204 | ✗ 内联 |
| Context Compression Guard | L1206-1231 | ✗ 内联 |
| Token Budget 记录 | L1233-1305 | ✗ 内联 |
| 任务执行 (orchestrator) | L1318-1330 | ✗ 内联 |
| 评估 | L1332-1363 | ✗ 内联 |
| 自我优化闭环 (proof_loop) | L1365-1426 | ✗ 内联 |
| 事件同步健康检查 | L1441-1476 | ✗ 内联 |
| RunStore 回读验证 | L1478-1515 | ✗ 内联 |
| 结果构建 | L1517-1589 | ✗ 内联 |

**问题:** executor.py 已存在但仅作为"尝试路径"，失败后回退到完整的 600 行内联实现。

## 4. CuratorService 接入状态

| 组件 | 存在 | 接入主链路 |
|---|---|---|
| CuratorService (core/curator.py) | ✓ | **否** |
| ValidationGate (core/validator.py) | ✓ | 部分 (schema only) |
| SkillRepository (skills/repository.py) | ✓ | 未连接 |
| DelayedValidationGate (core/delayed_validation.py) | ✓ | stub |
| proof_loop.evaluate_and_learn() | ✓ | **是 (旧路径)** |

**主流程仍调用 `self._orchestrator.proof_loop.evaluate_and_learn()` (L1373)**，未接入 CuratorService。

## 5. ValidationGate 真伪分析

| 方法 | 状态 | 说明 |
|---|---|---|
| validate_schema | **真逻辑** | 检查 candidate_id, source_run_id, proposed_rule, when_to_use, validation_plan, risk_level, 长度 |
| validate_regression | **stub** | 直接返回 passed=True |
| validate_delayed | **stub** | 直接返回 passed=True, validations_count=1 |
| can_promote | **真逻辑** | 6 项条件检查 + 高风险拦截 |
| can_canary | **真逻辑** | 3 项条件检查 |

## 6. CLI / stdio MCP 依赖分析

| 入口 | 依赖 HTTP | 代码位置 |
|---|---|---|
| CLI `task run` | **是** | `cmd_task_run()` → `_http_post("http://127.0.0.1:8000/mcp/")` |
| stdio MCP `tools/call` | **是** | `_handle_tools_call()` → `urllib.request("http://127.0.0.1:8000/mcp/")` |
| HTTP MCP | N/A (本身就是) | `web/server.py` |

**影响:** 必须先启动 `cli serve` 才能使用 CLI 和 stdio MCP。

## 7. Dashboard Replay 状态

- ✓ V11.4 已修复历史事件回放
- ✓ `/observe/{run_id}` 能从 RunStore 回读事件
- ✓ WebSocket 实时补充正常
- 需要瘦身: 当前面板信息偏杂

## 8. 当前是否已精简化

**部分精简:**
- ✓ tool_profiles.py 实现了 minimal/default/full 三级过滤
- ✓ core/ 目录已有 models, contracts, curator, validator, executor, delayed_validation
- ✓ skills/ 目录已有完整的 SkillRepository
- ✗ unified_tool_registry.py 仍然 2519 行，55 个 handler
- ✗ _h_task_os_agent 仍然 620 行 (含回退)
- ✗ CuratorService 未接入主链路
- ✗ CLI/stdio 仍依赖 HTTP
- ✗ Delayed Validation 仍是 stub

## 9. 下一步最小改动路径

```
Phase 1: 冻结契约 (test_os_agent_contract.py)
    ↓
Phase 2: 删除 _h_task_os_agent 内联回退，强制走 executor
    ↓
Phase 3: 在 executor.run() 后接入 CuratorService
    ↓
Phase 4: 实现 Delayed Validation v1 (替换 stub)
    ↓
Phase 5: 新增 LocalStableAgentRuntime，CLI/stdio 直接调用
    ↓
Phase 6-7: 文档更新 + Observer 瘦身
    ↓
Phase 8: 全量测试
```

**最小风险路径:** 先冻结契约 → 再删除回退 → 再接入 Curator → 再实现 Delayed Validation。
