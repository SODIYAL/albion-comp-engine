#!/usr/bin/env python3
"""
Generate the dashboard as a single self-contained HTML file with the dataset
inlined (design doc §6.1: static SPA, no backend, scoring in the client).

    dashboard/_shell.html          markup + core CSS
    dashboard/_decision_layer.css decision-first surface CSS
    dashboard/_app.js              client (contains NO capability numbers)
    dashboard/_decision_layer.js  caller-first translation of engine output
    dashboard/_loadout.js          per-member gear + spell picks (display only)
    out/dataset-latest.json        the single source of truth
        │
        ▼
    dashboard/index.html
    docs/index.html

Inlining rather than fetching is deliberate: the page must work from file://
and inside a strict-CSP artifact host, neither of which can fetch a sibling
JSON file. The shell opens a complete HTML document; this builder appends the
scripts and closes it so development servers can safely inject reload code.

Usage:  py -3 pipeline/build_dashboard.py
"""
import base64, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
DASH = os.path.join(ROOT, "dashboard")
DATASET = os.path.join(HERE, "out", "dataset-latest.json")

# Role/effect glyphs drawn for the dashboard: flat geometric SVGs (2026-08-21
# neon reskin; the retired painterly *-96.png renders remain beside them).
# The builder embeds them as data URIs so the generated page keeps its
# file:// / strict-artifact-host guarantee; SVG stays crisp at every chip size.
SEMANTIC_ICON_FILES = {
    "tank": "tank.svg",
    "healer": "healer.svg",
    "melee": "melee.svg",
    "range": "range.svg",
    "support": "support.svg",
    "peel": "peel.svg",
    "cc": "cc.svg",
    "aoe": "aoe.svg",
    "st": "st.svg",
    "dps": "dps.svg",
}


def load_semantic_icons():
    icon_dir = os.path.join(DASH, "assets", "semantic-icons")
    icons = {}
    for key, filename in SEMANTIC_ICON_FILES.items():
        path = os.path.join(icon_dir, filename)
        if not os.path.exists(path):
            sys.exit(f"semantic icon missing: {path}")
        mime = "image/svg+xml" if filename.endswith(".svg") else "image/png"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        icons[key] = f"data:{mime};base64,{encoded}"
    return icons


def load_loadouts(weapons):
    """The builds index (pipeline/build_builds.py) — validated, provenance-
    carrying build variants keyed content -> weapon -> [variant], ordered by
    the §F selection criteria with canonical defaults flagged. Only weapons
    the dataset knows are inlined. Replaces the old direct meta_comps.yaml
    parse: production build data lives in data/, normalization is generated,
    and every variant carries its source, patch, approval and confidence."""
    path = os.path.join(HERE, "out", "builds_index.json")
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    by_content = {ct: {w: vs for w, vs in by_weapon.items() if w in weapons}
                  for ct, by_weapon in doc.get("by_content", {}).items()}
    covers = (doc.get("_meta") or {}).get("content_covers", {})
    return by_content, covers


