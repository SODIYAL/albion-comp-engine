#!/usr/bin/env python3
"""
Report-only audit: ability text a sheet row cannot cite.

Every capability score cites an equippable spell (evidence_lint rule 2), and
curate_helper.py prints the text of equippable spells only. Two classes of
ability sit outside that reach and are listed here for curation:

  1. FORM ABILITIES. A shapeshifter staff's E transforms the wielder; the
     form's own abilities and passive carry a name and a description in the
     dumps but sit on no equip menu. A sheet scores them through the E (the
     Hellspawn precedent), so a form ability nobody read is a capability
     nobody scored. Each form's abilities are printed with their numbers
     resolved, beside the rows the sheet cites on the E and the prose flags
     of the text that no E row covers.
  2. ALLY PROTECTION. anti_dive counts a protection placed on other allies
     beside the effects landed on a diver (tests/VALIDATION.md, the
     anti-dive rule): an absorb shield, a damage immunity or a damage
     redirection on an ally, and a protective zone or aura. Every
     equippable weapon spell and gear ability whose text carries one is
     listed with the rows its holders score on it today. The `resistance`
     kind marks a resistance grant on allies: inside the rule where it is
     a zone or an aura, outside it where it is a buff on one targeted ally
     (the worksheet shows the text; the curator tells them apart).

Reads the dumps cache at the pinned snapshot, out/weapon_lines.json,
out/gear_spells.json, out/spell_index.json and the sheets. Writes
review/form_abilities.md (gitignored, never committed) and nothing a build
reads; the output is a worksheet, never an assertion.

Usage:  py -3 pipeline/audit_form_abilities.py [--out PATH]
"""
import glob
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import sheets_lib  # noqa: E402
from effect_lookup import PROSE_FALLBACK  # noqa: E402
from parse_dumps import FLAG_PATTERNS, en, line_key, load, resolve_description  # noqa: E402
# The form table (transformation type -> its spells' name prefixes) is the
# parser's, which records each shapeshifter line's form spells for the
# evidence review; a form spell that matches no prefix is listed here under
# "Unmapped" instead of vanishing.
from parse_dumps import FORM_PREFIXES, FORM_STATBLOCK, FORM_CHARGE  # noqa: E402,F401
from provenance import snapshot_commit, snapshot_dir  # noqa: E402

# The prose flags of parse_dumps, read as the capabilities a text can
# support. An ally shield is buff_allies before anything else.
FLAG_CAPS = dict(PROSE_FALLBACK)
FLAG_CAPS["shield"] = list(PROSE_FALLBACK["shield"]) + ["buff_allies"]

# Kind of protection -> the wording that states it. A sentence counts when
# it, the two before it or the one after it name an ally (or the spell
# targets one): "immune to damage until impact" on a leap is the caster's
# own.
PROTECT_KINDS = (
    ("shield", re.compile(r"\bshields?\b|\babsorb", re.I)),
    ("immunity", re.compile(r"\bimmun\w* to (?:\w+ )?damage|\binvulnerab", re.I)),
    ("redirection", re.compile(r"\bredirect", re.I)),
    ("resistance", re.compile(
        r"\bincreas\w*[^.]{0,60}\b(?:damage resistances?|armor)\b", re.I)),
)
ALLY = re.compile(r"\ball(?:y|ies)\b", re.I)
ALLY_TARGETS = ("friendall", "friendother", "friendotherplayers")
PROTECT_CAPS = ("anti_dive", "buff_allies", "peel", "tankiness", "cleanse")


def plain(text):
    return re.sub(r"\s+", " ", re.sub(r"\[/?\w+\]", "", text or "")).strip()


def protection_kinds(text, target):
    """The kinds of ally protection a description states, in PROTECT_KINDS
    order."""
    kinds = set()
    sents = re.split(r"(?<=[.:])\s+", text)
    for i, sent in enumerate(sents):
        near = " ".join(sents[max(0, i - 2):i + 2])
        if target in ALLY_TARGETS or ALLY.search(near):
            kinds |= {k for k, pat in PROTECT_KINDS if pat.search(sent)}
    return [k for k, _ in PROTECT_KINDS if k in kinds]


def flags_of(text):
    return [f for f, pat in FLAG_PATTERNS.items() if re.search(pat, text, re.I)]


