# Phase 1 — Runtime 拆薄 + LocalRuntime + Tool Profiles

> Phase 0 冻结契约,Phase 1 让 CLI 与 stdio MCP **真正不依赖 HTTP**;
> 同时把 47 个已注册工具按 profile 收口到 minimal/default/full 三层。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **不破坏 V11.4 既有部署** | HTTP MCP 仍然可用;CLI/stdio MCP 默认仍走 HTTP;LocalRuntime 是**新增并行入口**,不是替换 |
| **不动 540 行 monolith handler** | Phase 0 audit blocker B1 — `_h_task_os_agent` 暂不挪;`core/os_agent_handler.py` 是薄 façade |
| **shape 等价** | LocalRuntime 复用 `ResponseAdapter.to_mcp_content`,所以 Phase 0 contract snapshot 同时保护 HTTP / in-process 两条路径 |
| **profile 是过滤,不是定义** | 工具 schema 仍然只在 `tool_schemas.py` 一份;profile 只决定**谁能看到**它们 |

## 2. 新增组件

```
stable_agent/
├── core/
│   ├── __init__.py            (new)
│   └── os_agent_handler.py    (new — 薄 façade,9 字段 envelope)
├── runtime/
│   └── local_runtime.py       (new — in-process 工具运行时)
└── gateway/
    └── tool_profiles.py       (new — minimal/default/full)

tests/
├── test_local_runtime_contract.py  (new — 14 tests)
├── test_tool_profiles.py            (new — 9 tests)
└── test_cli_stdio_local_runtime.py  (new — 4 tests)

stable_agent/
├── cli.py             (edit — `task run --local` 旗标)
└── mcp_stdio.py       (edit — `--local` / `--profile` 旗标)
```

## 3. LocalRuntime 形状

```python
from stable_agent.runtime.local_runtime import LocalRuntime

runtime = LocalRuntime()
response = runtime.call_tool(
    "stableagent.task.os_agent",
    {"task_input": "demo", "open_dashboard": False},
)
# response shape ≡ HTTP MCP 的 result payload:
#   {"content": [...], "structuredContent": {...}, "isError": bool}
```

LocalRuntime 内部组件构造 mirror 了 `MCPGateway.__init__`:

| 组件 | 复用方式 |
|---|---|
| `StableAgentOrchestrator` | 懒构造单例(`get_default_runtime()`) |
| `UnifiedToolRegistry` | 完整 47 个工具,**未做任何替换** |
| `ToolRouter` | 完整 — security_policy / approval_manager / RunStore / EventStream / EventBus 全部接入 |
| `ResponseAdapter` | 同一 `to_mcp_content`,因此 sc 顶层 26 字段 + sc.data 27 字段不变 |

## 4. CLI envelope 投影

`stable_agent/core/os_agent_handler.py:run_os_agent` 是**唯一一个**把 sc 收成 9 字段 envelope 的位置(`cli.py:cmd_task_run` 不再重复写投影逻辑,直接调它)。投影规则与 Phase 0 PHASE0_CONTRACT.md §1 完全一致:

| 9 字段 | 来源 |
|---|---|
| `ok` | `sc.ok ∨ ¬isError` |
| `run_id` | `sc.run_id` |
| `dashboard_url` | `base_url + sc.dashboard_url`(空 base 时只返回路径) |
| `observer_url` | `base_url + sc.observer_url`(空 base 时只返回路径) |
| `missing_required_events` | `sc.missing_required_events` |
| `understanding_trace` | `sc.understanding_trace` |
| `token_report` | `sc.token_report` |
| `expression_matches` | `sc.expression_matches` |
| `error` | `sc.error \|\| sc.plain_text` 或 `"工具调用失败,原因未知"` |

## 5. CLI / stdio MCP 旗标

### CLI(`cli.py:cmd_task_run`)

```bash
# V11.4 默认 — 走 HTTP MCP(向后兼容,行为不变)
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run --task-input "..."

# Phase 1 新增 — in-process LocalRuntime,完全不依赖 HTTP server
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run --task-input "..." --local
```

### stdio MCP(`mcp_stdio.py:main`)

```bash
# V11.4 默认 — HTTP 模式,8 个工具(CORE_TOOLS)
.venv/bin/python -m stable_agent.mcp_stdio

# Phase 1 — in-process,minimal profile(默认 12 个工具)
.venv/bin/python -m stable_agent.mcp_stdio --local

# 自定义 profile
.venv/bin/python -m stable_agent.mcp_stdio --local --profile default
.venv/bin/python -m stable_agent.mcp_stdio --local --profile full

# 强制 HTTP(覆盖环境变量)
.venv/bin/python -m stable_agent.mcp_stdio --http
```

