# REMAINING_RISKS.md — 剩余风险

## 高优先级

1. **Local Runtime 初始化依赖链**
   - `LocalStableAgentRuntime._ensure_initialized()` 依赖 `Orchestrator`、`ToolRouter` 等
   - 如果这些组件的初始化失败，CLI/stdio 将无法工作
   - **缓解:** HTTP 回退路径仍然可用 (`--http` flag)

2. **CuratorService 生成的 candidate 质量**
   - `_generate_proposed_rule()` 使用硬编码模板
   - 实际场景中需要 LLM 生成更精确的规则
   - **缓解:** candidate 不直接影响执行，只进入候选池

3. **Delayed Validation v1 简化实现**
   - `_estimate_improvement()` 使用启发式估算，非真实执行
   - 需要集成真实 executor 才能得到准确结果
   - **缓解:** 当前实现已满足基本验证需求

## 中优先级

4. **MCP 网关测试 (10 个既存失败)**
   - 工具数量、格式等测试与当前架构不匹配
   - 需要更新这些测试以匹配新架构

5. **unified_tool_registry.py 仍有 1937 行**
   - 55 个 handler 方法可以进一步拆分
   - SaaS 相关 handler (12 个) 可以移到独立模块

## 低优先级

6. **Dashboard Observer 瘦身未完成**
   - Phase 7 (Observer 瘦身) 在本轮未实施
   - 当前 Observer 功能正常，只是信息偏杂

7. **最佳实践**
   - `export_best_skill()` 只从 promoted skills 汇总
   - 但目前没有自动 promote 机制 (需要 human review)
