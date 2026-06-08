# OS Agent — Claude Code 安装指南

## 一键安装

```bash
# 1. 启动 StableAgent OS 服务
uvicorn web.server:app --host 127.0.0.1 --port 8000 &

# 2. Claude Code 自动识别 .claude/skills/ 目录
# 无需额外配置

# 3. 验证
curl http://127.0.0.1:8000/api/connect/health
```

## 使用

在 Claude Code 中输入：
```
/os-agent 帮我优化项目架构
```

## MCP 配置（如需直接调用工具）

Claude Code 会自动读取项目内的 `.claude/` 配置。

MCP endpoint: `http://127.0.0.1:8000/mcp/v5/mcp`
