"""Run a single agent on its demo task and show the full trace.

Usage:
    python scripts/run_demo.py pipeline_doctor
    python scripts/run_demo.py document_extractor
    python scripts/run_demo.py deep_researcher
    python scripts/run_demo.py qa_agent
    python scripts/run_demo.py qa_agent deepseek
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eval.harness import build_agent
from eval.reporting import render_single

DEMO_TASKS = {
    "pipeline_doctor": {
        "repo": "agents/pipeline_doctor/sample_repo",
    },
    "document_extractor": {
        "docs": "agents/document_extractor/sample_docs",
    },
    "deep_researcher": {
        "question": "Write a report about the company: founding year, what "
                    "it does, and 2025 revenue.",
        "corpus": "agents/deep_researcher/corpus",
        "must_contain": ["2019", "logistics", "12M"],
        "focus_terms": ["founded", "2019", "logistics", "revenue"],
    },
    "qa_agent": {
        "scenarios": "agents/qa_agent/scenarios.json",
        "app": "agents/qa_agent/sample_app",
    },
}


def print_trace(trace):
    print("\n=== TRACE ===")
    for step in trace.steps:
        print(f"\n[{step.iteration}] THOUGHT: {step.thought}")
        print(f"    ACTION: {step.action} {json.dumps(step.args)}")
        if step.observation:
            preview = step.observation
            if len(preview) > 300:
                preview = preview[:300] + "..."
            print(f"    OBS: {preview}")
        if step.verifier:
            print(f"    VERIFY: {step.verifier}")


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "pipeline_doctor"
    if name not in DEMO_TASKS:
        print(f"Unknown agent '{name}'. Choose from: "
              f"{', '.join(DEMO_TASKS)}")
        sys.exit(1)
    llm_kind = sys.argv[2] if len(sys.argv) > 2 else "mock"
    agent = build_agent(name, llm_kind)
    trace = agent.run(DEMO_TASKS[name])
    print_trace(trace)
    print(f"\nOUTCOME: {trace.outcome}")
    print(f"SUMMARY: {trace.summary}")

    traces_dir = os.path.join(ROOT, "traces")
    os.makedirs(traces_dir, exist_ok=True)
    trace_path = os.path.join(traces_dir, f"{name}-{trace.run_id}.json")
    html_path = os.path.join(traces_dir, f"{name}-{trace.run_id}.html")
    trace.save(trace_path)
    render_single(trace.to_dict(), html_path)
    print(f"\nTrace JSON: {trace_path}")
    print(f"Trace HTML: {html_path}")


if __name__ == "__main__":
    main()
