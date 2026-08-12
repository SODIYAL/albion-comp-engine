#!/usr/bin/env python3
"""
Enumerate every combat effect the game defines, from the structured spell data.

WHY: capability scores are only as good as the list of effects we know exist.
That list has so far been 13 hand-written prose regexes in parse_dumps.py, and
we have twice found gaps by accident (the knockback phrasing bug; anti_zone).
This script derives the vocabulary from the data instead of inventing it, so
the gaps are enumerated up front.

TWO LAYERS, deliberately not collapsed:
  effects       game mechanics (~40 combat-relevant)  -> the EVIDENCE layer
  capabilities  comp-level needs (27, design doc §2.2) -> the SCORING layer
The mapping between them is many-to-many (a stun feeds both `peel` and
`clump_create` depending on direction) and it is a human judgement. Keeping
them separate is what lets the capability taxonomy survive balance patches:
a patch changes effects, not what a composition needs.

TWO SOURCES, because neither is complete:
  structured nodes  high precision, incomplete — `removeactiveeffects` with
                    target=enemy/category=buff appears only twice, yet purge is
                    common (Battle Howl), so removals are often indirect
  prose regex       broader recall, lower precision — it is what caught Battle
                    Howl's purge in the first place
The catalogue records both and flags disagreements for human review.

Effects resolve TRANSITIVELY through `applyspell`: PULSINGHEAL itself has no
knockback node — it applies PULSINGHEAL_KNOCKBACK, which does.

Usage:  py -3 pipeline/effect_catalogue.py <ao-bin-dumps path>
        py -3 pipeline/effect_catalogue.py <path> --report
"""
import json, os, re, sys, argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
from parse_dumps import FLAG_PATTERNS, load  # reuse the prose layer verbatim

MAX_DEPTH = 3          # applyspell recursion limit
APPLY_KEYS = ("applyspell", "pulsingspell", "channelingspell", "spelleffectarea")

# CONDITION nodes carry a PREDICATE, not an effect. `IfTargetCCEffect @type=stun`
# means "if the target is stunned", and `IfTargetType @type=player` means "only
# against players". Reading their @type as an effect credited every cleanse with
# a stun, and invented bogus "player"/"mob" effects. Never descend into them.
CONDITION_PREFIX = re.compile(r"^(if|not|or|and)", re.I)

# IMMUNITY / diminishing-returns contexts name the effect they DEFEND AGAINST.
# `cceffectimmunity @type=stun` is stun immunity — the opposite of applying a
# stun. Prefix them so they can never be mistaken for the effect itself.
GUARD_NODES = {
    "cceffectimmunity": "immunity",
    "spellimmunity": "immunity",
    "setcrowdcontroldiminishingreturns": "dr",
}

# @type values that are not effects at all:
#   onHit / onSuccessfullHit / onKillOrKnockdown  -> event TRIGGERS
#   T4_MOB_...                                    -> summoned-mob references
#   BEAR / PANTHER / IMP ...                      -> shapeshift FORM names
#     (detected structurally: SHAPESHIFT_<NAME> exists as a spell)
NON_EFFECT_TYPE = re.compile(r"^(on[A-Z]|T\d+_MOB_)")

# Structured nodes that ARE a combat mechanic by their mere presence.
MECHANIC_NODES = {
    "stun": "stun", "root": "root", "silence": "silence",
    "knockback": "knockback", "dash": "dash", "invincibility": "invincibility",
    "spellimmunity": "spell_immunity", "cceffectimmunity": "cc_immunity",
    "notinterruptible": "uninterruptible", "aura": "aura",
    "invisibility": "invisibility", "forcedmovement": "forced_movement",
}

# @type values are the buff/debuff vocabulary. Classify them, don't guess.
ECONOMY_PAT = re.compile(
    r"fishing|crafting|craft|gathering|gather|farm|loot|fame|resource|silver|"
    r"tax|vanity|emote|journal|destiny|maxload|island|hideout|siegebanner|"
    r"track|mount|foodbuff|repair|nutrition|premium|learningpoint", re.I)
COMBAT_PAT = re.compile(
    r"damage|defense|defence|resist|armor|armour|speed|crowdcontrol|\bcc\b|ccr|"
    r"stun|root|silence|slow|heal|energy|hitpoints|cooldown|casttime|attack|"
    r"invisib|immunit|forcedmovement|threat|shield|spellpower|abilitypower|"
    r"range|regeneration|lifesteal|pierce|penetration", re.I)

