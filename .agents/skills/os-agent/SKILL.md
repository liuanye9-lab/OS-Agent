---
name: os-agent
description: 启动 StableAgent OS 自优化工作流，每次执行都会在 Dashboard 实时展示 Agent 在做什么、为什么、进度多少
disable-model-invocation: true
---

# OS Agent Skill

在本项目中，OS Agent 是默认对话入口。用户输入 `/os-agent` 时，或项目规则要求默认启动 OS Agent 时：

1. 检查 StableAgent OS 是否在 `http://127.0.0.1:8000` 运行。
2. 如未运行，自动执行 `bash .agents/skills/os-agent/scripts/launch_dashboard.sh` 启动服务并打开 Dashboard；不要只提示用户手动运行。
3. 调用 MCP 工具: `stableagent.task.os_agent`，参数: `{"task_input": "$ARGUMENTS", "open_dashboard": true}`
4. 读取返回的 `run_id` 和 `dashboard_url`
5. 回复用户:

```
OS Agent 已启动

任务: $ARGUMENTS
运行 ID: {run_id}
当前阶段: {current_stage}
进度: {progress_pct}%
状态: {status_text_zh}

打开 Dashboard 查看实时进度:
→ {dashboard_url}
```

6. 不要暴露内部推理链，只展示可观察决策摘要
7. 如果 `$ARGUMENTS` 为空，询问用户想要执行什么任务
