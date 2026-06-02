# 02_RISK_AND_ROLLBACK.md — 风险与回滚策略

## 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| 删除内联回退后 executor 不稳定 | 中 | 高 | 先冻结契约测试，确保 executor 路径通过后再删除 |
| CuratorService 接入后破坏 eval 流程 | 低 | 中 | Curator 作为后置步骤，失败不影响主流程 |
| Delayed Validation 实现引入 bug | 中 | 低 | 第一版简化实现，不改变现有 promotion 逻辑 |
| Local Runtime 初始化失败 | 中 | 高 | 保留 HTTP 回退路径 (--http flag) |
| 测试覆盖不足 | 中 | 中 | 每个 Phase 新增对应测试 |

## 回滚策略

### Phase 2 (拆分 handler)

- **回滚方式:** `git revert` 单个 commit
- **验证:** `python -m pytest tests/test_unified_tool_registry.py tests/test_os_agent_handler_slim.py -q`
- **关键检查:** _h_task_os_agent 行数 ≤ 80

### Phase 3 (Curator 接入)

- **回滚方式:** 在 OSAgentHandler 中注释掉 CuratorService 调用
- **验证:** `python -m pytest tests/test_curator_main_loop.py -q`
- **关键检查:** force_eval_failed 生成 candidate

### Phase 4 (Delayed Validation)

- **回滚方式:** 恢复 validator.py 中的 stub 实现
- **验证:** `python -m pytest tests/test_delayed_validation_v1.py tests/test_promotion_policy.py -q`
- **关键检查:** validate_delayed 不再是 stub

### Phase 5 (Local Runtime)

- **回滚方式:** CLI/stdio 恢复 HTTP 调用
- **验证:** `python -m pytest tests/test_local_runtime.py tests/test_cli_without_http.py -q`
- **关键检查:** 不启动 server 时 CLI 能工作

## 逐阶段验证清单

- [ ] Phase 1: contract test 通过
- [ ] Phase 2: _h_task_os_agent ≤ 80 行
- [ ] Phase 3: Curator 接入主链路
- [ ] Phase 4: Delayed Validation 真实实现
- [ ] Phase 5: CLI/stdio 脱离 HTTP
- [ ] Phase 6: 文档更新
- [ ] Phase 7: Observer 瘦身
- [ ] Phase 8: 全量测试通过
