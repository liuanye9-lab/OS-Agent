#!/bin/bash
# 一键确保 StableAgent OS Dashboard 运行
set -e

HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"
ROOT_DIR="$(cd "$(dirname "$0")/../../../../" && pwd)"
BASE_URL="http://$HOST:$PORT"
PYTHON="$ROOT_DIR/.venv/bin/python"

echo "启动 StableAgent OS Dashboard..."
echo "Dashboard: $BASE_URL"
echo "Observer:  $BASE_URL/observer"
echo "Connect:   $BASE_URL/connect"

if curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
  echo "StableAgent OS 服务已运行"
else
  if [ ! -x "$PYTHON" ]; then
    echo "未找到项目 Python: $PYTHON" >&2
    echo "请先在项目根目录配置 .venv" >&2
    exit 1
  fi

  echo "服务未运行，自动启动..."
  (
    cd "$ROOT_DIR"
    "$PYTHON" - <<'PY'
import os
import subprocess

root = os.getcwd()
python = os.path.join(root, ".venv", "bin", "python")
log_path = "/tmp/stableagent-os-dashboard.log"
pid_path = "/tmp/stableagent-os-dashboard.pid"
env = os.environ.copy()
env["PYTHONPATH"] = "."

log = open(log_path, "ab", buffering=0)
proc = subprocess.Popen(
    [python, "-m", "stable_agent.cli", "serve"],
    cwd=root,
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
with open(pid_path, "w", encoding="utf-8") as f:
    f.write(str(proc.pid))
PY
  )

  for _ in $(seq 1 30); do
    if curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
      echo "StableAgent OS 服务启动成功"
      break
    fi
    sleep 1
  done

  if ! curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
    echo "服务启动失败，日志: /tmp/stableagent-os-dashboard.log" >&2
    exit 1
  fi
fi

open "$BASE_URL/observer" 2>/dev/null || xdg-open "$BASE_URL/observer" 2>/dev/null || echo "请手动打开: $BASE_URL/observer"
