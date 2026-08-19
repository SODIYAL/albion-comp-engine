#!/usr/bin/env python3
"""
Step 1 of the composition-engine pipeline (design doc §6.3).

Parses ao-bin-dumps game data into the compact, evidence-ready dataset the
engine and the evidence lint consume:

  out/weapon_lines.json   one entry per weapon line (MAIN_MACE, 2H_LONGBOW, ...):
                          localized name + full equippable spell list by slot
  out/spell_index.json    per spell: localized name/description, function tags
                          ([dmg]/[heal]/[cc]/[buff]/[debuff]/[mobility]),
                          keyword flags (purge/silence/stun/root/knockback/cleanse),
                          direction hints (enemy/ally/self), and structural
                          AREA GEOMETRY (radius/area/max_targets) extracted
                          from the spell-effect tree — the game-data half of
                          the ranged-AoE evidence model (changeschapter2.md §B)

Reads the PINNED snapshot (fetch_snapshot.py) by default; a positional
directory overrides it for local experiments, but then the provenance record
says "local-override" and the release check downstream fails closed.

Usage:  py -3 pipeline/parse_dumps.py [/path/to/ao-bin-dumps]
"""
import json, re, sys, os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provenance import record_derived, snapshot_commit, snapshot_dir  # noqa: E402

ADAPTER = "parse_dumps"
ADAPTER_VERSION = "2"

TAG_RE = re.compile(r"\[(dmg|heal|cc|debuff|buff|mobility|other)\]")

# keyword flags used by the evidence lint (capability-class consistency checks)
FLAG_PATTERNS = {
    "purge":     r"\bpurg|\bremoves?\b[^.]{0,40}\bbuffs?\b",
    "silence":   r"\bsilenc",
    "stun":      r"\bstun",
    "root":      r"\broot",
    # Must tolerate: "knocking back" (participle), "Knocks you back" (intervening
    # word), "knocked back by", and "Throws all enemies ... in the air". The
    # earlier pattern required knock(s|ed) immediately followed by "back", so it
    # silently missed the first two — which BLOCKS a curator from scoring a real
    # knockback_displace, since evidence_lint rule 3 requires the flag.
    "knockback": (r"\bknock\w*\s+(?:\w+\s+){0,2}(?:back|airborne|into the air)"
                  r"|\bknockback\b|\bpush(es|ed|ing)?\b|\bdisplac"
                  r"|\bthrow\w*\s+(?:\w+\s+){0,6}?in(?:to)? the air"),
    "cleanse":   r"\bremoves?\b[^.]{0,60}\b(debuffs?|crowd control)|\bcleans",
    # anti_zone: removing enemy-placed GROUND AREAS. Deliberately distinct from
    # `purge` (strips buffs off enemy units) and from `cleanse` (strips CC and
    # debuffs off allies) — same verb, three different mechanics.
    "area_removal": r"\b(removes?|destroys?|dispels?)\b[^.]{0,50}\b(ground[- ]based areas?|ground areas?|areas?)\b",
    "heal":      r"\bheal|\brestores?\b[^.]{0,20}\bhealth",
    "pull":      r"\bpulls?\b",
    "slow":      r"\bslow(s|ed)?\b",
    "shield":    r"\bshield|\bdamage taken\b|\bresistance",
    "pierce":    r"\bresistance reduction|\breduc\w+[^.]{0,30}\bresist|\barmor\b[^.]{0,20}\breduc|\b(decreas|reduc)\w*[^.]{0,40}\bdefense|\bdefense\b[^.]{0,25}\b(decreas|reduc)",
    "heal_reduction": r"\breduc\w+[^.]{0,30}\bhealing\b|\bhealing received\b[^.]{0,20}\breduc|\bhealing\s+(cast|done)\b[^.]{0,20}\breduc",
}

