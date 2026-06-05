# Phase 3 — Curator + Validator + 真实 A/B 闭环

> Phase 2 SkillRepo v2 让 candidate 有了落地点,Phase 3 让 candidate **真的被验证**:用 baseline vs candidate 的 A/B 跑出 score/token/latency/regression,只有指标真实达标的 candidate 才能进入 `validated` 状态。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **拒绝 simulated learning** | Curator 必须从真实信号(low score / missing events / failure attribution / user feedback / external findings)中学习,不接受 `round_num > 1` 这种伪触发 |
| **数据与策略分离** | `ABValidationRunner` 只算数学,`PromotionCriteria` 只判通过/失败 — 单测不需要 Orchestrator |
| **只有 Validator 能转 candidate→validated** | Curator 提案、Validator 验证、HumanReview 晋升,职责单一 |
| **高风险永不自动晋升** | `risk_level=high` 进 `deferred_human_review`,无论指标多漂亮 |
| **无 LLM 依赖** | Phase 3 Curator 用确定性模板;Phase 6 可加可选 LLM 改写 |

## 2. 模块布局

```
stable_agent/eval/                     新增
├── __init__.py
├── ab_validation_runner.py     — A/B 数学 + InMemoryRunner(显式 fake)
└── task_group_store.py         — JSONL 文件存储 + related-task 选择

stable_agent/core/                     新增
├── curator_service.py          — CuratorInput/Policy/Outcome/Decision
└── validator_service.py        — ValidationOutcome/Decision
```

## 3. 关键数据流

```
真实 run(eval_score / missing_events / feedback)
        │
        ▼
   CuratorService.evaluate(input)
        │ (有学习信号才提案)
        ▼
   SkillDocument(status=draft) ──write──▶ SkillRepository
                                              │
   transition_status(candidate)               │
        │                                     │
        ▼                                     ▼
   ValidatorService.validate(skill)     SQLite index
        │
        ├─ select_groups(retrieval_tags, task_type)
        ├─ for each group:
        │     ABValidationRunner.run(skill, group)
        │       ├─ baseline runs(无 candidate)
        │       ├─ candidate runs(注入 candidate)
        │       └─ aggregate → ValidationReport
        │           passed = PromotionCriteria.passes(report, risk_level)
        │
        ▼
   ValidationDecision { validated | rejected | deferred_human_review | no_groups }
        │
        ├─ validated → repo.transition_status(VALIDATED) + 写 metrics
        ├─ rejected  → 维持 candidate;reason 写入观察面
        └─ deferred  → 维持 candidate;HumanReview 接手
```

## 4. CuratorPolicy 默认值

| 参数 | 默认 | 来源 |
|---|---:|---|
| `min_eval_score_to_learn` | 0.75 | 路线图 §3.6 |
| `max_candidate_body_chars` | 8192 | Phase 3 实测合理上限(替代路线图的 `compression_ratio_max` — 后者只在有源 trace 长度时有意义) |
| `require_some_signal` | `True` | 这个旗标是 simulated-learning 防线;关掉它就退回到旧实验脚本的行为,**只在测试里关** |

## 5. PromotionCriteria 默认值

| 参数 | 默认 | 路线图 |
|---|---:|---|
| `min_delta_score_promote` | 0.03 | §3.6 promote 级 |
| `max_token_increase_promote` | 0.10 | §3.6 |
| `max_latency_increase_promote` | 0.15 | §3.6 |
| `max_regression_rate` | 0.0 | §3.6(必须 0 回归) |
| `min_required_events_completeness` | 1.0 | Phase 0 13 个必需事件 |
| `require_high_risk_human_review` | `True` | §3.6 |

## 6. 关键不变量(测试守护)

| 不变量 | 测试 |
|---|---|
| **零 score delta 不能 pass** | `test_validator_does_not_pass_with_zero_delta` — 直接守护"路线图 round_num > 1 简化版"复现 |
| **任一回归 → 整组 reject** | `test_ab_runner_rejects_on_any_regression` |
| **lost required events = regression** | `test_ab_runner_rejects_on_lost_required_events` |
| **token blowup → reject** | `test_ab_runner_rejects_token_blowup` |
| **high_risk → deferred,即使指标完美** | `test_validator_high_risk_always_deferred` |
| **candidate 写入不触碰 best_skill.md** | `test_candidate_does_not_publish_best_skill_md` |
| **空输入 / 无信号 → skip,不 propose** | `test_curator_skips_when_no_learning_signal`, `test_curator_skips_empty_input` |

## 7. 测试矩阵(27 测试)

| 文件 | 测试数 | 角度 |
|---|---:|---|
| `test_delayed_validation_ab.py` | 16 | A/B 数学;Validator 决策矩阵;TaskGroupStore IO;related-task 选择 |
| `test_curator_candidate_pipeline.py` | 11 | NO simulated learning 防线;5 种学习信号;persistence;duplicate handling |

## 8. PR 验收清单

- [x] candidate skill 由真实 trace 驱动(5 种信号)
- [x] baseline vs candidate A/B 跑通 — `ABValidationRunner` 通过 `InMemoryRunner` 单测
- [x] **不再 simulated learning** — `test_validator_does_not_pass_with_zero_delta` 守护
- [x] promotion 依赖 validation — `Validator` 是唯一能转 `VALIDATED` 的入口
- [x] 高风险 skill 必须转 human review
- [x] 不绕过 human review
- [x] 不让没有 source_run_id 的 candidate 进入验证

## 9. 与旧 `experiments/self_iteration_5_rounds/` 的关系

旧实验:`run_experiment.py:89` 硬编码 `learning_triggered = round_num > 1`。

Phase 3 之后:Phase 6 Harness CI 会用真实的 Curator + Validator 取代该实验脚本。Phase 3 本身不删旧脚本(blocker B5 by Phase 0 audit),但 `CuratorPolicy.require_some_signal=True` 默认值使旧逻辑在新管道里**永远 skip**,所以旧路径不再可能产生假学习指标。

## 10. 已知遗留(交给 Phase 4-6)

| # | 项 | 处置 |
|---|---|---|
| L1 | InMemoryRunner 在生产代码里 — 故意的(避免命名冲突),Phase 6 可挪到 `tests/_helpers/` | Phase 6 |
| L2 | LocalRuntime 接 ABValidationRunner 的 production wiring 还没接 — 测试足够覆盖数学 | Phase 6 Harness flow |
| L3 | `CuratorService._build_draft` 是确定性模板 — 没用 LLM 改写 | Phase 6 可加 feature flag |
| L4 | TaskGroup find_related 是手工分数(2/2/1 加权);未来可改成 BM25 over notes | Phase 5 |
| L5 | 路线图 `min_delta_score_canary=0.01` 的 canary 等级未实现 | Phase 6 |
