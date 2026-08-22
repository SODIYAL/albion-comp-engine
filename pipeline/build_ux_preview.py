#!/usr/bin/env python3
"""Build a reviewable decision-first Comp Forge preview without changing scoring.

Run after the normal dashboard build:
    py -3 pipeline/build_dashboard.py
    py -3 pipeline/build_ux_preview.py

Writes dashboard/ux-preview.html and docs/ux-preview.html. The preview injects
one decision-layer host above the wheel stage, its CSS, and a post-app JS
adapter. Production index.html remains untouched until the UX is approved.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
DOCS = ROOT / "docs"


def inject(src: str) -> str:
    css = (DASH / "_decision_layer.css").read_text(encoding="utf-8")
    js = (DASH / "_decision_layer.js").read_text(encoding="utf-8")
    marker = '<main class="main">'
    host = '\n    <section class="decision-layer" id="decision-layer" aria-label="Composition decision summary"></section>'
    if marker not in src:
        raise SystemExit("dashboard shell marker not found")
    src = src.replace(marker, marker + host, 1)
    src = src.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    src = src.replace("</body>", f"<script>\n{js}\n</script>\n</body>", 1)
    return src


def main():
    built = DASH / "index.html"
    if not built.exists():
        raise SystemExit("dashboard/index.html missing; run build_dashboard.py first")
    out = inject(built.read_text(encoding="utf-8"))
    (DASH / "ux-preview.html").write_text(out, encoding="utf-8")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "ux-preview.html").write_text(out, encoding="utf-8")
    print("wrote dashboard/ux-preview.html and docs/ux-preview.html")


if __name__ == "__main__":
    main()