# ---------------------------------------------------------------- number resolution
# Spell descriptions ship with placeholders: "{0}" filled positionally from the
# spell's `locareferences`, plus inline "$path$" / "$$SPELL.path$" tags. Both
# point into the effect tree, e.g.
#     $$PULSINGHEAL_KNOCKBACK.knockback[0].distance$  ->  9
# Resolving them is what turns "knocked back by {4}" into "knocked back by 9",
# which is the difference between guessing a capability score and calibrating it.
#
# CAVEAT: these are BASE values. The in-game number a player sees is item-power
# scaled (the wiki quotes tier-specific figures like "12.58/13.82m"). Base values
# are the right thing for curation anyway — scoring compares spells to each
# other, and every spell is scaled by the same mechanism.
PATH_SEG = re.compile(r"([A-Za-z_]\w*)(?:\[(\d+)\])?$")
TAG_INLINE = re.compile(r"\$\$?([A-Za-z_][\w.\[\]]*)\$")

# Description tags address some nodes by a logical name that differs from the
# XML element name (e.g. "$channeling.effectinterval$" reads `channelingspell`).
NODE_ALIASES = {"channeling": "channelingspell"}


def fmt_num(v):
    try:
        f = abs(float(v))          # descriptions state magnitudes ("dealing {0} damage")
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


def resolve_path(registry, current, path):
    segs = path.split(".")
    node = current
    if segs and segs[0] in registry:
        node, segs = registry[segs[0]], segs[1:]
    if not segs:
        return None
    attr, segs = segs[-1], segs[:-1]
    for seg in segs:
        m = PATH_SEG.match(seg)
        if not m or not isinstance(node, dict):
            return None
        nxt = node.get(m.group(1))
        if nxt is None and m.group(1) in NODE_ALIASES:
            nxt = node.get(NODE_ALIASES[m.group(1)])
        node = nxt
        if isinstance(node, list):
            i = int(m.group(2) or 0)
            node = node[i] if i < len(node) else None
        elif m.group(2) and m.group(2) != "0":
            return None
    m = PATH_SEG.match(attr)
    if not m or not isinstance(node, dict):
        return None
    v = node.get("@" + m.group(1))
    return fmt_num(v) if v is not None else None


def resolve_description(desc, spell, registry):
    """Fill {N} positional placeholders, then any inline $tag$ references."""
    if not desc:
        return desc, 0, 0
    refs = ((spell.get("locareferences") or {}).get("description") or {}).get("locareference", [])
    refs = refs if isinstance(refs, list) else [refs]
    hits = misses = 0

    for i, ref in enumerate(refs):
        tag = (ref or {}).get("@tag", "")
        m = TAG_INLINE.fullmatch(tag.strip())
        val = resolve_path(registry, spell, m.group(1)) if m else None
        if val is None:
            misses += 1
            continue
        if "{%d}" % i in desc:
            desc = desc.replace("{%d}" % i, val)
            hits += 1

    def sub(m):
        nonlocal hits, misses
        val = resolve_path(registry, spell, m.group(1))
        if val is None:
            misses += 1
            return m.group(0)
        hits += 1
        return val

    return TAG_INLINE.sub(sub, desc), hits, misses


def load(path):
    # explicit encoding: the dumps are UTF-8, but Python on Windows defaults to
    # the ANSI codepage (cp1252) and dies on the first non-Latin-1 glyph
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------ area geometry
# Structural extraction of WHERE a spell's damage lands (changeschapter2.md
# §B): the spell tree carries the honest facts — `effectarearadius` on damage
# effects, and `spelleffectarea > area > shape > circle/rectangle` for ground
# zones and skillshots. Dimension values may be KEYFRAMED ("A 0:4;0.8:4;
# 0.81:0" = radius 4 collapsing at 0.81s); the maximum keyframe is the spell's
# real footprint. These are recorded facts for the evidence model, never a
# substitute for the curated AoE-damage judgement.

