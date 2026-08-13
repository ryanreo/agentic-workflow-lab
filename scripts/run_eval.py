"""Run the full eval suite and produce an HTML report.

Usage:
    python scripts/run_eval.py                    # offline mock LLM
    python scripts/run_eval.py openai             # OpenAI-compatible API
    python scripts/run_eval.py deepseek           # DeepSeek API
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eval.harness import run_tasks
from eval.reporting import build_report


def main():
    llm_kind = sys.argv[1] if len(sys.argv) > 1 else "mock"
    summary = run_tasks(llm_kind=llm_kind)
    report_path = os.path.join(summary["results_dir"], "report.html")
    build_report(summary, report_path)

    print(f"\n=== EVAL SUMMARY ({llm_kind} backend) ===")
    for row in summary["results"]:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"  [{status}] {row['id']:<28} {row['iterations']:>3} steps "
              f"({row['duration_s']}s)")
    print(f"\n{summary['passed']}/{summary['total']} tasks passed")
    print(f"Results:   {os.path.join(summary['results_dir'], 'summary.json')}")
    print(f"Report:    {report_path}")


if __name__ == "__main__":
    main()
