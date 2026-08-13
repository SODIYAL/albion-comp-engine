#!/usr/bin/env python3
"""
Shared lookup: which capabilities can a given spell legitimately ground?

    spell -> structured effects (+ target direction) -> candidate capabilities

Both the seeder (proposes scores) and the evidence lint (blocks bad ones) go
through here, so they can never disagree about what a spell supports.

The answer is a CANDIDATE SET, never an assertion. `dash` offers mobility,
engage, disengage and catch; whether a particular weapon's 3m dodge is really
an engage tool is a curation judgement. The lint's job is to reject
capabilities the spell cannot support at all — not to pick between the ones it
can.

Reads out/effect_catalogue.json (built by effect_catalogue.py) and
effect_map.yaml. Falls back to the prose flags in spell_index.json where the
structured layer is silent, because neither source is complete on its own.
"""
import json, os, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# Prose flag -> capabilities it can support. The structured layer supersedes
# this; it survives as a safety net for effects the nodes express indirectly
# (Battle Howl's purge was found by prose before the structured pass caught it).
PROSE_FALLBACK = {
    "purge": ["purge"], "silence": ["silence"], "stun": ["stun"],
    "root": ["root"], "slow": ["slow"], "knockback": ["knockback_displace"],
    "cleanse": ["cleanse"], "heal": ["heal_burst", "heal_sustain", "self_sustain"],
    "pull": ["clump_create"], "pierce": ["resist_shred"],
    "heal_reduction": ["heal_reduction"], "area_removal": ["anti_zone"],
    "shield": ["tankiness", "self_sustain"],
}

# Structured effects that COVER a prose flag. "The structured layer supersedes
# this" used to be aspiration, not code: candidates() applied the prose
# fallback even when the spell had a structured entry for the same mechanic,
# with the direction stripped. That is how Frost Shot (structured
# knockback on SELF) still offered knockback_displace via prose — the exact
# self-reposition error the Longbow curation documented — and how every
# resist-SHRED spell offered tankiness via its noisy prose `shield` flag.
# A prose flag now fires only when the spell has NO structured counterpart;
# when a counterpart exists, its direction-resolved mapping is the answer.
# (Found in batch-2 curation review, 2026-08-12.)
PROSE_SUPERSEDED_BY = {
    "stun": {"stun"}, "root": {"root"}, "silence": {"silence"},
    "slow": {"movespeedbonus-"},
    "knockback": {"knockback", "forced_movement"},
    "pull": {"forced_movement"},
    "heal": {"healmodifier+", "healbonus+", "hitpointsregenerationbonus+"},
    "shield": {"physicalarmor+", "physicalarmor-", "magicresistance+",
               "magicresistance-", "bonusdefensevsplayers+",
               "bonusdefensevsplayers-", "invincibility"},
    "pierce": {"physicalarmor-", "magicresistance-", "bonusdefensevsplayers-"},
    "purge": {"remove:buff", "remove:buff_damageshield", "remove:movementbuff"},
    "cleanse": {"remove:crowdcontrol", "remove:debuff", "remove:damage"},
    "heal_reduction": {"healmodifier-", "healbonus-", "remove:heal"},
}

# heal_flag_meaning override values -> what the prose heal flag yields instead.
HEAL_MEANING = {
    "self_only": ["self_sustain"],
    "negate": ["heal_reduction"],
}