环境变量(部署友好):

| 变量 | 取值 | 说明 |
|---|---|---|
| `STABLE_AGENT_RUNTIME_MODE` | `local` / `http` | 默认 `http`(V11.4 兼容) |
| `STABLE_AGENT_TOOL_PROFILE` | `minimal` / `default` / `full` | 默认 `minimal`(stdio 入口) |

## 6. Tool profiles

| Profile | 工具数 | 受众 |
|---|---:|---|
| **minimal** | ≤ 12(硬上限 `MINIMAL_MAX`) | Claude Code / Codex / Cursor 等 AI host |
| **default** | ~38 | 个人开发者 CLI |
| **full** | 47(无过滤) | 调试 / SaaS 后端 |

Phase 1 minimal 包含的 12 个:

```
stableagent.task.os_agent
stableagent.task.process
stableagent.feedback.remember
stableagent.feedback.dont_do_this_again
stableagent.feedback.correct_and_remember
stableagent.understanding.trace
stableagent.trace.get_run
stableagent.approval.respond
stableagent.token.summary
stableagent.memory.health
stableagent.capsule.status
stableagent.eval.evaluate
```

> 加任何一个新工具到 minimal,`test_minimal_under_hard_cap` 会立刻失败 —
> 这是防止 profile drift 的硬门禁。

## 7. 推荐 `.mcp.json`(host 配置)

```json
{
  "mcpServers": {
    "stableagent": {
      "type": "stdio",
      "command": "/ABSOLUTE_PATH/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio", "--local", "--profile", "minimal"],
      "env": {
        "PYTHONPATH": "/ABSOLUTE_PATH",
        "STABLE_AGENT_RUNTIME_MODE": "local",
        "STABLE_AGENT_TOOL_PROFILE": "minimal"
      }
    }
  }
}
```

CLAUDE.md 现在的 fallback 命令(`PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run --task-input "..."`)在 Phase 1 之后可以选择性加 `--local`,以摆脱 `serve` 前置依赖。

## 8. 测试矩阵

| 测试文件 | 用途 | 关键断言 |
|---|---|---|
| `test_local_runtime_contract.py` | LocalRuntime ≡ HTTP MCP | sc 顶层 / sc.data 键集合一致;13 必需事件齐;`event_sync_ok` 三连绿;urlopen 被 monkeypatch 后 LocalRuntime 仍能完成调用 |
| `test_tool_profiles.py` | profile 过滤逻辑 | minimal ≤ 12;default ⊇ minimal;env 与 CLI 旗标优先级;无重复 |
| `test_cli_stdio_local_runtime.py` | stdio MCP `--local` 子进程契约 | tools/list 受 profile 约束;tools/call 离线可用;sc shape 与 HTTP 一致 |

## 9. PR 验收清单

- [x] CLI `task run --local` 默认无需 HTTP server
- [x] stdio MCP `--local` 默认无需 HTTP server
- [x] minimal profile 硬上限 12,test 守护
- [x] LocalRuntime 复用 `ResponseAdapter` → Phase 0 契约同时保护两条路径
- [x] V11.4 既有部署不破:HTTP 路径与所有现有测试不变
- [x] 不动 `_h_task_os_agent`(façade only)
- [x] 不引入新依赖

## 10. 已知遗留(交给 Phase 2+)

| # | 项 | 处置 |
|---|---|---|
| L1 | LocalRuntime 启动期会构造 LLM client → 离线 host 必须能容忍 LLM 不可达 | 已经容忍 — 失败时 evaluator 走 fallback;无需阻断 |
| L2 | `mcp_stdio` 的静态 `CORE_TOOLS`(8 个)在 HTTP 模式下还是手写的 | Phase 5/6 统一到 profile 过滤即可;现阶段保留以避免破坏 V11.4 客户端 |
| L3 | `core/os_agent_handler.py` 当前只是投影函数,Phase 2 SkillRepo / Phase 3 Curator 完成后可以变成真正的 orchestration entry | — |
| L4 | 顶层 `OS-Agent/` 子目录是旧镜像 | 维持 Phase 0 audit 中的标注,Phase 6 单独清理 |
