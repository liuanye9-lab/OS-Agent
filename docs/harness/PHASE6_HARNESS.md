# Phase 6 — Harness 收口:CI + 治理边界 + Quickstart

> Phase 0–5 把后端能力都建好了,Phase 6 把它们**编排成有治理边界的闭环**:`Curator → Validator → ValidationReportStore → ReviewGate → ReviewQueue`。最关键的不变量:**`ReviewGate.evaluate()` 永远不会自动 promote**,只有显式 `approve(review_id, reviewer=...)` 调用才会触发 `validated → promoted`。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **PR-only,绝不自动上线** | HarnessFlow 写 skill / report / queue 到磁盘,**永不**触碰 git;CI 之后由人在 PR 里决定是否合并 |
| **`evaluate()` 永不 promote** | 这是 Phase 6 的核心治理不变量,被 4 个不同的 ValidationOutcome 参数化测试守护 |
| **rollback ≠ demote** | 候选 v2 回归 → 标 `rejected`;已 promoted 的 v1 **完全不动** |
| **审批可审计** | 每条 review 落 JSON 文件,记 reviewer / reason / timestamp;同一个 review_id 双重决策抛 `ValueError`(单次性硬约束) |
| **失败可定位** | CI 四阶段门禁,每个 gate 对应一份 PHASE 文档,出错能 trace 到设计源 |

## 2. 模块布局

```
stable_agent/harness/                  新增
├── __init__.py
├── flow.py            — HarnessFlow / HarnessReport
├── review_gate.py     — ReviewGate + ReviewGateOutcome
├── review_queue.py    — ReviewQueueStore (JSON-on-disk)
├── plan.py            — read-only dry-run preview
├── patch.py           — SkillPatchDescriptor (PR builder 输入)
└── validate.py        — out-of-band revalidate() helper

docs/harness/
└── harness-ci.workflow.yml   — 4-gate 流水线 (待激活,见下)

scripts/
├── quickstart_harness.sh   — venv + deps + doctor + .mcp.json
└── write_mcp_config.sh     — 单独打印 .mcp.json 块

> **激活 CI**:GitHub OAuth `workflow` scope 限制本地 push 进
> `.github/workflows/`,所以 workflow 文件先放在 `docs/harness/`。
> 复制到激活位置:
>
> ```bash
> mkdir -p .github/workflows
> cp docs/harness/harness-ci.workflow.yml .github/workflows/harness-ci.yml
> ```
>
> 或在 GitHub Web UI 直接通过 "Add file → Create new file" 粘贴内容
> 到 `.github/workflows/harness-ci.yml`(Web 会话权限不受此限制)。
```

## 3. HarnessFlow 数据流

```
CuratorInput
    │
    ▼
CuratorService.evaluate()
    │  outcome ∈ {SKIPPED, REJECTED_DUPLICATE, PROPOSED}
    │
    ▼ (只有 PROPOSED 继续)
ValidatorService.validate(candidate, related_groups)
    │  outcome ∈ {VALIDATED, REJECTED, DEFERRED_HUMAN_REVIEW, NO_GROUPS}
    │
    ▼
ValidationReportStore.save()  →  data/validations/val_*.json
    │
    ▼
ReviewGate.evaluate()
    │
    ├── SKIPPED_NO_PROPOSAL
    ├── DUPLICATE_REJECTED
    ├── VALIDATION_FAILED         (无 promoted v 时)
    ├── ROLLBACK_REQUIRED         (有 promoted v 时,候选自动转 rejected)
    ├── NO_GROUPS
    ├── HIGH_RISK_HUMAN_REVIEW    (写 review_queue)
    └── READY_FOR_HUMAN_REVIEW    (写 review_queue)
                                       │
              ────── 操作员手动调用 ──── ▼
                              ReviewGate.approve(review_id, reviewer=...)
                                   或 ReviewGate.reject(review_id, ...)
                                       │
                                       ▼
                                 PROMOTED / REJECTED  ← 终态
```

## 4. ReviewGateOutcome

