#!/usr/bin/env python3
"""
PvP interaction system gates (duplicate / reflect / cleanse semantics —
the 2026-08-19 interaction-system spec, implemented in interactions.yaml +
build_interactions.py).

The real seed data deliberately carries ZERO verified non-stacking scoring
entries (nothing in the pinned game data states duplicate-caster utility
stacking), so the scoring machinery is proven with SYNTHETIC verified
fixtures injected into a temp dataset — including a cross-engine check that
Python and JS price the same duplicate identically. Real entries stay
unknown and are asserted to change nothing (§12).

Run:  py -3 tests/test_interactions.py   (needs node for the parity check)
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PIPELINE = os.path.join(ROOT, "pipeline")
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, PIPELINE)

from engine import Engine  # noqa: E402
from build_interactions import rollup_reflect  # noqa: E402

DATASET = os.path.join(PIPELINE, "out", "dataset-latest.json")
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if detail:
        print(f"      {detail}")
    return ok


with open(DATASET, encoding="utf-8") as f:
    BASE = json.load(f)

# Synthetic VERIFIED fixture: FRAZZLE2 (Frazzle, arcane W — grounds
# resist_shred on four arcane weapons) declared damage_only with
# resist_shred counting once. Purely a test fixture; the real data does not
# verify this.
SYN = copy.deepcopy(BASE)
SYN["interactions"]["FRAZZLE2"] = {
    "name": "Frazzle", "effect_name": "Frazzle (test fixture)",
    "duplicate": "damage_only", "reflect": "unknown",
    "components": [], "cc_types": [],
    "badges": ["DUPLICATE:DAMAGE_ONLY"],
    "nonstacking_caps": ["resist_shred"],
    "scoring_note": "synthetic test fixture",
    "confidence": "verified", "source": "test fixture", "as_of": "2026-08-19",
    "verified_patch": "", "structural_reflect_statements": [], "notes": None,
}
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                  encoding="utf-8")
json.dump(SYN, tmp)
tmp.close()

CONTENT, SIZE, STYLE = "blackzone_roam", 20, "balanced"
base_e = Engine(DATASET, content=CONTENT, size=SIZE, style=STYLE)
syn_e = Engine(tmp.name, content=CONTENT, size=SIZE, style=STYLE)

W = "2H_ARCANESTAFF"


def combo_with(e, weapon, spell):
    """A combo index whose equipped kit includes `spell`."""
    for c in range(len(e._combo_extras(weapon))):
        if any(sid == spell for _s, sid in e.combo_spells(weapon, c)):
            return c
    return None


c = combo_with(syn_e, W, "FRAZZLE2")
check("fixture sanity: an arcane combo equips Frazzle", c is not None)
party, combos = [W, W], [c, c]

# ---- duplicate utility: supply counts once, fitness drops --------------------
s_base = base_e.effective_supply(party, combos)
s_syn = syn_e.effective_supply(party, combos)
v = syn_e._nonstack_contrib(W, c)["FRAZZLE2"]["resist_shred"]
check("nonstacking cap counts once across two members (max, not sum)",
      abs(s_base["resist_shred"] - s_syn["resist_shred"] - v) < 1e-12,
      f"base {s_base['resist_shred']} syn {s_syn['resist_shred']} unit {v}")
check("other capabilities are untouched by the adjustment",
      all(abs(s_base.get(k, 0.0) - s_syn.get(k, 0.0)) < 1e-12
          for k in set(s_base) | set(s_syn) if k != "resist_shred"))
check("a single copy scores identically with and without the fixture",
      abs(base_e.fitness([W], [c]) - syn_e.fitness([W], [c])) < 1e-12)
check("the duplicate's fitness is LOWER under the verified non-stacking rule",
      syn_e.fitness(party, combos) < base_e.fitness(party, combos))

# ---- the marginal invariant survives the adjustment (F1-style, 1e-9) --------
state = syn_e.party_state([W], [c])
score, _df, _ds, _meta, picked, _var, vg = syn_e._eval_pick(state, W)
delta = (syn_e.comp_score([W, W], [c, picked], [None, vg])
         - syn_e.comp_score([W], [c]))
check("pick score == exact comp_score delta with the count-once rule (1e-9)",
      abs(score - delta) < 1e-9, f"score {score:.12f} delta {delta:.12f}")

# same effect via two DIFFERENT weapons is also priced once
cross = ["2H_ARCANESTAFF", "2H_ARCANESTAFF_CRYSTAL"]
cc2 = [combo_with(syn_e, cross[0], "FRAZZLE2"),
       combo_with(syn_e, cross[1], "FRAZZLE2")]
s_cross = syn_e.effective_supply(cross, cc2)
s_cross_base = base_e.effective_supply(cross, cc2)
check("the same spell via two different weapons is priced once too",
      s_cross_base["resist_shred"] - s_cross["resist_shred"] > 0)

# ---- analyzer: duplicate warning ---------------------------------------------
conf = syn_e.duplicate_conflicts(party, combos)
frz = [x for x in conf if x["spell"] == "FRAZZLE2"]
check("analyzer emits a warning naming the exact non-stacking effect",
      len(frz) == 1 and frz[0]["severity"] == "warning"
      and "resist_shred" in frz[0]["reason"],
      frz[0]["reason"] if frz else "no conflict emitted")

# ---- unknown never changes a score (§12) --------------------------------------
UNK = copy.deepcopy(SYN)
UNK["interactions"]["FRAZZLE2"]["confidence"] = "likely"
tmp2 = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                   encoding="utf-8")
json.dump(UNK, tmp2)
tmp2.close()
unk_e = Engine(tmp2.name, content=CONTENT, size=SIZE, style=STYLE)
check("a non-verified entry changes NO score (unknown/likely never score)",
      abs(unk_e.fitness(party, combos) - base_e.fitness(party, combos)) < 1e-12
      and abs(unk_e.comp_score(party, combos)
              - base_e.comp_score(party, combos)) < 1e-12)

# ---- different named debuffs on the same stat are not conflated ---------------
pair = ["2H_AXE_AVALON", "MAIN_MACE_HELL"]     # Aftershock vs Shrinking Curse
conf = base_e.duplicate_conflicts(pair)
check("Realmbreaker + Incubus (two named max-HP effects) raise NO conflict",
      conf == [], str(conf))

# ---- no false duplicate: same broad category, different spells ----------------
bows = ["2H_BOW", "2H_AXE"]                    # DEADLYSHOT vs AXESMASH pierce
cb = [combo_with(syn_e, "2H_BOW", "DEADLYSHOT"),
      combo_with(syn_e, "2H_AXE", "AXESMASH")]
conf = syn_e.duplicate_conflicts(bows, cb)
s_two = syn_e.effective_supply(bows, cb)
s_two_base = base_e.effective_supply(bows, cb)
check("two different pierce spells: no conflict, both count in supply",
      conf == [] and abs(s_two.get("resist_shred", 0)
                         - s_two_base.get("resist_shred", 0)) < 1e-12)

# ---- partial reflect rollup ----------------------------------------------------
check("mixed known component reflect statuses roll up to 'partial'",
      rollup_reflect([{"reflect": "reflectable"},
                      {"reflect": "non_reflectable"}]) == "partial")
check("known + unknown mix rolls up to 'partial'; all-unknown stays unknown",
      rollup_reflect([{"reflect": "unknown"},
                      {"reflect": "non_reflectable"}]) == "partial"
      and rollup_reflect([{"reflect": "unknown"}]) == "unknown")
check("Dawnsong's Flaming Phoenix compiled as the partial-reflect showcase",
      BASE["interactions"]["FIREPHOENIX"]["reflect"] == "partial"
      and any(cmp.get("reflect") == "non_reflectable"
              for cmp in BASE["interactions"]["FIREPHOENIX"]["components"]))

# ---- missing utility -----------------------------------------------------------
# (the original prompt's example trio included Witchwork, whose arcane kit
# DOES carry curated cleanse 2 — the data corrected the example; Wailing Bow
# keeps the trio genuinely cleanse-less)
a = base_e.analyze(["2H_ICECRYSTAL_UNDEAD", "2H_BOW_HELL", "2H_LONGBOW"])
missing = [m["cap"] for m in a["missing_capabilities"]]
check("a damage trio without cleanse is told it lacks cleanse (and healing)",
      "cleanse" in missing and "heal_sustain" in missing)
check("analyzer reports strengths, cc coverage and profiles",
      isinstance(a["strengths"], list) and "stun" in a["cc_coverage"]
      and a["damage_profile"].get("burst_aoe", 0) > 0)

# ---- seed-data integrity --------------------------------------------------------
inter = BASE["interactions"]
check("all curated spells are embedded in the dataset (9 seeds + the "
      "reflect backlog incl. PUMMELING_STRIKES surfaced by the fuller "
      "descriptions + CURSEDOT, 2026-08-24)",
      len(inter) == 30 and "DEATHCURSE2" in inter and "SPEEDARCHER_KITE" in inter
      and "METEOR" in inter and "THORNSAREA" in inter
      and "PUMMELING_STRIKES" in inter and "CURSEDOT" in inter)
check("the structural-reflect curation backlog is empty",
      json.load(open(os.path.join(PIPELINE, "out", "interactions.json"),
                     encoding="utf-8"))["_meta"]["structural_unclaimed"] == [])
check("interrupt facts derive from the descriptions' own words",
      inter["ENFEEBLEBLADES"]["interrupt"]["uninterruptible"] is True
      and "UNINTERRUPTIBLE" in inter["ENFEEBLEBLADES"]["badges"]
      and inter["GROWING_PUNCH"]["interrupt"]["uninterruptible"] is True
      and inter["METEOR"]["interrupt"]["uninterruptible"] is None)

# ---- ability facts layer (2026-08-19): every effect visible per spell ----
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


SPELL_IDX = load_json(os.path.join(PIPELINE, "out", "spell_index.json"))
FX = load_json(os.path.join(PIPELINE, "out",
                            "effect_catalogue.json"))["spell_effects"]
leap = SPELL_IDX["MACELEAP"]                     # Deep Leap — the example
check("Deep Leap's resolved description carries the game's own numbers "
      "(damage, slow, STUN DURATION)",
      "203 physical damage" in leap["description"]
      and "stunned for 1.8" in leap["description"]
      and "Slows all enemies hit by 0.3 for 3" in leap["description"])
check("Deep Leap's typed effect list accounts for stun, slow and the self "
      "immunities",
      {"stun", "movespeedbonus-"} <=
      {e["effect"] for e in FX["MACELEAP"]}
      and any(e["effect"].startswith("immunity:") for e in FX["MACELEAP"]))
gear_sp = load_json(os.path.join(PIPELINE, "out", "gear_spells.json"))
check("equipment abilities are parsed with the same coverage (Knight "
      "Helmet's Block is a named, described spell)",
      "BLOCK" in gear_sp["HEAD_PLATE_SET1"]["actives"]
      and SPELL_IDX["BLOCK"]["name"] == "Block"
      and (SPELL_IDX["BLOCK"]["description"] or "").startswith("Block"))
check("gear reflect facts are backlogged separately, never silently dropped",
      isinstance(json.load(open(os.path.join(PIPELINE, "out",
                                             "interactions.json"),
                                encoding="utf-8"))
                 ["_meta"]["structural_unclaimed_gear"], list))
check("Death Curse carries the verified shared Vile-Curse-Charge model",
      inter["DEATHCURSE2"]["duplicate"] == "shared_stack"
      and inter["DEATHCURSE2"]["confidence"] == "verified")
check("Enchanted Quiver corrected to a verified full-value self-buff",
      inter["SPEEDARCHER_KITE"]["duplicate"] == "full"
      and inter["SPEEDARCHER_KITE"]["confidence"] == "verified")
check("verified non-reflect badges come from the game's own descriptions",
      "NON-REFLECTABLE" in inter["FROST_ULTIMATE"]["badges"]
      and inter["FROST_ULTIMATE"]["structural_reflect_statements"])
# REVISED 2026-08-24 (forge-quality round 4): the first verified
# non-stacking scoring record exists — CURSEDOT. Its description states the
# target-side 4-charge cap ("stacks up to 4 times"), DEATHCURSE2's verified
# record reads the same pool, and the owner ruled: "the q spells … stack
# but don't do extra damage from more people." CURSEDOT must be the ONLY
# such record (any new one needs its own citation + a pin here), and the
# count-once machinery must actually collapse the party's curse-Q supply.
check("CURSEDOT is the one verified non-stacking scoring record "
      "(sustained_dps counts once across cursed wielders)",
      [s for s, r in sorted(inter.items())
       if r.get("nonstacking_caps") and r.get("confidence") == "verified"]
      == ["CURSEDOT"]
      and inter["CURSEDOT"]["nonstacking_caps"] == ["sustained_dps"]
      and (inter["CURSEDOT"]["scoring_note"] or "").strip() != "")
_c1 = combo_with(base_e, "MAIN_CURSEDSTAFF", "CURSEDOT")
_s1 = base_e.effective_supply(["MAIN_CURSEDSTAFF"], [_c1])
_s3 = base_e.effective_supply(["MAIN_CURSEDSTAFF"] * 3, [_c1] * 3)
check("three cursed Qs supply strictly less than 3x one cursed Q's "
      "sustained DoT (count-once bites; non-CURSEDOT sources still add)",
      _s1.get("sustained_dps", 0) > 0
      and _s1.get("sustained_dps", 0) - 1e-9
      <= _s3.get("sustained_dps", 0)
      < 3 * _s1.get("sustained_dps", 0) - 1e-9)
check("shared-stack duplicates read as synergy in the analyzer",
      next(x for x in base_e.duplicate_conflicts(
          ["MAIN_CURSEDSTAFF", "MAIN_CURSEDSTAFF"],
          [combo_with(base_e, "MAIN_CURSEDSTAFF", "DEATHCURSE2")] * 2)
          if x["spell"] == "DEATHCURSE2")["severity"] == "info")

# ---- twin-engine parity on the synthetic duplicate (1e-9) -----------------------
node_script = f"""
const E = require({json.dumps(os.path.join(ROOT, 'engine', 'app_scoring.js'))});
const ds = require({json.dumps(tmp.name)});
const e = new E(ds, {json.dumps(CONTENT)}, {SIZE}, {json.dumps(STYLE)});
const party = {json.dumps(party)}, combos = {json.dumps(combos)};
const st = e.partyState([party[0]], [combos[0]]);
const pick = e._evalPick(st, party[0]);
process.stdout.write(JSON.stringify({{
  fitness: e.fitness(party, combos),
  comp: e.compScore(party, combos),
  supply_rs: e.effectiveSupply(party, combos).resist_shred,
  pick_score: pick.score,
  conflicts: e.duplicateConflicts(party, combos)
             .map(c => c.severity + '|' + c.spell),
}}));
"""
proc = subprocess.run(["node", "-e", node_script], capture_output=True,
                      text=True)
if proc.returncode != 0:
    check("JS mirror executes", False, proc.stderr[:300])
else:
    js = json.loads(proc.stdout)
    check("JS fitness/comp_score/supply match Python at 1e-9 on the "
          "non-stacking duplicate",
          abs(js["fitness"] - syn_e.fitness(party, combos)) < 1e-9
          and abs(js["comp"] - syn_e.comp_score(party, combos)) < 1e-9
          and abs(js["supply_rs"] - s_syn["resist_shred"]) < 1e-9)
    check("JS pick marginal matches Python at 1e-9",
          abs(js["pick_score"] - score) < 1e-9,
          f"js {js['pick_score']:.12f} py {score:.12f}")
    check("JS analyzer emits the identical conflict",
          js["conflicts"] == ["warning|FRAZZLE2"], str(js["conflicts"]))

os.unlink(tmp.name)
os.unlink(tmp2.name)

n_ok = sum(1 for _, ok in results if ok)
print("=" * 74)
print(f"{n_ok}/{len(results)} interaction tests passed")
sys.exit(0 if n_ok == len(results) else 1)
