#!/usr/bin/env python3
"""
Build the versioned dataset the engine and the SPA both consume
(design doc §6.3 step 5).

    sheets/*.yaml              curated, evidence-linted        (authoritative)
    sheets/illustrative/*.yaml design-doc §2.3 placeholders    (NOT a release;
                               empty since 2026-08-12 — all weapons curated,
                               the file is a tombstone record)
    templates/*.yaml           content templates + scoring config
        │
        ▼
    out/dataset-<version>.json + out/dataset-latest.json

Why this exists: before it, capability numbers lived in BOTH a Python dict
inside the prototype and the curated YAML sheets, and they had already
diverged (Longbow resist_shred was 2 in the prototype, 1 in the curated
sheet). One source of truth, one export, both consumers read the export.

Precedence: a curated sheet always shadows an illustrative entry for the same
weapon. `release_clean` is true only when zero illustrative sheets are present
AND the evidence lint passes.

Usage:  python3 build_dataset.py [--version 2026.08.1]
"""
import json, os, glob, argparse, subprocess, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DEFAULT_VERSION = "2026.08.1"

sys.path.insert(0, HERE)
from provenance import load_manifest, verify_derived  # noqa: E402
import mastersheet  # noqa: E402  (MASTERSHEET.md override layer)
import sheets_lib  # noqa: E402  (tree-pool composition)
import build_interactions as _inter_mod  # noqa: E402  (adapter versions)
import fetch_gear_lines as _gear_mod  # noqa: E402
import fetch_item_stats as _stats_mod  # noqa: E402
import parse_dumps as _parse_mod  # noqa: E402

# Every game-data input the release artifacts consume, and the adapter
# version the CURRENT code would produce it with. verify_derived() fails the
# release if any file is missing, hash-drifted, version-stale, or from a
# different snapshot commit than the others (changeschapter2.md §A).
PROVENANCE_INPUTS = {
    "weapon_lines.json": (_parse_mod.ADAPTER, _parse_mod.ADAPTER_VERSION),
    "spell_index.json": (_parse_mod.ADAPTER, _parse_mod.ADAPTER_VERSION),
    "item_stats.json": (_stats_mod.ADAPTER, _stats_mod.ADAPTER_VERSION),
    "gear_lines.json": (_gear_mod.ADAPTER, _gear_mod.ADAPTER_VERSION),
    "gear_spells.json": (_parse_mod.ADAPTER, _parse_mod.ADAPTER_VERSION),
    "interactions.json": (_inter_mod.ADAPTER, _inter_mod.ADAPTER_VERSION),
}


def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def load_weapon_lines():
    with open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8") as f:
        return json.load(f)


def display_name(line, key):
    """Game data names are tier-prefixed ("Adept's Heavy Mace"); strip it."""
    name = (line or {}).get("name", key)
    for prefix in ("Adept's ", "Novice's ", "Journeyman's ", "Expert's ",
                   "Master's ", "Grandmaster's ", "Elder's ", "Beginner's ",
                   "Minor ", "Major "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def load_gear_sheets(gear_lines, gear_spells):
    """The FULL-BUILD member model's gear layer (2026-08-20): curated gear
    capability sheets (sheets/gear/*.yaml), same evidence discipline as
    weapons. A gear item's loadout has ONE active-ability slot (the player
    picks one D/R/F per piece); GEAR_STATS-evidenced rows are always-on
    (capes, offhands, potions, food). Composed by the engine into
    person contribution = weapon build + every gear slot's contribution."""
    gear = {}
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "gear", "*.yaml"))):
        for entry in _load_yaml(path):
            key = entry.get("gear")
            if not key:
                continue
            caps, evidence, uses = {}, {}, {}
            for c in entry.get("capabilities", []):
                if not isinstance(c, dict):
                    continue
                cap, score = c.get("cap"), c.get("score", 0)
                if not cap or not score:
                    continue
                caps[cap] = max(caps.get(cap, 0), score)
                if c.get("evidence"):
                    evidence.setdefault(cap, [])
                    if c["evidence"] not in evidence[cap]:
                        evidence[cap].append(c["evidence"])
                if c.get("use"):
                    uses[cap] = c["use"]
            menu = gear_spells.get(key) or {}
            pseudo_line = {"spells": {"active": menu.get("actives") or [],
                                      "passive": menu.get("passives") or []}}
            gl = gear_lines.get(key) or {}
            gear[key] = {
                # filled after loading: the item's combat stats (item_stats
                # bank) — the engine's build-stat channel reads these
                "stats": {},
                "unique_name": key,
                "display_name": display_name(gl, key),
                "slot": entry.get("slot") or gl.get("slot"),
                "curated_as_of": (str(entry["curated_as_of"])
                                  if entry.get("curated_as_of") else None),
                "capabilities": caps,
                "evidence": evidence,
                "loadout": build_loadout(caps, evidence, pseudo_line, uses),
            }
    return gear


def build_loadout(caps, evidence, line, uses=None):
    """Group a weapon's capabilities by the ability SLOT they come from, so the
    engine can enforce one-spell-per-slot (a player equips one Q, one W, one E,
    one passive — not the whole menu). Slot is auto-derived from each
    capability's evidence spell via the weapon's equippable spell list
    (weapon_lines[key]["spells"], keyed q/w/e/passive). Capabilities from base
    stats / auto-attack (evidence WEAPON_STATS, no slot) are "always on".

    A sheet may split ONE spell into mutually exclusive `use:` variants
    (Chillhowl's Frozen Crystal saves an ALLY or freezes an ENEMY — never both
    in the same moment); each (spell, use) pair becomes its own bundle in the
    spell's slot, so the engine scores one use, not the union.

    Returns {"always": {cap: score}, "slots": [[bundle, ...], ...],
             "slot_names": [game slot per entry in slots],
             "slot_spells": [[spell id per bundle], ...]} where each bundle is
    one spell-use's {cap: score} and each inner list is the mutually-exclusive
    choices for one slot. slot_names/slot_spells let the dashboard map a
    player's actual Q/W/passive picks onto the scored bundles. Measured
    2026-08-14: 1278/1319 cap-entries resolve to exactly one slot, 0 span
    multiple slots, 41 are WEAPON_STATS."""
    spell_slot = {}
    for slot, ids in ((line or {}).get("spells", {}) or {}).items():
        for sid in ids:
            spell_slot.setdefault(sid, slot)
    uses = uses or {}
    always, bundles = {}, {}
    for cap, score in caps.items():
        slot_spell = next(((spell_slot[sp], sp) for sp in evidence.get(cap, [])
                           if sp in spell_slot), None)
        if slot_spell:
            key = slot_spell + (uses.get(cap),)
            bundles.setdefault(key, {})[cap] = score
        else:
            always[cap] = score
    slots, spells = {}, {}
    for (slot, sp, _use), b in bundles.items():
        slots.setdefault(slot, []).append(b)
        spells.setdefault(slot, []).append(sp)
    names = list(slots)
    return {"always": always, "slots": [slots[n] for n in names],
            "slot_names": names, "slot_spells": [spells[n] for n in names]}


