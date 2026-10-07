#!/usr/bin/env python3
"""
Evidence lint: the CI gate for the capability sheets (design doc §6.3 step 4).

Every nonzero capability score cites an evidence spell, and every sheet file
holds only what pipeline/sheets/README.md promises. Exit code 1 on any ERROR
blocks the data release; a WARNING never blocks.

Grounding (rows COMPOSED as the build reads them: an entry's own rows plus
the tree-pool rows that apply to it, sheets_lib.compose / compose_gear):
  1. the weapon line (gear item) exists in the parsed game data
  2. the cited spell is equippable on that weapon in a Q/W/E/passive slot
     (sits on the gear item's dumps menu); gear capabilities belong on gear
     sheets, not weapons, and each layer cites its own stat sentinel
     (WEAPON_STATS on weapons, GEAR_STATS on gear rows and self_costs)
  3. the spell can GROUND the claimed capability: its structured effects,
     read through the direction-aware effect map (effect_map.yaml), must
     offer it, with the prose flags kept as a fallback because neither
     source is complete alone

Contract (weapon sheets, gear sheets, both pool layers):
  4. schema: entries, rows, excepts, self_costs and pool documents carry
     only known keys; an unknown key is a typo the build would ignore
  5. score is an int 1-7 (score_unit 2 in templates/scoring.yaml); zero or
     missing is an ERROR, MASTERSHEET tune:sheets being the channel that
     zeroes a score
  6. every cap is in CAPABILITIES, and the templates and the effect map
     name nothing outside it, so the vocabulary cannot drift silently
  7. no duplicate (cap, evidence, use) row in one entry or pool, no
     duplicate except
  8. every except names a pool row the entry would otherwise receive: the
     pair is in the tree pool, the entry can equip the spell (or it is
     WEAPON_STATS) and no own row of the entry already overrides it
  9. one definition per weapon key and per gear key
 10. curated_as_of is an ISO date (YYYY-MM-DD); role_hint is in ROLE_HINTS;
     a gear slot is in GEAR_SLOTS and agrees with the game data
 11. layout: a weapon entry sits in sheets/<its weapon_lines subcategory>.yaml,
     a gear entry in sheets/gear/<its slot>.yaml, a pool in
     sheets/pools/<subcategory>.yaml or sheets/gear/pools/<tree>.yaml, and
     every sheets/*.yaml is named after a weapon tree

Warnings: an own row identical to the pool row it shadows (same cap,
evidence, score, use) changes nothing; a cited spell with neither structured
effects nor prose flags cannot be verified by rule 3; patch staleness
(below).

Rule 3's boundary is computed, never listed: a capability is checked iff the
effect map or the prose fallback can produce it at all, less the damage
capabilities (raw damage is a plain health change, not a typed effect, so
the effect layer can neither confirm nor deny a damage claim). The rest is
curation judgment and gets rules 1-2 only; the run's first line prints that
set.

Patch staleness: if out/patch_history.json exists (patch_history.py), a
WARNING is raised for any evidence spell a weapon entry cites that a game
patch touched after the entry's curated_as_of date; the scores resting on
it need a re-read.

Usage:  py -3 pipeline/evidence_lint.py [sheets/*.yaml]
"""
import datetime
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
sys.path.insert(0, HERE)
from effect_lookup import EffectLookup, HEAL_MEANING, PROSE_FALLBACK  # noqa: E402
import sheets_lib  # noqa: E402

SHEETS = os.path.join(HERE, "sheets")
POOL_DIR = os.path.join(SHEETS, "pools")
GEAR_DIR = os.path.join(SHEETS, "gear")
GEAR_POOL_DIR = os.path.join(GEAR_DIR, "pools")
TEMPLATES = os.path.join(HERE, "templates")


def _read_out(name, required=True):
    path = os.path.join(HERE, "out", name)
    if not required and not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


WEAPONS = _read_out("weapon_lines.json")
GEAR_SPELLS = _read_out("gear_spells.json", required=False)
GEAR_LINES = _read_out("gear_lines.json", required=False)
SUBCATEGORIES = {line.get("subcategory") for line in WEAPONS.values()} - {None}

# ---- the capability taxonomy -------------------------------------------------
# The one list of capability names a sheet row may carry. The vocabulary
# also lives in the design doc §2.2 table (its history: the table still
# lists energy_drain, retired as a documented fabrication per the
# seed_sheets.py HUMAN_ONLY note, and predates interrupt, max_health_cut
# and reflect), in dashboard/_app.js (GROUPS and the label maps, display
# only), in the templates (the scored rows) and in effect_map.yaml (what the
# effect layer can ground). lint_vocabulary() fails the run when a template
# or the effect map names a capability outside this list.
CAPABILITIES = frozenset({
    # sustain
    "heal_burst", "heal_sustain", "cleanse", "self_sustain",
    # frontline
    "tankiness", "engage", "disengage", "anti_dive", "zone_control", "reflect",
    # control
    "stun", "root", "silence", "interrupt", "knockback_displace", "slow",
    "clump_create", "peel",
    # denial
    "purge", "anti_zone", "heal_reduction", "resist_shred", "damage_debuff",
    "max_health_cut",
    # damage
    "burst_st", "burst_aoe", "sustained_dps", "execute",
    # tempo
    "mobility", "catch", "buff_allies",
})
# Derived by build_dataset, never curated: ranged_presence lands in a
# bundle whose burst_aoe claim the spell's own cast range delivers at range.
# A template may name it; a sheet row may not.
DERIVED_CAPABILITIES = frozenset({"ranged_presence"})
# composition.yaml roles.by_hint maps these; lint_vocabulary() keeps the two
# in step.
ROLE_HINTS = frozenset({"melee", "range", "tank", "healer", "support"})
GEAR_SLOTS = frozenset({"head", "armor", "shoes", "offhand", "cape", "potion",
                        "food"})
