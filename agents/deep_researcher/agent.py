"""Agent #3: deep researcher with a fact-check loop.

Decomposes a question, searches an offline corpus, drafts a report, then
verifies every claim against its sources - dropping or fixing anything it
cannot back up - until the report is fully supported.
"""

import json
import os
import re

from core.agent import Agent
from core.llm import MockLLM
from core.tools import Tool, ToolRegistry

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
SYSTEM_PROMPT = (
    "You are a meticulous research analyst. Decompose the question, search "
    "your sources, draft a report, then verify EVERY claim against the "
    "sources. Rewrite until no unsupported claims remain. Never invent facts."
)
STOP = {"the", "and", "was", "has", "had", "for", "with", "from", "into",
        "over", "what", "does", "its", "are", "is", "in", "on", "of", "to",
        "a", "an", "by", "at", "it", "as", "or", "about", "write"}


def _resolve(task, key, default):
    value = task.get(key) or default
    if not os.path.isabs(value):
        value = os.path.join(ROOT, value)
    return os.path.abspath(value)


def tokens(text):
    return [w.lower() for w in re.findall(r"\w+", text)
            if len(w) > 3 and w.lower() not in STOP]


def corpus_sentences(docs_dir):
    sentences = []
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(docs_dir, name), encoding="utf-8") as fh:
            text = fh.read()
        body = " ".join(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#"))
        for part in re.split(r"(?<=[.!?])\s+", body):
            sentence = part.strip().replace("\n", " ")
            if len(sentence) > 15:
                sentences.append({"source": name, "sentence": sentence})
    return sentences


def support(sentence, sentences):
    """True if every content word of the sentence appears in one source sentence."""
    words = tokens(sentence)
    if not words:
        return True, None
    for candidate in sentences:
        if all(w in candidate["sentence"].lower() for w in words):
            return True, candidate["source"]
    return False, words


def check_report(text, sentences):
    issues = []
    body = " ".join(
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#"))
    for part in re.split(r"(?<=[.!?])\s+", body):
        sentence = part.strip()
        if not sentence or len(sentence) < 15:
            continue
        ok, missing = support(sentence, sentences)
        if not ok:
            issues.append((sentence, missing))
    return issues


def make_tools():
    def search(state, args):
        query_tokens = set(tokens(args["query"]))
        if not query_tokens:
            return "no usable query terms"
        scored = []
        for item in corpus_sentences(state["docs_dir"]):
            hits = len(query_tokens & set(tokens(item["sentence"])))
            if hits:
                scored.append((hits, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return "\n".join(
            f"{item['source']}: {item['sentence']}"
            for _, item in scored[:5])

    def read_source(state, args):
        name = os.path.basename(args["path"])
        with open(os.path.join(state["docs_dir"], name),
                  encoding="utf-8") as fh:
            return fh.read()

    def write_report(state, args):
        path = state["output_path"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(args["content"])
        state["report_path"] = path
        words = len(args["content"].split())
        return f"report written to {path} ({words} words)"

    def verify_report(state, args):
        with open(state["report_path"], encoding="utf-8") as fh:
            text = fh.read()
        issues = check_report(text, corpus_sentences(state["docs_dir"]))
        if not issues:
            return "ALL CLAIMS VERIFIED"
        lines = ["UNSUPPORTED CLAIMS:"]
        for sentence, missing in issues:
            lines.append(f"- {sentence} (missing from sources: {missing})")
        return "\n".join(lines)

    return ToolRegistry([
        Tool("search",
             "Search the corpus and return the most relevant source sentences.",
             search, {"query": "search query"}),
        Tool("read_source",
             "Read a full source document.",
             read_source, {"path": "source filename (e.g. company.md)"}),
        Tool("write_report",
             "Write the research report to disk.",
             write_report, {"content": "full report text"}),
        Tool("verify_report",
             "Check every claim in the written report against the sources.",
             verify_report),
    ])


def verifier(task, state, history):
    path = state.get("report_path")
    if not path:
        return False, "self-check: no report has been written yet"
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    issues = check_report(text, corpus_sentences(state["docs_dir"]))
    if issues:
        return False, (f"self-check: {len(issues)} unsupported claim(s) in "
                       f"report, e.g. '{issues[0][0][:70]}...'")
    missing = [fact for fact in task.get("must_contain", [])
               if fact.lower() not in text.lower()]
    if missing:
        return False, f"self-check: report is missing required facts: {missing}"
    return True, "self-check: every claim verified against sources; all " \
                 "required facts present"


class ResearcherPolicy:
    """Demo brain: gather, draft (with a tempting unsupported summary),
    verify, and rewrite with only source-backed claims."""

    def __init__(self):
        self.sources = []

    def _focus_words(self, task):
        words = set(tokens(task.get("question", "")))
        for term in task.get("focus_terms", []):
            words.add(term.lower())
        return words

    def _sourced_sentences(self, task):
        docs_dir = _resolve(task, "corpus",
                            os.path.join("agents", "deep_researcher",
                                         "corpus"))
        focus = self._focus_words(task)
        picked = []
        for item in corpus_sentences(docs_dir):
            if len(focus & set(tokens(item["sentence"]))) >= 2:
                picked.append(item["sentence"])
        return picked

    def __call__(self, task, state, history, feedback):
        last = history[-1] if history else None
        if last and last["action"] == "verify_report" and \
                last["observation"].startswith("ALL CLAIMS VERIFIED"):
            return {"thought": "Every claim is backed by a source. Done.",
                    "action": "finish",
                    "args": {"summary": "Report written and fully verified "
                                        "against sources."}}
        if not history:
            return {"thought": "Decompose the question and search the corpus "
                               "for relevant sources.",
                    "action": "search", "args": {"query": task["question"]}}
        if last["action"] == "search":
            self.sources = []
            for line in last["observation"].splitlines():
                source = line.split(":", 1)[0].strip()
                if source and source not in self.sources:
                    self.sources.append(source)
            if not self.sources:
                return {"thought": "No results; broadening the query.",
                        "action": "search",
                        "args": {"query": task["question"]}}
            return {"thought": f"Reading sources: {', '.join(self.sources)}.",
                    "action": "read_source", "args": {"path": self.sources[0]}}
        if last["action"] == "read_source":
            index = self.sources.index(last["args"]["path"]) + 1
            if index < len(self.sources):
                return {"thought": "Continue reading the remaining sources.",
                        "action": "read_source",
                        "args": {"path": self.sources[index]}}
            summary = task.get(
                "mock_summary",
                "The company was founded in 2019, makes logistics software, "
                "and earned $12M in revenue in 2025.")
            extra = task.get(
                "mock_extra",
                "The company was founded in 2020 and has 500 employees.")
            draft = ("# Research Report\n\n" + summary + " " + extra + " " +
                     " ".join(self._sourced_sentences(task)))
            return {"thought": "Drafting the report from sources plus a "
                               "synthesized summary that needs checking.",
                    "action": "write_report", "args": {"content": draft}}
        if last["action"] == "write_report":
            return {"thought": "Verifying every claim in the draft against "
                               "the sources.",
                    "action": "verify_report", "args": {}}
        if last["action"] == "verify_report":
            return {"thought": "Some claims were not backed by a source; "
                               "rewriting using only source-backed sentences.",
                    "action": "write_report",
                    "args": {"content": "# Research Report\n\n" +
                                        " ".join(self._sourced_sentences(task))}}
        return {"thought": "Unexpected state; searching again.",
                "action": "search", "args": {"query": task["question"]}}


def build_mock_llm():
    return MockLLM(ResearcherPolicy())


def build_agent(llm, max_iterations=15):
    def state_factory(task):
        return {
            "docs_dir": _resolve(task, "corpus",
                                 os.path.join("agents", "deep_researcher",
                                              "corpus")),
            "output_path": _resolve(task, "output",
                                    os.path.join("agents", "deep_researcher",
                                                 "outputs", "report.md")),
            "report_path": None,
        }

    return Agent("deep_researcher", make_tools(), verifier, llm,
                 max_iterations=max_iterations,
                 system_prompt=SYSTEM_PROMPT,
                 state_factory=state_factory)