def load_sheets(weapon_lines, tune_sheets=None):
    """Curated sheets win over illustrative ones for the same weapon key.

    Rows are COMPOSED (sheets_lib): the weapon's own rows plus the shared
    tree-pool rows from sheets/pools/<subcategory>.yaml that apply to it.

    tune_sheets (MASTERSHEET.md tune:sheets): {WEAPON: {cap: score}} expert
    score overrides, applied at the ROW level so they flow into caps AND
    loadout bundles. An override may re-rank or remove (score 0) a
    capability the composed sheet already grounds — it may NOT invent a new
    one (that needs a sheet row with evidence); unmatched overrides fail
    the build."""
    weapons, sources = {}, {}
    pools = sheets_lib.load_pools()
    overrides = tune_sheets or {}
    unmatched = {(w, c) for w, m in overrides.items()
                 for c in (m or {})}

    def ingest(path, status):
        for entry in _load_yaml(path):
            key = entry.get("weapon")
            if not key:
                continue
            # curated always wins; never let illustrative overwrite it
            if weapons.get(key, {}).get("status") == "curated" and status != "curated":
                continue
            caps, evidence, uses = {}, {}, {}
            for c in sheets_lib.compose(entry, weapon_lines.get(key), pools):
                if not isinstance(c, dict):
                    continue
                cap, score = c.get("cap"), c.get("score", 0)
                ov = overrides.get(key)
                if ov and cap in ov:
                    score = ov[cap]
                    unmatched.discard((key, cap))
                if not cap or not score:
                    continue
                # a sheet may cite several spells for one capability; the score
                # is the capability's total, not a per-spell increment
                caps[cap] = max(caps.get(cap, 0), score)
                if c.get("evidence"):
                    evidence.setdefault(cap, [])
                    if c["evidence"] not in evidence[cap]:
                        evidence[cap].append(c["evidence"])
                # `use:` marks mutually exclusive uses of ONE spell — the
                # capability lands in a use-specific loadout bundle
                if c.get("use"):
                    uses[cap] = c["use"]
            line = weapon_lines.get(key)
            weapons[key] = {
                "unique_name": key,
                "display_name": display_name(line, key),
                "status": status,
                "in_game_data": line is not None,
                "role_hint": entry.get("role_hint"),
                # retired by the game: still scoreable (old permalinks must
                # load) but never recommended — see Engine.pool
                "removed": bool(entry.get("removed")),
                # YAML parses the unquoted date; keep it a plain string in JSON
                "curated_as_of": (str(entry["curated_as_of"])
                                  if entry.get("curated_as_of") else None),
                "capabilities": caps,
                "evidence": evidence,
                # one-spell-per-slot decomposition for loadout-aware scoring
                # (engine reads this; flat `capabilities` stays for display +
                # base-party supply). Auto-derived from evidence spell -> slot.
                "loadout": build_loadout(caps, evidence, line, uses),
            }
            sources[key] = os.path.relpath(path, HERE).replace("\\", "/")

    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "illustrative", "*.yaml"))):
        ingest(path, "illustrative")
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        ingest(path, "curated")

    if unmatched:
        sys.exit("MASTERSHEET.md tune:sheets — override(s) matched nothing "
                 "(unknown weapon, or a capability the composed sheet does "
                 "not ground; adding a NEW capability needs a sheet row with "
                 "evidence): "
                 + ", ".join(f"{w}.{c}" for w, c in sorted(unmatched)))

    for key, src in sources.items():
        weapons[key]["source"] = src
    return weapons


# Positioning capability (§B rework, 2026-08-19). The capability model needs
# to know WHERE damage comes from: a Galatine spin at 3m and a Frost bomb at
# 20m supply identical `burst_aoe`, and a "clap" comp needs the bomb, not the
# spin. Two earlier derivations shipped and were replaced: role_hint
# (PROVISIONAL), then basic-attack `attackrange >= 9` — which wrongly granted
# permanent ranged_presence to weapons whose long autoattack says nothing
# about whether their SELECTED Q/W/E delivers ranged AoE (one-hand Cursed,
# Chillhowl).
#
# The current model is per SPELL BUNDLE, evidence-first:
#   - the bundle must claim `burst_aoe` — a curated, evidence-linted human
#     judgement that the spell delivers AoE damage;
#   - the claiming spell's own game data must say it is delivered at range:
#     target `ground`/`enemy` with cast_range >= RANGED_MIN_CASTRANGE.
#     Cast ranges cluster like autoattack ranges did: melee spins/cleaves sit
#     at 6-8, real ranged delivery at 9-26, so 9 splits in a real gap;
#   - structure cannot tell a thrown bomb from a LEAP that carries the
#     wielder into the clump (both are `target: ground` at range), so
#     ranged_overrides.yaml carries explicit curated grant/deny records with
#     citations — gap-closers are denied there;
#   - a claim whose spell has no structural facts is UNKNOWN: the capability
#     stays off and the weapon is listed for curation, never inferred.
#
# The capability lands in the qualifying BUNDLE, not `loadout.always`: it
# participates in scoring only when the scored combo actually equips the AoE
# spell. The flat capability map still gets 1 when any bundle qualifies —
# pred_members (composition ranged_aoe_core) and the display read that map as
# "this weapon CAN bring ranged AoE with the right spell".
#
# Every decision is written to out/ranged_presence_report.json with the facts
# it rests on (spell, slot, cast range, radius, max targets, cooldown, basis)
# and the report participates in release validation.
RANGED_MIN_CASTRANGE = 9
RANGED_DELIVERY = ("ground", "enemy")
AOE_CLAIM = "burst_aoe"


def load_ranged_overrides():
    path = os.path.join(HERE, "ranged_overrides.yaml")
    if not os.path.exists(path):
        return {}
    out = {}
    for e in _load_yaml(path):
        if isinstance(e, dict) and e.get("weapon") and e.get("spell"):
            out[(e["weapon"], e["spell"])] = e
    return out


