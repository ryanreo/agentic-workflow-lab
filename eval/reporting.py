"""Render traces and eval results as self-contained HTML."""

import html
import json
import os


def _esc(value):
    return html.escape(str(value))


def step_html(step):
    iteration = step["iteration"]
    action = _esc(step["action"])
    args = _esc(json.dumps(step["args"]))
    thought = _esc(step["thought"])
    observation = _esc(step.get("observation") or "")
    verifier = _esc(step.get("verifier") or "")
    done = step.get("done")
    is_finish = action == "finish"

    kind = "finish" if is_finish else "action"
    if done:
        kind += " verified"
    parts = [f'<div class="step {kind}">']
    parts.append(f'<div class="step-head"><span class="iter">#{iteration}</span>'
                 f'<span class="action-name">{action}</span>'
                 f'<code class="args">{args}</code></div>')
    if thought:
        parts.append(f'<div class="thought">&ldquo;{thought}&rdquo;</div>')
    if observation:
        parts.append(f'<div class="obs">{observation}</div>')
    if verifier:
        tone = "ok" if done else "warn"
        parts.append(f'<div class="verify {tone}">VERIFY: {verifier}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def trace_html(trace):
    steps = "\n".join(step_html(s) for s in trace.get("steps", []))
    return f'<div class="trace">{steps}</div>'


def trace_card_html(trace, trace_path):
    outcome = trace.get("outcome", "unknown")
    badge = ("pass" if outcome == "success" else "fail")
    header = (
        f'<div class="card-header">'
        f'<span class="task-id">{_esc(trace_path)}</span>'
        f'<span class="badge {badge}">{outcome}</span>'
        f'<span class="meta">{trace.get("iterations", 0)} steps · '
        f'{trace.get("duration_s", 0)}s</span>'
        f'</div>')
    summary = trace.get("summary", "")
    if summary:
        header += f'<div class="summary-text">{_esc(summary)}</div>'
    return header + trace_html(trace)


def build_report(summary, out_path):
    rows = summary.get("results", [])
    cards = []
    for row in rows:
        trace_path = os.path.join(summary["results_dir"], "traces",
                                  f"{row['id']}.json")
        try:
            with open(trace_path, encoding="utf-8") as fh:
                trace = json.load(fh)
            cards.append(
                f'<h2>{_esc(row["id"])} '
                f'<small>({_esc(row["agent"])})</small></h2>' +
                trace_card_html(trace, f"{row['id']}.json"))
        except FileNotFoundError:
            cards.append(
                f'<h2>{_esc(row["id"])}</h2>'
                f'<p class="error">trace file missing: {_esc(trace_path)}</p>')

    rate = summary["passed"] / summary["total"] if summary["total"] else 0
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Agentic Workflows - Eval Report</title>
<style>
body {{ font-family: system-ui, 'Segoe UI', sans-serif; max-width: 980px;
       margin: 32px auto; padding: 0 16px; color: #1c2430; background: #f7f8fa; }}
h1 {{ font-size: 24px; }}
h2 {{ font-size: 18px; margin: 28px 0 10px; }}
small {{ color: #6b7280; font-weight: normal; }}
.hero {{ background: #fff; border: 1px solid #e2e6ee; border-radius: 10px;
        padding: 18px 22px; margin-bottom: 22px; }}
.stats {{ display: flex; gap: 28px; margin-top: 8px; flex-wrap: wrap; }}
.stat .num {{ font-size: 26px; font-weight: 700; }}
.stat .label {{ color: #6b7280; font-size: 13px; }}
.step {{ border: 1px solid #e2e6ee; border-left: 5px solid #4a6cf7;
        border-radius: 8px; padding: 10px 14px; margin: 10px 0;
        background: #fff; }}
.step.finish {{ border-left-color: #8b5cf6; }}
.step.verified {{ border-left-color: #16a34a; }}
.step-head {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }}
.iter {{ font-size: 12px; font-weight: 700; color: #6b7280; }}
.action-name {{ font-weight: 600; color: #1d4ed8; }}
.args {{ font-size: 12px; color: #475569; background: #f1f5f9;
        padding: 2px 7px; border-radius: 5px; }}
.thought {{ font-style: italic; color: #475569; margin: 6px 0 4px; }}
.obs {{ background: #f3f4f6; border-radius: 6px; padding: 8px 10px;
       font-family: ui-monospace, Consolas, monospace; font-size: 12.5px;
       white-space: pre-wrap; margin-top: 6px; }}
.verify {{ margin-top: 7px; padding: 5px 9px; border-radius: 6px;
          font-size: 13px; }}
.verify.ok {{ background: #ecfdf5; color: #047857; }}
.verify.warn {{ background: #fffbeb; color: #b45309; }}
.badge {{ padding: 3px 10px; border-radius: 999px; font-size: 12px;
         font-weight: 600; text-transform: capitalize; }}
.badge.pass {{ background: #dcfce7; color: #15803d; }}
.badge.fail {{ background: #fee2e2; color: #b91c1c; }}
.meta {{ color: #6b7280; font-size: 13px; margin-left: auto; }}
.summary-text {{ color: #374151; margin: 8px 0 4px; }}
.error {{ color: #b91c1c; }}
</style>
</head>
<body>
<h1>Agentic Workflows - Eval Report</h1>
<div class="hero">
  <div class="stats">
    <div class="stat"><div class="num">{summary['passed']}/{summary['total']}</div>
      <div class="label">tasks passed</div></div>
    <div class="stat"><div class="num">{rate:.0%}</div>
      <div class="label">pass rate</div></div>
    <div class="stat"><div class="num">{_esc(summary['llm'])}</div>
      <div class="label">LLM backend</div></div>
  </div>
</div>
{''.join(cards)}
</body>
</html>"""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out_path


def render_single(trace, out_path):
    """Render one trace dict to a standalone HTML file."""
    title = f"{trace.get('agent')} - {trace.get('run_id')} - {trace.get('outcome')}"
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
body {{ font-family: system-ui, 'Segoe UI', sans-serif; max-width: 860px;
       margin: 32px auto; padding: 0 16px; color: #1c2430; background: #f7f8fa; }}
h1 {{ font-size: 20px; }}
.meta {{ color: #6b7280; margin-bottom: 18px; }}
.step {{ border: 1px solid #e2e6ee; border-left: 5px solid #4a6cf7;
        border-radius: 8px; padding: 10px 14px; margin: 10px 0;
        background: #fff; }}
.step.finish {{ border-left-color: #8b5cf6; }}
.step.verified {{ border-left-color: #16a34a; }}
.step-head {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }}
.iter {{ font-size: 12px; font-weight: 700; color: #6b7280; }}
.action-name {{ font-weight: 600; color: #1d4ed8; }}
.args {{ font-size: 12px; color: #475569; background: #f1f5f9;
        padding: 2px 7px; border-radius: 5px; }}
.thought {{ font-style: italic; color: #475569; margin: 6px 0 4px; }}
.obs {{ background: #f3f4f6; border-radius: 6px; padding: 8px 10px;
       font-family: ui-monospace, Consolas, monospace; font-size: 12.5px;
       white-space: pre-wrap; margin-top: 6px; }}
.verify {{ margin-top: 7px; padding: 5px 9px; border-radius: 6px;
          font-size: 13px; }}
.verify.ok {{ background: #ecfdf5; color: #047857; }}
.verify.warn {{ background: #fffbeb; color: #b45309; }}
.badge {{ padding: 3px 10px; border-radius: 999px; font-size: 12px;
         font-weight: 600; text-transform: capitalize; }}
.badge.pass {{ background: #dcfce7; color: #15803d; }}
.badge.fail {{ background: #fee2e2; color: #b91c1c; }}
</style>
</head>
<body>
<h1>{_esc(trace.get('agent'))} <span class="badge {'pass' if trace.get('outcome') == 'success' else 'fail'}">{_esc(trace.get('outcome'))}</span></h1>
<div class="meta">run {_esc(trace.get('run_id'))} · {trace.get('iterations', 0)} steps · {trace.get('duration_s', 0)}s</div>
<div class="summary-text">{_esc(trace.get('summary', ''))}</div>
{trace_html(trace)}
</body>
</html>"""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out_path
