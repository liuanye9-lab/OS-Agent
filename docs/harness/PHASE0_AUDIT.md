# Phase 0 — OS-Agent 仓库审计

> **作用域**:这份文档冻结的是仓库 **现状真相**(2026-06-05),作为 Phase 1+ 重构的不可破坏基线。
> 它**不是**需求规划,也**不重新评判**路线图;只回答四个问题:目录里到底有什么、契约源在哪、关键测试是否真的存在、Phase 1 之前还差什么。

## 1. 目录现状(顶层)

| 目录 | 文件数 | 角色 | 备注 |
|---|---:|---|---|
| `stable_agent/` | 166 .py | 主代码包 | 27 个一级子模块 |
| `stable_agent/gateway/` | — | 工具注册与路由 | `unified_tool_registry.py` 2464 行 — Phase 1 拆分目标 |
| `stable_agent/runtime/` | — | run lifecycle / state machine | LocalRuntime 待补 |
| `stable_agent/core/` | — | 编排核心 | 待容纳 `os_agent_handler.py` |
| `stable_agent/skills/` | — | skill 引擎相关 | 与根 `skills/` 分工不清 |
| `stable_agent/saas/` | — | workspace/project/apikey | **路线图建议抽离**,当前与 Harness 目标耦合度低 |
| `tests/` | 131 test_*.py | 测试 | 见 §3 |
| `skills/` | — | skill artifacts | `candidates/` `rejected/` `skill_versions/` |
| `experiments/` | — | 实验 | `self_iteration_5_rounds/` 见 §4 |
| `web/` | — | Dashboard / Observer 模板 | Phase 5 改造目标 |
| `docs/` | — | 设计文档 | 本文档新增至 `docs/harness/` |
| `OS-Agent/` | 镜像 | **顶层有一份 `OS-Agent/` 子目录,看似旧版镜像** | 不在主路径内,Phase 1+ 不动 |
| `research/` | — | 研究素材 | 路线图 Phase 4 ExternalCrawler 起点 |

> 顶层 `OS-Agent/` 子目录是早期镜像,与主开发路径并行存在,**不计入主仓库代码量**;CLI 引用的 venv `~/OS-Agent/OS-Agent/.venv/bin/python` 也固定在该镜像内。这是一个可容忍但需文档说明的双副本现状。

## 2. `stableagent.task.os_agent` 契约源定位

| 关注点 | 文件 / 行号 | 说明 |
|---|---|---|
| 工具名常量 | `stable_agent/gateway/unified_tool_registry.py:125` | `_register("stableagent.task.os_agent", self._h_task_os_agent)` |
| Handler 入口 | `stable_agent/gateway/unified_tool_registry.py:960` | `_h_task_os_agent` — 540+ 行的单方法 |
| Handler 终态 data block | `:1469-1503` | 27 个内层字段 |
| `_make_result` 包装器 | `:178-224` | sc 顶层 26 字段来源 |
| `REQUIRED_NORMAL_EVENTS` | `:1387-1400` | 13 个必需事件 |
| `REQUIRED_FAILURE_EVENTS` | `:1407-1412` | 4 个失败链额外事件 |
| 事件 emit `_emit()` | `:996-1046` | 内置健康统计 |
| event_sync_ok 计算 | `:1421` | `len(sync_errors)==0 ∧ ¬missing_required_events` |
| event_api_ok 回读 | `:1449-1453` | 从 RunStore 校验 |
| dashboard_replay_ok | `:1453` | `event_api_ok` 别名 |
| CLI envelope 装配 | `stable_agent/cli.py:244-254` | 9 字段 |
| stdio MCP 工具列表 | `stable_agent/mcp_stdio.py:46` | |
| Tool schema 注册 | `stable_agent/gateway/tool_schemas.py:199-200` | |

**已注册工具数量**:`unified_tool_registry.py:111-139` 共注册 **29 个工具**,覆盖 task/context/memory/rag/eval/badcase/skillopt/trace/approval/understanding/expression/saas/regression/skill 各域。`stableagent.task.os_agent` 只是其中一个,但承担了**端到端 happy-path** 的角色。

## 3. 关键测试覆盖现状(对比路线图)

路线图 Phase 0 提示词点名了 6 个测试文件。仓库实际有/无情况:

| 路线图列名 | 仓库实际 | 状态 | 等价覆盖 |
|---|---|---|---|
| `test_cli_without_http.py` | ❌ 不存在 | 缺失 | `test_cli_task_run.py` / `test_cli_task_run_mcp_http.py` 覆盖 CLI 调 HTTP 路径,但**没有测试"完全无 HTTP"路径** |
| `test_curator_policy.py` | ❌ 不存在 | 缺失 | 暂无对应统一 curator 服务 |
| `test_delayed_validation.py` | ❌ 不存在 | 缺失 | `test_validation_gate.py` / `test_skill_validation_review.py` / `test_regression_validation_runner.py` / `test_regression_validation_ab_mode.py` 覆盖部分 |
| `test_delayed_validation_v1.py` | ❌ 不存在 | 缺失 | 同上 |
| `test_dashboard_history_replay.py` | ❌ 不存在 | 缺失 | `test_dashboard_run_detail.py` / `test_dashboard_sync.py` / `test_dashboard_projection.py` 覆盖 |
| `test_approval_resume.py` | ✅ 存在 | 完整 | `test_approval_resume_service.py` / `test_high_risk_approval_block.py` 协同 |
| `test_learning_impact_no_fake_improvement.py` | ❌ 不存在 | 缺失 | `test_learning_evidence.py` / `test_self_improvement_proof_loop.py` 覆盖一部分 |