def derive_ranged_presence(weapons, spell_index, overrides):
    """Per-bundle ranged_presence with an evidence trail. Returns
    (tagged_count, report, problems) — problems are release blockers
    (an override referencing a weapon/spell that does not exist)."""
    report, problems = {}, []
    used_overrides = set()
    tagged = 0
    for key, w in sorted(weapons.items()):
        lo = w.get("loadout") or {}
        slots = lo.get("slots") or []
        names = lo.get("slot_names") or []
        spells = lo.get("slot_spells") or []
        decisions, granted = [], False
        for i, slot in enumerate(slots):
            for j, bundle in enumerate(slot):
                if not bundle.get(AOE_CLAIM):
                    continue
                sid = spells[i][j]
                facts = spell_index.get(sid) or {}
                cast_range = facts.get("cast_range")
                cast_range = float(cast_range) if cast_range is not None else None
                rec = {
                    "spell": sid, "slot": names[i] if i < len(names) else None,
                    "cast_range": cast_range,
                    "radius": facts.get("radius"),
                    "max_targets": facts.get("max_targets"),
                    "cooldown": facts.get("cooldown"),
                    "delivery": facts.get("target"),
                }
                ov = overrides.get((key, sid))
                if ov:
                    used_overrides.add((key, sid))
                    rec["basis"] = f"curated_override_{ov['decision']}"
                    rec["granted"] = ov["decision"] == "grant"
                    rec["override"] = {"reason": (ov.get("reason") or "").strip(),
                                       "source": (ov.get("source") or "").strip(),
                                       "as_of": str(ov.get("as_of") or "")}
                elif cast_range is None or not facts:
                    rec["basis"] = "unknown_no_structural_facts"
                    rec["granted"] = False
                elif (facts.get("target") in RANGED_DELIVERY
                        and cast_range >= RANGED_MIN_CASTRANGE):
                    rec["basis"] = "curated_burst_aoe+structural_range"
                    rec["granted"] = True
                else:
                    rec["basis"] = "structural_below_threshold"
                    rec["granted"] = False
                decisions.append(rec)
                if rec["granted"]:
                    bundle["ranged_presence"] = 2   # 1-7 scale: 2 = one unit
                    granted = True
                    tagged += 1
        if granted:
            w["capabilities"]["ranged_presence"] = 2
            w.setdefault("evidence", {})["ranged_presence"] = sorted(
                {d["spell"] for d in decisions if d["granted"]})
        if decisions:
            unknown = any(d["basis"] == "unknown_no_structural_facts"
                          for d in decisions)
            report[key] = {
                "status": ("granted" if granted else
                           "unknown" if unknown else "not_granted"),
                "decisions": decisions,
            }
    for (wk, sid), ov in sorted(overrides.items()):
        if (wk, sid) in used_overrides:
            continue
        line = (weapons.get(wk) or {}).get("loadout") or {}
        all_spells = {s for sl in line.get("slot_spells", []) for s in sl}
        if wk not in weapons:
            problems.append(f"ranged_overrides: unknown weapon {wk}")
        elif sid not in all_spells:
            problems.append(
                f"ranged_overrides: spell {sid} is not a curated bundle "
                f"spell on {wk}")
        else:
            # equippable but its bundle claims no burst_aoe — the override
            # is dead weight; surface it rather than let it rot
            problems.append(
                f"ranged_overrides: {wk}/{sid} matched no burst_aoe bundle")
    return tagged, report, problems


# ---------------------------------------------------------------- style fit
# Per-weapon playstyle identity (owner-specified 2026-08-23): a weapon's
# identity comes from its E spell FIRST (the E is the weapon's identity —
# the same rule the sheets are structured around), then its kit and role.
# Derived structurally, overridable with cited owner rulings
# (style_overrides.yaml), audited in out/style_fit_report.json.
# DESCRIPTIVE layer: comp_identity() reads it; no scoring path does.
STYLE_FIT_STYLES = ("brawl", "clap", "kite", "brawl_clap", "clap_kite")
STYLE_FIT_BANDS = ("trio", "gang", "group")      # <=3 / 4-9 / 10+
STYLE_FIT_VERDICTS = ("fits", "situational", "unfit")
DAMAGE_CAPS = ("burst_st", "burst_aoe", "sustained_dps", "execute")
# Utility that can carry a group slot even when the weapon's own damage
# does not scale (the Dagger Pair case — golden T15: its value at scale is
# utility, not kill damage). A single-scale damage carrier with at least
# UTILITY_EXEMPT_MIN of these points degrades to 'situational', not 'unfit'.
# resist_shred + damage_debuff added by owner ruling 2026-08-23 (the
# Harpoon review-queue case): pierce on the clump and damage amps are
# group jobs in their own right — the exact tools the kill checklist
# names — so a pierce-bot carries a slot without group-scale damage.
UTILITY_EXEMPT_CAPS = ("catch", "clump_create", "engage", "peel", "purge",
                       "silence", "stun", "root", "knockback_displace",
                       "heal_reduction", "max_health_cut", "anti_dive",
                       "resist_shred", "damage_debuff")
UTILITY_EXEMPT_MIN = 6
DMG_CARRIER_MIN = 4                              # flat damage points
# An E damage spell with a real area footprint is group-scale even when the
# sheet grades its damage sustained_dps rather than burst_aoe (Blazing
# Staff's 5-radius Flame Tornado is a DoT zone — still a group tool).
# Battleaxe's 1.5-radius Axe Throw stays single.
GROUP_AOE_MIN_RADIUS = 3.0
# Weak-group-E rule (owner ruling 2026-08-24, round 7): "dps weapons that
# have low damage AND add nothing to the group" are trio-class even when
# the E's footprint is technically an area — "the AND is important, like
# heavy mace has low damage on its e but it silences enemy group so is
# really useful in group setting." A group-scale dps E does its job when
# its damage reaches E_DMG_JOB_MIN sheet points (owner-calibrated:
# Energy Shaper "super high damage ... great in large group fights" and
# Greataxe "its e can hit everyone in its vicinity ... it's okay" both sit
# at 4 and stay), OR when the E carries one REAL group tool — a
# UTILITY_EXEMPT/interrupt cap at E_UTILITY_TOOL_MIN+ (Carrioncaller's
# heal cut 4, Frost Staff's root 6; scattered 2-point dabs do not rescue,
# the Double-Bladed-Staff class the owner graded below the mace standard).
# Self-only effects (mobility, disengage, self_sustain) never rescue.
# PROVISIONAL — both constants reviewable in out/style_fit_report.json.
E_DMG_JOB_MIN = 4
E_UTILITY_TOOL_MIN = 4
E_GROUP_UTILITY_CAPS = UTILITY_EXEMPT_CAPS + ("interrupt",)
# Non-stacking budget slots are EARNED (owner rulings 2026-08-24/25): a
# member of a derived NON-STACKING group (the cursed line — its shared Q
# pool is priced count-once by the CURSEDOT record) brings damage the
# budget already discounts, so a GROUP-band (10+) slot is earned by the
# E's enemy-DEBUFF tool: "the only weapon i see in any party bigger than
# 15 people is the lifecurse, damnation, or rotcaller" — purge, pierce,
# heal-cut. Displacement/CC is NOT a debuff and does not earn the slot
# ("demonic staff is not a true brawl weapon at larger than 7 people" —
# its fear peels but denies nothing). Members whose best E debuff sits
# below E_UTILITY_TOOL_MIN demote to situational at group for EVERY
# style — a legitimate manual pick, never generated. Trio/gang untouched
# (Shadowcaller stays a real small-gang pick).
E_DEBUFF_CAPS = ("purge", "resist_shred", "heal_reduction",
                 "max_health_cut", "damage_debuff")


def load_style_overrides():
    path = os.path.join(HERE, "style_overrides.yaml")
    if not os.path.exists(path):
        return {}
    out = {}
    for e in _load_yaml(path):
        if isinstance(e, dict) and e.get("weapon"):
            out[e["weapon"]] = e
    return out


