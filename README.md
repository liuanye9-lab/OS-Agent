<p align="center">
  <img src="https://img.shields.io/badge/StableAgent-OS-111827?style=for-the-badge" alt="StableAgent OS">
  <img src="https://img.shields.io/badge/MCP-55_tools-7c3aed?style=for-the-badge" alt="MCP Tools">
  <img src="https://img.shields.io/badge/Closed_Loop-30%2F30-22c55e?style=for-the-badge" alt="Closed Loop">
  <img src="https://img.shields.io/badge/Dashboard-Visualized-0ea5e9?style=for-the-badge" alt="Dashboard">
  <img src="https://img.shields.io/badge/Agent_Capsule-Portable-f59e0b?style=for-the-badge" alt="Agent Capsule">
</p>

<h1 align="center">StableAgent OS</h1>

<p align="center">
  <strong>给 AI Coding Agent 配一套"外接大脑"</strong><br />
  <sub>记住你的习惯 · 防止任务跑偏 · 记录失败经验 · 可视化每一次 Agent 思考</sub>
</p>

---

## StableAgent Capsule MCP + CLI Dual Gateway

StableAgent Capsule 彻底打通 MCP 和 CLI 通道，提供三种可用入口：

### 三种模式对比

| 模式 | 是否需要 server | Claude Code 是否识别为工具 | 稳定性 | 适合场景 |
|---|---|---|---|---|
| HTTP MCP | 需要 | 是 | 中高 | 正式集成 |
| stdio MCP | 不需要 | 是 | 高 | Claude Code 本地稳定集成 |
| CLI | 不需要工具识别 | 否，通过 Bash | 最高 | fallback / 自动化 |

### 1. HTTP MCP Mode

Claude Code / Codex / Trae 通过 `http://127.0.0.1:8000/mcp/` 连接 StableAgent。

**配置**：

```json
{
  "mcpServers": {
    "stableagent-http": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp/",
      "timeout": 60000
    }
  }
}
```

**启动服务**：

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve
```

### 2. Native CLI Mode

任何 Coding 软件都可以通过命令行调用：

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "任务描述" \
  --open-dashboard \
  --json
```

### 3. Stdio MCP Mode

把 CLI 包装成一个 stdio MCP server，让 Claude Code 可以通过本地命令方式加载 StableAgent，不依赖 HTTP 服务：

```json
{
  "mcpServers": {
    "stableagent-stdio": {
      "type": "stdio",
      "command": "/Users/Zhuanz/OS-Agent/OS-Agent/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio"],
      "env": {
        "PYTHONPATH": "/Users/Zhuanz/OS-Agent/OS-Agent"
      }
    }
  }
}
```

**详细配置指南**：[docs/CLAUDE_CODE_MCP_SETUP.md](docs/CLAUDE_CODE_MCP_SETUP.md)

---

## 这个项目一句话是什么？

**StableAgent OS 是一个接在 Claude Code / Codex / Trae / Cursor 这类 AI Coding 工具旁边的“个人 Agent 操作系统”。**

它不训练模型权重，也不是另一个聊天机器人。它做的是：

> 把你的表达习惯、项目上下文、失败经验、评测标准、Token 预算和 Dashboard 轨迹，打包成一套可迁移的 **Agent Capsule**，让不同 AI 工具更稳定地理解你。

可以把它想成：

| 类比 | StableAgent OS 是什么 |
|---|---|
| 学生 | 大模型本身，例如 Claude / GPT / Qwen / DeepSeek |
| 老师 | 你对模型的反馈和纠正 |
| 错题本 | Bad Case Bank，记录模型犯过的错 |
| 学习计划 | Skill Patch，把失败经验变成可复用规则 |
| 书包/U 盘 | Agent Capsule，打包你的记忆、规则、习惯和评测标准 |
| 仪表盘 | Dashboard，把 Agent 每一步理解、压缩、判断、学习过程可视化 |
| 免疫系统 | Context Guard，像白细胞一样拦截有害输入、保护关键上下文不被污染 |
| 黑匣子/飞行记录仪 | Run Trace，记录每一步操作，出问题时可以回溯完整事故链 |
| 导航仪 | Understanding Trace，在任务出发前先规划路线，防止 Agent 开错方向 |
| 驾校教练 | Human Review，新规则进入长期记忆前的最后一道人工把关 |
| 健身计划 | Skill Evolution，渐进式训练，规则越练越强、越用越精准 |
| 体检报告 | Effectiveness Dashboard，用量化指标衡量健康度，不靠感觉靠数据 |
| 处方药方 | Skill Patch，针对具体诊断出的问题开出的定向修复方案 |
| 记忆宫殿 | Agent Capsule，结构化的长期存储，每个房间放不同类型的记忆 |

