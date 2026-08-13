"""Agent #2: self-auditing document extractor.

Extracts structured fields from messy documents, validates arithmetic
consistency (line items vs total vs VAT), fixes what it got wrong, and loops
until every document validates cleanly.
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
    "You are a data extraction specialist. Extract structured fields from "
    "each document, then validate the numbers: line items must sum to the "
    "total, and VAT must equal total x rate. Fix any field that fails "
    "validation. Do not finish until every document passes validation."
)

ITEM_RE = re.compile(r"^- (.+?) - (\d+) x \$([\d.]+) = \$([\d.]+)$")
TOTAL_RE = re.compile(r"^Total: \$([\d.]+)$")
VAT_RE = re.compile(r"^VAT: (\d+)% -> \$([\d.]+)$")


def _resolve(task, key, default):
    value = task.get(key) or default
    if not os.path.isabs(value):
        value = os.path.join(ROOT, value)
    return os.path.abspath(value)


def parse_doc(text):
    doc = {"invoice": None, "customer": None, "line_items": [],
           "total": None, "vat_rate": None, "vat_amount": None}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Invoice "):
            doc["invoice"] = line.split()[1]
        elif line.startswith("Customer:"):
            doc["customer"] = line.split(":", 1)[1].strip()
        else:
            match = ITEM_RE.match(line)
            if match:
                doc["line_items"].append({
                    "name": match.group(1),
                    "qty": int(match.group(2)),
                    "unit_price": float(match.group(3)),
                    "line_total": float(match.group(4)),
                })
                continue
            match = TOTAL_RE.match(line)
            if match:
                doc["total"] = float(match.group(1))
                continue
            match = VAT_RE.match(line)
            if match:
                doc["vat_rate"] = int(match.group(1)) / 100.0
                doc["vat_amount"] = float(match.group(2))
    return doc


def validate_doc(extraction):
    errors = []
    total = round(sum(i["line_total"] for i in extraction["line_items"]), 2)
    if abs((extraction.get("total") or 0) - total) > 0.005:
        errors.append(
            f"- total mismatch: expected {total:.2f}, "
            f"got {extraction['total']:.2f}")
    vat = round(total * (extraction.get("vat_rate") or 0), 2)
    if abs((extraction.get("vat_amount") or 0) - vat) > 0.005:
        errors.append(
            f"- vat_amount mismatch: expected {vat:.2f}, "
            f"got {extraction['vat_amount']:.2f}")
    return errors


def make_tools():
    def list_docs(state, args):
        return "\n".join(
            sorted(f for f in os.listdir(state["docs_dir"])
                   if f.endswith(".txt")))

    def read_doc(state, args):
        with open(os.path.join(state["docs_dir"], args["name"]),
                  encoding="utf-8") as fh:
            return fh.read()

    def extract(state, args):
        with open(os.path.join(state["docs_dir"], args["name"]),
                  encoding="utf-8") as fh:
            state["extractions"][args["name"]] = parse_doc(fh.read())
        return json.dumps(state["extractions"][args["name"]], indent=2)

    def validate(state, args):
        errors = validate_doc(state["extractions"][args["name"]])
        if not errors:
            return f"VALIDATION CLEAN: {args['name']}"
        return f"VALIDATION: {args['name']}\n" + "\n".join(errors)

    def fix_field(state, args):
        extraction = state["extractions"][args["name"]]
        value = args["value"]
        try:
            value = float(value)
        except (TypeError, ValueError):
            pass
        extraction[args["field"]] = value
        return (f"fixed {args['name']}: {args['field']} = "
                f"{args['value']}")

    def show_extraction(state, args):
        return json.dumps(state["extractions"][args["name"]], indent=2)

    return ToolRegistry([
        Tool("list_docs", "List the documents available for processing.",
             list_docs),
        Tool("read_doc", "Read the raw text of a document.",
             read_doc, {"name": "document filename"}),
        Tool("extract", "Parse a document into structured fields.",
             extract, {"name": "document filename"}),
        Tool("validate",
             "Check a document's arithmetic consistency (items vs total vs VAT).",
             validate, {"name": "document filename"}),
        Tool("fix_field", "Correct a field in the extracted data.",
             fix_field, {"name": "document filename",
                         "field": "field name",
                         "value": "correct value"}),
        Tool("show_extraction", "Show the current extracted fields.",
             show_extraction, {"name": "document filename"}),
    ])


def verifier(task, state, history):
    docs_dir = state["docs_dir"]
    names = sorted(f for f in os.listdir(docs_dir) if f.endswith(".txt"))
    extractions = state.get("extractions", {})
    if set(extractions) != set(names):
        return False, ("self-check: not every document has been extracted "
                       f"({len(extractions)}/{len(names)})")
    errors = []
    for name in names:
        for err in validate_doc(extractions[name]):
            errors.append(f"{name} {err}")
    if errors:
        return False, "self-check: validation errors -> " + "; ".join(errors)
    return True, "self-check: all documents pass arithmetic validation"


class DocPolicy:
    """Demo brain: extract everything, then validate/fix document by document."""

    def __init__(self):
        self.pending_validates = []
        self.fix_queue = []
        self.current_doc = None

    def _names(self, task):
        docs_dir = _resolve(task, "docs",
                            os.path.join("agents", "document_extractor",
                                         "sample_docs"))
        return sorted(f for f in os.listdir(docs_dir) if f.endswith(".txt"))

    def __call__(self, task, state, history, feedback):
        names = self._names(task)
        if not history:
            return {"thought": "Start by listing the documents to process.",
                    "action": "list_docs", "args": {}}
        last = history[-1]

        if last["action"] == "list_docs":
            return {"thought": f"Found {len(names)} documents. Extract the "
                               "first one.",
                    "action": "extract", "args": {"name": names[0]}}

        extracted = [h for h in history if h["action"] == "extract"]
        if len(extracted) < len(names):
            return {"thought": "Continue extracting fields from every document.",
                    "action": "extract", "args": {"name": names[len(extracted)]}}

        if last["action"] == "extract" and not self.pending_validates:
            self.pending_validates = list(names)
            return {"thought": "Validate the arithmetic consistency of the "
                               "first document.",
                    "action": "validate", "args": {"name": names[0]}}

        if last["action"] == "validate":
            name = last["args"]["name"]
            if last["observation"].startswith("VALIDATION CLEAN"):
                self.pending_validates = [
                    n for n in self.pending_validates if n != name]
                if not self.pending_validates:
                    return {"thought": "Every document validates cleanly.",
                            "action": "finish",
                            "args": {"summary": "Extracted and validated all "
                                                "documents successfully."}}
                return {"thought": "This document is clean; check the next.",
                        "action": "validate",
                        "args": {"name": self.pending_validates[0]}}

            self.current_doc = name
            self.fix_queue = []
            for line in last["observation"].splitlines():
                match = re.match(
                    r"^- (total|vat_amount) mismatch: expected ([\d.]+),",
                    line.strip())
                if match:
                    self.fix_queue.append((match.group(1), match.group(2)))
            if self.fix_queue:
                field, value = self.fix_queue[0]
                return {"thought": f"{name} has an inconsistent {field}; "
                                   f"correcting it to {value}.",
                        "action": "fix_field",
                        "args": {"name": name, "field": field,
                                 "value": value}}

        if last["action"] == "fix_field":
            self.fix_queue = self.fix_queue[1:] if self.fix_queue else []
            if self.fix_queue:
                field, value = self.fix_queue[0]
                return {"thought": "More fields to correct; continuing.",
                        "action": "fix_field",
                        "args": {"name": self.current_doc, "field": field,
                                 "value": value}}
            return {"thought": "Corrections applied; re-validating this "
                               "document.",
                    "action": "validate", "args": {"name": self.current_doc}}

        return {"thought": "Re-checking current extraction state.",
                "action": "show_extraction", "args": {"name": names[0]}}


def build_mock_llm():
    return MockLLM(DocPolicy())


def build_agent(llm, max_iterations=20):
    def state_factory(task):
        return {
            "docs_dir": _resolve(task, "docs",
                                 os.path.join("agents", "document_extractor",
                                              "sample_docs")),
            "extractions": {},
        }

    return Agent("document_extractor", make_tools(), verifier, llm,
                 max_iterations=max_iterations,
                 system_prompt=SYSTEM_PROMPT,
                 state_factory=state_factory)
