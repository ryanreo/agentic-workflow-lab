"""Agent #1: pipeline doctor.

Given a repository whose test suite is failing, the agent:
  1. runs the tests and observes the failure,
  2. reads the failing code, plans a fix and writes it,
  3. re-runs the tests,
  4. loops until the suite is green (or gives up after a budget).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

from core.agent import Agent
from core.llm import MockLLM
from core.tools import Tool, ToolRegistry

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
SYSTEM_PROMPT = (
    "You are a senior reliability engineer. A repository's test suite is "
    "failing. Find the root cause, fix the code, and keep re-running the "
    "tests until everything passes. Do not claim success until the suite is "
    "green."
)


def _resolve(task, key, default):
    value = task.get(key) or default
    if not os.path.isabs(value):
        value = os.path.join(ROOT, value)
    return os.path.abspath(value)


def make_tools():
    def run_tests(state, args):
        proc = subprocess.run(
            [sys.executable, "runner.py"], cwd=state["repo"],
            capture_output=True, text=True, timeout=60)
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            return "TESTS PASSED\n" + output
        return "TESTS FAILED\n" + output

    def read_file(state, args):
        with open(os.path.join(state["repo"], args["path"]),
                  encoding="utf-8") as fh:
            return fh.read()

    def write_file(state, args):
        path = os.path.join(state["repo"], args["path"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(args["content"])
        state["fixed"].append(args["path"])
        return f"wrote {args['path']}"

    def grep(state, args):
        matches = []
        for name in sorted(os.listdir(state["repo"])):
            if not name.endswith(".py"):
                continue
            for i, line in enumerate(
                    open(os.path.join(state["repo"], name),
                         encoding="utf-8"), 1):
                if args["pattern"] in line:
                    matches.append(f"{name}:{i}: {line.strip()}")
        return "\n".join(matches) or "no matches"

    def list_files(state, args):
        return "\n".join(sorted(os.listdir(state["repo"])))

    return ToolRegistry([
        Tool("run_tests",
             "Run the repository test suite. Returns TESTS PASSED or "
             "TESTS FAILED with failure details.",
             run_tests),
        Tool("read_file",
             "Read a file from the repository.",
             read_file, {"path": "relative path in the repo"}),
        Tool("write_file",
             "Write a file in the repository.",
             write_file, {"path": "relative path in the repo",
                          "content": "full new file content"}),
        Tool("grep",
             "Search repository files for a pattern.",
             grep, {"pattern": "text to search for"}),
        Tool("list_files",
             "List files in the repository root.",
             list_files),
    ])


def verifier(task, state, history):
    """Truthful self-check: re-run the tests and inspect the result."""
    proc = subprocess.run(
        [sys.executable, "runner.py"], cwd=state["repo"],
        capture_output=True, text=True, timeout=60)
    if proc.returncode == 0:
        return True, "self-check: test suite passes"
    output = (proc.stdout or "") + (proc.stderr or "")
    failures = [ln for ln in output.splitlines() if ln.startswith("FAIL:")]
    detail = failures[0] if failures else "unknown failure"
    return False, f"self-check: tests still failing -> {detail}"


FIXME_RE = re.compile(
    r"^(?P<indent>\s*)(?P<target>\w+\s*=\s*).*?# FIXME: set to (?P<value>.*?)\s*$"
)


def mock_policy(task, state, history, feedback):
    """Demo brain: find the first planted bug, fix it, re-run tests."""
    if history and history[-1]["observation"].startswith("TESTS PASSED"):
        return {
            "thought": "The suite is green - all checks pass now.",
            "action": "finish",
            "args": {"summary": "Fixed the failing checks and verified the "
                                "suite is green."},
        }
    repo = state["repo"]
    for name in sorted(os.listdir(repo)):
        if not name.endswith(".py") or name == "runner.py":
            continue
        lines = open(os.path.join(repo, name), encoding="utf-8") \
            .read().splitlines()
        for i, line in enumerate(lines):
            match = FIXME_RE.match(line)
            if match:
                new_lines = list(lines)
                new_lines[i] = (
                    f"{match.group('indent')}{match.group('target')}"
                    f"{match.group('value')}  # fixed"
                )
                return {
                    "thought": f"Tests failed; found the bug in {name}:{i + 1} "
                               f"and corrected it to {match.group('value')}.",
                    "action": "write_file",
                    "args": {"path": name, "content": "\n".join(new_lines)},
                }
    return {"thought": "No obvious bug marker; reading the code to diagnose.",
            "action": "read_file", "args": {"path": "pipeline.py"}}


def build_mock_llm():
    return MockLLM(mock_policy)


def build_agent(llm, max_iterations=12):
    def state_factory(task):
        source = _resolve(task, "repo",
                          os.path.join("agents", "pipeline_doctor",
                                       "sample_repo"))
        workdir = tempfile.mkdtemp(prefix="workflowww-pipeline-")
        for name in os.listdir(source):
            path = os.path.join(source, name)
            if os.path.isfile(path):
                shutil.copy2(path, os.path.join(workdir, name))
        return {"repo": workdir, "fixed": []}

    def teardown(state):
        repo = state.get("repo")
        if repo and os.path.isdir(repo) and \
                os.path.basename(repo).startswith("workflowww-pipeline-"):
            shutil.rmtree(repo, ignore_errors=True)

    return Agent("pipeline_doctor", make_tools(), verifier, llm,
                 max_iterations=max_iterations,
                 system_prompt=SYSTEM_PROMPT,
                 state_factory=state_factory,
                 teardown=teardown)