---

## 为什么需要 StableAgent OS？

AI Coding 工具越来越强，但长任务里经常出现这些问题：

```text
你说：只修这个小 bug，不要大范围重构。

AI 可能会：
1. 改了 12 个无关文件；
2. 忘了你刚刚强调的约束；
3. 生成看似正确但无法运行的代码；
4. 同一个错误下次继续犯；
5. 解释得很自信，但你不知道它到底怎么理解任务；
6. token 越堆越多，最后上下文又乱又贵。
```

StableAgent OS 想解决的是：

> **不是让模型“变聪明”，而是给模型外面装一层能记忆、能复盘、能约束、能可视化的使用层。**

---

## 一句话类比总览：把 StableAgent OS 想象成什么？

想象你是一个每天去健身房的人。大模型（Claude / GPT / Qwen）是你自己的身体——天生有力量，但没人告诉你该怎么练、练多少、哪些动作容易受伤。

StableAgent OS 就是你的 **私人健身教练 + 营养师 + 健康档案系统**：

- **教练**（Understanding Trace）会在你开练之前先纠正姿势，确保你没理解错今天的训练目标；
- **护腰带**（Context Guard）在大重量训练时保护你的腰椎，就像保护关键约束不被上下文压缩丢掉；
- **训练日志**（Run Trace + Bad Case Bank）记下每一次动作和失误，下次训练不重复犯错；
- **渐进式训练计划**（Skill Evolution）根据你过去的表现动态调整训练强度和内容；
- **体检报告**（Effectiveness Dashboard）每月用数据告诉你，体脂降了没有、力量涨了没有，而不是光凭感觉说"好像好了一点"；
- **运动背包**（Agent Capsule）把你的训练计划、饮食偏好、伤病史全部打包，换一个健身房也能无缝继续；
- **免疫系统**（Context Guard）在你身体接触到不该吃的东西时自动拦截，就像拦截有害输入、防止上下文被污染；
- **驾校教练**（Human Review）在你正式上路前做最后检查——规则必须经过人工确认才能进入长期记忆。

> 一句话总结：大模型是你的身体，StableAgent OS 是让你**科学训练、不受伤、持续进步**的整套保障体系。

---

## 核心比喻：给每个模型学生配一套“学习装备”

不同大模型就像不同学生：

- 有些写代码强，但容易过度修改；
- 有些推理强，但工具调用慢；
- 有些文案自然，但工程稳定性弱；
- 有些便宜好用，但上下文保护差。

StableAgent OS 不去改学生的大脑，而是给学生配装备：

