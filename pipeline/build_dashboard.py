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
    dashboard/how-it-works.html

Inlining rather than fetching is deliberate: the page must work from file://
and inside a strict-CSP artifact host, neither of which can fetch a sibling
JSON file. The shell opens a complete HTML document; this builder appends the
scripts and closes it so development servers can safely inject reload code.

Usage:  py -3 pipeline/build_dashboard.py
"""
import json, os, re, sys

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
DASH = os.path.join(ROOT, "dashboard")
DATASET = os.path.join(HERE, "out", "dataset-latest.json")


def load_loadouts(weapons):
    """Caller-provided skill loadouts from tests/meta_comps.yaml (the 'skills'
    columns, e.g. Timothy's blap sheet). Keyed content -> weapon -> variants.
    Only real caller data ever lands here — never invented."""
    path = os.path.join(ROOT, "tests", "meta_comps.yaml")
    if yaml is None or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        comps = (yaml.safe_load(f) or {}).get("comps", [])
    out = {}
    for comp in comps:
        content = comp.get("content")
        m = re.search(r'"([^"]+)"', comp.get("source", ""))
        caller = m.group(1) if m else comp.get("id", "caller")
        for party in comp.get("parties", []):
            for slot in party.get("slots", []):
                sk = slot.get("skills")
                if not sk or not slot.get("weapons"):
                    continue
                mm = re.search(r"q(\d+)\D+w(\d+)\D+p(\d+)", sk, re.I)
                if not mm:
                    continue
                w = slot["weapons"][0]
                if w not in weapons:
                    continue
                variant = {"q": int(mm.group(1)), "w": int(mm.group(2)),
                           "p": int(mm.group(3)),
                           "role": slot.get("role_raw") or slot.get("role") or "",
                           "caller": caller}
                bucket = out.setdefault(content, {}).setdefault(w, [])
                if variant not in bucket:
                    bucket.append(variant)
    return out


def main():
    if not os.path.exists(DATASET):
        sys.exit("dataset missing — run: py -3 pipeline/build_dataset.py")

    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(DASH, "_shell.html"), encoding="utf-8") as f:
        shell = f.read()
    # The scoring engine is app_scoring.js — the same file node runs in
    # tests/test_js_parity.py. _app.js contains rendering only.
    with open(os.path.join(HERE, "app_scoring.js"), encoding="utf-8") as f:
        scoring = f.read()
    with open(os.path.join(DASH, "_app.js"), encoding="utf-8") as f:
        app = f.read()
    # Item icons (fetch_icons.py). Optional: the page renders placeholders
    # for any weapon missing from the manifest.
    icons_path = os.path.join(HERE, "out", "icon_data.json")
    icons = {}
    if os.path.exists(icons_path):
        with open(icons_path, encoding="utf-8") as f:
            icons = json.load(f)
    # Weapon tree (subcategory) per weapon — powers the tree filter.
    with open(os.path.join(HERE, "out", "weapon_lines.json"), encoding="utf-8") as f:
        lines = json.load(f)
    trees = {k: (lines.get(k) or {}).get("subcategory", "other")
             for k in data["weapons"]}
    # Render-service item ids (T4_2H_MACE …) — the dossier hot-loads the
    # full-resolution render at runtime when online, falling back to the
    # small inlined icon offline.
    items = {k: (lines.get(k) or {}).get("example_item")
             for k in data["weapons"]
             if (lines.get(k) or {}).get("example_item")}
    # Spell pools with display names — powers the weapon detail drawer and
    # resolves caller loadout indices (q3 = 3rd Q option, game-data order).
    with open(os.path.join(HERE, "out", "spell_index.json"), encoding="utf-8") as f:
        spell_index = json.load(f)

    def spell_name(sid):
        return (spell_index.get(sid) or {}).get("name") or sid

    spells = {}
    for k in data["weapons"]:
        sp = (lines.get(k) or {}).get("spells") or {}
        spells[k] = {slot: [[sid, spell_name(sid)] for sid in sp.get(slot, [])]
                     for slot in ("q", "w", "e", "passive")}
    loadouts = load_loadouts(data["weapons"])
    # Real-usage sample (sample_battles.py). Optional; display evidence only.
    usage_path = os.path.join(HERE, "out", "weapon_usage_v2.json")
    usage = {}
    if os.path.exists(usage_path):
        with open(usage_path, encoding="utf-8") as f:
            usage = json.load(f)
        # The usage sample is filtered against the dataset at GENERATION
        # time, but the dataset can move on (weapon renames) while the
        # sample file sits still — inline only keys the page can render.
        if isinstance(usage.get("buckets"), dict):
            usage["buckets"] = {b: {w: n for w, n in m.items()
                                    if w in data["weapons"]}
                                for b, m in usage["buckets"].items()}

    # Parity fixture: run the Python engine over the dashboard's seed party and
    # inline its output, so the client asserts against the real engine on every
    # build instead of a hardcoded expectation that goes stale after curation.
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    from engine import Engine  # noqa: E402
    eng = Engine()
    seed = [w for w in ("2H_LONGBOW", "MAIN_ARCANESTAFF_UNDEAD", "2H_ICECRYSTAL_UNDEAD")
            if w in eng.weapons]
    expected = {
        # The fixture carries its own party + context: the client seeds and
        # re-scores exactly this, so the two can never drift apart (three
        # hardcoded copies of the seed used to have to agree by eyeball).
        "party": seed,
        "content": eng.content,
        "size": eng.size,
        # full precision — the client compares fitness with a 1e-9 tolerance
        # like the test suite. Rounding both sides to 2 decimals looked safe
        # but Python round() (half-even) vs toFixed (half-up) can disagree on
        # exact ties and raise a false "do not trust" banner.
        "fitness": eng.fitness(seed),
        "recs": [r["weapon"] for r in eng.recommend(seed, 4)],
        "weaknesses": [w["cap"] for w in eng.weaknesses(seed)],
    }

    # `</script>` inside a JSON string would close the tag early; escape it.
    # (Escaping happens outside the f-string: expression-part backslashes
    # need Python 3.12+, and this must build on 3.11 too.)
    def js(obj):
        return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")

    blob = js(data)

    out = (f"{shell}<script>\n{scoring}\n</script>\n"
           f"<script>\nconst DATASET = {blob};\n"
           f"const ICONS = {js(icons)};\n"
           f"const TREES = {js(trees)};\n"
           f"const ITEMS = {js(items)};\n"
           f"const SPELLS = {js(spells)};\n"
           f"const LOADOUTS = {js(loadouts)};\n"
           f"const USAGE = {js(usage)};\n"
           f"const PARITY_EXPECTED = {js(expected)};\n{app}</script>\n"
           f"</body>\n</html>\n")
    path = os.path.join(DASH, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    # The explainer is authored as a separate, self-contained source page so
    # the generated dashboard and GitHub Pages copies cannot drift apart.
    explainer_src = os.path.join(DASH, "_explainer.html")
    with open(explainer_src, encoding="utf-8") as f:
        explainer = f.read()
    explainer_path = os.path.join(DASH, "how-it-works.html")
    with open(explainer_path, "w", encoding="utf-8") as f:
        f.write(explainer)
    # GitHub Pages copy (Settings -> Pages -> main /docs): byte-for-byte the
    # same complete standards-mode document as the dashboard build.
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    with open(os.path.join(docs, "how-it-works.html"), "w", encoding="utf-8") as f:
        f.write(explainer)
    open(os.path.join(docs, ".nojekyll"), "w").close()

    m = data["_meta"]
    print(f"wrote dashboard/index.html  ({len(out)/1024:.0f} KB)")
    print(f"wrote dashboard/how-it-works.html  ({len(explainer)/1024:.0f} KB)")
    print(f"  dataset v{m['version']}: {m['weapons_curated']} curated / "
          f"{m['weapons_illustrative']} illustrative, release_clean={m['release_clean']}")
    if not m["release_clean"]:
        print("  NOTE: dashboard is showing placeholder data for illustrative weapons.")


if __name__ == "__main__":
    main()