def derive_style_fit(weapons, spell_index, item_stats, role_sets, overrides,
                     econ=None, heal_dedicated_min=4, nonstack_members=None):
    """Per-weapon style/size fit with an evidence trail. Returns
    (report, problems) — problems block the release (an override naming an
    unknown weapon/style/band/verdict).

    Structural rules (all PROVISIONAL, reviewable in the audit report):
    - delivery side: autoattack range >= RANGED_MIN_CASTRANGE -> ranged;
      melee autoattack whose E damage still lands at that range -> flex
      (Realmbreaker: the damage arrives at range even though the body
      follows); otherwise melee.
    - damage scale: the E decides (E-first identity) — an E bundle claiming
      burst_aoe is group-scale; anything else is single-scale.
    - healers / frontline / support are style-flexible (their identity is
      their job, not a playstyle); damage carriers are where fit bites.
    - trio (<=3): everything fits — small-scale content takes any comp.
    """
    healers = set(role_sets.get("healers") or [])
    frontline = set(role_sets.get("frontline") or [])
    pure_dps = set(role_sets.get("pure_dps") or [])
    report, problems = {}, []

    def all_bands(v):
        return {b: v for b in STYLE_FIT_BANDS}

    for key, w in sorted(weapons.items()):
        caps = w.get("capabilities") or {}
        dmg_pts = sum(caps.get(c, 0) for c in DAMAGE_CAPS)
        util_pts = sum(caps.get(c, 0) for c in UTILITY_EXEMPT_CAPS)
        flexible = (key in healers or key in frontline
                    or key not in pure_dps)
        carrier = dmg_pts >= DMG_CARRIER_MIN and not flexible
        attackrange = ((item_stats.get(key) or {}).get("stats")
                       or {}).get("attackrange") or 0
        # E-slot damage facts
        lo = w.get("loadout") or {}
        names = lo.get("slot_names") or []
        slots = lo.get("slots") or []
        spells = lo.get("slot_spells") or []
        e_spells, e_reach, e_group = [], 0.0, False
        e_dmg_pts, e_util_max, e_debuff_max = 0, 0, 0
        for i, slot in enumerate(slots):
            if i >= len(names) or names[i] != "e":
                continue
            for j, bundle in enumerate(slot):
                # E group utility reads EVERY e bundle (a utility-only E
                # still carries its tool); the damage facts below only the
                # damage-bearing ones
                for c in E_GROUP_UTILITY_CAPS:
                    v = bundle.get(c, 0)
                    if v > e_util_max:
                        e_util_max = v
                for c in E_DEBUFF_CAPS:
                    v = bundle.get(c, 0)
                    if v > e_debuff_max:
                        e_debuff_max = v
                if not any(bundle.get(c) for c in DAMAGE_CAPS):
                    continue
                bd = sum(bundle.get(c, 0) for c in DAMAGE_CAPS)
                if bd > e_dmg_pts:
                    e_dmg_pts = bd
                sid = spells[i][j]
                facts = spell_index.get(sid) or {}
                cr = facts.get("cast_range")
                e_spells.append(sid)
                if cr is not None:
                    e_reach = max(e_reach, float(cr))
                radius = facts.get("radius")
                radius = float(radius) if radius is not None else 0.0
                mts = facts.get("max_targets") or 0
                if (bundle.get(AOE_CLAIM) or radius >= GROUP_AOE_MIN_RADIUS
                        or mts >= 3):
                    e_group = True
        if not slots and caps.get(AOE_CLAIM):
            e_group = True                       # flat-sheet fallback
        delivery = ("ranged" if attackrange >= RANGED_MIN_CASTRANGE
                    else "flex" if e_reach >= RANGED_MIN_CASTRANGE
                    else "melee")
        scale = ("none" if not carrier
                 else "group" if e_group else "single")
        # A single-scale carrier whose kit clears the utility exemption is
        # a UTILITY CARRIER (Harpoon the pierce-bot, Dagger Pair the catch
        # bot): its damage is incidental to its job, so it can hold a
        # group slot — and (blind-label ruling 2026-08-23, the 20v20 comp)
        # it never anchors a damage-identity split in comp_identity.
        utility_carrier = (carrier and scale == "single"
                          and util_pts >= UTILITY_EXEMPT_MIN)

        # Weak-group-E (round 7): technically-area E, but its damage is
        # below the job bar AND no single E tool reaches the rescue bar —
        # trio-class like a single-scale carrier ("low damage and adds
        # nothing to the group"; the AND protects Heavy-Mace-style
        # utility Es and every real tool carrier)
        weak_group_e = (scale == "group"
                        and e_dmg_pts < E_DMG_JOB_MIN
                        and e_util_max < E_UTILITY_TOOL_MIN)
        fit = {s: all_bands("fits") for s in STYLE_FIT_STYLES}
        if carrier:
            if scale == "group" and not weak_group_e:
                if delivery == "ranged":
                    for b in ("gang", "group"):
                        fit["brawl"][b] = "situational"
                elif delivery == "melee":
                    for b in ("gang", "group"):
                        fit["clap"][b] = "situational"
                        fit["kite"][b] = "unfit"
                # flex group-scale damage fits everywhere (the all-rounder)
            else:
                deep = "situational" if util_pts >= UTILITY_EXEMPT_MIN else "unfit"
                for s in STYLE_FIT_STYLES:
                    fit[s]["gang"] = "situational"
                    fit[s]["group"] = deep
            # clap_kite serves whichever half a weapon serves: its verdict
            # is the BEST of the weapon's clap and kite verdicts per band
            # (owner 2026-08-23: the hybrid fields bomb pieces AND kite
            # pieces). Overrides still win afterwards ('*' covers it).
            rank = {"fits": 0, "situational": 1, "unfit": 2}
            for b in STYLE_FIT_BANDS:
                best = min((fit["clap"][b], fit["kite"][b]),
                           key=lambda v: rank[v])
                fit["clap_kite"][b] = best

        # E-first for HEALERS too (owner ruling 2026-08-23 round 2: "it's
        # not which line but which weapon ... it should all be based on
        # what the weapon does and its effect"): a dedicated heal E that
        # heals a SINGLE ally does not scale to group play any more than
        # single-scale damage does — "1 hand holy is full healer but it's
        # not a good group healer for anything larger than 5 people. I
        # would use it at 3 people and very rarely at 5 but never above
        # that." Same ladder as the single-scale damage carrier:
        # situational at gang, unfit at group. Derived facts only — an
        # unknown heal scale never degrades anything (heal_scale semantics
        # in derive_economics; overrides below still win).
        ec = (econ or {}).get(key) or {}
        if (key in healers and ec.get("heal_scale") == "single"
                and ec.get("e_heal_points", 0) >= heal_dedicated_min):
            for s in STYLE_FIT_STYLES:
                fit[s]["gang"] = "situational"
                fit[s]["group"] = "unfit"

        # Non-stacking budget slots are EARNED (owner ruling 2026-08-25,
        # see E_DEBUFF_CAPS): a non-stacking-group member whose E carries
        # no real enemy-debuff tool demotes to situational at GROUP for
        # every style — never unfit (manual picks stay legitimate), never
        # below group band. Overrides below still win.
        nonstack = key in (nonstack_members or ())
        if nonstack and e_debuff_max < E_UTILITY_TOOL_MIN:
            for s in STYLE_FIT_STYLES:
                if fit[s]["group"] == "fits":
                    fit[s]["group"] = "situational"

        basis = "derived"
        ov = overrides.get(key)
        override_rec = None
        if ov:
            basis = "curated_override"
            override_rec = {"reason": (ov.get("reason") or "").strip(),
                            "source": (ov.get("source") or "").strip(),
                            "as_of": str(ov.get("as_of") or "")}
            if not (override_rec["reason"] and override_rec["source"]):
                problems.append(f"style_overrides: {key} needs reason + source")
            for s_key, bands in (ov.get("set") or {}).items():
                s_list = STYLE_FIT_STYLES if s_key == "*" else (s_key,)
                if s_key != "*" and s_key not in STYLE_FIT_STYLES:
                    problems.append(f"style_overrides: {key}: unknown style "
                                    f"'{s_key}'")
                    continue
                for b_key, verdict in (bands or {}).items():
                    b_list = STYLE_FIT_BANDS if b_key == "*" else (b_key,)
                    if b_key != "*" and b_key not in STYLE_FIT_BANDS:
                        problems.append(f"style_overrides: {key}: unknown "
                                        f"band '{b_key}'")
                        continue
                    if verdict not in STYLE_FIT_VERDICTS:
                        problems.append(f"style_overrides: {key}: unknown "
                                        f"verdict '{verdict}'")
                        continue
                    for s in s_list:
                        for b in b_list:
                            fit[s][b] = verdict

        w["style_fit"] = {"delivery": delivery, "damage_scale": scale,
                          "utility_carrier": utility_carrier, "fit": fit}
        rec = {"delivery": delivery, "damage_scale": scale,
               "utility_carrier": utility_carrier,
               "damage_pts": dmg_pts, "utility_pts": util_pts,
               "role_flexible": flexible, "attackrange": attackrange,
               "e_damage_spells": e_spells, "e_reach": e_reach,
               "e_damage_pts": e_dmg_pts, "e_utility_max": e_util_max,
               "weak_group_e": weak_group_e,
               "e_debuff_max": e_debuff_max, "nonstack_member": nonstack,
               "fit": fit, "basis": basis}
        if override_rec:
            rec["override"] = override_rec
        report[key] = rec
    for wk in sorted(overrides):
        if wk not in weapons:
            problems.append(f"style_overrides: unknown weapon {wk}")
    return report, problems