```mermaid
flowchart LR
    A[不同大模型学生<br/>Claude / GPT / Qwen / DeepSeek] --> B[StableAgent OS 外接装备]
    B --> C[记住你的表达习惯]
    B --> D[保护任务关键约束]
    B --> E[记录失败错题]
    B --> F[生成 Skill Patch]
    B --> G[Token 预算和压缩]
    B --> H[Dashboard 可视化]
    C --> I[更懂你]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

换句话说：

> 模型能力会不断迭代，但你的个人使用层也应该能成长。StableAgent OS 就是这套可迁移的个人使用层。

---

## 项目目标

StableAgent OS 的目标不是做一个“更大的 Agent”，而是做一个 **AI Coding 用户的个人稳定层**。

它要做到：

1. **不跑偏**：任务开始前先理解你的真实意图；
2. **不失忆**：把长期偏好、项目记忆、表达习惯存在 Agent Capsule 里；
3. **不重复犯错**：把 bad case 转成 regression case 和 skill patch；
4. **不瞎压缩上下文**：Token 预算时保护关键约束；
5. **不黑箱执行**：Dashboard 展示每一步发生了什么；
6. **不只靠感觉证明有用**：Effectiveness Dashboard 用 A/B 数据验证是否真的更稳。

---

## 整体架构

```mermaid
flowchart TB
    User["👤 用户<br/>AI Coding 重度使用者"] --> Client["💻 Coding Agent<br/>Claude Code / Codex / Trae / Cursor"]
    Client --> MCP["🔌 MCP Gateway<br/>55 tools / HTTP + stdio + CLI"]
    MCP --> OSAgent["⚙️ stableagent.task.os_agent<br/>任务主调度引擎"]

    subgraph CORE["🧠 StableAgent OS 核心六大模块"]
        direction TB
        U["🧭 Understanding Trace<br/>语义理解轨迹<br/>解析真实意图 + 表达习惯匹配"]
        C["🛡️ Context Guard<br/>上下文免疫系统<br/>拦截有害输入 + 保护关键约束"]
        T["📊 Token Budget<br/>Token 预算管理器<br/>智能压缩 + 关键信息优先保留"]
        M["🎒 Agent Capsule<br/>个人记忆胶囊<br/>习惯 / 偏好 / 项目记忆打包"]
        E["🔬 Evaluation<br/>评测与失败归因<br/>Bad Case 记录 + 回归测试生成"]
        S["💪 Skill Evolution<br/>规则渐进进化<br/>Skill Patch 候选 + 验证 + 沉淀"]
    end

    OSAgent --> U
    OSAgent --> C
    OSAgent --> T
    OSAgent --> M
    OSAgent --> E
    OSAgent --> S

    subgraph OBSERVE["📺 可视化观测层"]
        Dash["Dashboard Observer<br/>Run Trace / Understanding / Token / Memory / BadCase / Skill"]
        EffDash["Effectiveness Dashboard<br/>A/B 对比数据 + 量化指标"]
    end

    U --> Dash
    C --> Dash
    T --> Dash
    M --> Dash
    E --> Dash
    S --> Dash
    E --> EffDash
    S --> EffDash

    subgraph LOOP["🔄 反馈闭环"]
        Dash --> Human["👨‍🏫 Human Review<br/>用户人工确认 / 纠正 / 审批"]
        Human --> Capsule["💾 长期记忆与规则沉淀<br/>.stableagent-capsule/"]
    end

    Capsule -->|"下次任务自动加载"| OSAgent
```

---

## Agent Capsule：像 U 盘一样带走你的 AI 使用习惯

StableAgent OS 的核心不是一次任务，而是长期积累的 **Agent Capsule**。

它可以理解为：

```text
.stableagent-capsule/
├── profile/              # 你的表达习惯，比如“不要AI味”是什么意思
├── memory/               # 长期记忆、项目记忆、偏好记忆
├── skills/               # 经过验证的工作规则
├── bad_cases/            # 模型犯过的错
├── evals/                # 个人评测样例和回归测试
├── token_ledger/         # Token 使用和节省记录
├── model_profiles/       # 不同模型的能力画像
└── effectiveness/        # 项目有效性 A/B 数据
```

它的目标是：

> 不管你今天用 Claude Code，明天用 Codex，后天换 Trae，你的习惯、错题本、评测标准和任务边界都可以继续迁移。

### 记忆宫殿：Agent Capsule 的房间布局

把 Agent Capsule 想象成一座记忆宫殿，每个房间存放不同类型的记忆：

```mermaid
flowchart TB
    subgraph PALACE["🏛️ 记忆宫殿 Agent Capsule"]
        direction TB

        subgraph ROOM1["🗣️ 表达厅 profile/"]
            P1["不要AI味 = 避免模板化表达"]
            P2["简洁 = 少用形容词"]
            P3["专业 = 用行业术语"]
        end

        subgraph ROOM2["🧠 记忆阁 memory/"]
            M1["项目架构偏好"]
            M2["常用技术栈"]
            M3["个人编码风格"]
        end

        subgraph ROOM3["🛠️ 技能库 skills/"]
            S1["已验证的工作规则"]
            S2["经过审核的 Skill Patch"]
            S3["渐进式训练成果"]
        end

        subgraph ROOM4["❌ 错题室 bad_cases/"]
            B1["过度修改案例"]
            B2["遗忘约束案例"]
            B3["跑偏记录"]
        end

        subgraph ROOM5["📋 考场 evals/"]
            E1["回归测试用例"]
            E2["个人评测标准"]
            E3["质量红线"]
        end

        subgraph ROOM6["💰 账房 token_ledger/"]
            T1["Token 使用记录"]
            T2["压缩节省统计"]
            T3["预算分配历史"]
        end

        subgraph ROOM7["🤖 画像室 model_profiles/"]
            MP1["Claude 能力画像"]
            MP2["GPT 能力画像"]
            MP3["Qwen 能力画像"]
        end

        subgraph ROOM8["📊 体检室 effectiveness/"]
            EF1["A/B 对比数据"]
            EF2["跑偏率趋势"]
            EF3["返工次数统计"]
        end
    end

    ROOM1 -.->|"表达习惯指导理解"| ROOM2
    ROOM4 -.->|"错题生成考题"| ROOM5
    ROOM5 -.->|"验证通过的技能"| ROOM3
    ROOM8 -.->|"数据驱动优化"| ROOM3

    style PALACE fill:#fefce8,stroke:#eab308
    style ROOM1 fill:#ede9fe,stroke:#a78bfa
    style ROOM2 fill:#dbeafe,stroke:#60a5fa
    style ROOM3 fill:#d1fae5,stroke:#34d399
    style ROOM4 fill:#fee2e2,stroke:#f87171
    style ROOM5 fill:#fef3c7,stroke:#fbbf24
    style ROOM6 fill:#fce7f3,stroke:#f472b6
    style ROOM7 fill:#e0e7ff,stroke:#818cf8
    style ROOM8 fill:#ecfdf5,stroke:#10b981
