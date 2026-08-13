"""Run the agent eval suite and record results + traces."""

import importlib
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load_tasks(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "tasks.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["tasks"]


def build_agent(agent_name, llm_kind="mock"):
    module = importlib.import_module(f"agents.{agent_name}.agent")
    if llm_kind == "openai":
        from core.llm import OpenAIClient
        llm = OpenAIClient()
    elif llm_kind == "deepseek":
        from core.llm import DeepSeekClient
        llm = DeepSeekClient()
    else:
        llm = module.build_mock_llm()
    return module.build_agent(llm)


def run_tasks(tasks=None, llm_kind="mock", results_dir=None):
    tasks = tasks if tasks is not None else load_tasks()
    results_dir = results_dir or os.path.join(
        ROOT, "eval", "results", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(results_dir, exist_ok=True)
    traces_dir = os.path.join(results_dir, "traces")
    os.makedirs(traces_dir, exist_ok=True)

    rows = []
    for item in tasks:
        agent = build_agent(item["agent"], llm_kind)
        started = time.time()
        trace = agent.run(item["task"])
        elapsed = round(time.time() - started, 2)
        trace_path = os.path.join(traces_dir, f"{item['id']}.json")
        trace.save(trace_path)
        rows.append({
            "id": item["id"],
            "agent": item["agent"],
            "passed": trace.outcome == "success",
            "outcome": trace.outcome,
            "iterations": trace.iteration_count,
            "duration_s": elapsed,
            "summary": trace.summary,
            "trace_path": os.path.relpath(trace_path, ROOT),
        })

    summary = {
        "llm": llm_kind,
        "total": len(rows),
        "passed": sum(1 for r in rows if r["passed"]),
        "results": rows,
        "results_dir": results_dir,
    }
    with open(os.path.join(results_dir, "summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary
