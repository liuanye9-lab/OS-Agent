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

## 这个项目是什么？

想象你雇了一个天才实习生——**Claude Code / Codex / Cursor**。

他极其聪明，但有四个致命弱点：

| 弱点 | 表现 | 后果 |
|---|---|---|
| 🔴 跑偏 | 做着做着忘了你真正要什么 | 白费 token，返工 |
| 🔴 失忆 | 每次对话都从零开始 | 你得反复解释项目规范 |
| 🔴 重复犯错 | 上次踩过的坑，这次又踩 | 同一个 bug 修三次 |
| 🔴 压缩降智 | 上下文太长时丢掉关键信息 | 忘了你的架构约束 |

**StableAgent Capsule 就是给这个实习生配的一套「外接大脑」。**

它不是另一个 AI，不替代 Claude Code。它是一层**旁路系统**，安插在你和 AI 之间：

```
  你 (高见远)
   ↓ 任务描述
  StableAgent Capsule ← 记住习惯、约束、失败经验
   ↓ 增强后的上下文
  Claude Code / Codex / Cursor
   ↓ 执行结果
  StableAgent Capsule ← 评估、提炼、验证技能
   ↓ 可观测的反馈
  你
```

---

## 核心类比：餐厅厨房

把整个系统想成一家餐厅的后厨：

```
┌─────────────────────────────────────────────────────┐
│                   餐厅后厨                           │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │  Executor │   │  Curator │   │ Validation   │    │
│  │  (主厨)   │   │  (品控)  │   │   Gate       │    │
│  │          │   │          │   │  (卫生检查)   │    │
│  │ 炒菜      │   │ 试吃     │   │ 检查食材新鲜度│    │
│  │ 不负责摆盘 │   │ 记录配方 │   │ 检查温度达标  │    │
│  │          │   │ 不负责炒菜│   │ 不负责烹饪    │    │
│  └──────────┘   └──────────┘   └──────────────┘    │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │ SkillRepo │   │ Delayed  │   │ best_skill   │    │
│  │  (菜谱库) │   │ Validation│   │   .md        │    │
│  │          │   │  (食客反馈)│   │  (招牌菜)    │    │
│  │ 存放配方   │   │ 下次来吃  │   │ 只收录通过   │    │
│  │ 不是垃圾桶 │   │ 验证好不好│   │ 验证的配方   │    │
│  └──────────┘   └──────────┘   └──────────────┘    │
└─────────────────────────────────────────────────────┘
```

**类比对应：**

| 餐厅概念 | StableAgent 概念 | 说明 |
|---|---|---|
| 主厨炒菜 | **Executor** | 只管执行任务，不管学习 |
| 品控试吃 | **Curator** | 从执行结果中提炼经验 |
| 新配方草案 | **candidate** | 失败经验只能生成草案 |
| 卫生检查 | **ValidationGate** | 草案必须通过检查才能用 |
| 食客反馈 | **Delayed Validation** | 用后续任务验证配方好不好 |
| 招牌菜 | **best_skill.md** | 只收录经过验证的配方 |
| 菜谱库 | **SkillRepo** | 外部技能库，不是垃圾桶 |

---

## 为什么不是「另一个 Agent」？

市面上已经有很多 Agent 框架。StableAgent Capsule 的定位完全不同：

| 项目 | 做什么 | 类比 |
|---|---|---|
| Claude Code | 写代码的 AI | 天才实习生 |
| LangChain | 编排多个 AI | 项目经理 |
| AutoGPT | 自主完成任务 | 全栈自由职业者 |
| **StableAgent Capsule** | **让 AI 更稳定、可进化** | **导师 + 菜谱库 + 品控** |

它不训练模型权重，不替代你的 AI 工具。它做的事情是：

> **把你和 AI 的交互经验，沉淀成可验证、可回滚、可迁移的技能。**

---

## 四个核心问题 → 四个解决方案

```
 问题                           解决方案
 ─────                          ─────────
 跑偏？                   →    上下文压缩保护 + 意图对齐
   ↓                             ↓
 失忆？                   →    时间记忆 + SkillRepo
   ↓                             ↓
 重复犯错？               →    Curator → candidate → ValidationGate
   ↓                             ↓
 压缩降智？               →    Context Compression Guard + Token 预算
```

每一次任务执行，都会经过这条流水线：

```
 任务进来
   ↓
 ┌─ Phase 1: 接收 + 理解意图
 ├─ Phase 2: 召回时间记忆 (防失忆)
 ├─ Phase 3: RAG 检索项目资料
 ├─ Phase 4: 上下文压缩保护 (防降智)
 ├─ Phase 5: 执行任务
 ├─ Phase 6: 评估结果 (防跑偏)
 ├─ Phase 7: 提炼技能 (防重复犯错)
 └─ Phase 8: 完成 + 可视化
   ↓
 任务完成
```

---

## Skill 生命周期：从失败到招牌菜