```

每个房间独立维护，但彼此之间有引用关系。当你换工具（Claude Code → Codex → Trae）时，整座宫殿直接搬走——这就是"可迁移"的意义。

---

## 一次任务在 StableAgent 里如何流动？

```mermaid
sequenceDiagram
    participant U as 👤 用户
    participant C as 💻 Coding Agent
    participant S as ⚙️ StableAgent OS
    participant D as 📺 Dashboard
    participant P as 🎒 Agent Capsule

    U->>C: 继续优化这个项目，不要AI味，不要大范围重构
    Note right of U: 用户发出带约束的任务指令

    C->>S: 调用 stableagent.task.os_agent
    Note over C,S: 生成唯一 run_id，开始全链路追踪

    S->>S: 🧭 生成 Understanding Trace
    Note right of S: 解析真实意图<br/>匹配表达习惯（不要AI味 = 避免模板化）

    S->>P: 🎒 读取表达习惯与项目记忆
    P-->>S: 返回 profile + memory + skills
    Note over S,P: 记忆宫殿自动检索相关记忆

    S->>S: 🛡️ Context Guard 激活
    Note right of S: 保护关键约束不被压缩<br/>拦截可能的有害输入

    S->>S: 📊 生成 Token Report
    Note right of S: 预算分配 + 智能压缩<br/>关键信息优先保留

    S->>D: 📺 写入事件流和可视化面板
    D-->>U: 展示理解轨迹、Token预算、记忆命中、bad case 预警
    Note over D,U: 用户第一次看到 Agent 的完整脑内过程

    U->>D: 👨‍🏫 纠正 / 记住这个 / 下次别这样
    Note right of U: 用户反馈进入结构化闭环

    D->>P: 💾 写入表达习惯、bad case、skill patch 候选
    Note over D,P: 经验沉淀为可迁移的长期资产
```

---

## Dashboard：让 Agent 的“脑内过程”可视化

Dashboard 不是普通日志页面，它更像是 Agent 的监控仪表盘。

它会展示：

| 面板 | 作用 |
|---|---|
| Run Trace / 事件时间线 | 这次任务从接收到完成经历了哪些步骤 |
| Understanding Panel | 系统如何理解你的原话，有哪些假设和不确定点 |
| Token Budget | 原本要塞多少上下文，实际保留多少，节省多少 |
| Memory Map | 这次任务用了哪些长期记忆和表达习惯 |
| Bad Case Bank | 出现了哪些失败案例，是否生成回归测试 |
| Skill Evolution | 是否生成新的 Skill Patch，是否进入验证/人工审核 |
| Memory Health | 哪些记忆该保留、合并、删除或人工审核 |

```mermaid
flowchart LR
    A[任务输入] --> B[理解轨迹]
    B --> C[上下文保护]
    C --> D[Token 预算]
    D --> E[执行与评测]
    E --> F[Bad Case]
    F --> G[Skill Patch]
    G --> H[Human Review]
    A --> UI[Dashboard 可视化]
    B --> UI
    C --> UI
    D --> UI
    E --> UI
    F --> UI
    G --> UI
