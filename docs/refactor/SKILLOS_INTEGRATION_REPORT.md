# SKILLOS_INTEGRATION_REPORT.md — SkillOS 融合报告

## Executor / Curator 分离

**已实现。**

- `OSAgentExecutor` (core/executor.py) 只负责执行任务并生成 RunTrace
- `CuratorService` (core/curator.py) 只负责从 RunTrace 提炼 SkillCandidate
- `OSAgentHandler` (core/os_agent_handler.py) 编排两者

流程:
```
TaskSpec → OSAgentExecutor.run() → RunTrace
    → CuratorService.analyze_trace()
    → CuratorService.propose_candidates()
    → ValidationGate.validate_schema()
    → SkillRepository.create_candidate()
```

## Candidate 生成

**已实现。**

- eval_score < 0.75 → 触发学习
- force_eval_failed=true → 必须触发学习
- dashboard_replay_ok=false → 必须触发学习
- missing_required_events 非空 → 必须触发学习
- Candidate 写入 `.skills/candidates/`
- Candidate 带 `source_run_id`

## Delayed Validation

**已实现 (v1)。**

- `validator.validate_delayed()` 不再是 stub
- 使用 related tasks 进行 baseline vs candidate 对比
- 检查 score_delta >= 0.03, regression_count == 0
- `RelatedTaskStore` 提供 related tasks 数据源
- `DelayedValidationGate` 支持 holdout task 验证

## best_skill.md 来源

**已保证。**

- `SkillRepository.export_best_skill()` 只导出 promoted skills
- Candidate 不直接写入 best_skill.md
- dry_run_learning=true 时不允许 promote

## dry_run_learning 安全

**已保证。**

- `OSAgentHandler._run_curator()` 中检查 `task.dry_run_learning`
- dry_run_learning=true 时只生成 candidate，不 promote
- 不改变现有 dry_run_learning 行为
