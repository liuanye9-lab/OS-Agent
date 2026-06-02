# CHANGELOG.md

All notable changes to StableAgent Capsule — 个人技能进化层.

---

## V12.0 (2026-06-03) — StableAgent Capsule 收敛式精简重构

### Changed
- `_h_task_os_agent` 从 620 行瘦身到 39 行 (-94%)
- `unified_tool_registry.py` 从 2519 行缩减到 1937 行 (-23%)
- CLI `task run` 默认使用 local runtime，不需要启动 HTTP server
- stdio MCP 默认使用 local runtime，不需要启动 HTTP server
- `validate_delayed()` 从 stub 变为真实实现

### Added
- `stable_agent/core/os_agent_handler.py` — 薄编排层 (Executor → Curator → ContractBuilder)
- `stable_agent/eval/related_task_store.py` — Related Task Store (Delayed Validation 数据源)
- `stable_agent/runtime/local_runtime.py` — Local Runtime (CLI/stdio 脱离 HTTP)
- CuratorService 接入主学习闭环
- 7 个新测试文件，62 个新测试

### Removed
- `_h_task_os_agent` 内联回退路径 (575 行死代码)

---

## V11.5 (2026-06-02) — SkillOS Convergence Refactor

### Added
- `stable_agent/gateway/tool_profiles.py` — Tool Profile 三级暴露策略 (minimal/default/full)
- `stable_agent/core/` — 核心模块 (models, executor, curator, validator, contracts)
- `stable_agent/skills/` — SkillRepo v2 (文件 + SQLite 双层存储)
- `scripts/connect_claude_code.sh` — Claude Code MCP 配置生成
- `scripts/quickstart.sh` — 快速启动脚本
- CLI 新增 `doctor`, `skill list/show/validate/promote` 命令
- 6 个新测试文件 (70 个测试)
- 8 个新文档文件

### Changed
- `unified_tool_registry.py` — list_tools() 支持 profile 过滤
- `run_store.py` — 新增 SQLite 持久化层 (解决 Observer 0% 问题)
- `cli.py` — 新增 doctor 和 skill 命令

### Fixed
- Observer 0% 问题: RunStore 从纯内存改为内存+SQLite 双层存储
- 已完成 run 刷新页面后仍可回放历史事件

---

## V8.1 (2026-05-30) — Phase 1-9 闭环硬化 + 最后一公里打通

### Added
- `tools/check_closed_loop.py` — 闭环完整性自动检查脚本（7 项检查 → 8 项）
- `tools/integration_test.py` — 端到端集成测试自动化
- `scripts/deploy_local.sh` — 一键本地部署
- `scripts/integration_test.sh` — 集成测试脚本
- `scripts/smoke_test.sh` — 冒烟测试脚本
- Canvas 像素人 17 场景语义渲染，替换 emoji 回退
- 完整文档套件: 12 份 spec/audit/plan docs

### Changed
- **_h_task_os_agent 彻底重写**: 从只发 acting/completed → 20+ 阶段事件流水线
  - 显式阶段: received → intent_parsing → context_budgeting → temporal_memory → rag → context_compressing → acting → observing → evaluating → self_improvement → completed
  - 每阶段发布 EventStream + RunStore 事件
- `_generate_skill_patches` 不再自动推进状态线
- 日志面板默认折叠

### Fixed
- **P0**: `RegressionValidationRunner` 无回归用例时默认通过 → 改为 **passed=False** (old_score=0, new_score=0, reason_zh="没有回归用例，无法证明新 skill 更好")
- **P0**: `SelfImprovementProofLoop` validation_passed 初始值 True → **False**（只有 RegressionValidationRunner 证明新规则更好时才改为 True）
- **P1**: `ValidationReport.from_results` 不再覆盖显式提供的 reason_zh
- 30 new tests for regression validation + proof loop edge cases

### Verified
- 1083+ tests passing
- check_closed_loop.py: 8/8 PASS
- 闭环 14 环节全部打通

---

## V7.1 (2026-05-30) — Review API + 飞书通知 + Best Skill 版本化

### Added
- Human Review API 端点: `/api/reviews` (list/approve/reject)
- 飞书消息通知集成（审核通过/拒绝时通知）
- `best_skill.md` 版本化管理（`_export_best_skill_versioned` 带时间戳）
- `HumanReviewQueue` 正式类（V6.3 内联逻辑 → 独立模块）

### Changed
- Skill Export 逻辑: 审批通过后自动导出版本化 best_skill.md
- 审核队列状态流: pending → under_review → approved/rejected

---

## V7.0 (2026-05-30) — 物理清理

### Removed
- `stable_agent/observation/progress_model.py` — 已由 RunLifecycle 统一接管
- `stable_agent/gateway/run_lifecycle.py` — 已迁移至 `stable_agent/runtime/run_lifecycle.py`
- V3/V4 MCP 遗留代码（MCP Gateway V5 为唯一入口）

### Changed
- `_STAGE_MAP` 从 7 项扩展到 40+ 项精确映射
- obsolete modules 引用全部更新到新路径

---

## V6.3 (2026-05-30) — HumanReviewQueue + Best Skill 自动导出

### Added
- `HumanReviewQueue` — 人工审核队列（pending / approved / rejected 状态机）
- `best_skill.md` 自动导出: `_export_best_skill_versioned`
- `WorkflowStateMachine._step_retrieve_knowledge`: STUB `[]` → 真实 RAG 检索
- `stableagent.skill.patch_review` MCP 工具

### Changed
- Human Review 不再绕过 best_skill.md 导出
- Skill Patch 冻结时间戳，不可修改已审核通过的 patch

---

## V6.2 (2026-05-30) — Dashboard 收敛 + LLM 校验

### Added
- Dashboard RunObserver 页面 (`run_observer.html` + `run_observer.js`)
- WebSocket 实时事件推送 (`/dashboard-sync/ws/runs/{run_id}`)
- LLM 校验模式: 评估输出对 Skill Patch 的真实验证

### Removed
- V3 Dashboard 页面
- V4 MCP 旧端点

### Changed
- Dashboard 从多版本（V2/V3）收敛为单一 RunObserver
- LLM Validation: rule_weight=0.3 + llm_weight=0.7 混合评分

---

## V6.1 (2026-05-30) — TemporalMemoryBridge + ContextCompressionGuard + RegressionValidation

### Added
- `TemporalMemoryBridge` — 连接旧 MemoryRouter 到新 TemporalMemoryRouter（记忆迁移）
- `ContextCompressionGuard` — 6 层保护策略 + `enforce_budget()` 预算强制执行
- `RegressionValidationRunner` — 规则 + LLM 混合回归验证（取代硬置 validation_passed=True）
- `ValidationReport` + `ValidationCaseResult` — 结构化验证报告
- 28 个新测试

### Changed
- RunLifecycle: 20 → 22 阶段（新增 TEMPORAL_MEMORY_RETRIEVING, CONTEXT_COMPRESSING, MEMORY_UPDATE_CANDIDATE）
- Orchestrator: 步骤 6.5 注入 TemporalMemory + CompressionGuard
- `RunStageMeta`: 新增 scene 字段（像素人场景渲染）

### Fixed
- P0: 3 处 `except Exception: pass` 全部替换为 logger.exception
- P0: validation_passed 无条件硬置 True → 真实验证
- P1: Orchestrator run_id 未定义 bug

---

## V6.0 及之前

参见 git log 或旧版 `docs/changelogs/`。