```

---

## 反馈闭环：把“下次别这样”变成可验证规则

传统 AI 工具里，你说一句“下次别这样”，模型可能下一轮就忘了。

StableAgent OS 会把这句话变成结构化闭环：

```mermaid
flowchart TB
    A[用户反馈：下次别这样] --> B[BadCaseRecord<br/>记录失败案例]
    B --> C[PersonalEvalCase<br/>生成个人评测样例]
    C --> D[SkillPatchCandidate<br/>提出规则补丁]
    D --> E[RegressionValidationRunner<br/>回归验证]
    E -->|通过| F[HumanReviewQueue<br/>进入人工审核]
    E -->|失败| G[拒绝进入长期规则]
    F --> H[人工确认]
    H --> I[长期 Skill / 记忆沉淀]
```

关键原则：

> 失败经验不能直接污染长期规则，必须经过验证和人工审核。

### 免疫系统类比：从"病毒入侵"到"产生抗体"

把整个反馈闭环想象成人体免疫系统的工作方式：

```mermaid
flowchart TB
    subgraph INFECTION["🦠 病毒入侵（任务中出现 Bad Case）"]
        A["用户执行任务<br/>Agent 犯错或跑偏"] --> B["用户反馈<br/>下次别这样！"]
    end

    subgraph DETECT["🔍 免疫识别（诊断与记录）"]
        B --> C["BadCaseRecord<br/>🧫 病原体登记<br/>记录失败案例的完整上下文"]
        C --> D["归因分析<br/>🔬 病理分析<br/>到底是什么导致了这个错误？"]
    end

    subgraph ANTIBODY["💊 抗体生产（生成修复方案）"]
        D --> E["SkillPatchCandidate<br/>🧬 抗体候选<br/>针对诊断结果开出处方"]
        E --> F["RegressionValidationRunner<br/>🧪 抗体有效性测试<br/>跑回归测试验证修复"]
    end

    subgraph DEPLOY["🛡️ 免疫记忆（部署与保护）"]
        F -->|测试通过| G["HumanReviewQueue<br/>👨‍⚕️ 专家会诊<br/>人工确认抗体方案"]
        F -->|测试失败| H["❌ 丢弃无效抗体<br/>不进入长期规则"]
        G --> I["✅ 长期 Skill 沉淀<br/>💉 抗体正式入库"]
        I --> J["下次同类任务自动识别<br/>🛡️ 免疫应答自动触发"]
    end

    J -.->|"免疫力越来越强<br/>同类错误不再复发"| A

    style INFECTION fill:#fee2e2,stroke:#f87171
    style DETECT fill:#fef3c7,stroke:#fbbf24
    style ANTIBODY fill:#dbeafe,stroke:#60a5fa
    style DEPLOY fill:#d1fae5,stroke:#34d399
```

这个类比的关键对应关系：

| 免疫系统 | StableAgent OS | 说明 |
|---|---|---|
| 病毒/病原体 | Bad Case（错误案例） | 任务中出现的跑偏、过度修改、遗忘约束 |
| 免疫识别 | 归因分析 | 诊断错误的根本原因，而不是表面症状 |
| 抗体生产 | Skill Patch 候选 | 针对特定问题生成定向修复方案 |
| 抗体测试 | 回归验证 | 确保新抗体不会误伤正常功能 |
| 专家会诊 | Human Review | 人工确认是最后一道安全门 |
| 免疫记忆 | 长期 Skill 沉淀 | 下次同类问题自动识别、自动防御 |
| 免疫力增强 | 规则越用越精准 | 随着使用积累，系统防御力持续增强 |

---

## 表达习惯学习：让模型理解你的“人话”

比如你说：

```text
不要AI味。
```

模型可能不知道你具体指什么。

StableAgent 可以把它记录成：

```json
{
  "phrase": "不要AI味",
  "normalized_meaning": [
    "避免模板化表达",
    "保持克制",
    "减少空泛营销腔"
  ],
  "scope": "global",
  "confidence": 0.7
}
```

之后你再说：

```text
这个 README 不要AI味，写得自然一点。
```

StableAgent 会在 Understanding Trace 里命中这个表达习惯，让 Coding Agent 少猜一步。

---

## Effectiveness Dashboard：不靠感觉，靠数据证明项目有没有用

工程闭环成立，不等于产品有效。

StableAgent OS 新增了 Effectiveness Dashboard，用来做 A/B 对比：

```mermaid
flowchart LR
    T[同一类任务] --> A[Baseline<br/>直接用 Coding Agent]
    T --> B[StableAgent Mode<br/>先调用 os_agent]

    A --> M[记录指标]
    B --> M

    M --> R[Effectiveness Dashboard]
    R --> V{是否真的有效？}

    V -->|跑偏更少| YES[有效性增强]
    V -->|返工更少| YES
    V -->|约束保留更好| YES
    V -->|没有改善| NO[继续优化系统]
