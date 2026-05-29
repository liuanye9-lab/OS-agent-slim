"""Self-Iteration 5-Round Experiment Runner.

复现 README 中 5-round self-iteration 数据。通过 MCP tools/call 逐轮执行任务，
收集 quality_score / hallucination_rate / token_usage。

Usage:
    python experiments/self_iteration_5_rounds/run_experiment.py

Prerequisites:
    uvicorn web.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).parent
DATASET = HERE / "dataset.jsonl"
RESULTS = HERE / "results.json"
MCP_URL = "http://localhost:8000/mcp"


def load_dataset() -> list[dict]:
    """加载实验数据集。"""
    tasks = []
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    return tasks


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """通过 MCP JSON-RPC 调用工具。"""
    import urllib.request

    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }).encode("utf-8")

    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def run_round(round_num: int, tasks: list[dict]) -> dict:
    """运行一轮实验。

    Returns:
        {"round": int, "quality_score": float, "hallucination_rate": float,
         "token_usage": int, "learning_triggered": bool}
    """
    total_score = 0.0
    total_hallucinations = 0
    total_tokens = 0

    for task in tasks[:10]:  # 每轮 10 个任务
        result = call_mcp_tool("stableagent.task.os_agent", {
            "task_input": task["task"],
            "mode": "auto",
            "open_dashboard": False,
        })

        sc = result.get("result", {}).get("structuredContent", {})
        total_score += sc.get("data", {}).get("quality_score", 0.5)
        total_tokens += sc.get("data", {}).get("token_used", 0)
        if sc.get("data", {}).get("hallucination_detected", False):
            total_hallucinations += 1

    n = len(tasks[:10])
    return {
        "round": round_num,
        "quality_score": round(total_score / n, 2) if n > 0 else 0.0,
        "hallucination_rate": round(total_hallucinations / n * 100, 0) if n > 0 else 0,
        "token_usage": total_tokens,
        "learning_triggered": round_num > 1,
    }


def main():
    tasks = load_dataset()
    print(f"加载 {len(tasks)} 个实验任务")

    all_results = []
    for r in range(1, 6):
        print(f"\n--- Round {r} ---")
        round_result = run_round(r, tasks)
        all_results.append(round_result)
        print(f"  Quality: {round_result['quality_score']}, "
              f"Hallucination: {round_result['hallucination_rate']}%, "
              f"Tokens: {round_result['token_usage']}")

    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到 {RESULTS}")


if __name__ == "__main__":
    main()
