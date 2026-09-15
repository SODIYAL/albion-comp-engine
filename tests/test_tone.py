#!/usr/bin/env python3
"""Writing-conventions gate (CLAUDE.md "Writing conventions").

The repository is public. Every tracked text file — documents, comments,
docstrings, test names, YAML comments, the dashboard sources — reads as
plain instructions and rules: no attribution of a rule to a person, no
quoted conversation, no references to AI tools or review sessions.

Scanned: every tracked .md / .py / .js / .yaml / .yml / .ps1 / .html /
.txt file except generated pages, generated data, third-party source
records and test fixtures (EXCLUDED below). A line that must carry a
listed word (this file, a data field) ends with the marker `tone: allow`.

Script-style: exit 0 = clean.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
ALLOW = "tone: allow"
EXTS = (".md", ".py", ".js", ".yaml", ".yml", ".ps1", ".html", ".txt")
EXCLUDED = (
    "docs/",                 # generated pages
    "dashboard/index.html",  # generated page
    "dashboard/how-it-works.html",  # generated from _explainer.html
    "pipeline/out/",         # generated data
    "data/",                 # third-party source records, verbatim by design
    "pipeline/tests/fixtures/",
    "review/",
    "companion/",            # the C# sniffer: its own conventions
)
# (pattern, what it is). Word-bounded, case-insensitive.
FORBIDDEN = [
    (r"\bowner(?:'s|s)?\b", "attribution to a person"),                         # tone: allow
    (r"\brulings?\b|\bruled\b|\bre-?ruled\b", "'ruling': state the rule"),       # tone: allow
    (r"\bexpert(?:'s)? (?:ruling|pass|round|call|adjudicat\w+|sign-?off)\b",
     "attribution to a person"),                                                # tone: allow
    (r"\b(?:go ahead|good to go|sure on|you r\b|ok that seems|do what needs)",
     "chat phrase"),                                                            # tone: allow
    (r"\b(?:codex|chatgpt|gpt-?\d|openai|anthropic|llm)\b", "AI tool reference"),   # tone: allow
    (r"\bclaude\b(?!\.md)", "AI tool reference"),                                # tone: allow
    (r"\bblind (?:label|round)s?\b", "session vocabulary: say 'validation round'"),  # tone: allow
    (r"\bthe (?:harvest|d:) checkout\b", "machine vocabulary: say 'the harvest machine'"),  # tone: allow
]


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split("\n")
    for rel in out:
        rel = rel.strip()
        if not rel or not rel.lower().endswith(EXTS):
            continue
        if any(rel.startswith(x) or rel == x.rstrip("/") for x in EXCLUDED):
            continue
        yield rel


def scan():
    hits = []
    pats = [(re.compile(p, re.I), what) for p, what in FORBIDDEN]
    for rel in tracked_files():
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().split("\n")
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if ALLOW in line:
                continue
            for pat, what in pats:
                m = pat.search(line)
                if m:
                    hits.append((rel, i, what, line.strip()[:110]))
                    break
    return hits


def main():
    # a Windows console may not encode every character a doc line carries
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    hits = scan()
    by_file = {}
    for rel, i, what, text in hits:
        by_file.setdefault(rel, []).append((i, what, text))
    for rel in sorted(by_file):
        rows = by_file[rel]
        print(f"{rel}: {len(rows)} line(s)")
        for i, what, text in rows[:5]:
            print(f"  {i}: [{what}] {text}")
        if len(rows) > 5:
            print(f"  ... {len(rows) - 5} more")
    if hits:
        print(f"\nFAIL: {len(hits)} line(s) in {len(by_file)} file(s) break the "
              "writing conventions (CLAUDE.md)")
        sys.exit(1)
    print("PASS: writing conventions hold on every tracked text file")
    sys.exit(0)


if __name__ == "__main__":
    main()