SCORE_MIN, SCORE_MAX = 1, 7

# ---- the sheet schema --------------------------------------------------------
WEAPON_KEYS = frozenset({"weapon", "curated_as_of", "role_hint", "except",
                         "capabilities", "removed"})
WEAPON_REQUIRED = ("weapon", "curated_as_of", "role_hint", "capabilities")
GEAR_KEYS = frozenset({"gear", "slot", "curated_as_of", "except",
                       "capabilities", "self_costs"})
GEAR_REQUIRED = ("gear", "slot", "curated_as_of", "capabilities")
ROW_KEYS = frozenset({"cap", "score", "evidence", "use"})
EXCEPT_KEYS = frozenset({"cap", "evidence"})
SELF_COST_KEYS = frozenset({"cap", "points", "evidence"})
POOL_KEYS = frozenset({"subcategory", "curated_as_of", "capabilities"})
GEAR_POOL_KEYS = frozenset({"tree", "curated_as_of", "capabilities"})
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Evidence values that are not spells: base item stats (tankiness from
# armour value). WEAPON_STATS is the weapon sentinel, GEAR_STATS the gear
# one (statless gear items: capes, offhands, potions, food). Exempt from
# rule 3: there is no spell to check.
WEAPON_STATS, GEAR_STATS = "WEAPON_STATS", "GEAR_STATS"
NON_SPELL_EVIDENCE = {WEAPON_STATS, GEAR_STATS}

LOOKUP = EffectLookup()

# Every capability the effect map is capable of producing. A claim outside this
# set is a judgement call the data cannot adjudicate, so rule 3 skips it.
CHECKABLE = set()
for _rule in LOOKUP.map.values():
    if isinstance(_rule, dict):
        for _d, _caps in _rule.items():
            if _d not in ("note", "ignore") and isinstance(_caps, list):
                CHECKABLE.update(_caps)
for _caps in PROSE_FALLBACK.values():
    CHECKABLE.update(_caps)

# Raw damage is NOT part of the structured effect vocabulary — it is a plain
# health `directattributechange`, not a typed effect — so the effect layer can
# never confirm or deny a damage claim. The map only reaches these capabilities
# via damage-BUFF effects, which would wrongly demand that every damage score
# trace to a buff. Damage stays human judgement, like zone_control.
CHECKABLE -= {"burst_st", "burst_aoe", "sustained_dps", "execute"}


def _hashable(value):
    return value is None or isinstance(value, str)


def _load_pool_rows(directory, tag_key):
    """{tag: [row, ...]} the way sheets_lib.load_pools / load_gear_pools
    read the pool files (rows with a cap), keeping only rows the composer
    can key on. A malformed file is reported by the pool lint, never
    raised here."""
    pools = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.yaml"))):
        try:
            with open(path, encoding="utf-8") as f:
                doc = yaml.safe_load(f)
        except (yaml.YAMLError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        tag, rows = doc.get(tag_key), doc.get("capabilities")
        if not isinstance(tag, str) or not isinstance(rows, list):
            continue
        rows = [r for r in rows if isinstance(r, dict) and r.get("cap")
                and _hashable(r.get("cap")) and _hashable(r.get("evidence"))]
        if rows:
            pools.setdefault(tag, []).extend(rows)
    return pools


POOLS = _load_pool_rows(POOL_DIR, "subcategory")
GEAR_POOLS = _load_pool_rows(GEAR_POOL_DIR, "tree")

# ---- patch staleness (warning only, never blocks) ---------------------------
# out/patch_history.json (built by patch_history.py from ao-bin-dumps git
# history) records which spells each game patch touched, keyed back to the
# equippable root spells sheets cite. Every weapon entry declares
# `curated_as_of: YYYY-MM-DD` (rule 10); if a cited evidence spell changed in
# a LATER patch, the scores resting on it need a re-read. Without the file
# the check is silent.


def load_patch_index(path=os.path.join(HERE, "out", "patch_history.json")):
    """{equippable root spell: [patch dates it changed in]}, newest last."""
    if not os.path.exists(path):
        return {}
    idx = {}
    for p in json.load(open(path, encoding="utf-8")).get("patches", []):
        for s in p.get("spells", []):
            # VFX/audio/controller-metadata churn can't move a score; a
            # missing flag (older file) conservatively counts as relevant
            if not s.get("balance_relevant", True):
                continue
            for root in s.get("roots", [s["id"]]):
                idx.setdefault(root, set()).add(p["date"])
    return {k: sorted(v) for k, v in idx.items()}


PATCH_INDEX = load_patch_index()


def stale_evidence(curated_as_of, spell_ids, index=None):
    """[(spell_id, [dates])] for cited spells patched after the curation date.
    Dates are ISO strings, so string comparison is date comparison."""
    index = PATCH_INDEX if index is None else index
    if not curated_as_of:
        return []
    d0 = str(curated_as_of)
    out = []
    for sid in sorted(set(spell_ids)):
        dates = [d for d in index.get(sid, []) if d > d0]
        if dates:
            out.append((sid, dates))
    return out


# ---- shared checks -------------------------------------------------------------

def _rel(path):
    """A path as the messages print it: relative to pipeline/, forward
    slashes."""
    return os.path.relpath(os.path.abspath(path), HERE).replace(os.sep, "/")


def _same_path(a, b):
    return (os.path.normcase(os.path.abspath(a))
            == os.path.normcase(os.path.abspath(b)))


def _load(path, errors):
    """The parsed yaml document, or None with the parse failure recorded
    (an impossible unquoted date raises ValueError, not a YAMLError)."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, ValueError) as exc:
        errors.append(f"{_rel(path)}: not valid YAML ({exc})")
        return None


def _keys_text(keys):
    return ", ".join(sorted(keys))


def date_problem(value):
    """None when value is an ISO calendar date (a yaml date or a
    'YYYY-MM-DD' string), else what is wrong with it."""
    if isinstance(value, datetime.datetime):
        return f"curated_as_of {value} is a timestamp, not a date"
    if isinstance(value, datetime.date):
        return None
    if isinstance(value, str) and ISO_DATE.match(value):
        try:
            datetime.date.fromisoformat(value)
            return None
        except ValueError:
            pass
    return f"curated_as_of {value!r} is not an ISO date (YYYY-MM-DD)"


def score_problem(value, field="score"):
    """None when value is an int on the 1-7 sheet scale."""
    if value is None:
        return f"no {field}"
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{field} {value!r} is not an integer"
    if value == 0 and field == "score":
        return ("score 0 is not a sheet score; MASTERSHEET tune:sheets is "
                "the channel that zeroes a score")
    if not SCORE_MIN <= value <= SCORE_MAX:
        return f"{field} {value} is outside {SCORE_MIN}-{SCORE_MAX}"
    return None


def cap_problem(cap):
    """None when cap is a taxonomy capability."""
    if not isinstance(cap, str) or not cap:
        return f"cap {cap!r} is not a capability name"
    if cap in CAPABILITIES:
        return None
    if cap in DERIVED_CAPABILITIES:
        return f"'{cap}' is derived by the build, never a sheet row"
    if cap in LOOKUP.proposed_caps:
        return (f"'{cap}' is a proposed capability (effect_map.yaml "
                f"proposed_capabilities), not in the taxonomy")
    return f"unknown capability '{cap}' (not in evidence_lint.CAPABILITIES)"


def row_problems(row, keys=ROW_KEYS, score_field="score"):
    """What is wrong with one {cap, score, evidence[, use]} row."""
    if not isinstance(row, dict):
        return [f"a row must be a mapping, not {row!r}"]
    out = []
    unknown = sorted(str(k) for k in row if k not in keys)
    if unknown:
        out.append(f"unknown key(s) {', '.join(unknown)} "
                   f"(a row carries {_keys_text(keys)})")
    for p in (cap_problem(row.get("cap")),
              score_problem(row.get(score_field), score_field)):
        if p:
            out.append(p)
    ev = row.get("evidence")
    if ev is None or ev == "":
        out.append("no evidence")
    elif not isinstance(ev, str):
        out.append(f"evidence {ev!r} is not a spell id")
    if "use" in keys and "use" in row and (
            not isinstance(row["use"], str) or not row["use"]):
        out.append(f"use {row['use']!r} is not a name")
    return out


def _pair_text(key):
    cap, ev = key[0], key[1]
    use = key[2] if len(key) > 2 else None
    return f"{cap}, {ev}" + (f", use {use}" if use else "")


def check_rows(subject, rows, errors, keys=ROW_KEYS, score_field="score",
               label="row", field="capabilities"):
    """Rules 4-7 over one row list: schema, score, cap, duplicates. Returns
    the rows the composer can key on (hashable cap, evidence and use)."""
    if not isinstance(rows, list):
        errors.append(f"{subject}: {field} must be a list, not {rows!r}")
        return []
    safe, seen = [], {}
    for i, row in enumerate(rows, 1):
        cap = row.get("cap") if isinstance(row, dict) else None
        where = (f"{subject}.{cap}" if isinstance(cap, str) and cap
                 else f"{subject} {label} {i}")
        for p in row_problems(row, keys, score_field):
            errors.append(f"{where}: {p}")
        if not isinstance(row, dict):
            continue
        key = (row.get("cap"), row.get("evidence"), row.get("use"))
        if not all(_hashable(v) for v in key):
            continue
        if key in seen:
            errors.append(f"{where}: duplicate {label} ({_pair_text(key)}), "
                          f"the same as {label} {seen[key]}")
        else:
            seen[key] = i
        safe.append(row)
    return safe


def check_excepts(subject, excepts, errors):
    """Rules 4, 6 and 7 over an except list. Returns the distinct, keyable
    excepts."""
    if not isinstance(excepts, list):
        errors.append(f"{subject}: except must be a list of {{cap, evidence}}, "
                      f"not {excepts!r}")
        return []
    safe, seen = [], set()
    for i, x in enumerate(excepts, 1):
        where = f"{subject} except {i}"
        if not isinstance(x, dict):
            errors.append(f"{where}: must be a mapping {{cap, evidence}}")
            continue
        unknown = sorted(str(k) for k in x if k not in EXCEPT_KEYS)
        if unknown:
            errors.append(f"{where}: unknown key(s) {', '.join(unknown)} "
                          f"(an except carries {_keys_text(EXCEPT_KEYS)})")
        p = cap_problem(x.get("cap"))
        if p:
            errors.append(f"{where}: {p}")
        ev = x.get("evidence")
        if ev is None or ev == "":
            errors.append(f"{where}: no evidence")
        elif not isinstance(ev, str):
            errors.append(f"{where}: evidence {ev!r} is not a spell id")
        key = (x.get("cap"), ev)
        if not all(_hashable(v) for v in key):
            continue
        if key in seen:
            errors.append(f"{subject}: duplicate except ({_pair_text(key)})")
            continue
        seen.add(key)
        safe.append(x)
    return safe


def except_problems(subject, excepts, own_rows, pool_rows, can_apply,
                    pool_label):
    """Rule 8: an except must cancel a pool row the entry would otherwise
    receive, else it is dead (no such row) or inert (the row never applies,
    or an own row already overrides it)."""
    pool_pairs = {(r.get("cap"), r.get("evidence")) for r in pool_rows}
    own_pairs = {(r.get("cap"), r.get("evidence")) for r in own_rows}
    out = []
    for x in excepts:
        pair = (x.get("cap"), x.get("evidence"))
        text = f"{subject}: except ({_pair_text(pair)})"
        if pair not in pool_pairs:
            out.append(f"{text} names no row of {pool_label}")
        elif not can_apply(pair[1]):
            out.append(f"{text} is inert: {subject} cannot equip {pair[1]}, "
                       f"so the pool row never applies")
        elif pair in own_pairs:
            out.append(f"{text} is inert: the entry's own row for the pair "
                       f"already overrides the pool row")
    return out


def shadow_warnings(subject, own_rows, pool_rows, can_apply, pool_label):
    """An own row identical to the pool row it shadows changes nothing."""
    pool = {}
    for r in pool_rows:
        pool.setdefault((r.get("cap"), r.get("evidence")), r)
    out = []
    for r in own_rows:
        pr = pool.get((r.get("cap"), r.get("evidence")))
        if pr is None or not can_apply(r.get("evidence")):
            continue
        if r.get("score") == pr.get("score") and r.get("use") == pr.get("use"):
            out.append(f"{subject}.{r.get('cap')}: the own row repeats the "
                       f"{pool_label} row it shadows ({r.get('evidence')}, "
                       f"score {r.get('score')}); it changes nothing")
    return out


def ground(where, cap, ev, errors, warnings):
    """Rule 3: the cited spell must be able to ground the claimed capability."""
    if cap not in CHECKABLE:
        return                        # curation judgment, rules 1-2 only
    cands = LOOKUP.candidates(ev)
    if cap in cands:
        return
    name = LOOKUP.spells.get(ev, {}).get("name", ev)
    if not LOOKUP.has_structured(ev) and not LOOKUP.spells.get(ev, {}).get("flags"):
        warnings.append(
            f"{where}: '{name}' has no structured effects and no prose "
            f"flags — cannot verify, review by hand")
        return
    offer = ", ".join(sorted(cands)) or "nothing"
    errors.append(
        f"{where}: '{name}' cannot ground {cap}. Its effects support: {offer}")


def _entry_header(subject, entry, allowed, required, errors):
    """Rules 4 and 10 on an entry's own keys and its curated_as_of."""
    unknown = sorted(str(k) for k in entry if k not in allowed)
    if unknown:
        errors.append(f"{subject}: unknown key(s) {', '.join(unknown)} "
                      f"(an entry carries {_keys_text(allowed)})")
    missing = [k for k in required if k not in entry]
    if missing:
        errors.append(f"{subject}: missing {', '.join(missing)}")
    if "curated_as_of" in entry:
        p = date_problem(entry["curated_as_of"])
        if p:
            errors.append(f"{subject}: {p}")
            return False
        return True
    return False


# ---- weapon sheets -------------------------------------------------------------

def lint_weapon_entry(entry, path, index):
    """Every rule for one weapon sheet entry."""
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return [f"{_rel(path)} entry {index}: an entry must be a mapping"], []
    wkey = entry.get("weapon")
    if not isinstance(wkey, str) or not wkey:
        return [f"{_rel(path)} entry {index}: no weapon key"], []
    dated = _entry_header(wkey, entry, WEAPON_KEYS, WEAPON_REQUIRED, errors)
    role = entry.get("role_hint")
    if "role_hint" in entry and (not isinstance(role, str)
                                 or role not in ROLE_HINTS):
        errors.append(f"{wkey}: role_hint {role!r} is not one of "
                      f"{_keys_text(ROLE_HINTS)}")
    if "removed" in entry and not isinstance(entry["removed"], bool):
        errors.append(f"{wkey}: removed {entry['removed']!r} is not true/false")
    rows = (check_rows(wkey, entry["capabilities"], errors)
            if "capabilities" in entry else [])
    excepts = (check_excepts(wkey, entry["except"], errors)
               if "except" in entry else [])

    line = WEAPONS.get(wkey)
    if line is None:
        errors.append(f"{wkey}: unknown weapon line (not in game data)")
        return errors, warnings
    sub = line.get("subcategory")
    if not _same_path(path, os.path.join(SHEETS, f"{sub}.yaml")):
        errors.append(f"{wkey}: a {sub} weapon belongs in sheets/{sub}.yaml, "
                      f"not {_rel(path)}")
    equippable = sheets_lib.equippable(line)

    def can_apply(ev):
        return ev in sheets_lib.NON_SPELL_EVIDENCE or ev in equippable

    pool_rows = POOLS.get(sub, [])
    pool_label = f"sheets/pools/{sub}.yaml"
    errors += except_problems(wkey, excepts, rows, pool_rows, can_apply,
                              pool_label)
    warnings += shadow_warnings(wkey, rows, pool_rows, can_apply, pool_label)

    cited = set()
    # composed rows: the weapon's own + applicable tree-pool rows, so a
    # pool row that stops being equippable after a patch still FAILS here
    composed = sheets_lib.compose({"capabilities": rows, "except": excepts},
                                  line, POOLS)
    for c in composed:
        cap, score, ev = c.get("cap"), c.get("score", 0), c.get("evidence")
        if not score or cap not in CAPABILITIES or not isinstance(ev, str) \
                or not ev:
            continue                  # rules 4-6 already reported the row
        where = f"{wkey}.{cap}"
        if ev == GEAR_STATS:
            errors.append(f"{where}: GEAR_STATS is the gear sentinel; a "
                          f"weapon row cites a spell or WEAPON_STATS")
            continue
        if ev in NON_SPELL_EVIDENCE:
            continue
        if ev not in equippable:
            errors.append(
                f"{where}: evidence spell '{ev}' is NOT equippable on {wkey} "
                f"(if a gear item provides this, it belongs on that item's sheet)")
            continue
        cited.add(ev)
        ground(where, cap, ev, errors, warnings)
    if dated:
        for sid, dates in stale_evidence(entry.get("curated_as_of"), cited):
            warnings.append(
                f"{wkey}: evidence spell '{sid}' changed in patch(es) "
                f"{', '.join(dates)}, after curated_as_of "
                f"{entry['curated_as_of']} — re-verify the scores citing it "
                f"(details in out/patch_history.json)")
    return errors, warnings


def lint_sheet(path):
    """One weapon sheet file: every entry's contract and grounding."""
    errors, warnings = [], []
    docs = _load(path, errors)
    if docs is None:
        return errors, warnings
    if not isinstance(docs, list):
        return [f"{_rel(path)}: a weapon sheet is a list of entries"], warnings
    for i, entry in enumerate(docs, 1):
        e, w = lint_weapon_entry(entry, path, i)
        errors += e
        warnings += w
    return errors, warnings


def _defined_twice(places):
    return [f"{key}: defined {len(where)} times ({'; '.join(where)})"
            for key, where in sorted(places.items()) if len(where) > 1]


def lint_corpus(paths):
    """Across the weapon sheet files: one definition per weapon key (rule
    9), and every file under sheets/ named after a weapon tree (rule 11)."""
    errors, places = [], {}
    for path in paths:
        if _same_path(os.path.dirname(os.path.abspath(path)), SHEETS):
            base = os.path.splitext(os.path.basename(path))[0]
            if base not in SUBCATEGORIES:
                errors.append(f"{_rel(path)}: the file name is not a weapon "
                              f"tree (no weapon_lines subcategory '{base}')")
        docs = _load(path, [])
        if not isinstance(docs, list):
            continue
        for i, entry in enumerate(docs, 1):
            if isinstance(entry, dict) and isinstance(entry.get("weapon"), str):
                places.setdefault(entry["weapon"], []).append(
                    f"{_rel(path)} entry {i}")
    errors += _defined_twice(places)
    return errors, []


# ---- tree pools ----------------------------------------------------------------

def _pool_header(path, doc, allowed, tag_key, errors):
    """Rule 4 on a pool document; returns its tag (subcategory or tree)."""
    if not isinstance(doc, dict):
        errors.append(f"{_rel(path)}: a pool file is a mapping "
                      f"{{{tag_key}, capabilities}}")
        return None
    unknown = sorted(str(k) for k in doc if k not in allowed)
    if unknown:
        errors.append(f"{_rel(path)}: unknown key(s) {', '.join(unknown)} "
                      f"(a pool carries {_keys_text(allowed)})")
    if "curated_as_of" in doc:
        p = date_problem(doc["curated_as_of"])
        if p:
            errors.append(f"{_rel(path)}: {p}")
    if "capabilities" not in doc:
        errors.append(f"{_rel(path)}: missing capabilities")
    tag = doc.get(tag_key)
    if not isinstance(tag, str) or not tag:
        errors.append(f"{_rel(path)}: no {tag_key}")
        return None
    return tag


def lint_pools(paths=None):
    """Weapon pool files (sheets/pools/): the contract, and every row must
    APPLY somewhere and ground its cap.

    compose() applies a pool row only where the evidence spell is equippable,
    so a typo'd or patch-removed spell would silently apply to NOBODY — this
    check makes that an ERROR instead."""
    errors, warnings = [], []
    paths = sorted(glob.glob(os.path.join(POOL_DIR, "*.yaml"))) \
        if paths is None else paths
    tree = {}
    for wk, line in WEAPONS.items():
        tree.setdefault(line.get("subcategory"), []).append(wk)
    pool_files = {}
    for path in paths:
        parsed = len(errors)
        doc = _load(path, errors)
        if len(errors) > parsed:
            continue                  # not valid YAML, already reported
        sub = _pool_header(path, doc, POOL_KEYS, "subcategory", errors)
        if sub is None:
            continue
        if os.path.splitext(os.path.basename(path))[0] != sub:
            errors.append(f"{_rel(path)}: the {sub} pool belongs in "
                          f"sheets/pools/{sub}.yaml")
        if sub in pool_files:
            errors.append(f"pools/{sub}: a second pool file for the tree "
                          f"({pool_files[sub]} and {_rel(path)})")
        pool_files.setdefault(sub, _rel(path))
        rows = check_rows(f"pools/{sub}", doc.get("capabilities", []), errors)
        members = tree.get(sub, [])
        if not members:
            errors.append(f"pools/{sub}: no weapon line has this subcategory")
            continue
        if not os.path.exists(os.path.join(SHEETS, f"{sub}.yaml")):
            errors.append(f"pools/{sub}: no sheets/{sub}.yaml carries the "
                          f"tree's weapons, so the pool applies to none")
        for r in rows:
            cap, score, ev = r.get("cap"), r.get("score", 0), r.get("evidence")
            if not score or cap not in CAPABILITIES or not ev:
                continue              # rules 4-6 already reported the row
            where = f"pools/{sub}.{cap}"
            if ev == GEAR_STATS:
                errors.append(f"{where}: GEAR_STATS is the gear sentinel; a "
                              f"weapon pool row cites a spell or WEAPON_STATS")
                continue
            if ev in NON_SPELL_EVIDENCE:
                continue
            holders = [w for w in members
                       if ev in sheets_lib.equippable(WEAPONS[w])]
            if not holders:
                errors.append(
                    f"{where}: evidence spell '{ev}' is equippable on NO "
                    f"{sub} weapon — the row applies to nobody")
                continue
            ground(where, cap, ev, errors, warnings)
    return errors, warnings


def _menu(gkey):
    menu = GEAR_SPELLS.get(gkey) or {}
    return set(menu.get("actives") or []) | set(menu.get("passives") or [])


def lint_gear_pools(paths=None):
    """Gear pool files (sheets/gear/pools/): the contract, and every row
    must sit on the menu of at least one item of its tree and ground its
    cap. compose_gear applies a row only where the item's menu carries the
    spell, so a typo'd or patch-removed spell would silently apply to
    NOBODY — an ERROR here instead."""
    errors, warnings = [], []
    paths = sorted(glob.glob(os.path.join(GEAR_POOL_DIR, "*.yaml"))) \
        if paths is None else paths
    pool_files = {}
    for path in paths:
        parsed = len(errors)
        doc = _load(path, errors)
        if len(errors) > parsed:
            continue                  # not valid YAML, already reported
        tree = _pool_header(path, doc, GEAR_POOL_KEYS, "tree", errors)
        if tree is None:
            continue
        if os.path.splitext(os.path.basename(path))[0] != tree.lower():
            errors.append(f"{_rel(path)}: the {tree} pool belongs in "
                          f"sheets/gear/pools/{tree.lower()}.yaml")
        if tree in pool_files:
            errors.append(f"gear/pools/{tree}: a second pool file for the "
                          f"tree ({pool_files[tree]} and {_rel(path)})")
        pool_files.setdefault(tree, _rel(path))
        rows = check_rows(f"gear/pools/{tree}", doc.get("capabilities", []),
                          errors)
        members = [k for k in GEAR_SPELLS if sheets_lib.gear_tree(k) == tree]
        if not members:
            errors.append(f"gear/pools/{tree}: no item in the dumps has this tree")
            continue
        slot = tree.split("_")[0].lower()
        if not os.path.exists(os.path.join(GEAR_DIR, f"{slot}.yaml")):
            errors.append(f"gear/pools/{tree}: no sheets/gear/{slot}.yaml "
                          f"carries the tree's items, so the pool applies to none")
        for r in rows:
            cap, score, ev = r.get("cap"), r.get("score", 0), r.get("evidence")
            if not score or cap not in CAPABILITIES or not ev:
                continue              # rules 4-6 already reported the row
            where = f"gear/pools/{tree}.{cap}"
            holders = [k for k in members if ev in _menu(k)]
            if not holders:
                errors.append(
                    f"{where}: ability '{ev}' is on NO {tree} item's menu — "
                    f"the row applies to nobody")
                continue
            ground(where, cap, ev, errors, warnings)
    return errors, warnings


# ---- gear sheets ---------------------------------------------------------------

def lint_gear_entry(entry, path, index):
    """Every rule for one gear sheet entry: rows are the COMPOSED list (own
    rows + the tree pool's), as the build reads them."""
    errors, warnings = [], []
    if not isinstance(entry, dict):
        return [f"{_rel(path)} entry {index}: an entry must be a mapping"], []
    gkey = entry.get("gear")
    if not isinstance(gkey, str) or not gkey:
        return [f"{_rel(path)} entry {index}: no gear key"], []
    subject = f"gear/{gkey}"
    _entry_header(subject, entry, GEAR_KEYS, GEAR_REQUIRED, errors)
    rows = (check_rows(subject, entry["capabilities"], errors)
            if "capabilities" in entry else [])
    excepts = (check_excepts(subject, entry["except"], errors)
               if "except" in entry else [])
    costs = (check_rows(f"{subject} self_costs", entry["self_costs"], errors,
                        keys=SELF_COST_KEYS, score_field="points",
                        label="self_cost", field="self_costs")
             if "self_costs" in entry else [])

    known = gkey in GEAR_LINES or gkey in GEAR_SPELLS
    if (GEAR_LINES or GEAR_SPELLS) and not known:
        errors.append(f"{subject}: unknown gear item (not in game data)")
        return errors, warnings
    game_slot = ((GEAR_LINES.get(gkey) or {}).get("slot")
                 or (GEAR_SPELLS.get(gkey) or {}).get("slot"))
    slot = entry.get("slot")
    if "slot" in entry:
        if not isinstance(slot, str) or slot not in GEAR_SLOTS:
            errors.append(f"{subject}: slot {slot!r} is not one of "
                          f"{_keys_text(GEAR_SLOTS)}")
            slot = None
        elif game_slot and slot != game_slot:
            errors.append(f"{subject}: slot {slot} disagrees with the game "
                          f"data's slot {game_slot}")
    slot = game_slot or slot          # the game data decides the file
    if slot and not _same_path(path, os.path.join(GEAR_DIR, f"{slot}.yaml")):
        errors.append(f"{subject}: a {slot} item belongs in "
                      f"sheets/gear/{slot}.yaml, not {_rel(path)}")

    menu = GEAR_SPELLS.get(gkey)
    equippable = _menu(gkey)

    def can_apply(ev):
        return ev in equippable

    tree = sheets_lib.gear_tree(gkey)
    pool_rows = GEAR_POOLS.get(tree, []) if menu is not None else []
    pool_label = (f"sheets/gear/pools/{tree.lower()}.yaml" if tree
                  else "any gear pool (the key names no armor tree)")
    errors += except_problems(subject, excepts, rows,
                              GEAR_POOLS.get(tree, []), can_apply, pool_label)
    warnings += shadow_warnings(subject, rows, pool_rows, can_apply, pool_label)

    composed = sheets_lib.compose_gear({"gear": gkey, "capabilities": rows,
                                        "except": excepts}, menu, GEAR_POOLS)
    for c in composed:
        cap, score, ev = c.get("cap"), c.get("score", 0), c.get("evidence")
        if not score or cap not in CAPABILITIES or not isinstance(ev, str) \
                or not ev:
            continue                  # rules 4-6 already reported the row
        where = f"{subject}.{cap}"
        if ev == WEAPON_STATS:
            errors.append(f"{where}: WEAPON_STATS is the weapon sentinel; a "
                          f"gear row cites an ability or GEAR_STATS")
            continue
        if ev in NON_SPELL_EVIDENCE:
            continue
        if ev not in equippable:
            errors.append(f"{where}: ability '{ev}' is NOT on this item's menu")
            continue
        ground(where, cap, ev, errors, warnings)
    # a self cost cites the spell that charges it, on the item's own menu,
    # or the gear sentinel (rule 2's own-layer sentinel holds here too; no
    # rule 3: a cost is the downside, which grounds no capability)
    for c in costs:
        ev = c.get("evidence")
        if ev == WEAPON_STATS:
            errors.append(f"{subject}.{c.get('cap')}: WEAPON_STATS is the "
                          f"weapon sentinel; a self_cost cites an ability or "
                          f"GEAR_STATS")
            continue
        if isinstance(ev, str) and ev and ev not in NON_SPELL_EVIDENCE \
                and ev not in equippable:
            errors.append(f"{subject}.{c.get('cap')}: self_cost ability '{ev}' "
                          f"is NOT on this item's menu")
    return errors, warnings


def lint_gear(paths=None):
    """Gear sheets (sheets/gear/): every entry's contract and grounding, one
    definition per gear key (rule 9), every file named after a slot."""
    errors, warnings = [], []
    paths = sorted(glob.glob(os.path.join(GEAR_DIR, "*.yaml"))) \
        if paths is None else paths
    places = {}
    for path in paths:
        if _same_path(os.path.dirname(os.path.abspath(path)), GEAR_DIR):
            base = os.path.splitext(os.path.basename(path))[0]
            if base not in GEAR_SLOTS:
                errors.append(f"{_rel(path)}: the file name is not a gear "
                              f"slot ({_keys_text(GEAR_SLOTS)})")
        docs = _load(path, errors)
        if docs is None:
            continue
        if not isinstance(docs, list):
            errors.append(f"{_rel(path)}: a gear sheet is a list of entries")
            continue
        for i, entry in enumerate(docs, 1):
            e, w = lint_gear_entry(entry, path, i)
            errors += e
            warnings += w
            if isinstance(entry, dict) and isinstance(entry.get("gear"), str):
                places.setdefault(entry["gear"], []).append(
                    f"{_rel(path)} entry {i}")
    errors += _defined_twice(places)
    return errors, warnings


# ---- the vocabulary ------------------------------------------------------------
# Template sections whose KEYS are capabilities; the walk also reads every
# `caps` / `*_caps` list and every `capability` field.
CAP_KEYED_SECTIONS = ("requirements", "hard_floors", "multipliers",
                      "target_mults")


def template_capabilities():
    """{capability: {where, ...}} for every capability name templates/*.yaml
    uses: the keys of every requirements / hard_floors / multipliers /
    target_mults mapping (pool_rows and the style_bands cells included),
    every `caps` and `*_caps` list (styles chains, mechanics), every
    `capability` field, the weight_fit curated keys, the composition
    predicates and the scoring synergy pairs."""
    found = {}

    def add(cap, where):
        found.setdefault(cap if isinstance(cap, str) else repr(cap),
                         set()).add(where)

    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                ks = str(k)
                if ks in CAP_KEYED_SECTIONS and isinstance(v, dict):
                    for cap in v:
                        add(cap, f"{where} {ks}")
                elif (ks == "caps" or ks.endswith("_caps")) and isinstance(v, list):
                    for cap in v:
                        add(cap, f"{where} {ks}")
                elif ks == "capability" and isinstance(v, str):
                    add(v, f"{where} {ks}")
                walk(v, where)
        elif isinstance(node, list):
            for item in node:
                walk(item, where)

    for path in sorted(glob.glob(os.path.join(TEMPLATES, "*.yaml"))):
        where = f"templates/{os.path.basename(path)}"
        doc = _load(path, [])
        walk(doc, where)
        if not isinstance(doc, dict):
            continue
        for cap in ((doc.get("weight_fit") or {}).get("curated") or {}):
            add(cap, f"{where} weight_fit.curated")
        for pred in (doc.get("predicates") or {}).values():
            for cap in (pred if isinstance(pred, dict) else {}):
                add(cap, f"{where} predicates")
        for syn in doc.get("capability_synergies") or []:
            for side in ("a", "b"):
                if isinstance(syn, dict) and side in syn:
                    add(syn[side], f"{where} capability_synergies")
    return found


def lint_vocabulary():
    """Rule 6 beyond the sheets: the templates and the effect layer name no
    capability outside CAPABILITIES, so the list cannot drift silently."""
    errors = []
    allowed = CAPABILITIES | DERIVED_CAPABILITIES
    for cap, places in sorted(template_capabilities().items()):
        if cap not in allowed:
            where = "; ".join(sorted(places)[:3])
            errors.append(f"{where}: capability '{cap}' is not in "
                          f"evidence_lint.CAPABILITIES (or DERIVED_CAPABILITIES)")
    proposed = set(LOOKUP.proposed_caps)
    for effect, rule in sorted(LOOKUP.map.items()):
        if not isinstance(rule, dict):
            continue
        for direction, caps in rule.items():
            if direction in ("note", "ignore") or not isinstance(caps, list):
                continue
            for cap in caps:
                if not isinstance(cap, str) or (cap not in CAPABILITIES
                                                and cap not in proposed):
                    errors.append(f"effect_map.yaml {effect}.{direction}: "
                                  f"capability '{cap}' is not in "
                                  f"evidence_lint.CAPABILITIES")
    for cap in sorted(proposed & CAPABILITIES):
        errors.append(f"effect_map.yaml proposed_capabilities: '{cap}' is in "
                      f"evidence_lint.CAPABILITIES; a promoted capability "
                      f"leaves the proposed list")
    for source, table in (("effect_lookup.PROSE_FALLBACK", PROSE_FALLBACK),
                          ("effect_lookup.HEAL_MEANING", HEAL_MEANING)):
        for flag, caps in sorted(table.items()):
            for cap in caps:
                if cap not in CAPABILITIES:
                    errors.append(f"{source} {flag}: capability '{cap}' is "
                                  f"not in evidence_lint.CAPABILITIES")
    for sid, caps in sorted(LOOKUP.added_caps.items()):
        for cap in (caps or {}):
            if cap not in CAPABILITIES and cap not in proposed:
                errors.append(f"effect_overrides.yaml add {sid}: capability "
                              f"'{cap}' is not in evidence_lint.CAPABILITIES")
    comp = _load(os.path.join(TEMPLATES, "composition.yaml"), errors) or {}
    by_hint = ((comp.get("roles") or {}).get("by_hint")
               if isinstance(comp, dict) else None)
    if isinstance(by_hint, dict) and set(by_hint) != ROLE_HINTS:
        errors.append(f"templates/composition.yaml roles.by_hint maps "
                      f"{_keys_text(by_hint)}; evidence_lint.ROLE_HINTS is "
                      f"{_keys_text(ROLE_HINTS)}")
    return errors, []


# ---- the run -------------------------------------------------------------------

def run(paths):
    """[(label, errors, warnings)] for every section, in print order. paths:
    the weapon sheet files (default: sheets/*.yaml)."""
    judged = ", ".join(sorted(CAPABILITIES - CHECKABLE))
    out = [(f"vocabulary  ({len(CAPABILITIES)} capabilities; rule 3 checks "
            f"{len(CAPABILITIES & CHECKABLE)}, curation judgment only: "
            f"{judged})",) + lint_vocabulary()]
    for label, fn in (("sheets/pools/", lint_pools),
                      ("sheets/gear/pools/", lint_gear_pools),
                      ("sheets/gear/", lint_gear)):
        out.append((label,) + fn())
    out.append(("weapon keys and sheet file names",) + lint_corpus(paths))
    for path in paths:
        out.append((os.path.basename(path),) + lint_sheet(path))
    return out


def main(paths):
    # a console or pipe may not encode every character a spell name carries
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    total_err = 0
    for label, errors, warnings in run(paths):
        status = "FAIL" if errors else "OK"
        print(f"[{status}] {label}  ({len(errors)} errors, "
              f"{len(warnings)} warnings)")
        for e in errors:
            print(f"   ERROR  {e}")
        for w in warnings:
            print(f"   warn   {w}")
        total_err += len(errors)
    sys.exit(1 if total_err else 0)


if __name__ == "__main__":
    args = sys.argv[1:] or sorted(glob.glob(os.path.join(SHEETS, "*.yaml")))
    main(args)
