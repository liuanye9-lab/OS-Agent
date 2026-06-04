"""统一 MCP 工具 Schema 定义。

定义 V5 所有 14 个 stableagent.* 命名空间工具的 JSON Schema，
以及对应的头像状态映射（AVATAR_STATE_MAP）。

所有工具遵循统一的命名约定：stableagent.<domain>.<action>
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 14 个统一命名工具的 JSON Schema
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict[str, Any]] = {
    "stableagent.task.process": {
        "name": "stableagent.task.process",
        "title": "处理任务",
        "description": "端到端处理一个用户任务",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {
                    "type": "string",
                    "description": "用户任务描述",
                }
            },
            "required": ["task_input"],
        },
        "risk_level": "medium",
    },
    "stableagent.context.build": {
        "name": "stableagent.context.build",
        "title": "构建上下文包",
        "description": "整合记忆+RAG+规则构建上下文包",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.context.estimate_budget": {
        "name": "stableagent.context.estimate_budget",
        "title": "估算预算",
        "description": "估算任务所需 Token 预算",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.memory.retrieve": {
        "name": "stableagent.memory.retrieve",
        "title": "检索记忆",
        "description": "检索相关记忆条目",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.memory.write_candidate": {
        "name": "stableagent.memory.write_candidate",
        "title": "写入候选记忆",
        "description": "将一条经验写入记忆候选队列",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "item_type": {"type": "string", "default": "success_case"},
                "source": {"type": "string"},
            },
            "required": ["content", "source"],
        },
        "risk_level": "low",
    },
    "stableagent.rag.retrieve": {
        "name": "stableagent.rag.retrieve",
        "title": "RAG 检索",
        "description": "从知识库检索相关文档",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "risk_level": "low",
    },
    "stableagent.eval.evaluate": {
        "name": "stableagent.eval.evaluate",
        "title": "评测输出",
        "description": "评测模型输出质量",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "input_context": {"type": "string"},
                "output": {"type": "string"},
            },
            "required": ["task_input", "input_context", "output"],
        },
        "risk_level": "low",
    },
    "stableagent.badcase.record": {
        "name": "stableagent.badcase.record",
        "title": "记录失败案例",
        "description": "记录一个失败案例供后续改进",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string"},
                "input_context": {"type": "string"},
                "output": {"type": "string"},
                "evaluation": {"type": "object"},
            },
            "required": ["task_input", "input_context", "output"],
        },
        "risk_level": "low",
    },
    "stableagent.skillopt.status": {
        "name": "stableagent.skillopt.status",
        "title": "SkillOpt 状态",
        "description": "获取技能优化引擎状态",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    "stableagent.skillopt.get_current_skill": {
        "name": "stableagent.skillopt.get_current_skill",
        "title": "获取当前技能",
        "description": "获取当前技能文档内容和版本",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    "stableagent.skillopt.run_epoch": {
        "name": "stableagent.skillopt.run_epoch",
        "title": "运行优化回合",
        "description": "运行一轮技能优化",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_rollouts": {"type": "integer", "default": 40},
            },
        },
        "risk_level": "medium",
    },
    "stableagent.skillopt.export_best": {
        "name": "stableagent.skillopt.export_best",
        "title": "导出最优技能",
        "description": "导出 best_skill.md",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "medium",
    },
    "stableagent.trace.get_run": {
        "name": "stableagent.trace.get_run",
        "title": "获取运行轨迹",
        "description": "获取指定 run 的完整 trace",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
            },
            "required": ["run_id"],
        },
        "risk_level": "low",
    },
    "stableagent.approval.respond": {
        "name": "stableagent.approval.respond",
        "title": "响应审批",
        "description": "批准或拒绝一个待审批操作",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["approve", "reject"],
                },
                "reason": {"type": "string"},
            },
            "required": ["request_id", "action"],
        },
        "risk_level": "high",
    },
    # V6.5: /os-agent 快捷入口
    "stableagent.task.os_agent": {
        "name": "stableagent.task.os_agent",
        "title": "OS Agent 自优化工作流",
        "description": "启动 StableAgent OS 自优化工作流，将执行过程实时同步到可视化面板。",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {
                    "type": "string",
                    "description": "用户希望 OS Agent 执行或优化的任务",
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "diagnose", "optimize", "skillopt", "observe"],
                    "default": "auto",
                    "description": "运行模式",
                },
                "open_dashboard": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否返回 Dashboard 链接",
                },
                "run_id": {
                    "type": "string",
                    "description": "可选，已有 run_id",
                },
            },
            "required": ["task_input"],
        },
        "risk_level": "medium",
    },
    # =======================================================================
    # V11 Phase 3: Understanding Trace 语义理解工具
    # =======================================================================
    "stableagent.understanding.trace": {
        "name": "stableagent.understanding.trace",
        "title": "语义理解轨迹",
        "description": "解析用户输入的语义意图，生成 UnderstandingTrace",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_input": {"type": "string", "description": "用户输入文本"},
                "run_id": {"type": "string", "description": "关联运行 ID"},
            },
            "required": ["task_input"],
        },
        "risk_level": "low",
    },
    "stableagent.understanding.correct": {
        "name": "stableagent.understanding.correct",
        "title": "记录纠正",
        "description": "记录用户对系统理解的纠正，可转化为表达规则",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "关联运行 ID"},
                "wrong_interpretation": {"type": "string", "description": "错误解读"},
                "correct_interpretation": {"type": "string", "description": "正确解读"},
                "trigger_phrase": {"type": "string", "description": "触发纠正的短语"},
            },
            "required": ["wrong_interpretation", "correct_interpretation"],
        },
        "risk_level": "low",
    },
    "stableagent.expression.list": {
        "name": "stableagent.expression.list",
        "title": "列出表达习惯",
        "description": "列出已记录的用户表达习惯",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "按作用域过滤"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.expression.add": {
        "name": "stableagent.expression.add",
        "title": "添加表达习惯",
        "description": "添加用户表达习惯规则",
        "input_schema": {
            "type": "object",
            "properties": {
                "phrase": {"type": "string", "description": "用户表达短语"},
                "meaning": {"type": "array", "items": {"type": "string"}, "description": "标准化含义"},
                "scope": {"type": "string", "description": "作用域"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["phrase", "meaning"],
        },
        "risk_level": "low",
    },
    "stableagent.expression.delete": {
        "name": "stableagent.expression.delete",
        "title": "删除表达习惯",
        "description": "删除指定的用户表达习惯",
        "input_schema": {
            "type": "object",
            "properties": {
                "phrase": {"type": "string", "description": "要删除的表达短语"},
            },
            "required": ["phrase"],
        },
        "risk_level": "low",
    },
    # =======================================================================
    # SaaS v1.2: 12 个商业 SaaS 工具
    # =======================================================================
    "stableagent.workspace.create": {
        "name": "stableagent.workspace.create",
        "title": "创建工作空间",
        "description": "创建新的 SaaS 工作空间（团队空间），包含默认计费套餐",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "工作空间名称"},
                "tier": {"type": "string", "enum": ["free", "pro", "team", "enterprise"], "default": "free"},
                "project_id": {"type": "string", "description": "关联项目 ID（SaaS 模式必填）"},
            },
            "required": ["name"],
        },
        "risk_level": "low",
    },
    "stableagent.project.create": {
        "name": "stableagent.project.create",
        "title": "创建项目",
        "description": "在指定工作空间下创建新项目",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "name": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["workspace_id", "name"],
        },
        "risk_level": "low",
    },
    "stableagent.project.list": {
        "name": "stableagent.project.list",
        "title": "列出项目",
        "description": "列出指定工作空间下的所有项目",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
            },
            "required": ["workspace_id"],
        },
        "risk_level": "low",
    },
    "stableagent.run.get": {
        "name": "stableagent.run.get",
        "title": "获取运行详情",
        "description": "获取指定 run 的完整状态、进度、评分和 trace",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["run_id"],
        },
        "risk_level": "low",
    },
    "stableagent.eval.run": {
        "name": "stableagent.eval.run",
        "title": "运行评测",
        "description": "对指定 run 执行评测，返回多维度评分",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["run_id"],
        },
        "risk_level": "medium",
    },
    "stableagent.regression.create": {
        "name": "stableagent.regression.create",
        "title": "创建回归用例",
        "description": "从 BadCase 生成 Regression Case",
        "input_schema": {
            "type": "object",
            "properties": {
                "bad_case_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["bad_case_id"],
        },
        "risk_level": "low",
    },
    "stableagent.skill.patch_propose": {
        "name": "stableagent.skill.patch_propose",
        "title": "提议 Skill 补丁",
        "description": "提交一个 Skill 优化补丁",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "patch_content": {"type": "string"},
                "from_version": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["skill_id", "patch_content"],
        },
        "risk_level": "medium",
    },
    "stableagent.skill.validate": {
        "name": "stableagent.skill.validate",
        "title": "验证 Skill 补丁",
        "description": "通过 Validation Gate 验证 Skill 补丁",
        "input_schema": {
            "type": "object",
            "properties": {
                "patch_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["patch_id"],
        },
        "risk_level": "medium",
    },
    "stableagent.skill.review": {
        "name": "stableagent.skill.review",
        "title": "审核 Skill 补丁",
        "description": "对已验证的 Skill 补丁执行人工审核",
        "input_schema": {
            "type": "object",
            "properties": {
                "patch_id": {"type": "string"},
                "action": {"type": "string", "enum": ["approve", "reject"]},
                "reviewer": {"type": "string"},
                "comment": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["patch_id", "action"],
        },
        "risk_level": "high",
    },
    "stableagent.skill.export_best": {
        "name": "stableagent.skill.export_best",
        "title": "导出最佳 Skill",
        "description": "将已审批的 Skill 导出为 best_skill.md",
        "input_schema": {
            "type": "object",
            "properties": {
                "patch_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["patch_id"],
        },
        "risk_level": "high",
    },
    "stableagent.usage.get": {
        "name": "stableagent.usage.get",
        "title": "查询用量",
        "description": "查询项目或工作空间的用量统计",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "workspace_id": {"type": "string"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.apikey.create": {
        "name": "stableagent.apikey.create",
        "title": "创建 API Key",
        "description": "为工作空间创建新的 API Key",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "name": {"type": "string"},
                "scopes": {"type": "array", "items": {"type": "string"}},
                "project_id": {"type": "string"},
            },
            "required": ["workspace_id", "name"],
        },
        "risk_level": "high",
    },
    "stableagent.apikey.revoke": {
        "name": "stableagent.apikey.revoke",
        "title": "撤销 API Key",
        "description": "撤销指定的 API Key（不可逆）",
        "input_schema": {
            "type": "object",
            "properties": {
                "key_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["key_id"],
        },
        "risk_level": "high",
    },
    # =======================================================================
    # V11 Agent Capsule: 胶囊 + 记忆生命周期 + 理解轨迹 + Token + 模型 + 评测 + 反馈
    # =======================================================================
    # --- Capsule ---
    "stableagent.capsule.status": {
        "name": "stableagent.capsule.status",
        "title": "胶囊状态",
        "description": "获取 Agent Capsule 当前状态、统计信息和结构健康",
        "input_schema": {
            "type": "object",
            "properties": {
                "capsule_path": {"type": "string", "description": "胶囊路径（可选，默认使用环境变量或项目目录）"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.capsule.doctor": {
        "name": "stableagent.capsule.doctor",
        "title": "胶囊体检",
        "description": "对胶囊执行完整健康检查：manifest、目录、sqlite、jsonl、敏感信息、大文件、过期日志",
        "input_schema": {
            "type": "object",
            "properties": {
                "capsule_path": {"type": "string"},
            },
        },
        "risk_level": "low",
    },
    # --- Memory Lifecycle ---
    "stableagent.memory.health": {
        "name": "stableagent.memory.health",
        "title": "记忆健康报告",
        "description": "生成记忆健康报告：建议保留、合并、删除、冲突、过期、高价值记忆",
        "input_schema": {
            "type": "object",
            "properties": {
                "capsule_path": {"type": "string"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.memory.review": {
        "name": "stableagent.memory.review",
        "title": "记忆审核建议",
        "description": "列出需要用户确认的高价值未确认记忆",
        "input_schema": {
            "type": "object",
            "properties": {
                "capsule_path": {"type": "string"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.memory.prune": {
        "name": "stableagent.memory.prune",
        "title": "记忆修剪",
        "description": "修剪低价值记忆（需确认）",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_ids": {"type": "array", "items": {"type": "string"}, "description": "要修剪的记忆 ID 列表"},
                "capsule_path": {"type": "string"},
            },
            "required": ["memory_ids"],
        },
        "risk_level": "medium",
    },
    "stableagent.memory.promote": {
        "name": "stableagent.memory.promote",
        "title": "记忆晋升",
        "description": "将记忆晋升为 semantic_memory（长期保存）",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "capsule_path": {"type": "string"},
            },
            "required": ["memory_id"],
        },
        "risk_level": "medium",
    },
    "stableagent.memory.delete": {
        "name": "stableagent.memory.delete",
        "title": "删除记忆",
        "description": "删除指定记忆",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
                "capsule_path": {"type": "string"},
            },
            "required": ["memory_id"],
        },
        "risk_level": "medium",
    },
    # --- Model Profile ---
    "stableagent.model.profile": {
        "name": "stableagent.model.profile",
        "title": "获取模型画像",
        "description": "获取指定模型的画像信息，包括 strengths/risks/adapter rules",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "模型标识，如 claude/gpt/qwen/generic",
                },
            },
            "required": ["model_id"],
        },
        "risk_level": "low",
    },
    "stableagent.model.list": {
        "name": "stableagent.model.list",
        "title": "列出模型画像",
        "description": "列出所有已知模型画像",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    "stableagent.model.suggest": {
        "name": "stableagent.model.suggest",
        "title": "推荐模型",
        "description": "根据任务类型和可用模型列表推荐最佳模型",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "description": "任务类型，如 code_generation/bug_fix/general_qa",
                },
                "available_models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可用模型 ID 列表",
                },
            },
            "required": ["task_type", "available_models"],
        },
        "risk_level": "low",
    },
    "stableagent.model.update": {
        "name": "stableagent.model.update",
        "title": "更新模型画像",
        "description": "根据失败案例更新模型画像的风险和回避列表",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "模型标识",
                },
                "bad_case": {
                    "type": "object",
                    "description": "失败案例，需包含 failure_reason 和可选 failure_mode",
                },
            },
            "required": ["model_id", "bad_case"],
        },
        "risk_level": "low",
    },
    # =======================================================================
    # V11 Phase 6: Personal Eval / A-B Regression 工具
    # =======================================================================
    "stableagent.eval.case.create": {
        "name": "stableagent.eval.case.create",
        "title": "创建评估用例",
        "description": "创建一个个人评估用例，用于 A/B 回归测试",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "任务描述"},
                "task_type": {"type": "string", "default": "general", "description": "任务类型"},
                "must_keep": {"type": "array", "items": {"type": "string"}, "description": "必须保留的关键词"},
                "must_avoid": {"type": "array", "items": {"type": "string"}, "description": "必须避免的关键词"},
                "success_criteria": {"type": "string", "description": "成功标准"},
                "failure_modes": {"type": "array", "items": {"type": "string"}, "description": "失败模式"},
                "source_bad_case_id": {"type": "string", "description": "来源 bad case ID"},
            },
            "required": ["task"],
        },
        "risk_level": "low",
    },
    "stableagent.eval.case.list": {
        "name": "stableagent.eval.case.list",
        "title": "列出评估用例",
        "description": "列出所有个人评估用例",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "按任务类型过滤"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.eval.run_ab": {
        "name": "stableagent.eval.run_ab",
        "title": "执行 A/B 回归测试",
        "description": "比较 old_skill 和 new_skill 在评估用例上的表现",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "评估用例 ID"},
                "old_skill": {"type": "string", "description": "旧 skill 文本"},
                "new_skill": {"type": "string", "description": "新 skill 文本"},
                "rubric_id": {"type": "string", "default": "vibe_coding_default", "description": "评分维度集 ID"},
            },
            "required": ["case_id", "old_skill", "new_skill"],
        },
        "risk_level": "low",
    },
    "stableagent.eval.rubric.get": {
        "name": "stableagent.eval.rubric.get",
        "title": "获取评分维度",
        "description": "获取指定评分维度集的定义",
        "input_schema": {
            "type": "object",
            "properties": {
                "rubric_id": {"type": "string", "default": "vibe_coding_default"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.eval.rubric.update": {
        "name": "stableagent.eval.rubric.update",
        "title": "更新评分维度",
        "description": "更新评分维度集的维度和权重",
        "input_schema": {
            "type": "object",
            "properties": {
                "rubric_id": {"type": "string", "description": "评分维度集 ID"},
                "dimensions": {
                    "type": "object",
                    "description": "维度名称 → 权重映射",
                    "additionalProperties": {"type": "number"},
                },
            },
            "required": ["rubric_id", "dimensions"],
        },
        "risk_level": "low",
    },
    # =======================================================================
    # V11 Phase 7: Feedback Loop 反馈闭环工具
    # =======================================================================
    "stableagent.feedback.remember": {
        "name": "stableagent.feedback.remember",
        "title": "记住这个",
        "description": "用户标记'记住这个'，生成 memory candidate",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "关联运行 ID"},
                "user_note": {"type": "string", "description": "用户备注"},
                "context": {"type": "object", "description": "附加上下文"},
            },
            "required": ["run_id", "user_note"],
        },
        "risk_level": "low",
    },
    "stableagent.feedback.dont_do_this_again": {
        "name": "stableagent.feedback.dont_do_this_again",
        "title": "下次别这样",
        "description": "用户标记'下次别这样'，生成 bad case + eval case + skill patch candidate",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "关联运行 ID"},
                "user_note": {"type": "string", "description": "用户备注"},
                "context": {"type": "object", "description": "附加上下文"},
            },
            "required": ["run_id", "user_note"],
        },
        "risk_level": "low",
    },
    "stableagent.feedback.correct_and_remember": {
        "name": "stableagent.feedback.correct_and_remember",
        "title": "纠正并记住",
        "description": "用户纠正行为并要求记住，生成 correction + memory + regression case",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "关联运行 ID"},
                "user_note": {"type": "string", "description": "用户备注"},
                "context": {"type": "object", "description": "附加上下文"},
            },
            "required": ["run_id", "user_note"],
        },
        "risk_level": "low",
    },
    # --- Token Budget Ledger ---
    "stableagent.token.report": {
        "name": "stableagent.token.report",
        "title": "Token 节省报告",
        "description": "获取指定运行的 token 节省报告，包含基线对比、节省比例和风险评估",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "运行 ID"},
            },
            "required": ["run_id"],
        },
        "risk_level": "low",
    },
    "stableagent.token.run": {
        "name": "stableagent.token.run",
        "title": "Token 运行记录",
        "description": "获取指定运行的完整 token 预算记录",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "运行 ID"},
            },
            "required": ["run_id"],
        },
        "risk_level": "low",
    },
    "stableagent.token.summary": {
        "name": "stableagent.token.summary",
        "title": "Token 周期汇总",
        "description": "获取指定周期内的 token 消耗汇总统计",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 7, "description": "统计天数"},
            },
        },
        "risk_level": "low",
    },
    # ── Computer Use 工具 ──
    "stableagent.computer.screenshot": {
        "name": "stableagent.computer.screenshot",
        "title": "屏幕截图",
        "description": "截取当前屏幕并返回图片 (base64)",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "array", "items": {"type": "integer"}, "description": "[x,y,w,h] 截图区域，留空全屏"},
                "quality": {"type": "integer", "default": 75, "description": "JPEG 压缩质量"},
            },
        },
        "risk_level": "low",
    },
    "stableagent.computer.mouse_click": {
        "name": "stableagent.computer.mouse_click",
        "title": "鼠标点击",
        "description": "在指定坐标执行鼠标点击",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "屏幕 X 坐标"},
                "y": {"type": "integer", "description": "屏幕 Y 坐标"},
                "button": {"type": "string", "default": "left", "enum": ["left", "right", "middle"]},
                "clicks": {"type": "integer", "default": 1, "description": "点击次数，2=双击"},
            },
            "required": ["x", "y"],
        },
        "risk_level": "medium",
    },
    "stableagent.computer.mouse_move": {
        "name": "stableagent.computer.mouse_move",
        "title": "鼠标移动",
        "description": "移动鼠标到指定坐标",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        "risk_level": "low",
    },
    "stableagent.computer.mouse_scroll": {
        "name": "stableagent.computer.mouse_scroll",
        "title": "鼠标滚动",
        "description": "鼠标滚动（正=向上，负=向下）",
        "input_schema": {
            "type": "object",
            "properties": {
                "clicks": {"type": "integer", "default": -3},
            },
        },
        "risk_level": "low",
    },
    "stableagent.computer.keyboard_type": {
        "name": "stableagent.computer.keyboard_type",
        "title": "键盘输入",
        "description": "模拟键盘输入文本",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要输入的文本"},
            },
            "required": ["text"],
        },
        "risk_level": "medium",
    },
    "stableagent.computer.keyboard_hotkey": {
        "name": "stableagent.computer.keyboard_hotkey",
        "title": "组合键",
        "description": "执行组合键操作（如 cmd+c）",
        "input_schema": {
            "type": "object",
            "properties": {
                "keys": {"type": "array", "items": {"type": "string"}, "description": "按键列表"},
            },
            "required": ["keys"],
        },
        "risk_level": "medium",
    },
    "stableagent.computer.keyboard_press": {
        "name": "stableagent.computer.keyboard_press",
        "title": "按键",
        "description": "按下指定按键 (enter/tab/escape 等)",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "presses": {"type": "integer", "default": 1},
            },
            "required": ["key"],
        },
        "risk_level": "low",
    },
    "stableagent.computer.screen_info": {
        "name": "stableagent.computer.screen_info",
        "title": "屏幕信息",
        "description": "获取屏幕分辨率和鼠标位置",
        "input_schema": {"type": "object", "properties": {}},
        "risk_level": "low",
    },
    # ── Local Terminal 工具 ──
    "stableagent.terminal.run_command": {
        "name": "stableagent.terminal.run_command",
        "title": "终端命令",
        "description": "在本地终端执行 shell 命令",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell 命令"},
                "cwd": {"type": "string", "description": "工作目录"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
        "risk_level": "medium",
    },
    "stableagent.terminal.write_file": {
        "name": "stableagent.terminal.write_file",
        "title": "写文件",
        "description": "写入文件到本地路径",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        },
        "risk_level": "medium",
    },
    "stableagent.terminal.read_file": {
        "name": "stableagent.terminal.read_file",
        "title": "读文件",
        "description": "读取本地文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        },
        "risk_level": "low",
    },
}

AVATAR_STATE_MAP: dict[str, str] = {
    "mcp.call.received": "listening",
    "task.classified": "thinking",
    "context.budgeted": "calculating",
    "memory.retrieved": "reading_notes",
    "rag.retrieved": "searching_books",
    "tool.risk_checked": "safety_check",
    "approval.required": "waiting_approval",
    "workflow.step.started": "tooling",
    "planning.started": "planning",
    "eval.completed": "grading",
    "skillopt.patch.proposed": "learning",
    "skillopt.validation.running": "grading",
    "skillopt.exported": "archiving",
    "tool.failed": "failed",
    "task.completed": "done",
    "token.budget.estimated": "calculating",
    "token.savings.reported": "archiving",
    "default": "listening",
}

# ---------------------------------------------------------------------------
# 13 语义场景映射 —— 头像状态 → 场景/道具/标签
# ---------------------------------------------------------------------------

AVATAR_SCENE_MAP: dict[str, dict[str, str]] = {
    "listening": {
        "scene": "desk",
        "prop": "task_card",
        "label_zh": "正在接收任务",
        "label_en": "Receiving task",
    },
    "thinking": {
        "scene": "thinking_board",
        "prop": "magnifier",
        "label_zh": "正在理解你的需求",
        "label_en": "Understanding your intent",
    },
    "reading_notes": {
        "scene": "memory_wall",
        "prop": "memory_cards",
        "label_zh": "正在找以前的经验",
        "label_en": "Retrieving prior memory",
    },
    "searching_books": {
        "scene": "library",
        "prop": "bookshelf",
        "label_zh": "正在查找项目资料",
        "label_en": "Searching project knowledge",
    },
    "calculating": {
        "scene": "budget_panel",
        "prop": "abacus",
        "label_zh": "正在计算 token 成本",
        "label_en": "Estimating token budget",
    },
    "planning": {
        "scene": "map_table",
        "prop": "route_map",
        "label_zh": "正在规划执行步骤",
        "label_en": "Planning execution steps",
    },
    "tooling": {
        "scene": "tool_bench",
        "prop": "wrench",
        "label_zh": "正在调用工具",
        "label_en": "Calling a tool",
    },
    "safety_check": {
        "scene": "checkpoint",
        "prop": "helmet",
        "label_zh": "正在做安全检查",
        "label_en": "Running safety check",
    },
    "waiting_approval": {
        "scene": "approval_gate",
        "prop": "red_card",
        "label_zh": "等待你确认",
        "label_en": "Waiting for approval",
    },
    "grading": {
        "scene": "exam_table",
        "prop": "score_sheet",
        "label_zh": "正在评估结果",
        "label_en": "Evaluating output",
    },
    "learning": {
        "scene": "skill_book",
        "prop": "notebook",
        "label_zh": "正在总结经验",
        "label_en": "Learning from this run",
    },
    "archiving": {
        "scene": "archive_cabinet",
        "prop": "best_skill_file",
        "label_zh": "正在更新 best_skill.md",
        "label_en": "Updating best_skill.md",
    },
    "done": {
        "scene": "delivery_desk",
        "prop": "done_stamp",
        "label_zh": "任务完成",
        "label_en": "Task completed",
    },
    "failed": {
        "scene": "error_board",
        "prop": "warning_sign",
        "label_zh": "任务失败，正在记录原因",
        "label_en": "Task failed, recording reason",
    },
}

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def get_tool_names() -> list[str]:
    """返回所有已注册工具的完整名称列表。"""
    return list(TOOLS.keys())


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """按名称获取单个工具的定义。如果未找到则返回 None。"""
    return TOOLS.get(name)


def get_avatar_state(event_type: str) -> str:
    """根据事件类型获取对应的头像状态。

    如果未找到精确匹配，返回默认状态 "idle"。

    Args:
        event_type: 事件类型字符串，如 "mcp.call.received"。

    Returns:
        对应的头像动画状态名称。
    """
    return AVATAR_STATE_MAP.get(event_type, AVATAR_STATE_MAP["default"])


def get_scene_for_state(state: str) -> dict[str, str]:
    """根据头像状态名获取对应的语义场景配置。

    Args:
        state: 头像状态名，如 "listening"、"thinking" 等。

    Returns:
        包含 scene, prop, label_zh, label_en 的字典。
        如果未找到，返回 listening 的默认场景。
    """
    return AVATAR_SCENE_MAP.get(state, AVATAR_SCENE_MAP["listening"])


def get_risk_level(tool_name: str) -> str:
    """获取指定工具的风险等级。

    Args:
        tool_name: 工具完整名称。

    Returns:
        风险等级字符串（"low"/"medium"/"high"），如果工具未注册则返回 "low"。
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        return "low"
    return tool.get("risk_level", "low")