def kf_max(v):
    """'5' -> 5.0 ; 'A 0:4;0.8:4;0.81:0' -> 4.0 ; garbage -> None."""
    if v is None:
        return None
    s = str(v).strip()
    if s.startswith("A "):
        vals = []
        for part in s[2:].split(";"):
            bits = part.split(":")
            if len(bits) == 2:
                try:
                    vals.append(float(bits[1]))
                except ValueError:
                    pass
        return max(vals) if vals else None
    try:
        return float(s)
    except ValueError:
        return None


def spell_geometry(sid, registry, max_depth=8):
    """{radius, max_targets, area:[{kind,...}]} for a spell, following
    applyspell/spelleffectarea references through the full registry. `radius`
    is the largest damage/zone footprint found; None means the tree carries
    no structural area — 'unknown', never 'not AoE'."""
    best = {"radius": None, "max_targets": None}
    shapes = []
    visited = {sid}

    def bump_radius(r):
        if r is not None and r > 0 and (best["radius"] is None or r > best["radius"]):
            best["radius"] = r

    def bump_targets(t):
        t = kf_max(t)
        if t and (best["max_targets"] is None or t > best["max_targets"]):
            best["max_targets"] = int(t)

    def walk(key, node, depth):
        if depth > max_depth:
            return
        if isinstance(node, list):
            for item in node:
                walk(key, item, depth)
            return
        if not isinstance(node, dict):
            return
        # damage / effect nodes that state their own area
        r = kf_max(node.get("@effectarearadius"))
        if r and key not in ("dummy",):        # dummy = pure UI indicator
            bump_radius(r)
        if node.get("@maxeffectareatargets") is not None:
            bump_targets(node.get("@maxeffectareatargets"))
        # explicit shapes under spelleffectarea/spellindicationarea
        if key == "circle":
            r = kf_max(node.get("@radius"))
            if r:
                shapes.append({"kind": "circle", "radius": r})
                bump_radius(r)
        elif key == "rectangle":
            w, h = kf_max(node.get("@width")), kf_max(node.get("@height"))
            if w or h:
                shapes.append({"kind": "rect", "width": w, "length": h})
                bump_radius(max(x for x in (w, h) if x) / 2)
        elif key == "cone":
            r = kf_max(node.get("@radius"))
            if r:
                shapes.append({"kind": "cone", "radius": r,
                               "angle": kf_max(node.get("@angle"))})
                bump_radius(r)
        # follow references to sub-spells (HAIL -> applyspell HAIL_DAMAGE …)
        for ref_attr in ("@spell", "@effect"):
            ref = node.get(ref_attr)
            if (key in ("applyspell", "usespell", "spelleffectarea")
                    and isinstance(ref, str) and ref in registry
                    and ref not in visited):
                visited.add(ref)
                walk(None, registry[ref], depth + 1)
        for k, v in node.items():
            if not k.startswith("@"):
                walk(k, v, depth + 1)

    node = registry.get(sid)
    if node is not None:
        walk(None, node, 0)
    out = dict(best)
    if shapes:
        out["area"] = shapes[:4]
    return out

def en(tuv_list):
    for v in (tuv_list if isinstance(tuv_list, list) else [tuv_list]):
        if v.get("@xml:lang") == "EN-US":
            return v.get("seg", "")
    return ""

def line_key(unique_name):
    """T5_MAIN_MACE@2 -> MAIN_MACE ; T4_2H_DUALAXE_KEEPER -> 2H_DUALAXE_KEEPER"""
    base = unique_name.split("@")[0]
    return re.sub(r"^T\d+_", "", base)

