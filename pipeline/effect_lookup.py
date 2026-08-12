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


class EffectLookup:
    def __init__(self):
        with open(os.path.join(OUT, "effect_catalogue.json"), encoding="utf-8") as f:
            cat = json.load(f)
        with open(os.path.join(HERE, "effect_map.yaml"), encoding="utf-8") as f:
            emap = yaml.safe_load(f)
        with open(os.path.join(OUT, "spell_index.json"), encoding="utf-8") as f:
            self.spells = json.load(f)
        self.spell_effects = cat.get("spell_effects", {})
        self.map = emap["effects"]
        self.proposed_caps = emap.get("proposed_capabilities", {})

    def effects_of(self, spell_id):
        return self.spell_effects.get(spell_id, [])

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
        for flag in self.spells.get(spell_id, {}).get("flags", []):
            for cap in PROSE_FALLBACK.get(flag, []):
                out.setdefault(cap, [])
                reason = f"prose:{flag}"
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