# ---------------------------------------------------------------------------
# Weapon economics + primary-healer derivation (owner rulings 2026-08-23,
# forge-quality blind round; config and the rulings' own words live in
# composition.yaml — `viability.cost_gate` and `primary_healer`).
#
# cost_tier reads the unique_name's line suffix — the game's own naming:
# ..._CRYSTAL crystal-artifact, ..._AVALON avalonian, the four faction
# artifact lines, everything else base. Only `crystal` is gated anywhere
# (regear economics); avalonian/artifact/base ship for display and audit.
# NOTE the suffix rule is safe against family names: Permafrost Prism is
# 2H_ICECRYSTAL_UNDEAD — "CRYSTAL" in the family, _UNDEAD the suffix.
#
# full_healer: a weapon whose E-slot bundle supplies >= e_heal_min summed
# heal points (owner: "the weapon needs to have high healing numbers on its
# e"). The E is combo-independent (E-first identity), so the flag is static.
COST_TIER_SUFFIXES = (("_CRYSTAL", "crystal"), ("_AVALON", "avalonian"),
                      ("_UNDEAD", "artifact"), ("_KEEPER", "artifact"),
                      ("_HELL", "artifact"), ("_MORGANA", "artifact"))
PRIMARY_HEAL_CAPS = ("heal_sustain", "heal_burst")


def load_heal_overrides():
    path = os.path.join(HERE, "heal_overrides.yaml")
    if not os.path.exists(path):
        return {}
    out = {}
    for e in _load_yaml(path):
        if isinstance(e, dict) and e.get("weapon") and e.get("spell"):
            out[(e["weapon"], e["spell"])] = e
    return out


def apply_resilience_penetration(weapons):
    """Stamp per-weapon `resil_pen` from pipeline/resilience_penetration.yaml
    (cited wiki table, post-Realm-Divided; a MELEE-ONLY stat — weapons
    absent from the table carry none, which the wiki states categorically
    for ranged/magic lines). Owner ruling 2026-08-25 wires it as a partial
    rebate on the Focus-Fire ST tax (engine `_eff`); both ports read the
    stamped field. Wiki rows outside the combat catalog are reported,
    never guessed."""
    path = os.path.join(HERE, "resilience_penetration.yaml")
    if not os.path.exists(path):
        return
    rows = (_load_yaml(path) or {}).get("rows") or []
    by_name = {}
    for k, w in weapons.items():
        dn = (w.get("display_name") or "").strip().lower()
        if dn and not w.get("removed"):
            by_name[dn] = k
    matched, unmatched = 0, []
    for r in rows:
        key = by_name.get(str(r.get("name", "")).strip().lower())
        if key is None:
            unmatched.append(str(r.get("name")))
            continue
        weapons[key]["resil_pen"] = float(r["pen"])
        matched += 1
    note = f"; not in catalog: {', '.join(unmatched)}" if unmatched else ""
    print(f"  resil_pen     : {matched} weapon(s) stamped{note}")