```

它关注这些指标：

| 指标 | 解释 | 希望变化 |
|---|---|---|
| success_rate | 任务是否完成 | 上升 |
| test_pass_rate | 测试是否通过 | 上升 |
| intent_drift_rate | 是否跑偏 | 下降 |
| over_editing_rate | 是否过度修改 | 下降 |
| constraint_preservation_rate | 是否保留约束 | 上升 |
| bad_case_recurrence_rate | 同类错误是否复发 | 下降 |
| avg_rework_count | 平均返工次数 | 下降 |
| avg_estimated_tokens | Token 消耗 | 下降或不明显上升 |
| avg_user_satisfaction | 用户满意度 | 上升 |

---

## 默认调用规则：AGENTS.md / CLAUDE.md

项目已经加入默认规则文件：

```text
AGENTS.md
CLAUDE.md
```

目标是让 Coding Agent 打开本仓库时默认知道：

> 非平凡编码任务开始前，先调用 `stableagent.task.os_agent`，生成 run_id 和 Dashboard，再继续执行。

典型调用：

```json
{
  "method": "tools/call",
  "params": {
    "name": "stableagent.task.os_agent",
    "arguments": {
      "task_input": "继续优化这个项目，不要AI味，不要大范围重构无关文件",
      "open_dashboard": true
    }
  }
}
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/liuanye9-lab/OS-Agent.git
cd OS-Agent
```

### 2. 使用 Python 3.11+

macOS 示例：

```bash
brew install python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 推荐使用 CLI 启动
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve

# 或直接使用 uvicorn
# PYTHONPATH=. uvicorn web.server:app --host 127.0.0.1 --port 8000
```

启动成功后访问：

```text
http://127.0.0.1:8000/api/health
```

预期：

```json
{
  "ok": true,
  "service": "StableAgent OS"
}
```

### 4. 健康检查

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json
```

### 5. 执行任务 (CLI Mode)

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "你的任务描述" \
  --open-dashboard \
  --json
```

---

## MCP 接入配置

推荐配置：

```json
{
  "mcpServers": {
    "stableagent": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8000/mcp/",
      "timeout": 60000
    }
  }
}
```

调试工具列表：

```bash
curl http://127.0.0.1:8000/mcp/tools
```

调用主工具：

```bash
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "stableagent.task.os_agent",
      "arguments": {
        "task_input": "继续优化这个项目，不要AI味，不要大范围重构无关文件",
        "open_dashboard": true
      }
    },
    "id": 1
  }'
```

---

## 常用页面

| 页面 | 地址 |
|---|---|
| 健康检查 | `http://127.0.0.1:8000/api/health` |
| MCP 工具列表 | `http://127.0.0.1:8000/mcp/tools` |
| Run Observer | `http://127.0.0.1:8000/observe/{run_id}?check=1` |
| Run Detail | `http://127.0.0.1:8000/runs/{run_id}` |
| Effectiveness Dashboard | `http://127.0.0.1:8000/effectiveness` |
| API Docs | `http://127.0.0.1:8000/docs` |

---

## CLI Mode：稳定保底入口

MCP 是推荐集成方式，但不同 Coding 软件对 MCP 的支持不稳定（Trae / Codex / Claude Code 可能因配置路径、streamableHttp、SSE、JSON-RPC 兼容问题导致工具列表无法加载）。

**CLI Mode 是稳定保底入口**，所有 Coding 软件都可以通过 shell 命令调用 StableAgent。

### 启动服务（推荐用 CLI）

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve
```

### 健康检查

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json
```

### 执行任务

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "继续优化这个项目，不要AI味，不要大范围重构无关文件" \
  --open-dashboard \
  --json
```

### 反馈命令

```bash
# 记住这个
PYTHONPATH=. .venv/bin/python -m stable_agent.cli feedback remember \
  --run-id run_xxx --note "以后记住这个约束" --json

# 下次别这样
PYTHONPATH=. .venv/bin/python -m stable_agent.cli feedback dont \
  --run-id run_xxx --note "下次不要大范围重构无关文件" --json

