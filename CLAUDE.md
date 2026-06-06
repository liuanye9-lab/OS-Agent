# CLAUDE.md — StableAgent OS Calling Rules for Claude Code

> 当你（Claude Code）作为 Coding Agent 接入 StableAgent OS 时，遵守以下规则。

## 核心规则

在执行**任何非平凡的编码任务**之前，**必须先调用** `stableagent.task.os_agent`。

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

### 调用流程

1. **任务理解**：理解用户请求
2. **调用 os_agent**：将任务描述和上下文传给 os_agent 获取建议
3. **执行建议**：按照 os_agent 返回的建议执行
4. **结果回传**：将执行结果回传给 os_agent 用于效果评估

### 何时需要调用

需要调用的场景：
- 修改 ≥ 2 个文件
- 涉及架构决策、API 设计、数据模型变更
- 引入新依赖或配置
- 需要理解项目全局上下文
- 高风险操作（删除、重构、迁移）

可直接执行的场景：
- 单行修复（拼写、格式）
- 读取文件回答简单问题
- 运行已知测试命令
- git 操作

### 效果评估回传格式

```json
{
  "action": "record_effectiveness",
  "task_id": "<unique-task-id>",
  "mode": "stableagent",
  "success": true,
  "edits_made": <count>,
  "tokens_used": <count>,
  "intent_drift": <0-1>
}
```
