#!/bin/bash
# OS Agent 健康检查
ENDPOINT="${1:-http://127.0.0.1:8000}"
echo "检查 StableAgent OS 服务: $ENDPOINT"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT/api/health" 2>/dev/null)
if [ "$STATUS" = "200" ]; then
    echo "✅ 服务运行中"
    curl -s "$ENDPOINT/api/health" | python3 -m json.tool
else
    echo "❌ 服务未运行 (HTTP $STATUS)"
    echo "启动命令: PYTHONPATH=. ./.venv/bin/python -m stable_agent.cli serve"
fi
