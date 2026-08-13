"""Generate embed-friendly standalone pages for the workflow visuals.

These are the same visuals as visuals/*.html but without the outer
full-viewport shell, so they can sit inside an <iframe> on another site
(e.g. the portfolio homepage).
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = pathlib.Path(
    r"C:\Users\osage\.codex\plugins\cache\openai-bundled\visualize\1.0.20"
    r"\skills\visualize")
VISUALIZATIONS = pathlib.Path(
    r"C:\Users\osage\.codex\visualizations\2026\08\13"
    r"\019ffcf4-8701-7531-9ebd-9dbcdec83658")
FRAGMENT_PLACEHOLDER = "<!--__INLINE_VISUALIZATION_FRAGMENT__-->"
NAMES = ["agentic-core-loop", "pipeline-doctor", "document-extractor",
         "deep-researcher", "qa-agent"]


def main():
    css = (SKILL / "assets" / "visualize.css").read_text(encoding="utf-8")
    kit = (SKILL / "assets" / "visualize.html").read_text(encoding="utf-8")
    out_dir = ROOT / "visuals" / "embed"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        fragment = (VISUALIZATIONS / f"{name}.html").read_text(
            encoding="utf-8")
        inner = kit.replace(FRAGMENT_PLACEHOLDER, fragment)
        document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<style>{css}</style>
</head>
<body>{inner}</body>
</html>"""
        target = out_dir / f"{name}.html"
        target.write_text(document, encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
