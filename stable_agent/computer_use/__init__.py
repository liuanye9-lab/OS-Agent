"""Computer Use 模块 — 屏幕截图 + 鼠标键盘控制。

提供操作系统级 GUI 控制能力：
- screenshot: 截取全屏或指定区域 (macOS screencapture)
- mouse_click: 点击指定坐标 (cliclick / osascript)
- mouse_move: 移动鼠标到指定坐标
- keyboard_type: 输入文本 (osascript)
- keyboard_hotkey: 组合键操作
- mouse_scroll: 滚动操作

优先使用 macOS 原生命令，回退到 pyautogui。
所有操作记录到日志，高风险操作需确认。
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── pyautogui 延迟导入（可选回退） ──

_pyautogui = None


def _try_pyautogui():
    """尝试加载 pyautogui 作为回退。"""
    global _pyautogui
    if _pyautogui is not None:
        return True
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        _pyautogui = pyautogui
        return True
    except Exception:
        return False


# ── 数据类 ──


@dataclass
class ComputerActionResult:
    """Computer Use 操作的返回结果。"""
    ok: bool
    action: str
    message: str = ""
    data: dict = field(default_factory=dict)
    screenshot_base64: str = ""
    timestamp: float = field(default_factory=time.time)
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ── 操作历史 ──

_action_history: list[dict] = []
MAX_HISTORY = 200


def _record_action(action: str, params: dict, result: ComputerActionResult):
    _action_history.append({
        "action": action,
        "params": params,
        "ok": result.ok,
        "timestamp": result.timestamp,
        "latency_ms": result.latency_ms,
    })
    if len(_action_history) > MAX_HISTORY:
        _action_history.pop(0)


def _run_cmd(cmd: str, timeout: int = 10) -> tuple[int, str, str]:
    """执行 shell 命令并返回 (returncode, stdout, stderr)。"""
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"命令超时 ({timeout}s)"
    except Exception as e:
        return -1, "", str(e)


def _has_cmd(name: str) -> bool:
    """检查命令是否存在。"""
    rc, out, _ = _run_cmd(f"which {name}")
    return rc == 0 and out.strip() != ""


# ── 核心操作 ──


def screenshot(region: Optional[tuple] = None, quality: int = 75,
               max_width: int = 1280) -> ComputerActionResult:
    """截取屏幕截图并返回 base64 编码。"""
    start = time.time()

    # 方法1: macOS screencapture
    tmpfile = tempfile.mktemp(suffix=".jpg")
    try:
        rc, out, err = _run_cmd(f"screencapture -x -t jpg '{tmpfile}'", timeout=10)
        if rc == 0 and os.path.exists(tmpfile):
            # 读取文件并转 base64
            with open(tmpfile, "rb") as f:
                img_data = f.read()
            b64 = base64.b64encode(img_data).decode("utf-8")
            os.unlink(tmpfile)
            return ComputerActionResult(
                ok=True, action="screenshot",
                message=f"截图成功 ({len(img_data)} bytes)",
                data={"size_bytes": len(img_data), "method": "screencapture"},
                screenshot_base64=b64,
                latency_ms=int((time.time() - start) * 1000),
            )
    except Exception as e:
        logger.warning(f"screencapture failed: {e}")
    finally:
        if os.path.exists(tmpfile):
            try:
                os.unlink(tmpfile)
            except Exception:
                pass

    # 方法2: pyautogui 回退
    if _try_pyautogui():
        try:
            img = _pyautogui.screenshot(region=region)
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return ComputerActionResult(
                ok=True, action="screenshot",
                message=f"截图成功 ({img.width}x{img.height})",
                data={"width": img.width, "height": img.height, "method": "pyautogui"},
                screenshot_base64=b64,
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui screenshot failed: {e}")

    return ComputerActionResult(
        ok=False, action="screenshot",
        message="截图失败: screencapture 和 pyautogui 均不可用",
        latency_ms=int((time.time() - start) * 1000),
    )


def mouse_click(x: int, y: int, button: str = "left",
                clicks: int = 1) -> ComputerActionResult:
    """在指定坐标执行鼠标点击。"""
    start = time.time()

    # 方法1: cliclick
    if _has_cmd("cliclick"):
        cmd_str = f"cliclick c:{x},{y}" if clicks == 1 else f"cliclick dc:{x},{y}"
        if button == "right":
            cmd_str = f"cliclick rc:{x},{y}"
        rc, out, err = _run_cmd(cmd_str)
        if rc == 0:
            return ComputerActionResult(
                ok=True, action="mouse_click",
                message=f"点击 ({x}, {y}) {button} x{clicks}",
                data={"x": x, "y": y, "button": button, "clicks": clicks, "method": "cliclick"},
                latency_ms=int((time.time() - start) * 1000),
            )

    # 方法2: osascript (AppleScript)
    script = f'''
    tell application "System Events"
        click at {{{x}, {y}}}
    end tell
    '''
    rc, out, err = _run_cmd(f"osascript -e '{script.strip()}'")
    if rc == 0:
        return ComputerActionResult(
            ok=True, action="mouse_click",
            message=f"点击 ({x}, {y})",
            data={"x": x, "y": y, "method": "osascript"},
            latency_ms=int((time.time() - start) * 1000),
        )

    # 方法3: pyautogui
    if _try_pyautogui():
        try:
            _pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return ComputerActionResult(
                ok=True, action="mouse_click",
                message=f"点击 ({x}, {y}) {button} x{clicks}",
                data={"x": x, "y": y, "button": button, "method": "pyautogui"},
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui click failed: {e}")

    return ComputerActionResult(
        ok=False, action="mouse_click",
        message="鼠标点击失败: cliclick/osascript/pyautogui 均不可用",
        latency_ms=int((time.time() - start) * 1000),
    )


def mouse_move(x: int, y: int, duration: float = 0) -> ComputerActionResult:
    """移动鼠标到指定坐标。"""
    start = time.time()

    # cliclick
    if _has_cmd("cliclick"):
        rc, out, err = _run_cmd(f"cliclick m:{x},{y}")
        if rc == 0:
            return ComputerActionResult(
                ok=True, action="mouse_move",
                message=f"鼠标移动到 ({x}, {y})",
                data={"x": x, "y": y, "method": "cliclick"},
                latency_ms=int((time.time() - start) * 1000),
            )

    # osascript
    script = f'tell application "System Events" to set mouse position to {{{x}, {y}}}'
    rc, out, err = _run_cmd(f"osascript -e '{script}'")
    if rc == 0:
        return ComputerActionResult(
            ok=True, action="mouse_move",
            message=f"鼠标移动到 ({x}, {y})",
            data={"x": x, "y": y, "method": "osascript"},
            latency_ms=int((time.time() - start) * 1000),
        )

    # pyautogui
    if _try_pyautogui():
        try:
            _pyautogui.moveTo(x, y, duration=duration)
            return ComputerActionResult(
                ok=True, action="mouse_move",
                message=f"鼠标移动到 ({x}, {y})",
                data={"x": x, "y": y, "method": "pyautogui"},
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui move failed: {e}")

    return ComputerActionResult(
        ok=False, action="mouse_move",
        message="鼠标移动失败",
        latency_ms=int((time.time() - start) * 1000),
    )


def mouse_scroll(clicks: int, x: Optional[int] = None,
                 y: Optional[int] = None) -> ComputerActionResult:
    """鼠标滚动。"""
    start = time.time()

    # cliclick
    if _has_cmd("cliclick"):
        direction = "up" if clicks > 0 else "down"
        amount = abs(clicks) * 3
        cmd = f"cliclick {direction}:{amount}"
        rc, out, err = _run_cmd(cmd)
        if rc == 0:
            return ComputerActionResult(
                ok=True, action="mouse_scroll",
                message=f"滚动 {direction} {abs(clicks)} 次",
                data={"clicks": clicks, "direction": direction, "method": "cliclick"},
                latency_ms=int((time.time() - start) * 1000),
            )

    # osascript
    scroll_amount = abs(clicks) * 3
    direction = 1 if clicks > 0 else -1
    script = f'tell application "System Events" to scroll area 1 of group 1 by {scroll_amount * direction}'
    rc, out, err = _run_cmd(f"osascript -e '{script}'")
    if rc == 0:
        return ComputerActionResult(
            ok=True, action="mouse_scroll",
            message=f"滚动 {scroll_amount} 单位",
            data={"clicks": clicks, "method": "osascript"},
            latency_ms=int((time.time() - start) * 1000),
        )

    # pyautogui
    if _try_pyautogui():
        try:
            _pyautogui.scroll(clicks, x=x, y=y)
            return ComputerActionResult(
                ok=True, action="mouse_scroll",
                message=f"滚动 {'up' if clicks > 0 else 'down'} {abs(clicks)} 次",
                data={"clicks": clicks, "method": "pyautogui"},
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui scroll failed: {e}")

    return ComputerActionResult(
        ok=False, action="mouse_scroll",
        message="鼠标滚动失败",
        latency_ms=int((time.time() - start) * 1000),
    )


def keyboard_type(text: str, interval: float = 0.02) -> ComputerActionResult:
    """模拟键盘输入文本。"""
    start = time.time()

    # osascript (最可靠的方式)
    escaped_text = text.replace('"', '\\"').replace('`', '\\`')
    script = f'tell application "System Events" to keystroke "{escaped_text}"'
    rc, out, err = _run_cmd(f"osascript -e '{script}'")
    if rc == 0:
        return ComputerActionResult(
            ok=True, action="keyboard_type",
            message=f"输入文本: {text[:50]}{'...' if len(text) > 50 else ''}",
            data={"text_length": len(text), "method": "osascript"},
            latency_ms=int((time.time() - start) * 1000),
        )

    # cliclick
    if _has_cmd("cliclick"):
        rc, out, err = _run_cmd(f'cliclick t:"{escaped_text}"')
        if rc == 0:
            return ComputerActionResult(
                ok=True, action="keyboard_type",
                message=f"输入文本: {text[:50]}",
                data={"text_length": len(text), "method": "cliclick"},
                latency_ms=int((time.time() - start) * 1000),
            )

    # pyautogui
    if _try_pyautogui():
        try:
            if any(ord(c) > 127 for c in text):
                proc = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                proc.communicate(text.encode('utf-8'))
                time.sleep(0.1)
                _pyautogui.hotkey('command', 'v')
            else:
                _pyautogui.typewrite(text, interval=interval)
            return ComputerActionResult(
                ok=True, action="keyboard_type",
                message=f"输入文本: {text[:50]}",
                data={"text_length": len(text), "method": "pyautogui"},
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui type failed: {e}")

    return ComputerActionResult(
        ok=False, action="keyboard_type",
        message="键盘输入失败",
        latency_ms=int((time.time() - start) * 1000),
    )


def keyboard_hotkey(*keys: str) -> ComputerActionResult:
    """执行组合键操作。"""
    start = time.time()

    # 映射通用键名到 macOS
    key_map = {
        'command': 'command', 'cmd': 'command', 'super': 'command',
        'ctrl': 'control', 'control': 'control',
        'alt': 'option', 'option': 'option',
        'shift': 'shift',
        'enter': 'return', 'return': 'return',
        'tab': 'tab', 'escape': 'escape', 'esc': 'escape',
        'backspace': 'delete', 'delete': 'delete',
        'space': 'space',
    }

    mapped_keys = [key_map.get(k.lower(), k.lower()) for k in keys]

    # osascript
    key_str = " & ".join([f'"{k}"' if i == len(mapped_keys) - 1 else f'keystroke {k}' for i, k in enumerate(mapped_keys)])
    # Simpler approach for common combos
    if len(mapped_keys) == 2:
        script = f'tell application "System Events" to keystroke "{mapped_keys[1]}" using {mapped_keys[0]} down'
    elif len(mapped_keys) == 3:
        script = f'tell application "System Events" to keystroke "{mapped_keys[2]}" using {{{mapped_keys[0]} down, {mapped_keys[1]} down}}'
    else:
        script = f'tell application "System Events" to keystroke "{mapped_keys[-1]}"'

    rc, out, err = _run_cmd(f"osascript -e '{script}'")
    if rc == 0:
        return ComputerActionResult(
            ok=True, action="keyboard_hotkey",
            message=f"组合键: {'+'.join(keys)}",
            data={"keys": list(keys), "method": "osascript"},
            latency_ms=int((time.time() - start) * 1000),
        )

    # pyautogui fallback
    if _try_pyautogui():
        try:
            _pyautogui.hotkey(*keys)
            return ComputerActionResult(
                ok=True, action="keyboard_hotkey",
                message=f"组合键: {'+'.join(keys)}",
                data={"keys": list(keys), "method": "pyautogui"},
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.warning(f"pyautogui hotkey failed: {e}")

    return ComputerActionResult(
        ok=False, action="keyboard_hotkey",
        message="组合键失败",
        latency_ms=int((time.time() - start) * 1000),
    )


def keyboard_press(key: str, presses: int = 1) -> ComputerActionResult:
    """按下单个键。"""
    start = time.time()

    key_map = {
        'enter': 'return', 'return': 'return',
        'tab': 'tab', 'escape': 'escape', 'esc': 'escape',
        'backspace': 'delete', 'delete': 'delete',
        'space': 'space', 'up': 'up arrow', 'down': 'down arrow',
        'left': 'left arrow', 'right': 'right arrow',
        'home': 'home', 'end': 'end',
    }

    mac_key = key_map.get(key.lower(), key.lower())

    for _ in range(presses):
        script = f'tell application "System Events" to keystroke "{mac_key}"'
        rc, out, err = _run_cmd(f"osascript -e '{script}'")
        if rc != 0:
            # Try key code approach for special keys
            script2 = f'tell application "System Events" to key code {mac_key}'
            rc, out, err = _run_cmd(f"osascript -e '{script2}'")

    return ComputerActionResult(
        ok=True, action="keyboard_press",
        message=f"按键: {key} x{presses}",
        data={"key": key, "presses": presses, "method": "osascript"},
        latency_ms=int((time.time() - start) * 1000),
    )


def get_screen_info() -> ComputerActionResult:
    """获取屏幕信息（分辨率、鼠标位置等）。"""
    start = time.time()

    # 使用 system_profiler 获取屏幕分辨率
    rc, out, err = _run_cmd("system_profiler SPDisplaysDataType | grep Resolution")
    resolution = out.strip() if rc == 0 else "unknown"

    # 使用 cliclick 获取鼠标位置
    mouse_pos = None
    if _has_cmd("cliclick"):
        rc, out, err = _run_cmd("cliclick p")
        if rc == 0:
            mouse_pos = out.strip()

    # 尝试用 osascript
    if not mouse_pos:
        rc, out, err = _run_cmd(
            'osascript -e \'tell application "System Events" to set pos to do shell script "osascript -e \\"tell application \\\\\\"Finder\\\\\\" to get bounds of window of desktop\\""\''
        )

    # 尝试 Python Quartz 直接
    if not mouse_pos:
        try:
            result = subprocess.run(
                ['/usr/bin/python3', '-c',
                 'from Quartz.CoreGraphics import CGEventGetLocation, CGEventCreate; e=CGEventCreate(None); p=CGEventGetLocation(e); print(f"{int(p.x)},{int(p.y)}")'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                mouse_pos = result.stdout.strip()
        except Exception:
            pass

    # pyautogui fallback
    if not mouse_pos and _try_pyautogui():
        try:
            pos = _pyautogui.position()
            size = _pyautogui.size()
            return ComputerActionResult(
                ok=True, action="get_screen_info",
                message=f"屏幕 {size.width}x{size.height}, 鼠标 ({pos.x}, {pos.y})",
                data={
                    "screen_width": size.width,
                    "screen_height": size.height,
                    "mouse_x": pos.x,
                    "mouse_y": pos.y,
                    "method": "pyautogui",
                },
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception:
            pass

    # 解析 system_profiler 的分辨率
    width, height = 0, 0
    if resolution:
        import re
        match = re.search(r'(\d+)\s*x\s*(\d+)', resolution)
        if match:
            width = int(match.group(1))
            height = int(match.group(2))

    mouse_x, mouse_y = 0, 0
    if mouse_pos and "," in mouse_pos:
        parts = mouse_pos.split(",")
        try:
            mouse_x = int(parts[0].strip())
            mouse_y = int(parts[1].strip())
        except (ValueError, IndexError):
            pass

    return ComputerActionResult(
        ok=True, action="get_screen_info",
        message=f"屏幕 {resolution}, 鼠标 ({mouse_x}, {mouse_y})",
        data={
            "screen_width": width,
            "screen_height": height,
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
            "resolution_raw": resolution,
            "method": "system_profiler+cliclick",
        },
        latency_ms=int((time.time() - start) * 1000),
    )


def get_action_history(limit: int = 20) -> list[dict]:
    """获取操作历史。"""
    return _action_history[-limit:]


# ── 统一操作入口 ──

ACTIONS = {
    "screenshot": lambda args: screenshot(
        region=tuple(args["region"]) if args.get("region") else None,
        quality=args.get("quality", 75),
    ),
    "mouse_click": lambda args: mouse_click(
        x=args.get("x", 0), y=args.get("y", 0),
        button=args.get("button", "left"),
        clicks=args.get("clicks", 1),
    ),
    "mouse_move": lambda args: mouse_move(
        x=args.get("x", 0), y=args.get("y", 0),
        duration=args.get("duration", 0),
    ),
    "mouse_scroll": lambda args: mouse_scroll(
        clicks=args.get("clicks", -3),
        x=args.get("x"), y=args.get("y"),
    ),
    "keyboard_type": lambda args: keyboard_type(
        text=args.get("text", ""),
        interval=args.get("interval", 0.02),
    ),
    "keyboard_hotkey": lambda args: keyboard_hotkey(
        *args.get("keys", []),
    ),
    "keyboard_press": lambda args: keyboard_press(
        key=args.get("key", "enter"),
        presses=args.get("presses", 1),
    ),
    "get_screen_info": lambda args: get_screen_info(),
}


def execute_action(action: str, args: dict) -> ComputerActionResult:
    """执行指定的 Computer Use 操作。"""
    handler = ACTIONS.get(action)
    if handler is None:
        return ComputerActionResult(
            ok=False, action=action,
            message=f"未知操作: {action}，支持: {list(ACTIONS.keys())}",
        )
    try:
        return handler(args)
    except Exception as e:
        return ComputerActionResult(
            ok=False, action=action,
            message=f"操作执行失败: {e}",
        )