| 值 | 含义 | 队列 | 动作 |
|---|---|:---:|---|
| `SKIPPED_NO_PROPOSAL` | Curator 决定不学习 | — | 无 |
| `DUPLICATE_REJECTED` | 签名撞 — 已存在 | — | 无 |
| `VALIDATION_FAILED` | 数学未达标 | — | 候选保持 candidate |
| `ROLLBACK_REQUIRED` | 撞 promoted 旧版 | — | 候选自动转 `rejected`,旧版 unchanged |
| `NO_GROUPS` | 找不到 related task | — | 候选保持 candidate |
| `HIGH_RISK_HUMAN_REVIEW` | 高风险 → 强制人审 | ✅ | 操作员决定 |
| `READY_FOR_HUMAN_REVIEW` | 低风险 + validated → 等人审 | ✅ | 操作员决定 |
| `PROMOTED` | **只来自 `approve()`** | ✅(decided) | skill 转 PROMOTED |
| `REJECTED` | **只来自 `reject()`** | ✅(decided) | skill 转 REJECTED |

## 5. CI 四阶段门禁

`.github/workflows/harness-ci.yml` 的 4 个 job 顺序 chained:

| # | Gate | Phase | 测试集 |
|---|---|---|---|
| 1 | **contract-gate** | 0 | `test_os_agent_contract_snapshot.py` + `test_required_events_snapshot.py` |
| 2 | **runtime-gate** | 1 | `test_local_runtime_contract.py` + `test_tool_profiles.py` + `test_cli_stdio_local_runtime.py` |
| 3 | **delayed-validation-gate** | 2/3/4 | skill repo + curator + delayed validation + external crawler |
| 4 | **observer-evidence-gate** | 5/6 | observer + harness e2e + review gate |

`needs:` 链让最便宜的 gate 先失败。每个 gate 的命名直接映射到 docs/harness/PHASE{N} 文件,操作员看 CI 失败能直接 trace 到设计文档。

## 6. 关键不变量(测试守护)

| 不变量 | 测试 |
|---|---|
| **`evaluate()` 永不返回 PROMOTED**(任何 ValidationOutcome) | `test_evaluate_never_returns_promoted`(parametrized 4 outcomes) |
| **VALIDATED → READY_FOR_HUMAN_REVIEW,不自动 promote** | `test_evaluate_validated_queues_for_review_but_does_not_promote` |
| **高风险即使指标完美也走 review** | `test_high_risk_skill_always_queued_even_with_perfect_validation` |
| **rollback 不动 promoted v1** | `test_regressing_candidate_against_promoted_v1_does_not_demote_v1` |
| **首次失败不算 rollback** | `test_validation_failed_without_promoted_version_yields_validation_failed` |
| **approve 是唯一 promote 路径** | `test_only_approve_call_promotes` |
| **同一 review_id 双重决策抛 ValueError** | `test_double_decide_same_review_raises` |
| **路径遍历 review_id 拒绝** | `test_review_queue_path_traversal_rejected` |
| **审批落盘可审计**(reviewer / reason / timestamp) | `test_approve_promotes_skill_via_explicit_action` |

## 7. 测试矩阵(28 测试)

| 文件 | 测试数 | 角度 |
|---|---:|---|
| `test_review_gate_and_rollback.py` | 16 | 治理边界 + 高风险 + rollback + approve/reject 审计 + 队列 path-traversal |
| `test_harness_end_to_end.py` | 12 | HarnessFlow 端到端;plan/patch/revalidate 子模块 |

## 8. CLI 与 host 配置

### 推荐 `.mcp.json`(Claude Code / Codex / Cursor)

`scripts/write_mcp_config.sh` 输出:

```json
{
  "mcpServers": {
    "stableagent": {
      "type": "stdio",
      "command": "/abs/path/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--local", "--profile", "minimal"],
      "env": {
        "PYTHONPATH": "/abs/path",
        "STABLE_AGENT_RUNTIME_MODE": "local",
        "STABLE_AGENT_TOOL_PROFILE": "minimal",
        "STABLE_AGENT_HARNESS_MODE": "1"
      }
    }
  }
}
```

### Quickstart

```bash
./scripts/quickstart_harness.sh
```

做四件事(idempotent,可重复运行):
1. 在 `./.venv` 建/激活 venv
2. `pip install -r requirements.txt`
3. doctor — Phase 0–6 全部测试 collect-only(快速验证 import 没坏)
4. 打印推荐 `.mcp.json` 块