# Proposed effect -> capability map. UNMAPPED entries are the whole point of
# this script: they are the anti_zone-class gaps still hiding in the data.
# Nothing here is authoritative until a domain expert signs it off.
EFFECT_TO_CAPABILITY = {
    "stun": "stun", "root": "root", "silence": "silence",
    "knockback": "knockback_displace", "forced_movement": "knockback_displace",
    "slow": "slow", "movespeedbonus-": "slow", "movespeedbonus+": "mobility",
    "dash": "mobility",
    "healmodifier-": "heal_reduction", "healbonus-": "heal_reduction",
    "physicalarmor-": "resist_shred", "magicresistance-": "resist_shred",
    "bonusdefensevsplayers-": "resist_shred",
    "physicalarmor+": "tankiness", "magicresistance+": "tankiness",
    "bonusdefensevsplayers+": "tankiness", "hitpointsmaxbonus+": "tankiness",
    "crowdcontrolresistance+": "tankiness",
    "hitpointsregenerationbonus+": "self_sustain",
    "healbonus+": "heal_sustain", "healmodifier+": "buff_allies",
    "physicalattackdamagebonus+": "buff_allies",
    "magicattackdamagebonus+": "buff_allies",
    "attackspeedbonus+": "buff_allies",
    "energycostreduction+": "energy_drain", "energyregenerationbonus-": "energy_drain",
    "invisibility": "disengage", "invincibility": "tankiness",
    "spell_immunity": "cleanse", "cc_immunity": "peel",
}


# Plain-language definition of the MECHANIC, so a reviewer never has to infer
# what an effect is from an example spell's prose. `%s` receives "Increases" or
# "Reduces" for +/- variants.
DEFINITIONS = {
    "stun":              "Stuns the target — no actions or movement for the duration.",
    "root":              "Roots the target in place. It can still act, but cannot move.",
    "silence":           "Silences the target — it can still move, but cannot cast abilities.",
    "knockback":         "Physically displaces the target. Check WHO moves — several spells knock the CASTER back rather than the enemy.",
    "forced_movement":   "Moves a character against their will (pull, push, throw). Direction and who moves both matter.",
    "dash":              "Moves the caster rapidly — a gap-close or an escape depending on use.",
    "invisibility":      "Makes the target invisible.",
    "invincibility":     "Target takes no damage for the duration.",
    "uninterruptible":   "Casts and channels cannot be interrupted.",
    "aura":              "A persistent area around the caster that applies an effect while it lasts.",
    "movespeedbonus":    "%s movement speed. Negative is a slow; positive is a speed buff.",
    "physicalarmor":     "%s physical damage resistance. Negative on an enemy is armour shred.",
    "magicresistance":   "%s magic damage resistance. Negative on an enemy is resistance shred.",
    "bonusdefensevsplayers": "%s damage resistance against PLAYERS specifically.",
    "bonusdefensevsmobs":    "%s damage resistance against MOBS only — PvE, irrelevant to PvP comps.",
    "crowdcontrolresistance": "%s resistance to crowd control. Negative on an enemy makes your CC land harder.",
    "hitpointsmaxbonus": "%s maximum health.",
    "hitpointsregenerationbonus": "%s health regeneration over time.",
    "healmodifier":      "%s healing the target RECEIVES. Negative on an enemy is healing reduction.",
    "healbonus":         "%s healing the target DEALS.",
    "physicalattackdamagebonus": "%s physical auto-attack damage.",
    "magicattackdamagebonus":    "%s magic auto-attack damage.",
    "physicalspelldamagebonus":  "%s physical ability damage.",
    "magicspelldamagebonus":     "%s magic ability damage.",
    "bonusdamagevsplayers": "%s damage dealt to PLAYERS specifically.",
    "bonusdamagevsmobs":    "%s damage dealt to MOBS only — PvE.",
    "attackspeedbonus":  "%s auto-attack speed.",
    "attackrangebonus":  "%s auto-attack range.",
    "magiccooldownreduction": "%s ability cooldown recovery.",
    "magiccasttimereduction": "%s cast speed.",
    "energycostreduction":    "%s energy cost of abilities.",
    "energyregenerationbonus": "%s energy regeneration.",
    "threatbonus":       "%s threat generated against mobs — PvE taunt mechanic.",
    "bonusccdurationvsplayers": "%s duration of crowd control you apply to players.",
    "bonusccrvsplayers": "%s crowd-control resistance against players.",
    "bonusccdurationvsmobs": "%s duration of crowd control you apply to MOBS only — PvE.",
    "focusfireprotectionpenetration": "%s ability to pierce focus-fire protection (the damage falloff protecting an already-focused target).",
}
REMOVAL_DEFS = {
    "buff":              "Strips beneficial buffs off the target. This is purge.",
    "crowdcontrol":      "Removes crowd-control effects. On an ally this is cleanse.",
    "debuff":            "Removes debuffs. On an ally this is cleanse.",
    "movementbuff":      "Strips movement buffs (sprint, speed) off the target — anti-escape.",
    "invisibility":      "Reveals invisible targets.",
    "buff_damageshield": "Strips damage shields off the target.",
    "heal":              "Removes heal-over-time effects.",
    "damage":            "Removes damage-over-time effects.",
    "instant":           "Removes an instant-category effect.",
    "foodbuff":          "Removes food buffs — non-combat.",
    "cape_cooldown":     "Resets or removes cape cooldown — utility, not combat.",
    "forcedmovement":    "Cancels forced movement already in flight.",
}