# 纠正表达习惯
PYTHONPATH=. .venv/bin/python -m stable_agent.cli feedback correct \
  --run-id run_xxx \
  --phrase "不要AI味" \
  --meaning "避免模板化表达，保持克制，减少空泛营销腔" \
  --json
```

### 效果评估

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli effectiveness summary --json
```

### MCP Mode vs CLI Mode

| 特性 | MCP Mode | CLI Mode |
|------|----------|----------|
| 集成方式 | Claude Code / Codex / Trae 直接识别为工具 | 所有 Coding 软件通过 shell 命令调用 |
| 稳定性 | 依赖 MCP 配置兼容性 | 稳定保底入口 |
| 输出格式 | JSON-RPC 2.0 | `--json` 模式输出 JSON |
| 推荐场景 | MCP 正常工作时 | MCP 识别失败时作为 fallback |
| Dashboard | 自动展示 | 通过 Web 服务展示 |

---

## 当前能力状态

| 能力 | 状态 |
|---|---|
| MCP Gateway | 已支持 JSON-RPC / tools / health / SSE |
| CLI Mode | 已支持 task run / serve / health / feedback / effectiveness / dashboard |
| stdio MCP Server | 已支持 initialize / tools/list / tools/call |
| stableagent.task.os_agent | 已接入主流程 |
| Understanding Trace | 已支持 |
| Expression Profile | 已支持 |
| Token Budget Ledger | 已支持 |
| FeedbackLearningService | 已支持 |
| Bad Case → Eval Case → Skill Patch | 已支持 |
| Validation → Human Review | 已支持 |
| Dashboard 六大面板 | 已支持 |
| AGENTS.md / CLAUDE.md | 已支持（含 MCP/CLI 优先级规则） |
| Effectiveness Dashboard | MVP 已支持，仍需真实 A/B 数据积累 |

---

## 项目不是在做什么？

StableAgent OS **不是**：

- 不是微调模型；
- 不是训练新的基础大模型；
- 不是另一个聊天壳；
- 不是普通 prompt 模板库；
- 不是只做日志记录。

它真正做的是：

> 把 AI Coding 的使用过程变成一个可记忆、可评测、可纠正、可迁移、可视化的系统。

---

## 适合谁使用？

适合：

- 高频使用 Claude Code / Codex / Trae / Cursor 的开发者；
- 经常遇到 AI 长任务跑偏的人；
- 想把个人提示词、项目习惯、失败经验沉淀下来的人；
- 想验证 AI Coding 是否真的提升效率的人；
- 想做 Agent / MCP / AI Workflow 产品的人。

不适合：

- 只想一次性问答的人；
- 不需要长期项目记忆的人；
- 不关心可视化、评测和复盘的人。

---

## 项目路线图

```mermaid
flowchart TB
    V10[V10<br/>事件链和 Dashboard 打通] --> V11[V11<br/>Agent Capsule]
    V11 --> V112[V11.2<br/>Trustworthy Feedback Loop]
    V112 --> V113[V11.3<br/>Default Agent Rules + Effectiveness MVP]
    V113 --> V1131[V11.3.1<br/>Effectiveness Hardening]
    V1131 --> V114[V11.4<br/>MCP + CLI Dual Gateway]
    V114 --> V12[V12<br/>多工具稳定接入与真实数据评测]
```

### 下一步重点

- [ ] 修正 Effectiveness schema，加入 `test_passed / rework_count / user_satisfaction` 等完整指标；
- [ ] 将 Effectiveness 数据默认写入 `.stableagent-capsule/effectiveness/`；
- [ ] 统一 `/api/effectiveness/*` 返回结构；
- [ ] Run Observer 增加“记录到 Effectiveness”；
- [ ] 积累至少 10 个真实 A/B 任务数据；
- [ ] 输出一份真实效果报告。

---

## 最小有效性实验

想证明 StableAgent 是否真的有用，不要靠感觉，跑 10 个任务：

```text
同类任务 A：直接用 Coding Agent 做。
同类任务 B：先调用 StableAgent，再让 Coding Agent 做。
```

记录：

```json
{
  "task_id": "T01",
  "mode": "baseline | stableagent",
  "success": true,
  "test_passed": true,
  "intent_drift": false,
  "over_editing": false,
  "constraint_preserved": true,
  "rework_count": 1,
  "estimated_tokens": 12000,
  "user_satisfaction": 4
}
```

如果 StableAgent 组出现：