## 9. PR 验收清单

- [x] HarnessFlow 端到端可跑(端到端测试 12 条全过)
- [x] 失败时 candidate 自动转 `rejected`(rollback 路径 + ROLLBACK_REQUIRED outcome)
- [x] 只能到 `ready_for_human_review` / `high_risk_human_review`,**不能自动上线** — 4 个参数化测试守护
- [x] `.mcp.json` 与 quickstart 可用 — write_mcp_config.sh 已 smoke-test
- [x] PR-only — Harness 不调用 git
- [x] 不自动 merge / 不自动 deploy / 不绕过 approval / 不跳过 validation
- [x] CI 4 gate 覆盖 Phase 0-6 全部测试

## 10. Phase 0–6 完整测试总数

| Phase | 测试文件数 | 测试数 |
|---|---:|---:|
| Phase 0(契约 + 必需事件) | 2 | 20 |
| Phase 1(LocalRuntime + profiles) | 3 | 27 |
| Phase 2(SkillRepo v2) | 2 | 30 |
| Phase 3(Curator + Validator) | 2 | 27 |
| Phase 4(ExternalCrawler + Indexer) | 2 | 27 |
| Phase 5(Observer + Compare) | 1 | 14 |
| Phase 6(Harness + ReviewGate) | 2 | 28 |
| **总计** | **14** | **173** |

## 11. 已知遗留(Phase 6 之外)

| # | 项 | 处置 |
|---|---|---|
| L1 | `experiments/self_iteration_5_rounds/run_experiment.py:89` 的 `learning_triggered = round_num > 1` 仍在 | Phase 0 audit 标 blocker B5;Phase 6 通过 `CuratorPolicy.require_some_signal=True` 默认让该路径**永远 skip**,实际旧实验脚本不再产假数据 — 但脚本本身留着,等下个 PR 显式删除或改写 |
| L2 | 顶层 `OS-Agent/` 镜像目录仍在 | Phase 0 audit blocker B6;Phase 6 不动,issue 跟踪 |
| L3 | LocalRuntime 接 ABValidationRunner 的真实 wiring 还没接 — Phase 3 ValidatorService 测试用 InMemoryRunner | 后续 PR:`stable_agent/harness/runner_adapter.py` 把 LocalRuntime 包装成 `TaskRunner` Protocol |
| L4 | `evolve.md` 提到的 ICLR / ACL Anthology HTML fallback connector 没建 | Phase 4 已经覆盖三种主流 source(GitHub/arXiv/OpenReview),其余可作为后续 connector 增量 |
| L5 | Observer 没有 HTML 模板,只有 JSON API | Phase 5 文档已记;前端模板可以基于 `/api/runs/*/impact|compare` 后续增量 |
| L6 | `harness-ci.yml` 没有 ARM runner / windows runner | 默认 ubuntu-latest 即可;若有需求可后续加 matrix |

## 12. 整体工程位置变化(从路线图开始到 Phase 6 结束)

| 维度 | Before | After |
|---|---|---|
| 契约稳定性 | 无 snapshot | 26 字段 sc + 27 字段 sc.data + 13 必需事件冻结 |
| 运行时 | CLI/stdio 必须经 HTTP MCP | LocalRuntime 直连,3 个 profile 控制暴露面 |
| skill 系统 | best_skill.md 单文件覆盖 | SkillRepo v2:文件 + SQLite + 双层签名去重 + 7 状态生命周期 |
| 学习触发 | `round_num > 1` 硬编码(simulated) | 5 类真实信号 + `require_some_signal=True` 防线 |
| 验证 | 无 baseline vs candidate A/B | A/B + delayed validation + 6 项 PromotionCriteria + InMemoryRunner 单测 |
| 外部研究 | 无 | GitHub + arXiv + OpenReview 三 connector + FTS5 索引 + dedupe + research-bridge |
| 证据可见性 | dashboard 显示 0% 假象 | impact / compare / detail 三 API + 13 必需事件透明化 |
| 治理边界 | 无显式 review gate | ReviewGate 永不自动 promote + rollback 不 demote + 审计落盘 |
| CI | 测试零散 | 4-gate 流水线,每个 gate 对应一份 PHASE 文档 |