def derive_economics(weapons, composition, spell_index, overrides):
    """Stamp cost_tier + heal identity (heal_scale, full_healer) on every
    weapon. Returns (report, problems); problems block the release (a
    malformed override, or one naming a weapon/spell that is not that
    weapon's E heal).

    Heal identity is STRUCTURAL, E-first (owner ruling 2026-08-23 round 2:
    no per-weapon taste rules): the E bundle with the highest summed heal
    points names the heal spell; the spell's own area facts decide the
    scale (area -> group; facts without area -> single; no facts ->
    unknown, never inferred). heal_overrides.yaml corrects spells whose
    area lives in a landing/impact sub-effect the dumps do not surface —
    cited FACT corrections, the ranged_overrides.yaml pattern.
    full_healer — the healing-FOUNDATION flag the forge's primary_heal
    minima count — requires magnitude (e_heal_min) AND group scale."""
    ph = composition.get("primary_healer", {}) or {}
    e_min = ph.get("e_heal_min", 6)
    r_min = ph.get("group_min_radius", 3.0)
    t_min = ph.get("group_min_targets", 5)
    problems, used, report = [], set(), {}
    for e in overrides.values():
        if e.get("scale") not in ("group", "single"):
            problems.append(f"heal_overrides: {e.get('weapon')}: scale must "
                            "be group|single")
        if not ((e.get("reason") or "").strip()
                and (e.get("source") or "").strip()):
            problems.append(f"heal_overrides: {e.get('weapon')} needs "
                            "reason + source")
    for key, w in sorted(weapons.items()):
        tier = "base"
        for suf, t in COST_TIER_SUFFIXES:
            if key.endswith(suf):
                tier = t
                break
        lo = w.get("loadout") or {}
        names = lo.get("slot_names") or []
        slots = lo.get("slots") or []
        spells = lo.get("slot_spells") or []
        e_heal, heal_spell = 0, None
        for i, slot in enumerate(slots):
            if i >= len(names) or names[i] != "e":
                continue
            for j, bundle in enumerate(slot):
                h = sum(bundle.get(c, 0) for c in PRIMARY_HEAL_CAPS)
                if h > e_heal:
                    e_heal = h
                    heal_spell = (spells[i][j]
                                  if i < len(spells) and spells[i]
                                  and j < len(spells[i]) else None)
        if not slots:
            # flat-sheet fallback (illustrative entries without a loadout
            # decomposition): the flat map is all we can read; scale stays
            # unknown — never inferred
            caps = w.get("capabilities") or {}
            e_heal = max((caps.get(c, 0) for c in PRIMARY_HEAL_CAPS),
                         default=0)
        basis = "derived"
        if not e_heal:
            scale = "none"
        else:
            ov = overrides.get((key, heal_spell)) if heal_spell else None
            facts = (spell_index.get(heal_spell) or None) if heal_spell else None
            if ov:
                used.add((key, heal_spell))
                scale = ov["scale"]
                basis = "curated_override"
                report_ov = {"reason": (ov.get("reason") or "").strip(),
                             "source": (ov.get("source") or "").strip(),
                             "as_of": str(ov.get("as_of") or "")}
            elif not facts:
                scale = "unknown"
            else:
                radius = facts.get("radius")
                mts = facts.get("max_targets") or 0
                scale = ("group"
                         if ((radius is not None and float(radius) >= r_min)
                             or mts >= t_min) else "single")
        full = e_heal >= e_min and scale == "group"
        w["cost_tier"] = tier
        w["heal_scale"] = scale
        w["full_healer"] = full
        rec = {"cost_tier": tier, "e_heal_points": e_heal,
               "heal_spell": heal_spell, "heal_scale": scale,
               "full_healer": full, "basis": basis}
        if basis == "curated_override":
            rec["override"] = report_ov
        report[key] = rec
    for (wk, sid), _ov in sorted(overrides.items()):
        if (wk, sid) in used:
            continue
        if wk not in weapons:
            problems.append(f"heal_overrides: unknown weapon {wk}")
        else:
            problems.append(f"heal_overrides: {sid} is not {wk}'s E heal "
                            "spell")
    return report, problems


def load_templates(tune=None):
    templates, scoring, styles, mechanics, composition = {}, {}, {}, {}, {}
    for path in sorted(glob.glob(os.path.join(HERE, "templates", "*.yaml"))):
        doc = _load_yaml(path)
        if not isinstance(doc, dict):
            continue
        base = os.path.basename(path)
        if base == "scoring.yaml":
            scoring = doc
        elif base == "styles.yaml":
            styles = doc.get("styles", {})
        elif base == "mechanics.yaml":
            mechanics = doc
        elif base == "composition.yaml":
            composition = doc
        else:
            templates[doc["content"]] = doc
    # MASTERSHEET overrides (the expert's single control surface): scoring
    # and mechanics deep-merge; template overrides address one content's
    # requirement caps. Unknown keys fail the build — never silent.
    tune = tune or {}
    scoring = mastersheet.deep_merge(scoring, tune.get("scoring", {}))
    mechanics = mastersheet.deep_merge(mechanics, tune.get("mechanics", {}))
    for content, caps in (tune.get("templates") or {}).items():
        if content not in templates:
            sys.exit(f"MASTERSHEET.md tune:templates: unknown content "
                     f"'{content}' (known: {', '.join(sorted(templates))})")
        reqs = templates[content].setdefault("requirements", {})
        for cap, fields in (caps or {}).items():
            if cap not in reqs:
                sys.exit(f"MASTERSHEET.md tune:templates: {content} has no "
                         f"requirement '{cap}'")
            reqs[cap] = mastersheet.deep_merge(reqs[cap], fields or {})
    return templates, scoring, styles, mechanics, composition


def check_provenance(weapons, item_stats, stats_meta):
    """The fail-closed release gate (§A): verified snapshot chain + full
    curated-weapon coverage + internally consistent item bank. Returns a list
    of problems — empty means the release may proceed."""
    problems = verify_derived(sorted(PROVENANCE_INPUTS), PROVENANCE_INPUTS)
    if stats_meta.get("inconsistent"):
        problems.append(
            f"item_stats.json records {len(stats_meta['inconsistent'])} "
            "cross-tier slot/category inconsistencies — fix upstream")
    missing_stats = sorted(
        k for k, w in weapons.items()
        if w["status"] == "curated" and w["in_game_data"]
        and not w.get("removed") and k not in item_stats)
    if missing_stats:
        problems.append(
            f"{len(missing_stats)} curated weapon(s) missing from the item "
            f"stats bank: {missing_stats[:8]}")
    return problems


