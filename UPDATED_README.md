<p align="center">
  <img src="https://img.shields.io/badge/StableAgent-Capsule-111827?style=for-the-badge" alt="StableAgent Capsule">
  <img src="https://img.shields.io/badge/MCP-10_tools_(minimal)-7c3aed?style=for-the-badge" alt="MCP Tools">
  <img src="https://img.shields.io/badge/Skill_Curation-Layer-22c55e?style=for-the-badge" alt="Skill Curation">
  <img src="https://img.shields.io/badge/CLI--First-Ready-0ea5e9?style=for-the-badge" alt="CLI-First">
  <img src="https://img.shields.io/badge/Delayed_Validation-v1-f59e0b?style=for-the-badge" alt="Delayed Validation">
</p>

<h1 align="center">StableAgent Capsule</h1>

<p align="center">
  <strong>A lightweight CLI/MCP skill curation layer for self-evolving coding agents.</strong><br />
  <sub>减少 AI Coding Agent 的跑偏、失忆、重复犯错和上下文压缩降智</sub>
</p>

---

## 一句话定位

**StableAgent Capsule 是一个通过 CLI/MCP 接入 Claude Code、Codex、Cursor 的个人技能进化层。**

它不是另一个 Agent，不堆 55 个工具。它是一层可观察、可验证、可回滚、可迁移的 **Skill Curation Layer**。

| 概念 | 说明 |
|---|---|
| Executor | 只负责执行任务 |
| Curator | 只负责整理技能 |
| SkillRepo | 外部技能库，不是记忆垃圾桶 |
| ValidationGate | candidate 必须经过验证 |
| Delayed Validation | 用后续相关任务验证改进效果 |
| best_skill.md | 只来自 promoted skills 汇总导出 |

## 架构概览

```
CLI / stdio MCP / HTTP MCP
        ↓
  OSAgentHandler (薄编排层)
        ↓
  OSAgentExecutor.run() → RunTrace
        ↓
  CuratorService.analyze_trace()
        ↓
  CuratorService.propose_candidates()
        ↓
  ValidationGate.validate_schema()
        ↓
  SkillRepository.create_candidate()
        ↓
  DelayedValidation → validated / promoted
```

## 快速开始

### CLI Mode (推荐，不需要启动 server)

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "重构登录模块" \
  --json
```

### stdio MCP Mode (Claude Code 集成)

```json
{
  "mcpServers": {
    "stableagent-stdio": {
      "type": "stdio",
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--profile", "minimal"],
      "env": {
        "PYTHONPATH": "/path/to/OS-Agent"
      }
    }
  }
}
```

### HTTP MCP Mode (可选)

```bash
# 启动 server
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve

# Claude Code 配置
{
  "mcpServers": {
    "stableagent-http": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp/"
    }
  }
}
```

## Tool Profiles

| Profile | 工具数 | 说明 |
|---|---|---|
| minimal | 10 | 核心闭环 (默认) |
| default | 20 | 核心 + eval/skill 调试 |
| full | 55 | 所有旧工具 (兼容) |

```bash
export STABLE_AGENT_TOOL_PROFILE=minimal
```

## Skill 生命周期

```
draft → candidate → validated → promoted → deprecated → archived
```

- 失败经验只能生成 **candidate**
- candidate 必须经过 **ValidationGate**
- **Delayed Validation** 用后续相关任务验证
- `dry_run_learning=true` 时只允许生成 candidate，不允许 promote
- `best_skill.md` 只来自 promoted skills 汇总

## 核心组件

| 组件 | 文件 | 职责 |
|---|---|---|
| OSAgentHandler | `core/os_agent_handler.py` | 薄编排层 |
| OSAgentExecutor | `core/executor.py` | 执行任务，生成 RunTrace |
| CuratorService | `core/curator.py` | 从 trace 提炼 skill 候选 |
| ValidationGate | `core/validator.py` | Schema + Regression + Delayed 验证 |
| SkillRepository | `skills/repository.py` | 文件 + SQLite 双层存储 |
| DelayedValidationGate | `core/delayed_validation.py` | 延迟验证 (related tasks) |
| LocalRuntime | `runtime/local_runtime.py` | CLI/stdio 本地运行时 |

## 详细文档

- [核心架构](docs/CORE_ARCHITECTURE.md)
- [MCP 配置](docs/CLAUDE_CODE_MCP_SETUP.md)
- [SkillOS 集成](docs/SKILLOS_ADAPTATION.md)
- [CLI 指南](docs/CLI_FIRST_GUIDE.md)
- [重构报告](docs/refactor/FINAL_PROGRESS_REPORT.md)
