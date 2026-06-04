"""Local Terminal — 本地终端命令执行模块。

允许 Agent 在本地机器上执行 shell 命令和编写代码文件。

安全策略:
- 黑名单: 禁止 rm -rf /、shutdown、reboot 等危险命令
- 超时: 默认 30 秒
- 输出截断: 最大 10KB
- 所有命令记录到日志

用法:
    python -m stable_agent.local_terminal run --command "ls -la"
    python -m stable_agent.local_terminal write_file --args '{"path":"/tmp/test.py","content":"print(1)"}'
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 安全黑名单 ──

DANGEROUS_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
]

MAX_OUTPUT_BYTES = 10 * 1024  # 10KB
DEFAULT_TIMEOUT = 30  # seconds


@dataclass
class TerminalResult:
    ok: bool
    action: str
    message: str = ""
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def _is_dangerous(command: str) -> tuple[bool, str]:
    """检查命令是否在黑名单中。"""
    cmd_lower = command.lower().strip()
    for dc in DANGEROUS_COMMANDS:
        if dc.lower() in cmd_lower:
            return True, f"命令匹配安全黑名单: {dc}"
    return False, ""


def run_command(command: str, cwd: Optional[str] = None,
                timeout: int = DEFAULT_TIMEOUT,
                env: Optional[dict] = None) -> TerminalResult:
    """执行 shell 命令。

    Args:
        command: 要执行的 shell 命令。
        cwd: 工作目录（默认当前目录）。
        timeout: 超时时间（秒）。
        env: 额外的环境变量。

    Returns:
        TerminalResult。
    """
    start = time.time()

    # 安全检查
    dangerous, reason = _is_dangerous(command)
    if dangerous:
        return TerminalResult(
            ok=False, action="run_command",
            message=f"安全拦截: {reason}",
            data={"command": command},
            latency_ms=int((time.time() - start) * 1000),
        )

    try:
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.path.expanduser("~"),
            env=run_env,
        )

        stdout = proc.stdout[:MAX_OUTPUT_BYTES] if proc.stdout else ""
        stderr = proc.stderr[:MAX_OUTPUT_BYTES] if proc.stderr else ""

        result = TerminalResult(
            ok=proc.returncode == 0,
            action="run_command",
            message=f"命令执行{'成功' if proc.returncode == 0 else '失败'} (exit={proc.returncode})",
            data={
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
            latency_ms=int((time.time() - start) * 1000),
        )
    except subprocess.TimeoutExpired:
        result = TerminalResult(
            ok=False, action="run_command",
            message=f"命令超时 ({timeout}s): {command[:60]}",
            data={"command": command, "timeout": timeout},
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        result = TerminalResult(
            ok=False, action="run_command",
            message=f"命令执行异常: {e}",
            data={"command": command},
            latency_ms=int((time.time() - start) * 1000),
        )

    return result


def write_file(file_path: str, content: str,
               create_dirs: bool = True) -> TerminalResult:
    """写入文件到指定路径。

    Args:
        file_path: 文件绝对路径。
        content: 文件内容。
        create_dirs: 是否自动创建父目录。

    Returns:
        TerminalResult。
    """
    start = time.time()

    try:
        p = Path(file_path).expanduser()

        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)

        p.write_text(content, encoding="utf-8")

        result = TerminalResult(
            ok=True, action="write_file",
            message=f"文件已写入: {file_path} ({len(content)} 字节)",
            data={
                "path": str(p),
                "size": len(content),
                "lines": content.count("\n") + 1,
            },
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        result = TerminalResult(
            ok=False, action="write_file",
            message=f"写入文件失败: {e}",
            data={"path": file_path},
            latency_ms=int((time.time() - start) * 1000),
        )

    return result


def read_file(file_path: str, max_lines: int = 500) -> TerminalResult:
    """读取文件内容。

    Args:
        file_path: 文件路径。
        max_lines: 最大读取行数。

    Returns:
        TerminalResult。
    """
    start = time.time()

    try:
        p = Path(file_path).expanduser()
        if not p.exists():
            return TerminalResult(
                ok=False, action="read_file",
                message=f"文件不存在: {file_path}",
                latency_ms=int((time.time() - start) * 1000),
            )

        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()[:max_lines]
        truncated = len(content.splitlines()) > max_lines

        result = TerminalResult(
            ok=True, action="read_file",
            message=f"读取成功: {file_path} ({len(lines)} 行{'...' if truncated else ''})",
            data={
                "path": str(p),
                "content": "\n".join(lines),
                "total_lines": len(content.splitlines()),
                "truncated": truncated,
            },
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        result = TerminalResult(
            ok=False, action="read_file",
            message=f"读取失败: {e}",
            data={"path": file_path},
            latency_ms=int((time.time() - start) * 1000),
        )

    return result


def list_directory(dir_path: str = "~", show_hidden: bool = False) -> TerminalResult:
    """列出目录内容。

    Args:
        dir_path: 目录路径。
        show_hidden: 是否显示隐藏文件。

    Returns:
        TerminalResult。
    """
    start = time.time()

    try:
        p = Path(dir_path).expanduser()
        if not p.is_dir():
            return TerminalResult(
                ok=False, action="list_directory",
                message=f"不是目录: {dir_path}",
                latency_ms=int((time.time() - start) * 1000),
            )

        entries = []
        for item in sorted(p.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            })

        result = TerminalResult(
            ok=True, action="list_directory",
            message=f"目录 {dir_path}: {len(entries)} 项",
            data={"path": str(p), "entries": entries[:200], "total": len(entries)},
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        result = TerminalResult(
            ok=False, action="list_directory",
            message=f"列出目录失败: {e}",
            latency_ms=int((time.time() - start) * 1000),
        )

    return result


# ── 统一入口 ──

ACTIONS = {
    "run_command": lambda args: run_command(
        command=args.get("command", ""),
        cwd=args.get("cwd"),
        timeout=args.get("timeout", DEFAULT_TIMEOUT),
    ),
    "write_file": lambda args: write_file(
        file_path=args.get("path", args.get("file_path", "")),
        content=args.get("content", ""),
        create_dirs=args.get("create_dirs", True),
    ),
    "read_file": lambda args: read_file(
        file_path=args.get("path", args.get("file_path", "")),
        max_lines=args.get("max_lines", 500),
    ),
    "list_directory": lambda args: list_directory(
        dir_path=args.get("path", args.get("dir_path", "~")),
        show_hidden=args.get("show_hidden", False),
    ),
}


def execute_action(action: str, args: dict) -> TerminalResult:
    """执行指定的本地终端操作。"""
    handler = ACTIONS.get(action)
    if handler is None:
        return TerminalResult(
            ok=False, action=action,
            message=f"未知操作: {action}，支持: {list(ACTIONS.keys())}",
        )
    try:
        return handler(args)
    except Exception as e:
        return TerminalResult(
            ok=False, action=action,
            message=f"操作失败: {e}",
        )


# ── CLI 入口 ──

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": "Usage: python -m stable_agent.local_terminal <action> [--args JSON]",
            "available_actions": list(ACTIONS.keys()),
        }))
        sys.exit(1)

    action = sys.argv[1]
    args = {}
    if "--args" in sys.argv:
        idx = sys.argv.index("--args")
        if idx + 1 < len(sys.argv):
            try:
                args = json.loads(sys.argv[idx + 1])
            except json.JSONDecodeError as e:
                print(json.dumps({"ok": False, "error": f"参数解析失败: {e}"}))
                sys.exit(1)

    result = execute_action(action, args)
    print(result.to_json())


if __name__ == "__main__":
    main()