def load_sheets():
    """{weapon: sheet entry} over sheets/*.yaml, {gear: entry} over
    sheets/gear/*.yaml."""
    weapons, gear = {}, {}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        for e in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            if isinstance(e, dict) and e.get("weapon"):
                weapons[e["weapon"]] = e
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "gear", "*.yaml"))):
        for e in (yaml.safe_load(open(path, encoding="utf-8")) or []):
            if isinstance(e, dict) and e.get("gear"):
                gear[e["gear"]] = e
    return weapons, gear


def cell(text):
    return text.replace("|", "/")


def form_section(lines, sheets, pools, items, registry, names, equip):
    """Markdown lines for class 1, plus (forms, abilities, uncovered) counts."""
    form_of = {}
    for w in items.get("transformationweapon", []):
        u = w.get("@uniquename", "")
        if "@" not in u and w.get("@transformation"):
            form_of[line_key(u)] = w["@transformation"]

    spells = {}
    for sid, s in registry.items():
        if sid in equip or sid.startswith("SHAPESHIFT_") or sid == FORM_CHARGE:
            continue
        if not ((s.get("@statblock") or "").startswith(FORM_STATBLOCK)
                or s.get("@spellchargesspell") == FORM_CHARGE
                or sid.startswith("PASSIVE_SHAPE_")):
            continue
        # the spell's own tags win: a reworked ability keeps its id and
        # points at a new description (Barbed Roots reads ..._V2_DESC; the
        # text under the id's default tag is the retired one)
        name = names.get(s.get("@namelocatag") or "") or names.get("@SPELLS_" + sid)
        desc = (names.get(s.get("@descriptionlocatag") or "")
                or names.get("@SPELLS_" + sid + "_DESC"))
        if not (name and desc):
            continue
        text = plain(resolve_description(desc, s, registry)[0])
        spells[sid] = {"name": name, "text": text, "spell": s}

    out, used = ["## 1. Form abilities", ""], set()
    n_abilities = n_uncovered = 0
    for wkey in sorted(form_of):
        form = form_of[wkey]
        line = lines.get(wkey)
        if line is None:
            continue
        e_spells = set(line["spells"].get("e") or [])
        rows = sheets_lib.compose(sheets.get(wkey) or {}, line, pools)
        e_rows = {r["cap"]: r.get("score", 0) for r in rows
                  if r.get("evidence") in e_spells and r.get("score")}
        prefixes = FORM_PREFIXES.get(form, ())
        # one row per ability name: a combo's second step and a recast
        # effect repeat the first spell's name; the form-statblock spell wins
        mine, seen = [], set()
        for sid in sorted(spells, key=lambda k: (
                not (spells[k]["spell"].get("@statblock") or "").startswith(
                    FORM_STATBLOCK), k)):
            if not sid.startswith(prefixes):
                continue
            used.add(sid)
            if spells[sid]["name"] in seen:
                continue
            seen.add(spells[sid]["name"])
            mine.append(sid)
        out.append(f"### {line.get('name', wkey)} (`{wkey}`): form {form}, "
                   f"E `{', '.join(sorted(e_spells))}`")
        out.append("")
        out.append("Rows the sheet cites on the E: "
                   + (", ".join(f"{c} {s}" for c, s in sorted(e_rows.items()))
                      or "none") + ".")
        out.append("")
        out.append("| Ability | Spell | Cooldown | Charges | Text | "
                   "Prose flags | Flags no E row covers |")
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for sid in mine:
            sp, s = spells[sid], spells[sid]["spell"]
            flags = flags_of(sp["text"])
            bare = [f for f in flags
                    if not set(FLAG_CAPS.get(f, [])) & set(e_rows)]
            n_abilities += 1
            n_uncovered += bool(bare)
            out.append("| {} | `{}` | {} | {} | {} | {} | {} |".format(
                cell(sp["name"]), sid, s.get("@recastdelay") or "-",
                s.get("@spellchargesrequired") or "-", cell(sp["text"]),
                ", ".join(flags) or "-", ", ".join(bare) or "-"))
        out.append("")
    unmapped = sorted(set(spells) - used)
    if unmapped:
        out.append("### Unmapped form spells")
        out.append("")
        for sid in unmapped:
            out.append(f"- `{sid}` {spells[sid]['name']}: {spells[sid]['text']}")
        out.append("")
    return out, (len(form_of), n_abilities, n_uncovered, len(unmapped))


