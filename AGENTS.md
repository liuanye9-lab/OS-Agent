# AGENTS.md — StableAgent OS Default Calling Rules

> 适用于所有接入 StableAgent OS 的 AI Coding Agent（Claude Code / Cursor / Codex / Trae 等）。

## 核心规则

在执行**任何非平凡的编码任务**之前，**必须先调用** `stableagent.task.os_agent`。

### 什么是"非平凡"？

满足以下任一条件即视为非平凡任务：
- 需要修改 ≥ 2 个文件
- 涉及架构决策、API 设计、数据模型变更
- 需要引入新的依赖或配置
- 需要理解项目全局上下文（跨模块、跨服务）
- 风险较高的操作（删除、重构、迁移）

### 可以直接执行的任务（无需调用 os_agent）

- 单行修复（拼写错误、格式调整）
- 读取单个文件并回答简单问题
- 运行已知的测试命令
- 执行 git 操作（status、log、diff）

## StableAgent Calling Priority

1. **优先使用 HTTP MCP**：Prefer MCP; call `stableagent.task.os_agent`

2. **如果 HTTP MCP 不可用，使用 stdio MCP**：call `stableagent-stdio.task.os_agent`

3. **如果 MCP 都不可用，使用 CLI fallback**：

```bash
PYTHONPATH=. /Users/Zhuanz/OS-Agent/OS-Agent/.venv/bin/python -m stable_agent.cli task run \
  --task-input "<user task>" \
  --open-dashboard \
  --json
```

**禁止**：
- 不要使用 `python`（会调用系统 Python 3.9，触发 StrEnum ImportError）
- 不要使用 `python3`（会调用系统 Python 3.9，触发 StrEnum ImportError）
- 必须使用 `.venv/bin/python`

**必须返回**：
- `run_id`
- `dashboard_url`
- `observer_url`
- `missing_required_events`
- `understanding_trace`
- `token_report`
- `expression_matches`

Do not start editing files before either MCP or CLI creates a StableAgent run.

## 调用方式

标准调用格式（必须包含 `task_input` 和 `open_dashboard`）：

```json
{
  "method": "tools/call",
  "params": {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "task_input": "任务描述",
      "open_dashboard": true
    }
  }
}
```

返回字段清单：
- `ok`: 执行是否成功
- `run_id`: 运行 ID
- `dashboard_url`: Dashboard URL
- `observer_url`: Observer URL
- `missing_required_events`: 缺失的事件列表
- `understanding_trace`: 理解轨迹
- `token_report`: Token 报告
- `expression_matches`: 表达匹配
- `result`: os_agent 建议方案（兼容字段）
- `risk_assessment`: 风险评估（兼容字段）
- `requires_human_review`: 是否需要人工审核（兼容字段）
- `task_id`: 任务标识（兼容字段）

## 返回处理

os_agent 返回结果后：
1. 解析 `result` 字段获取建议方案
2. 如建议包含风险评估，需确认后再执行
3. 如建议标记为 `requires_human_review`，停止并请求人工审批
4. 执行完成后，将结果回传给 os_agent 用于效果评估

## 效果评估数据回传

每次任务完成后，调用 os_agent 记录效果数据：

```json
{
  "method": "tools/call",
  "params": {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "action": "record_effectiveness",
      "task_id": "任务标识",
      "mode": "stableagent | baseline",
      "success": true,
      "edits_made": 5,
      "tokens_used": 12000,
      "intent_drift": 0
    }
  }
}
```
