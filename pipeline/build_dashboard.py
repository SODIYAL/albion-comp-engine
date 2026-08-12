#!/usr/bin/env python3
"""
Generate the dashboard as a single self-contained HTML file with the dataset
inlined (design doc §6.1: static SPA, no backend, scoring in the client).

    dashboard/_shell.html   markup + CSS
    dashboard/_app.js       client (contains NO capability numbers)
    out/dataset-latest.json the single source of truth
        │
        ▼
    dashboard/index.html

Inlining rather than fetching is deliberate: the page must work from file://
and inside a strict-CSP artifact host, neither of which can fetch a sibling
JSON file.

Usage:  py -3 pipeline/build_dashboard.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
DASH = os.path.join(ROOT, "dashboard")
DATASET = os.path.join(HERE, "out", "dataset-latest.json")


def main():
    if not os.path.exists(DATASET):
        sys.exit("dataset missing — run: py -3 pipeline/build_dataset.py")

    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(DASH, "_shell.html"), encoding="utf-8") as f:
        shell = f.read()
    with open(os.path.join(DASH, "_app.js"), encoding="utf-8") as f:
        app = f.read()

    # Parity fixture: run the Python engine over the dashboard's seed party and
    # inline its output, so the client asserts against the real engine on every
    # build instead of a hardcoded expectation that goes stale after curation.
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    from engine import Engine  # noqa: E402
    eng = Engine()
    seed = [w for w in ("2H_LONGBOW", "MAIN_ARCANESTAFF_UNDEAD", "2H_ICECRYSTAL_UNDEAD")
            if w in eng.weapons]
    expected = {
        "fitness": round(eng.fitness(seed), 2),
        "recs": [r["weapon"] for r in eng.recommend(seed, 4)],
        "weaknesses": [w["cap"] for w in eng.weaknesses(seed)],
    }

    # `</script>` inside a JSON string would close the tag early; escape it.
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

    out = (f"{shell}<script>\nconst DATASET = {blob};\n"
           f"const PARITY_EXPECTED = {json.dumps(expected)};\n{app}</script>\n")
    path = os.path.join(DASH, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)

    m = data["_meta"]
    print(f"wrote dashboard/index.html  ({len(out)/1024:.0f} KB)")
    print(f"  dataset v{m['version']}: {m['weapons_curated']} curated / "
          f"{m['weapons_illustrative']} illustrative, release_clean={m['release_clean']}")
    if not m["release_clean"]:
        print("  NOTE: dashboard is showing placeholder data for illustrative weapons.")


if __name__ == "__main__":
    main()