def protection_section(lines, sheets, pools, gear_menus, gear_sheets,
                       gear_pools, index):
    """Markdown lines for class 2, plus the listed-spell count."""
    holders = {}
    for wkey, line in lines.items():
        rows = sheets_lib.compose(sheets.get(wkey) or {}, line, pools)
        for sid in sheets_lib.equippable(line):
            holders.setdefault(sid, []).append((line.get("name", wkey), rows))
    for gkey, menu in gear_menus.items():
        entry = gear_sheets.get(gkey)
        rows = (sheets_lib.compose_gear(entry, menu, gear_pools)
                if entry else [])
        for sid in set(menu.get("actives") or []) | set(menu.get("passives") or []):
            holders.setdefault(sid, []).append((gkey, rows))

    out = ["## 2. Ally protection", "",
           "| Spell | Id | Kind | Holders | Text | anti_dive today | "
           "Other protective rows citing it |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    n = 0
    for sid in sorted(holders):
        rec = index.get(sid) or {}
        text = plain(rec.get("description"))
        kinds = protection_kinds(text, rec.get("target"))
        if not kinds:
            continue
        held = holders[sid]
        tally = {}
        for _name, rows in held:
            for r in rows:
                if (r.get("evidence") == sid and r.get("score")
                        and r.get("cap") in PROTECT_CAPS):
                    tally.setdefault((r["cap"], r["score"]), 0)
                    tally[(r["cap"], r["score"])] += 1
        def fmt(items):
            return ", ".join(f"{c} {s}" + (f" ({k} of {len(held)})"
                                           if k != len(held) else "")
                             for (c, s), k in sorted(items)) or "-"
        dive = [(k, v) for k, v in tally.items() if k[0] == "anti_dive"]
        rest = [(k, v) for k, v in tally.items() if k[0] != "anti_dive"]
        who = (", ".join(sorted(h for h, _ in held)) if len(held) <= 3
               else f"{len(held)} holders ({sorted(h for h, _ in held)[0]} ...)")
        n += 1
        out.append("| {} | `{}` | {} | {} | {} | {} | {} |".format(
            cell(rec.get("name") or sid), sid, ", ".join(kinds), cell(who),
            cell(text), fmt(dive), fmt(rest)))
    out.append("")
    return out, n


def main(argv):
    out_path = os.path.join(ROOT, "review", "form_abilities.md")
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]
    dump_dir = snapshot_dir()
    if not dump_dir or not os.path.isdir(dump_dir):
        sys.exit("no dumps cache at the pinned snapshot: run fetch_snapshot.py")

    items = load(os.path.join(dump_dir, "items.json"))["items"]
    spells_root = load(os.path.join(dump_dir, "spells.json"))["spells"]
    registry = {}
    for entries in spells_root.values():
        for s in (entries if isinstance(entries, list) else [entries]):
            if isinstance(s, dict) and s.get("@uniquename"):
                registry.setdefault(s["@uniquename"], s)
    tmx = load(os.path.join(dump_dir, "localization.json"))["tmx"]["body"]["tu"]
    names = {tu.get("@tuid"): en(tu.get("tuv") or []) for tu in tmx}

    lines = sheets_lib.load_weapon_lines()
    index = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))
    gear_menus = json.load(open(os.path.join(OUT, "gear_spells.json"), encoding="utf-8"))
    sheets, gear_sheets = load_sheets()
    pools, gear_pools = sheets_lib.load_pools(), sheets_lib.load_gear_pools()
    equip = {s for line in lines.values() for s in sheets_lib.equippable(line)}
    for menu in gear_menus.values():
        equip |= set(menu.get("actives") or []) | set(menu.get("passives") or [])

    form_md, (n_forms, n_abil, n_bare, n_unmapped) = form_section(
        lines, sheets, pools, items, registry, names, equip)
    prot_md, n_prot = protection_section(
        lines, sheets, pools, gear_menus, gear_sheets, gear_pools, index)

    doc = ["# Ability text a sheet row cannot cite: worksheet", "",
           f"Snapshot `{(snapshot_commit() or '')[:12]}`. Generated by "
           "`pipeline/audit_form_abilities.py`; a worksheet for curation, "
           "never an assertion. Base values (item power scales them in "
           "game).", ""] + form_md + prot_md
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(doc))
    print(f"forms {n_forms}, form abilities {n_abil}, with a prose flag no "
          f"E row covers {n_bare}, unmapped {n_unmapped}")
    print(f"ally-protection spells {n_prot}")
    print(f"wrote {os.path.relpath(out_path, ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