> **结论**:路线图提到的 7 个测试文件中,只有 1 个真实存在;其余 6 个是路线图作者**假设** 的命名。仓库内已有等价覆盖,但分散且命名风格不一致。**Phase 1+ 不必新建这些重名文件**,但应在 Phase 3(Curator/Validator)/Phase 5(Observer)显式标识对应测试。

## 4. 自迭代实验现状(路线图核心论据交叉验证)

路线图的核心质疑:`experiments/self_iteration_5_rounds/run_experiment.py` 中 `learning_triggered` 是按 `round_num > 1` 硬编码,而非来自真实学习事件。

**经源码核对,路线图的判断属实**:

`experiments/self_iteration_5_rounds/run_experiment.py:89`:
```python
return {
    "round": round_num,
    "quality_score": ...,
    "hallucination_rate": ...,
    "token_usage": total_tokens,
    "learning_triggered": round_num > 1,    # ← 硬编码,与真实学习无关
}
```

同时该脚本的 `quality_score` / `hallucination_rate` 也只是简单聚合,未与 baseline vs candidate A/B 比较挂钩。这就是路线图所说"当前实验是 simulated demo"的具体证据。

**Phase 0 不修复此处**(路线图 Phase 3 才处理 Curator/Validator 真实闭环),但应在 PHASE0_AUDIT.md 中明确记录,以便:
- 后续向外报告时不再以这份实验数据作为"自进化已实现"的证据
- Phase 3 完成后该字段必须改为"由 ValidationService 真实结果填充"

## 5. 契约冻结边界 — Phase 1+ 不可破坏清单

> 详细字段表见 [PHASE0_CONTRACT.md](./PHASE0_CONTRACT.md);此处只列**Phase 1 重构最容易踩雷的 5 处**。

| # | 不可破坏 | 风险点 | 自检方法 |
|---|---|---|---|
| 1 | CLI envelope 9 字段名+类型 | 抽 handler 时若改返回 dict 形状 → CLI 会拿不到 `understanding_trace` | 跑 `tests/test_os_agent_contract_snapshot.py` |
| 2 | 13 个 `REQUIRED_NORMAL_EVENTS` | 重构 emit 链时漏发任何一个 → `event_sync_ok=False` | 跑 `tests/test_required_events_snapshot.py` |
| 3 | `event_sync_ok` ⇒ `event_api_ok` 不变量 | 若把 emit 与 RunStore append 解耦 → 假阳性 | snapshot 测试已校验 |
| 4 | `run_id` 前缀 `run_` | Dashboard 路径 `/runs/{run_id}` 硬编码,改前缀会让前端 404 | snapshot 测试 + 路由代码搜索 |
| 5 | sc.data 的 27 字段(尤其是 `dashboard_replay_ok`) | Dashboard UI 直接读这些键 | snapshot 测试 |

## 6. 已知 blocker(Phase 1 启动前)

| # | 问题 | 影响 | 处置建议 |
|---|---|---|---|
| B1 | `unified_tool_registry.py` 2464 行 / `_h_task_os_agent` 540+ 行单方法 | Phase 1 抽 handler 时回归风险高 | Phase 1 用**façade 模式**:新建 `core/os_agent_handler.py` 仅 import + 委托,旧 handler 暂不挪 |
| B2 | CLI 默认仍走 HTTP MCP(`cli.py:202` `_http_post(mcp_url, ...)`) | 路线图要求"CLI without HTTP"无法满足 | Phase 1 增加 `--local` flag + LocalRuntime 直连;HTTP 模式保留 |
| B3 | stdio MCP 当前是否真无 HTTP 依赖未验证 | 部分自动化场景失败 | Phase 1 测试中明确断言无 HTTP 端口监听 |
| B4 | 路线图引用的测试文件名大多缺失 | Phase 1+ 无法直接运行路线图列出的 pytest 命令 | 在每个 PHASE 文档里注明等价覆盖,而不是新建重名文件 |
| B5 | self-iteration 实验仍是 simulated | 对外宣传与现实脱节 | Phase 3 完成后改写或下架该实验脚本 |
| B6 | 顶层 `OS-Agent/` 子目录是旧镜像 | 容易让外部贡献者混淆 | 单独发 issue 跟踪,Phase 0 不处理 |

## 7. Phase 0 交付物对照

| 交付物 | 路径 | 状态 |
|---|---|---|
| 审计文档 | `docs/harness/PHASE0_AUDIT.md` | ✅ 本文件 |
| 契约文档 | `docs/harness/PHASE0_CONTRACT.md` | ✅ |
| Golden snapshot | `tests/golden/os_agent_response_shape.json` | ✅ 由 live run 生成 |
| 契约 snapshot 测试 | `tests/test_os_agent_contract_snapshot.py` | ✅ |
| 必需事件 snapshot 测试 | `tests/test_required_events_snapshot.py` | ✅ |

## 8. PR 验收清单(Phase 0)

- [x] `stableagent.task.os_agent` 契约 9 字段已冻结
- [x] 13 个 `REQUIRED_NORMAL_EVENTS` 已冻结
- [x] golden snapshot 由真实 live run 生成,非手写
- [x] 不修改任何业务逻辑、不删除旧测试、不引入新依赖
- [x] 服务未启动时新增测试 skip 而不是 fail
- [x] 审计文档列出 6 个 blocker 与 Phase 1 处置建议
- [x] 路线图与现实差异(13 vs 6 事件、缺失测试文件)已显式标注

## 9. 下一阶段衔接

Phase 1 启动条件(全部满足):
1. ✅ 契约已冻结 — 重构有边界
2. ✅ snapshot 测试已写 — 重构有回归门
3. ✅ B1/B2/B3 处置策略已定 — 风险可控