def main():
    if not os.path.exists(DATASET):
        sys.exit("dataset missing — run: py -3 pipeline/build_dataset.py")

    with open(DATASET, encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(DASH, "_shell.html"), encoding="utf-8") as f:
        shell = f.read()
    # Decision-first UX is part of the REAL dashboard build on this branch,
    # not a preview page. It is deliberately a translation layer: scoring
    # remains entirely inside app_scoring.js / CompEngine.
    with open(os.path.join(DASH, "_decision_layer.css"), encoding="utf-8") as f:
        decision_css = f.read()
    with open(os.path.join(DASH, "_decision_layer.js"), encoding="utf-8") as f:
        decision_js = f.read()
    shell = shell.replace("</style>", decision_css + "\n</style>", 1)
    shell = shell.replace(
        '<main class="main">',
        '<main class="main">\n'
        '    <section class="decision-layer" id="decision-layer" '
        'aria-label="Composition diagnosis and best next pick"></section>',
        1,
    )
    # The scoring engine is app_scoring.js — the same file node runs in
    # tests/test_js_parity.py. _app.js contains rendering only.
    with open(os.path.join(HERE, "app_scoring.js"), encoding="utf-8") as f:
        scoring = f.read()
    # Loadout layer — inlined BEFORE _app.js, which calls into it.
    with open(os.path.join(DASH, "_loadout.js"), encoding="utf-8") as f:
        loadout_js = f.read()
    with open(os.path.join(DASH, "_app.js"), encoding="utf-8") as f:
        app = f.read()
    semantic_icons = load_semantic_icons()
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
    # Gear ability pools (parse_dumps gear_spells.json) — the equipment half
    # of the ability-detail view: actives/passives with display names.
    gear_spells_path = os.path.join(HERE, "out", "gear_spells.json")
    gear_spells = {}
    if os.path.exists(gear_spells_path):
        with open(gear_spells_path, encoding="utf-8") as f:
            raw_gs = json.load(f)
        gear_spells = {k: {"a": [[s, spell_name(s)] for s in v.get("actives", [])],
                           "p": [[s, spell_name(s)] for s in v.get("passives", [])]}
                       for k, v in raw_gs.items()}
    # Per-spell FACTS for the ability-detail view: the game's own resolved
    # description (BASE numbers — in-game values scale with item power and
    # that curve is not in the public dumps, which the UI says out loud),
    # cooldown/range/radius/cast time/max targets, and the typed effect list
    # from the structured effect layer (effect_catalogue.py).
    fx_path = os.path.join(HERE, "out", "effect_catalogue.json")
    spell_fx = {}
    if os.path.exists(fx_path):
        with open(fx_path, encoding="utf-8") as f:
            spell_fx = json.load(f).get("spell_effects", {})
    wanted_spells = {sid for k in spells for pool in spells[k].values()
                     for sid, _n in pool}
    wanted_spells |= {sid for g in gear_spells.values()
                      for pool in g.values() for sid, _n in pool}
    spell_facts = {}
    for sid in sorted(wanted_spells):
        s = spell_index.get(sid) or {}
        fx = []
        for e in spell_fx.get(sid, []):
            tgt = ",".join(e.get("targets") or e.get("dirs") or [])
            tag = f"{e.get('effect')}>{tgt}"
            if tag not in fx:
                fx.append(tag)
        entry = {"d": s.get("description") or ""}
        for src, dst in (("cooldown", "cd"), ("cast_range", "cr"),
                         ("casting_time", "ct"), ("radius", "r"),
                         ("max_targets", "mt")):
            if s.get(src) is not None:
                entry[dst] = s[src]
        if fx:
            entry["fx"] = fx
        spell_facts[sid] = entry
    # Gear catalogue (fetch_gear_lines.py) — the loadout half: head, armor,
    # shoes, cape, offhand, potion, food. Optional, and DISPLAY ONLY for now:
    # no gear capabilities are curated yet, so the engine still scores weapons
    # alone. Shipping the catalogue + art first is what lets the loadout UI be
    # built against real items instead of placeholders.
    gear_path = os.path.join(HERE, "out", "gear_lines.json")
    gear_all = {}
    if os.path.exists(gear_path):
        with open(gear_path, encoding="utf-8") as f:
            gear_all = json.load(f)
    loadouts, loadout_covers = load_loadouts(data["weapons"])
    # Catalog inclusion must NOT depend on icon availability (§A): the page
    # gets the full catalogue; loArt() falls back inlined icon -> hotlinked
    # render -> neutral empty tile, so an artless entry degrades gracefully
    # instead of silently vanishing from the picker.
    gear = gear_all
    # PAGE WEIGHT: embed weapon art only. Gear art is hotlinked from the render
    # service at display size instead, the same way spell icons and the
    # full-res dossier art already are. Gear is ~270 of the ~400 icons, so
    # embedding it cost ~1.1 MB for a picker most sessions never open. Weapons
    # stay embedded because they are on screen from the first paint and must
    # survive file:// and offline use.
    icons = {k: v for k, v in icons.items() if k in data["weapons"]}
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
           f"const SEMANTIC_ICONS = {js(semantic_icons)};\n"
           f"const TREES = {js(trees)};\n"
           f"const ITEMS = {js(items)};\n"
           f"const SPELLS = {js(spells)};\n"
           f"const SPELL_FACTS = {js(spell_facts)};\n"
           f"const GEAR_SPELLS = {js(gear_spells)};\n"
           f"const LOADOUTS = {js(loadouts)};\n"
           f"const LOADOUT_COVERS = {js(loadout_covers)};\n"
           f"const GEAR = {js(gear)};\n"
           # aliased, not re-embedded: the full item-stat payload is already
           # inside DATASET; a second copy cost ~190 KB of page weight (§A)
           f"const ITEM_STATS = DATASET.item_stats || {{}};\n"
           f"const USAGE = {js(usage)};\n"
           f"const PARITY_EXPECTED = {js(expected)};\n{loadout_js}\n{app}\n{decision_js}</script>\n"
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