```
 一次失败的任务
       ↓
  ┌─────────┐
  │ Curator │ ← "这次为什么失败了？"
  └────┬────┘
       ↓
  ┌──────────┐
  │ candidate │ ← 草案：只是一条改进建议
  └────┬─────┘     不能直接用，不能写入菜谱
       ↓
  ┌──────────────┐
  │ ValidationGate│ ← Schema 检查：格式对不对？
  └────┬─────────┘     Regression 检查：会不会更差？
       ↓
  ┌──────────────────┐
  │ Delayed Validation│ ← 用后续相关任务验证
  └────┬─────────────┘     "这个配方在其他菜上也好用吗？"
       ↓
  ┌──────────┐
  │ validated │ ← 通过验证
  └────┬─────┘
       ↓
  ┌──────────┐
  │ promoted  │ ← 进入菜谱库，成为招牌菜
  └──────────┘     写入 best_skill.md
```

**关键约束：**

- 失败经验 **只能** 生成 candidate，不能直接写入长期记忆
- candidate **必须** 经过 ValidationGate
- `dry_run_learning=true` 时 **禁止** promote（只观察，不行动）
- `best_skill.md` **只** 来自 promoted skills 汇总

---

## 三种接入方式

### 1. CLI Mode（推荐，零依赖）

不需要启动 server，不需要配置 MCP。直接命令行：

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "重构登录模块" \
  --json
```

**类比：** 直接打电话给实习生，不需要通过前台。

### 2. stdio MCP Mode（Claude Code 集成）

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

**类比：** 实习生坐在你旁边，随时可用。

### 3. HTTP MCP Mode（可选）

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve
```

```json
{
  "mcpServers": {
    "stableagent-http": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp/"
    }
  }
}
```

**类比：** 通过前台转接，适合团队共享。

---

## Tool Profile：暴露多少工具？

| Profile | 工具数 | 类比 |
|---|---|---|
| **minimal** (默认) | 10 | 只给实习生最基本的工具 |
| default | 20 | 加上调试和评估工具 |
| full | 55 | 完整工具箱（兼容旧版） |

```bash
export STABLE_AGENT_TOOL_PROFILE=minimal
```

**为什么默认 minimal？**

> 工具越多，AI 越容易分心。给实习生一把锤子，他钉钉子；给他一整面工具墙，他先花半小时选工具。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    接入层                                 │
│  ┌─────────┐  ┌────────────┐  ┌────────────┐           │
│  │   CLI   │  │ stdio MCP  │  │  HTTP MCP  │           │
│  │         │  │            │  │            │           │
│  │ 命令行   │  │ Claude Code│  │ Codex/Trae │           │
│  └────┬────┘  └─────┬──────┘  └─────┬──────┘           │
│       └──────────────┼───────────────┘                  │
│                      ↓                                  │
│            ┌─────────────────┐                          │
│            │ OSAgentHandler  │  ← 薄编排层 (39 行)      │
│            └────────┬────────┘                          │
└─────────────────────┼───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│                    执行层                                 │
│  ┌──────────────────────────────────────────────┐       │
│  │              OSAgentExecutor                  │       │
│  │  接收 → 理解 → 记忆 → 压缩 → 执行 → 评估      │       │
│  └──────────────────────┬───────────────────────┘       │
│                         ↓ RunTrace                      │
└─────────────────────────┼───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    策展层                                 │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐     │
│  │ Curator  │ →  │ Validation│ →  │ SkillRepo    │     │
│  │          │    │   Gate    │    │              │     │
│  │ 分析trace │    │ Schema    │    │ candidates/  │     │
│  │ 生成候选  │    │ Regression│    │ skills/      │     │
│  └──────────┘    │ Delayed   │    │ index.sqlite │     │
│                  └───────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    可观测层                               │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │  Dashboard   │  │  best_skill  │                    │
│  │  /observe/   │  │    .md       │                    │
│  │  事件时间线   │  │  招牌菜汇总   │                    │
│  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 核心组件

| 组件 | 文件 | 职责 | 类比 |
|---|---|---|---|
| OSAgentHandler | `core/os_agent_handler.py` | 薄编排层 | 前台调度 |
| OSAgentExecutor | `core/executor.py` | 执行任务 | 主厨 |
| CuratorService | `core/curator.py` | 提炼技能 | 品控师 |
| ValidationGate | `core/validator.py` | 验证技能 | 卫生检查员 |
| SkillRepository | `skills/repository.py` | 存储技能 | 菜谱库 |
| DelayedValidationGate | `core/delayed_validation.py` | 延迟验证 | 食客反馈 |
| LocalRuntime | `runtime/local_runtime.py` | 本地运行时 | 内线电话 |

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/liuanye9-lab/OS-Agent.git
cd OS-Agent

# 2. 安装依赖
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 运行任务 (不需要启动 server)
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "帮我检查项目结构" \
  --json

# 4. 运行测试
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q --tb=no
```

---

## 一句话总结

> **StableAgent Capsule = 给天才实习生配一本会自己更新的菜谱，让他不再跑偏、失忆、重复犯错。**

---

## 详细文档

- [核心架构](docs/CORE_ARCHITECTURE.md)
- [MCP 配置指南](docs/CLAUDE_CODE_MCP_SETUP.md)
- [SkillOS 集成](docs/SKILLOS_ADAPTATION.md)
- [CLI 指南](docs/CLI_FIRST_GUIDE.md)
- [重构报告](docs/refactor/FINAL_PROGRESS_REPORT.md)
- [变更日志](CHANGELOG.md)