def run_lint():
    """Run the evidence lint over curated sheets only. Illustrative sheets are
    deliberately excluded — they have no evidence and would always fail."""
    paths = sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml")))
    if not paths:
        return True, "no curated sheets to lint"
    proc = subprocess.run([sys.executable, os.path.join(HERE, "evidence_lint.py")] + paths,
                          capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--skip-lint", action="store_true")
    ap.add_argument("--skip-provenance", action="store_true",
                    help="dev escape hatch: report provenance problems but "
                         "exit 0 (release_clean still goes false)")
    args = ap.parse_args()

    # MASTERSHEET.md — the expert's single control surface. Parse errors and
    # unknown keys fail the build (never silent).
    try:
        tune = mastersheet.load()
    except ValueError as exc:
        sys.exit(str(exc))
    for line in mastersheet.describe(tune):
        print(f"  mastersheet   : {line}")

    weapon_lines = load_weapon_lines()
    weapons = load_sheets(weapon_lines, tune.get("sheets"))
    templates, scoring, styles, mechanics, composition = load_templates(tune)
    stats_path = os.path.join(OUT, "item_stats.json")
    item_stats, stats_meta = {}, {}
    if os.path.exists(stats_path):
        with open(stats_path, encoding="utf-8") as f:
            stats_doc = json.load(f)
        item_stats = stats_doc.get("items", {})
        stats_meta = stats_doc.get("_meta", {})
    with open(os.path.join(OUT, "spell_index.json"), encoding="utf-8") as f:
        spell_index = json.load(f)
    interactions = {}
    inter_path = os.path.join(OUT, "interactions.json")
    if os.path.exists(inter_path):
        with open(inter_path, encoding="utf-8") as f:
            interactions = json.load(f).get("spells", {})
    # Gear layer (full-build members). Loaded before delivery stamping so
    # gear items get cap_delivery from their ability spells too.
    gear_spells, gear_lines_db = {}, {}
    for name, target in (("gear_spells.json", "gs"), ("gear_lines.json", "gl")):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                if target == "gs":
                    gear_spells = json.load(f)
                else:
                    gear_lines_db = json.load(f)
    gear = load_gear_sheets(gear_lines_db, gear_spells)
    # Build-stat channel: copy each gear item's combat-relevant base stats
    # from the item bank (T4-flat reference; IP scales them in game). The
    # engine turns absolute defense into tankiness units and % stats into
    # capability multipliers (mechanics.yaml build_stats).
    BUILD_STAT_KEYS = ("physicalarmor", "magicresistance",
                       "crowdcontrolresistance", "physicalspelldamagebonus",
                       "magicspelldamagebonus", "physicalattackdamagebonus",
                       "magicattackdamagebonus", "healbonus")
    for gk, g in gear.items():
        bank = (item_stats.get(gk) or {}).get("stats") or {}
        g["stats"] = {s: bank[s] for s in BUILD_STAT_KEYS if bank.get(s)}

    # Per-capability DELIVERY facts (2026-08-20, geometric-AoE step 3):
    # from each capability's evidence spell, the structural area geometry and
    # the game's own per-effect escalation factors (parse_dumps v4). Absent =
    # the spell tree carries no area — "unknown", never "not AoE". This is
    # display + physics INPUT data; the engine's geometric transform (step 1)
    # is what turns it into supply scaling.
    for w in list(weapons.values()) + list(gear.values()):
        delivery = {}
        for cap, spells in (w.get("evidence") or {}).items():
            for sid in spells:
                sp = spell_index.get(sid)
                if not sp:
                    continue
                d = {}
                if sp.get("radius") is not None:
                    d["radius"] = sp["radius"]
                if sp.get("max_targets") is not None:
                    d["max_targets"] = sp["max_targets"]
                if sp.get("escalation"):
                    d["escalation"] = sp["escalation"]
                if d:
                    d["spell"] = sid
                    delivery[cap] = d
                    break                      # one evidence spell per cap
        if delivery:
            w["cap_delivery"] = delivery

    n_ranged, ranged_report, ranged_problems = derive_ranged_presence(
        weapons, spell_index, load_ranged_overrides())
    with open(os.path.join(OUT, "ranged_presence_report.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": {
            "rule": (f"bundle claims {AOE_CLAIM} (curated, evidence-linted) "
                     f"AND its spell is {'/'.join(RANGED_DELIVERY)}-delivered "
                     f"with cast_range >= {RANGED_MIN_CASTRANGE}; "
                     "ranged_overrides.yaml wins with citation; missing "
                     "structural facts = unknown, never inferred"),
            "granted": sorted(k for k, r in ranged_report.items()
                              if r["status"] == "granted"),
            "unknown": sorted(k for k, r in ranged_report.items()
                              if r["status"] == "unknown"),
        }, "weapons": ranged_report}, f, indent=1, sort_keys=True)

    # Derived non-stacking groups (owner ruling 2026-08-24): membership
    # computed from the sheets per composition.yaml `derived_groups` —
    # structural, never a hand list — appended to the groups the forge
    # already enforces. Both engine ports read groups from the dataset, so
    # no engine change is involved.
    for g_name, g_cfg in sorted((composition.get("derived_groups") or {})
                                .items()):
        members, rules = set(), []
        cap = g_cfg.get("capability")
        if cap:
            min_pts = g_cfg.get("min_points", 4)
            members |= {k for k, w in weapons.items()
                        if (w.get("capabilities") or {}).get(cap, 0) >= min_pts
                        and not w.get("removed")}
            rules.append(f"{cap} >= {min_pts} (flat sheet points)")
        ev_spells = g_cfg.get("evidence_spells") or []
        if ev_spells:
            for k, w in weapons.items():
                if w.get("removed"):
                    continue
                kit = {s for sl in (w.get("loadout") or {})
                       .get("slot_spells", []) for s in (sl or [])}
                if kit & set(ev_spells):
                    members.add(k)
            rules.append("kit cites " + "/".join(ev_spells))
        members = sorted(members)
        # evidence_spells membership == a shared NON-STACKING kit (the
        # pool a verified count-once interaction record prices): flagged
        # so the style-fit derivation and the engines' generation gate can
        # require such a slot to be EARNED (owner ruling 2026-08-25).
        composition.setdefault("groups", []).append({
            "name": g_name, "max": g_cfg.get("max", 2), "weapons": members,
            "derived": True, "nonstacking": bool(ev_spells),
            "rule": "; ".join(rules)})
        print(f"  derived group : {g_name} (max {g_cfg.get('max', 2)}): "
              + ", ".join(members))

    apply_resilience_penetration(weapons)
    econ_report, econ_problems = derive_economics(
        weapons, composition, spell_index, load_heal_overrides())
    nonstack_members = {w for g in composition.get("groups", []) or []
                        if g.get("nonstacking") for w in g.get("weapons", [])}
    fit_report, fit_problems = derive_style_fit(
        weapons, spell_index, item_stats, scoring.get("role_sets") or {},
        load_style_overrides(), econ_report,
        (composition.get("primary_healer", {}) or {})
        .get("e_heal_dedicated_min", 4), nonstack_members)
    # MetaBattle cross-check (MECHANICS_TODO Q15): weapons real ZvZ builds
    # field must not derive group-band all-unfit — disagreements are the
    # owner's review queue, never silent fixes.
    review_queue = []
    mb_path = os.path.join(HERE, os.pardir, "data", "published_builds",
                           "metabattle_zvz.yaml")
    if os.path.exists(mb_path):
        mb = _load_yaml(mb_path) or {}
        mb_weapons = {b.get("weapon") for b in mb.get("builds", [])
                      if b.get("weapon")}
        for wk in sorted(mb_weapons & set(weapons)):
            f = weapons[wk]["style_fit"]["fit"]
            if all(f[s]["group"] == "unfit" for s in STYLE_FIT_STYLES):
                review_queue.append(wk)
    with open(os.path.join(OUT, "style_fit_report.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": {
            "rule": ("E-first identity: delivery side from autoattack range "
                     f"(>= {RANGED_MIN_CASTRANGE} ranged) or the E damage's "
                     "own reach (flex); damage scale from the E's burst_aoe "
                     "claim; healers/frontline/support style-flexible; "
                     "trio fits everything; style_overrides.yaml wins with "
                     "citation. DESCRIPTIVE - no scoring path reads this."),
            "bands": {"trio": "<=3", "gang": "4-9", "group": "10+"},
            "delivery_counts": {
                d: sum(1 for r in fit_report.values()
                       if r["delivery"] == d)
                for d in ("melee", "flex", "ranged")},
            "overridden": sorted(k for k, r in fit_report.items()
                                 if r["basis"] == "curated_override"),
            "metabattle_review_queue": review_queue,
        }, "weapons": fit_report}, f, indent=1, sort_keys=True)

    with open(os.path.join(OUT, "economics_report.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": {
            "rule": ("cost_tier from the unique_name's line suffix "
                     "(crystal/avalonian/artifact/base; only crystal is "
                     "gated — viability.cost_gate). full_healer (healing "
                     "FOUNDATION) requires an E bundle with >= "
                     "primary_healer.e_heal_min summed heal points AND a "
                     "GROUP-scale heal (the spell's own radius/max_targets "
                     "facts; heal_overrides.yaml corrects sub-effect areas "
                     "the dumps do not surface, with citation; unknown "
                     "never grants). Single-scale dedicated heal Es grade "
                     "gang situational / group unfit in style_fit — the "
                     "E-first ladder. Owner rulings 2026-08-23."),
            "crystal": sorted(k for k, r in econ_report.items()
                              if r["cost_tier"] == "crystal"),
            "full_healers": sorted(k for k, r in econ_report.items()
                                   if r["full_healer"]),
            "single_scale_healers": sorted(
                k for k, r in econ_report.items()
                if r["heal_scale"] == "single" and r["e_heal_points"] >= 4),
            "unknown_heal_scale": sorted(
                k for k, r in econ_report.items()
                if r["heal_scale"] == "unknown"),
            "overridden": sorted(k for k, r in econ_report.items()
                                 if r["basis"] == "curated_override"),
        }, "weapons": econ_report}, f, indent=1, sort_keys=True)

    provenance_problems = check_provenance(weapons, item_stats, stats_meta)
    provenance_problems += ranged_problems
    provenance_problems += fit_problems
    provenance_problems += econ_problems
    # every derived scoring capability must carry evidence (§B/H.6)
    for k, w in sorted(weapons.items()):
        if (w["capabilities"].get("ranged_presence")
                and not w.get("evidence", {}).get("ranged_presence")):
            provenance_problems.append(
                f"{k}: ranged_presence without an evidence record")
    manifest = load_manifest() or {}
    sources = manifest.get("sources", {})

    lint_ok, lint_out = (True, "skipped") if args.skip_lint else run_lint()

    curated = sorted(k for k, w in weapons.items() if w["status"] == "curated")
    illustrative = sorted(k for k, w in weapons.items() if w["status"] == "illustrative")
    unknown = sorted(k for k, w in weapons.items() if not w["in_game_data"])

    provenance_ok = not provenance_problems
    dataset = {
        "_meta": {
            "version": args.version,
            "weapons_total": len(weapons),
            "weapons_curated": len(curated),
            "weapons_illustrative": len(illustrative),
            "templates": sorted(templates),
            "lint_passed": lint_ok,
            "release_clean": bool(lint_ok and provenance_ok
                                  and not illustrative and not unknown),
            "note": ("NOT A RELEASE — contains illustrative placeholder sheets."
                     if illustrative else
                     "NOT A RELEASE — provenance verification failed."
                     if not provenance_ok else "release candidate"),
            "illustrative_weapons": illustrative,
            "unknown_to_game_data": unknown,
            # MASTERSHEET.md override layer — what the expert's control
            # surface changed in THIS build (human summary; the values
            # themselves are already merged into the sections below).
            "mastersheet": mastersheet.describe(tune),
            # Source provenance (§A): the one pinned snapshot every game-data
            # input came from, plus the verified hash of each input. No fetch
            # timestamp here — the dataset must be deterministic; timestamps
            # live in out/source_manifest.json.
            "provenance": {
                "source_repository": sources.get("repository"),
                "source_commit": sources.get("commit"),
                "commit_timestamp": sources.get("commit_timestamp"),
                "environment": sources.get("environment"),
                "game_patch": sources.get("game_patch"),
                "inputs": {name: (manifest.get("derived", {})
                                  .get(name, {}).get("sha256"))
                           for name in sorted(PROVENANCE_INPUTS)},
                "verified": provenance_ok,
                "problems": provenance_problems,
            },
        },
        "weapons": weapons,
        # Gear capability sheets (sheets/gear/) — the full-build member
        # model's non-weapon slots. The engine composes a person's
        # contribution as weapon loadout + every gear slot's contribution.
        "gear": gear,
        # Item stats bank (fetch_item_stats.py) — the game's own numbers for
        # every weapon and worn item. Optional so a checkout without it still
        # builds. REFERENCE DATA: nothing in the scoring path reads it, the
        # same rule gear capabilities follow. It is here so the engine and the
        # dossier read one source instead of two.
        "item_stats": item_stats,
        # PvP interaction records (build_interactions.py), spell-keyed. The
        # ONLY scoring coupling is verified `nonstacking_caps` (party supply
        # counts that spell's caps once across members equipping it);
        # everything else is dossier/analysis display. unknown never scores.
        "interactions": interactions,
        "templates": templates,
        "scoring": scoring,
        "styles": styles,
        "mechanics": mechanics,
        # Composition constraints + viability + size physics (composition.yaml)
        # — what the FORGE may generate; never a bar to scoring a manual party.
        "composition": composition,
        # Guild-approved builds (MASTERSHEET.md tune:guild_builds) — the
        # expert's guild guideline layer, shipped VERBATIM for display and
        # future prior/validation layers. A guideline, never a hard rule:
        # nothing in the scoring path reads it.
        "guild_builds": tune.get("guild_builds") or {},
    }

    os.makedirs(OUT, exist_ok=True)
    for name in (f"dataset-{args.version}.json", "dataset-latest.json"):
        with open(os.path.join(OUT, name), "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump(dataset, f, indent=1, sort_keys=True)

    print(f"dataset v{args.version}: {len(weapons)} weapons "
          f"({len(curated)} curated, {len(illustrative)} illustrative), "
          f"{len(templates)} template(s)")
    print(f"  evidence lint : {'PASS' if lint_ok else 'FAIL'}")
    if not lint_ok:
        print("   " + lint_out.replace("\n", "\n   "))
    n_unknown_rp = sum(1 for r in ranged_report.values()
                       if r["status"] == "unknown")
    print(f"  ranged_presence: {n_ranged} bundle grant(s) across "
          f"{len([r for r in ranged_report.values() if r['status'] == 'granted'])} "
          f"weapon(s), {n_unknown_rp} unknown -> out/ranged_presence_report.json")
    print(f"  provenance    : {'VERIFIED' if provenance_ok else 'FAIL'}"
          f"  (snapshot {str(sources.get('commit'))[:12]})")
    for p in provenance_problems:
        print(f"    PROBLEM {p}")
    if unknown:
        print(f"  NOT in game data: {unknown}")
    blocked_by = ("" if dataset["_meta"]["release_clean"] else
                  f"  (blocked by "
                  f"{'provenance; ' if not provenance_ok else ''}"
                  f"{len(illustrative)} illustrative sheet(s))")
    print(f"  release_clean : {dataset['_meta']['release_clean']}{blocked_by}")
    print(f"  wrote out/dataset-{args.version}.json + out/dataset-latest.json")
    if not lint_ok:
        return 1
    if provenance_problems and not args.skip_provenance:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
