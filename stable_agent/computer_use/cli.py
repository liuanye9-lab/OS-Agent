"""Computer Use CLI — 供 Node.js 桥接调用。

用法:
    python -m stable_agent.computer_use.cli <action> [--args JSON]

示例:
    python -m stable_agent.computer_use.cli screenshot
    python -m stable_agent.computer_use.cli mouse_click --args '{"x":100,"y":200}'
    python -m stable_agent.computer_use.cli keyboard_type --args '{"text":"hello"}'
    python -m stable_agent.computer_use.cli get_screen_info

输出 JSON 到 stdout。
"""

import json
import sys
import time

from stable_agent.computer_use import execute_action, get_action_history


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": "Usage: python -m stable_agent.computer_use.cli <action> [--args JSON]",
            "available_actions": [
                "screenshot", "mouse_click", "mouse_move", "mouse_scroll",
                "keyboard_type", "keyboard_hotkey", "keyboard_press",
                "get_screen_info", "history",
            ],
        }))
        sys.exit(1)

    action = sys.argv[1]

    # 解析参数
    args = {}
    if "--args" in sys.argv:
        idx = sys.argv.index("--args")
        if idx + 1 < len(sys.argv):
            try:
                args = json.loads(sys.argv[idx + 1])
            except json.JSONDecodeError as e:
                print(json.dumps({"ok": False, "error": f"参数 JSON 解析失败: {e}"}))
                sys.exit(1)

    # 特殊: 获取历史
    if action == "history":
        limit = args.get("limit", 20)
        history = get_action_history(limit)
        print(json.dumps({"ok": True, "action": "history", "data": {"history": history, "count": len(history)}}))
        return

    # 执行操作
    result = execute_action(action, args)
    print(result.to_json())


if __name__ == "__main__":
    main()