```text
跑偏率下降
返工次数下降
约束保留率上升
bad case 复发率下降
测试通过率不下降
```

才说明它真的有效。

---

## 项目背后的核心思想

StableAgent OS 的底层判断是：

> 未来的大模型会越来越强，但每个人真正需要的是“适配自己”的外部使用层。

模型像发动机，StableAgent 像仪表盘、导航、刹车、错题本和驾驶习惯记录器。

发动机升级当然重要，但如果没有稳定的驾驶系统，长任务依然会跑偏。

StableAgent OS 想做的就是这套系统。

---

## 可视化对比：有没有 StableAgent 差在哪？

同样是让 AI Coding 工具干活，有和没有 StableAgent 的体验完全不同：

```mermaid
flowchart LR
    subgraph WITHOUT["❌ 没有 StableAgent：盲开模式"]
        direction TB
        W1["用户说：不要大范围重构"] --> W2["Agent 直接开始改"]
        W2 --> W3["改了 12 个无关文件"]
        W3 --> W4["用户发现时已经太晚"]
        W4 --> W5["回滚 + 重来 + 同样的错"]
        W5 -.->|"下次继续犯"| W2
    end

    subgraph WITH["✅ 有 StableAgent：全程护航"]
        direction TB
        V1["用户说：不要大范围重构"] --> V2["Understanding Trace 解析意图"]
        V2 --> V3["Context Guard 保护约束"]
        V3 --> V4["Token Budget 智能压缩"]
        V4 --> V5["Dashboard 展示每一步"]
        V5 --> V6["用户实时看到执行轨迹"]
        V6 --> V7["反馈沉淀为长期规则"]
        V7 -.->|"下次自动防御"| V2
    end

    style WITHOUT fill:#fee2e2,stroke:#f87171
    style WITH fill:#d1fae5,stroke:#34d399
```

### 逐项对比表

| 维度 | ❌ 没有 StableAgent | ✅ 有 StableAgent | 差距 |
|---|---|---|---|
| **意图理解** | Agent 自己猜你想要什么 | Understanding Trace 先解析意图、匹配表达习惯 | 减少误解，少跑偏 |
| **约束保护** | 说完"不要重构"，Agent 下一轮就忘了 | Context Guard 像免疫系统一样持续保护关键约束 | 说了就记住，不会遗忘 |
| **上下文管理** | Token 爆了就让模型自己压缩，关键信息可能被丢 | Token Budget 智能分配，关键约束优先保留 | 不丢关键信息，Token 更省钱 |
| **犯错后** | 同一个错误反复出现，靠用户记忆提醒 | Bad Case 自动记录 → 生成回归测试 → 产出 Skill Patch | 同一个错不犯第二次 |
| **经验积累** | 每次对话独立，经验无法沉淀 | 经验进入 Agent Capsule，跨工具、跨项目迁移 | 越用越懂你 |
| **可视化** | 黑箱执行，不知道 Agent 怎么想的 | Dashboard 六大面板实时展示每一步 | 从黑箱变成透明 |
| **效果验证** | "好像快了一点"凭感觉 | Effectiveness Dashboard A/B 数据对比 | 用数据证明，不靠感觉 |
| **换工具成本** | 换一个 AI 工具，所有习惯要重新教 | Agent Capsule 一键迁移，习惯跟着走 | 零成本切换 |

### 类比理解

```text
没有 StableAgent 的 AI Coding：
  像一个没有导航、没有行车记录仪、没有保险的司机
  —— 每次出发都靠运气，出了事故没有记录，下次继续犯同样的错。

有 StableAgent 的 AI Coding：
  像一个配了导航仪 + 行车记录仪 + 全险 + 驾校教练的司机
  —— 出发前规划路线，全程有记录，出了事故有回溯，教练还会帮你总结经验。
```

> 本质上，StableAgent OS 不是让模型变强，而是让**使用模型的过程**变得可控、可追溯、可成长。

---

## H.Agent Integration

StableAgent Capsule can be used as the execution layer of H.Agent.

CLI:

```bash
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "..." \
  --json
```

Output follows the `h-agent-v1` contract. See [docs/H_AGENT_INTEGRATION_CONTRACT.md](docs/H_AGENT_INTEGRATION_CONTRACT.md).

---

## License

MIT

---

<p align="center">
  <strong>StableAgent OS — 让 AI Coding 不只是会做，而是可记忆、可复盘、可验证地越用越懂你。</strong>
</p>
