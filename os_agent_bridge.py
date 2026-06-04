#!/usr/bin/env python3
"""OS-Agent Bridge: 被 Telegram bot 调用的 Python 子进程。
接收 JSON 输入（task_input, chat_id），
通过 OS-Agent 的 LLM client + 记忆系统处理后返回 JSON。
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from stable_agent.llm_factory import get_llm_client


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"ok": False, "error": "No input"}))
            return

        inp = json.loads(raw)
        task_input = inp.get("task_input", inp.get("message", ""))
        chat_id = inp.get("chat_id", "unknown")
        system_prompt = inp.get("system_prompt", "你是一个友好、有帮助的 AI 助手。请用简洁的中文回复。")

        if not task_input:
            print(json.dumps({"ok": False, "error": "Empty task_input"}))
            return

        start = time.time()

        # 使用 OS-Agent 的 LLM 客户端
        client = get_llm_client()
        result = client.complete(
            task_input,
            system_prompt=system_prompt,
        )

        elapsed = int((time.time() - start) * 1000)

        print(json.dumps({
            "ok": True,
            "text": result.get("text", ""),
            "model": result.get("model_name", ""),
            "tokens": {
                "input": result.get("input_tokens", 0),
                "output": result.get("output_tokens", 0),
            },
            "latency_ms": elapsed,
            "chat_id": chat_id,
        }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