def define(key):
    base = re.sub(r"[+-]$", "", key)
    sign = key[-1] if key[-1] in "+-" else ""
    if base.startswith("remove:"):
        cat = base.split(":", 1)[1]
        return REMOVAL_DEFS.get(cat, f"Removes effects of category '{cat}'.")
    for guard, label in (("immunity:", "Grants IMMUNITY to"),
                         ("dr:", "Applies diminishing returns to")):
        if base.startswith(guard):
            what = re.sub(r"^DR", "", base.split(":", 1)[1])
            return (f"{label} {what}. This is protection AGAINST the effect — "
                    f"never evidence that the weapon applies it.")
    d = DEFINITIONS.get(base)
    if not d:
        return ""
    return d % ("Reduces" if sign == "-" else "Increases") if "%s" in d else d


def spell_registry(dump_dir):
    root = load(os.path.join(dump_dir, "spells.json"))["spells"]
    reg = {}
    for group in ("activespell", "passivespell", "togglespell"):
        entries = root.get(group, [])
        for s in (entries if isinstance(entries, list) else [entries]):
            if s.get("@uniquename"):
                reg[s["@uniquename"]] = s
    return reg


DIRECTION_OF = {
    "enemy": ("enemy",), "enemyplayers": ("enemy",), "enemymobs": ("enemy",),
    "enemyunmounted": ("enemy",),
    "self": ("self",),
    "friendall": ("ally",), "friendother": ("ally",), "friendotherplayers": ("ally",),
    "friendallunmounted": ("ally",), "friendfaction": ("ally",), "friendallmobs": ("ally",),
}


def direction_of(target):
    """Map a raw @target onto enemy/ally/self. Ambiguous targets ('all', '?')
    expand to every direction: the map yields CANDIDATE capabilities, so being
    permissive here costs nothing while being wrong would silently drop real
    ones."""
    if target in DIRECTION_OF:
        return DIRECTION_OF[target]
    return ("enemy", "ally", "self")


def classify(name):
    if ECONOMY_PAT.search(name):
        return "economy"
    if COMBAT_PAT.search(name):
        return "combat"
    return "unclear"


def sign_of(node):
    """+ / - / '' — sign carries the meaning: negative movespeedbonus is a slow,
    negative healmodifier is heal reduction, negative armor is a shred."""
    for key in ("@value", "@change", "@totalchange"):
        v = node.get(key)
        if v is None:
            continue
        try:
            f = float(v)
        except ValueError:
            continue
        if f < 0:
            return "-"
        if f > 0:
            return "+"
    return ""