class EffectLookup:
    def __init__(self):
        with open(os.path.join(OUT, "effect_catalogue.json"), encoding="utf-8") as f:
            cat = json.load(f)
        with open(os.path.join(HERE, "effect_map.yaml"), encoding="utf-8") as f:
            emap = yaml.safe_load(f)
        with open(os.path.join(OUT, "spell_index.json"), encoding="utf-8") as f:
            self.spells = json.load(f)
        with open(os.path.join(HERE, "effect_overrides.yaml"), encoding="utf-8") as f:
            ov = yaml.safe_load(f) or {}
        self.dir_overrides = ov.get("dir_overrides") or {}
        self.heal_flag_meaning = ov.get("heal_flag_meaning") or {}
        self.suppress_effects = ov.get("suppress_effects") or {}
        self.suppress_flags = ov.get("suppress_flags") or {}
        self.added_caps = ov.get("add") or {}
        self.spell_effects = cat.get("spell_effects", {})
        self.map = emap["effects"]
        self.proposed_caps = emap.get("proposed_capabilities", {})

    def effects_of(self, spell_id):
        entries = self.spell_effects.get(spell_id, [])
        dropped = set(self.suppress_effects.get(spell_id, []))
        if dropped:
            entries = [e for e in entries if e["effect"] not in dropped]
        fixes = self.dir_overrides.get(spell_id)
        if not fixes:
            return entries
        return [dict(e, dirs=fixes[e["effect"]]) if e["effect"] in fixes else e
                for e in entries]

    def candidates(self, spell_id):
        """{capability: [reason, ...]} — every capability this spell could ground."""
        out = {}
        for entry in self.effects_of(spell_id):
            rule = self.map.get(entry["effect"])
            if not isinstance(rule, dict) or rule.get("ignore"):
                continue
            for direction in entry["dirs"]:
                for cap in (rule.get(direction) or []):
                    reason = f"{entry['effect']} on {direction}"
                    out.setdefault(cap, [])
                    if reason not in out[cap]:
                        out[cap].append(reason)
        entries = self.effects_of(spell_id)
        structured = {e["effect"] for e in entries}
        # heal is direction-critical: a spell's SELF healing-cast buff must not
        # supersede the prose flag standing in for its (structurally invisible)
        # direct ally heal — Desperate Prayer's case. Only an ally-directed
        # heal counterpart proves the ally side is structurally covered.
        ally_structured = {e["effect"] for e in entries if "ally" in e["dirs"]}
        muted = set(self.suppress_flags.get(spell_id, []))
        for flag in self.spells.get(spell_id, {}).get("flags", []):
            if flag in muted:
                continue  # documented misfire — see effect_overrides.yaml
            covered = ally_structured if flag == "heal" else structured
            if PROSE_SUPERSEDED_BY.get(flag, set()) & covered:
                continue  # the structured, direction-resolved entry is the answer
            caps = PROSE_FALLBACK.get(flag, [])
            if flag == "heal":
                meaning = self.heal_flag_meaning.get(spell_id)
                if meaning:
                    caps = HEAL_MEANING[meaning]
            for cap in caps:
                out.setdefault(cap, [])
                reason = f"prose:{flag}"
                if flag == "heal" and spell_id in self.heal_flag_meaning:
                    reason = f"prose:heal[{self.heal_flag_meaning[spell_id]}]"
                if reason not in out[cap]:
                    out[cap].append(reason)
        for cap, why in (self.added_caps.get(spell_id) or {}).items():
            out.setdefault(cap, [])
            reason = f"override: {why}"
            if reason not in out[cap]:
                out[cap].append(reason)
        return out

    def supports(self, spell_id, capability):
        return capability in self.candidates(spell_id)

    def has_structured(self, spell_id):
        return bool(self.effects_of(spell_id))


if __name__ == "__main__":
    lk = EffectLookup()
    for sid in (sys.argv[1:] or ["SHRIEKMACE", "MACELEAP", "ARROWRAIN", "CLEANSEHEAL"]):
        print(f"\n=== {sid}  ({lk.spells.get(sid, {}).get('name', '?')})")
        for e in lk.effects_of(sid):
            print(f"    {e['effect']:<32}{'direct' if e['direct'] else 'via   '} "
                  f"dirs={','.join(e['dirs'])}")
        print("  candidates:")
        for cap, why in sorted(lk.candidates(sid).items()):
            print(f"    {cap:<22}{'; '.join(why[:3])}")