def main(dump_dir, source_commit):
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)

    items = load(os.path.join(dump_dir, "items.json"))["items"]
    # Shapeshifter staves live under `transformationweapon`, not `weapon`. They
    # are ordinary equippable mainhand weapons in every way that matters here
    # (slottype/twohanded/craftingspelllist are identical in shape), and their
    # craftingspelllist @reference chains point at siblings in the same category,
    # so they must be merged BEFORE by_name is built or the refs dangle.
    # Omitting them hid the second-most-used weapon family in the usage sample.
    weapons_raw = items["weapon"] + items.get("transformationweapon", [])

    # ---- localized item names ------------------------------------------------
    formatted = load(os.path.join(dump_dir, "formatted", "items.json"))
    item_names = {}
    for it in formatted:
        u = it.get("UniqueName", "")
        n = (it.get("LocalizedNames") or {}).get("EN-US")
        if n:
            item_names[u] = n

    # ---- weapon lines: resolve craftingspelllist references ------------------
    by_name = {w["@uniquename"]: w for w in weapons_raw}

    def craftspells(w, depth=0):
        """A craftingspelllist can hold @reference (inherited line spells),
        removespell (inherited spells this weapon can't use), AND its own
        craftspell entries (typically the weapon's unique E) — merge all three."""
        csl = w.get("craftingspelllist")
        if not csl or depth > 3:
            return []
        result = []
        if "@reference" in csl:
            ref = by_name.get(csl["@reference"])
            if ref:
                result.extend(craftspells(ref, depth + 1))
        removed = csl.get("removespell", [])
        removed = removed if isinstance(removed, list) else [removed]
        removed_ids = {r.get("@uniquename") for r in removed}
        result = [c for c in result if c.get("@uniquename") not in removed_ids]
        own = csl.get("craftspell", [])
        own = own if isinstance(own, list) else [own]
        result.extend(own)
        return result

    lines = {}
    for w in weapons_raw:
        u = w["@uniquename"]
        if "@" in u or w.get("@slottype") not in ("mainhand", "2h"):
            continue
        key = line_key(u)
        cs = craftspells(w)
        if not cs:
            continue
        # canonical entry = the tier with the LARGEST resolved spell list
        # (low tiers have spells locked/removed; T4+ carries the full kit)
        if key in lines and lines[key]["_nspells"] >= len(cs):
            continue
        slots = defaultdict(list)
        for c in cs:
            sid = c.get("@uniquename")
            slot = c.get("@slots")
            bucket = {"1": "q", "2": "w", "3": "e"}.get(slot, "passive")
            slots[bucket].append(sid)
        lines[key] = {
            "_nspells": len(cs),
            "example_item": u,
            "name": item_names.get(u, key),
            "subcategory": w.get("@shopsubcategory1"),
            "two_handed": w.get("@twohanded") == "true",
            "spells": {k: slots.get(k, []) for k in ("q", "w", "e", "passive")},
        }

    # ---- spell metadata ------------------------------------------------------
    spells_root = load(os.path.join(dump_dir, "spells.json"))["spells"]
    # full_registry spans EVERY group in spells.json — geometry extraction
    # follows applyspell/effect references that land outside the three
    # equippable groups (HAIL -> HAIL_DAMAGE and friends).
    full_registry = {}
    for entries in spells_root.values():
        for s in (entries if isinstance(entries, list) else [entries]):
            if isinstance(s, dict) and s.get("@uniquename"):
                full_registry.setdefault(s["@uniquename"], s)
    # registry holds EVERY spell node (including effect sub-spells like
    # PULSINGHEAL_KNOCKBACK) so description tags can be resolved across spells
    registry, spell_meta = {}, {}
    for group in ("activespell", "passivespell", "togglespell"):
        entries = spells_root.get(group, [])
        for s in (entries if isinstance(entries, list) else [entries]):
            sid = s.get("@uniquename")
            if not sid:
                continue
            registry[sid] = s
            spell_meta[sid] = {
                "target": s.get("@target"),
                "uitype": s.get("@uitype"),
                "preferred_target": s.get("@controllerpreferredtarget"),
                "namelocatag": s.get("@namelocatag"),
                "desclocatag": s.get("@descriptionlocatag"),
                "cooldown": s.get("@recastdelay"),
                "cast_range": s.get("@castrange"),
                "casting_time": s.get("@castingtime"),
                "energy": s.get("@energyusage"),
            }

    # ---- localization: names, descriptions, tags, flags ----------------------
    loc = load(os.path.join(dump_dir, "localization.json"))
    loc_map = {}
    for tu in loc["tmx"]["body"]["tu"]:
        tid = tu.get("@tuid", "")
        if tid.startswith("@SPELLS_"):
            loc_map[tid] = en(tu.get("tuv", []))

    used_spells = {s for L in lines.values() for slot in L["spells"].values() for s in slot}
    spell_index = {}
    resolved_hits = resolved_misses = 0
    for sid in sorted(used_spells):
        meta = spell_meta.get(sid, {})
        name = loc_map.get(meta.get("namelocatag") or f"@SPELLS_{sid}", sid)
        desc = loc_map.get(meta.get("desclocatag") or f"@SPELLS_{sid}_DESC", "")
        plain = re.sub(r"\[/?\w+\]", "", desc)
        plain, h, m_ = resolve_description(plain, registry.get(sid, {}), registry)
        resolved_hits += h
        resolved_misses += m_
        low = plain.lower()
        flags = sorted(k for k, pat in FLAG_PATTERNS.items() if re.search(pat, low))
        directions = []
        if re.search(r"\benemy|\benemies|\bopponent", low): directions.append("enemy")
        if re.search(r"\ballies|\bally\b|\bgroup members", low): directions.append("ally")
        if re.search(r"\byou(rself)?\b|\bcaster\b|\bown\b", low): directions.append("self")
        meta = spell_meta.get(sid, {})
        geom = spell_geometry(sid, full_registry)
        spell_index[sid] = {
            "name": name,
            "tags": sorted(set(TAG_RE.findall(desc))),
            "flags": flags,
            "directions": directions,
            "target": meta.get("target"),
            "preferred_target": meta.get("preferred_target"),
            "cooldown": meta.get("cooldown"),
            "cast_range": meta.get("cast_range"),
            "casting_time": meta.get("casting_time"),
            # structural area facts (§B): None/absent = unknown, never "no AoE"
            "radius": geom.get("radius"),
            "max_targets": geom.get("max_targets"),
            "area": geom.get("area"),
            "description": plain[:400],
        }

    for L in lines.values():
        L.pop("_nspells", None)

    wl_path = os.path.join(out_dir, "weapon_lines.json")
    si_path = os.path.join(out_dir, "spell_index.json")
    with open(wl_path, "w", encoding="utf-8") as f:
        json.dump(lines, f, indent=1, sort_keys=True)
    with open(si_path, "w", encoding="utf-8") as f:
        json.dump(spell_index, f, indent=1, sort_keys=True)

    src_files = ["items.json", "spells.json", "localization.json",
                 "formatted/items.json"]
    record_derived("weapon_lines.json", wl_path, ADAPTER, ADAPTER_VERSION,
                   source_commit, src_files)
    record_derived("spell_index.json", si_path, ADAPTER, ADAPTER_VERSION,
                   source_commit, src_files)

    total_tags = resolved_hits + resolved_misses
    print(f"weapon lines: {len(lines)}   spells indexed: {len(spell_index)}"
          f"   @ {source_commit[:12]}")
    print(f"description numbers resolved: {resolved_hits}/{total_tags} tags"
          f" ({resolved_hits / total_tags:.0%})" if total_tags else "")
    n_geom = sum(1 for s in spell_index.values() if s.get("radius"))
    print(f"structural area geometry: {n_geom}/{len(spell_index)} spells")
    print(f"wrote {out_dir}/weapon_lines.json, spell_index.json")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # explicit local directory: usable for experiments, but the release
        # check downstream fails closed on the "local-override" provenance
        print("WARNING: parsing an unpinned local directory — provenance "
              "will record 'local-override' and the release check will fail")
        main(sys.argv[1], "local-override")
    else:
        commit = snapshot_commit()
        cache = snapshot_dir()
        if not commit or not cache or not os.path.isdir(cache):
            sys.exit("pinned snapshot missing — run: py -3 pipeline/fetch_snapshot.py")
        main(cache, commit)