def direct_effects(spell, forms=frozenset()):
    """Effects present in THIS spell node (no applyspell recursion)."""
    found = set()

    def walk(node, depth=0, guard=None):
        if not isinstance(node, dict) or depth > 4:
            return
        for key, val in node.items():
            if key.startswith("@"):
                continue
            if CONDITION_PREFIX.match(key):
                continue                      # predicate, not an effect
            g = GUARD_NODES.get(key, guard)   # inherit guard into children
            for item in (val if isinstance(val, list) else [val]):
                if not isinstance(item, dict):
                    continue
                if key in MECHANIC_NODES and not g:
                    found.add((MECHANIC_NODES[key], "", item.get("@target", "?")))
                if key == "removeactiveeffects":
                    found.add((f"remove:{item.get('@category', '?')}",
                               "", item.get("@target", "?")))
                t = item.get("@type")
                if t and not NON_EFFECT_TYPE.match(t) and t not in forms:
                    name = f"{g}:{t}" if g else t
                    sign = "" if g else sign_of(item)
                    found.add((name, sign, item.get("@target", "?")))
                walk(item, depth + 1, g)

    walk(spell)
    return found


def resolve_effects(sid, reg, depth=0, seen=None, forms=frozenset()):
    """Effects of a spell INCLUDING those of spells it applies."""
    seen = seen if seen is not None else set()
    if sid in seen or depth > MAX_DEPTH or sid not in reg:
        return set()
    seen.add(sid)
    spell = reg[sid]
    found = set(direct_effects(spell, forms))

    def collect_refs(node, d=0):
        """Any attribute whose value names a real spell is a reference.

        An allowlist of node types and attribute names missed real links:
        DIVINE_JUMP chains its enemy knockback through `dash @endeffect`, not
        `applyspell @spell`, so Hallowfall looked like it had no enemy
        displacement at all. Matching against the registry catches every
        linking convention the data uses, present and future."""
        refs = []
        if not isinstance(node, dict) or d > 4:
            return refs
        for key, val in node.items():
            if key.startswith("@"):
                if isinstance(val, str) and val in reg:
                    refs.append(val)
                continue
            for item in (val if isinstance(val, list) else [val]):
                if isinstance(item, dict):
                    refs.extend(collect_refs(item, d + 1))
        return refs

    for ref in collect_refs(spell):
        found |= resolve_effects(ref, reg, depth + 1, seen, forms)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_dir")
    ap.add_argument("--report", action="store_true", help="print the gap report")
    args = ap.parse_args()

    reg = spell_registry(args.dump_dir)
    # BEAR, PANTHER, IMP ... are transformation FORM names, not effects.
    # Detected structurally: SHAPESHIFT_<NAME> exists as a spell.
    forms = frozenset(k[len('SHAPESHIFT_'):] for k in reg
                      if k.startswith('SHAPESHIFT_'))
    weapon_lines = json.load(open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8"))
    spell_index = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))

    weapon_spells = {s for L in weapon_lines.values()
                     for slot in L["spells"].values() for s in slot}

    effects = defaultdict(lambda: {"occurrences": 0, "targets": defaultdict(int),
                                   "example_spells": [], "direct_spells": [],
                                   "via_spells": [], "weapon_lines": set()})
    spell_effects, spell_direct = {}, {}

    for sid in reg:
        for name, sign, tgt in resolve_effects(sid, reg, forms=forms):
            key = f"{name}{sign}"
            e = effects[key]
            e["occurrences"] += 1
            e["targets"][tgt] += 1
            if len(e["example_spells"]) < 6:
                e["example_spells"].append(sid)
        if sid in weapon_spells:
            direct_keys = {f"{n}{sg}" for n, sg, _ in direct_effects(reg[sid], forms)}
            rows = {}
            for n, sg, tgt in resolve_effects(sid, reg, forms=forms):
                k = f"{n}{sg}"
                rows.setdefault(k, {"effect": k, "targets": set(), "direct": k in direct_keys})
                rows[k]["targets"].add(tgt)
            spell_effects[sid] = [
                {"effect": r["effect"], "direct": r["direct"],
                 "targets": sorted(r["targets"]),
                 "dirs": sorted({d for t in r["targets"] for d in direction_of(t)})}
                for r in sorted(rows.values(), key=lambda r: r["effect"])]
            spell_direct[sid] = sorted(direct_keys)

    # An example is only illustrative if the effect is DIRECT on that spell.
    # Inherited-via-applyspell examples are what made the `stun` row show a
    # cleanse's description.
    for sid, entries in spell_effects.items():
        direct = set(spell_direct.get(sid, []))
        for key in [e["effect"] for e in entries]:
            e = effects[key]
            bucket = "direct_spells" if key in direct else "via_spells"
            if len(e[bucket]) < 8:
                e[bucket].append(sid)
    for wkey, line in weapon_lines.items():
        for slot_ids in line["spells"].values():
            for sid in slot_ids:
                for entry in spell_effects.get(sid, []):
                    effects[entry["effect"]]["weapon_lines"].add(wkey)

    # which prose flag (if any) currently detects this effect
    prose_for = {}
    for key in effects:
        base = re.sub(r"[+-]$", "", key)
        hits = [f for f in FLAG_PATTERNS if f.lower() in base.lower()
                or base.lower() in f.lower()]
        prose_for[key] = hits[0] if hits else None

    out = {}
    for key, e in effects.items():
        base = re.sub(r"[+-]$", "", key)
        cls = ("removal" if base.startswith("remove:")
               else "guard" if base.startswith(("immunity:", "dr:"))
               else classify(base))
        out[key] = {
            "class": cls,
            "definition": define(key),
            "occurrences": e["occurrences"],
            "targets": dict(sorted(e["targets"].items(), key=lambda kv: -kv[1])),
            "example_spells": e["example_spells"],
            "direct_spells": e["direct_spells"],
            "via_spells": e["via_spells"],
            "weapon_lines": sorted(e["weapon_lines"]),
            "weapon_line_count": len(e["weapon_lines"]),
            "prose_flag": prose_for[key],
            "capability": EFFECT_TO_CAPABILITY.get(key),
        }

    combat_on_weapons = {k: v for k, v in out.items()
                         if v["weapon_line_count"] > 0 and v["class"] in ("combat", "removal")}
    gaps = {k: v for k, v in combat_on_weapons.items() if not v["capability"]}
    no_prose = {k: v for k, v in combat_on_weapons.items() if not v["prose_flag"]}
    unclear = {k: v for k, v in out.items()
               if v["class"] == "unclear" and v["weapon_line_count"] > 0}

    catalogue = {
        "_meta": {
            "spells_scanned": len(reg),
            "weapon_equippable_spells": len(weapon_spells),
            "distinct_effects": len(out),
            "combat_effects_on_weapons": len(combat_on_weapons),
            "unmapped_to_capability": len(gaps),
            "no_prose_flag": len(no_prose),
            "needs_classification": len(unclear),
            "note": ("EFFECT_TO_CAPABILITY is a PROPOSAL, not authoritative. "
                     "Every mapping needs domain sign-off before it drives scoring."),
        },
        "effects": dict(sorted(out.items(), key=lambda kv: -kv[1]["weapon_line_count"])),
        "spell_effects": spell_effects,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "effect_catalogue.json"), "w", encoding="utf-8") as f:
        json.dump(catalogue, f, indent=1, sort_keys=True)

    m = catalogue["_meta"]
    print(f"scanned {m['spells_scanned']} spells "
          f"({m['weapon_equippable_spells']} weapon-equippable)")
    print(f"distinct effects: {m['distinct_effects']}   "
          f"combat effects reachable from weapons: {m['combat_effects_on_weapons']}")
    print(f"  UNMAPPED to any capability : {m['unmapped_to_capability']}")
    print(f"  no prose flag detects them : {m['no_prose_flag']}")
    print(f"  need combat/economy call   : {m['needs_classification']}")
    print(f"wrote out/effect_catalogue.json")

    if args.report:
        def show(title, d, n=28):
            print(f"\n{'='*94}\n{title}\n{'='*94}")
            rows = sorted(d.items(), key=lambda kv: -kv[1]["weapon_line_count"])[:n]
            for k, v in rows:
                tg = ",".join(list(v["targets"])[:3])
                print(f"  {k:<34}{v['weapon_line_count']:>4} lines  "
                      f"prose={str(v['prose_flag']):<14}cap={str(v['capability']):<20}[{tg}]")
                print(f"      e.g. {', '.join(v['weapon_spells'][:4]) or '-'}")

        show("GAPS — combat effects on weapons with NO capability mapping", gaps)
        show("BLIND SPOTS — combat effects no prose regex detects", no_prose)
        show("NEEDS A HUMAN CALL — combat or economy?", unclear, 16)


if __name__ == "__main__":
    main()
