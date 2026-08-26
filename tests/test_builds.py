#!/usr/bin/env python3
"""
Evidence-layer gates (changeschapter2.md §B-§F / §H 5-16, 18).

Offline by design: reads committed outputs, data/ records and checked-in
fixtures only.

Run:  py -3 tests/test_builds.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PIPELINE = os.path.join(ROOT, "pipeline")
OUT = os.path.join(PIPELINE, "out")
sys.path.insert(0, PIPELINE)

import yaml  # noqa: E402
import builds_lib as bl  # noqa: E402
sys.path.insert(0, os.path.join(PIPELINE, "adapters"))
import metabattle  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if detail:
        print(f"      {detail}")
    return ok


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


DATASET = load_json(os.path.join(OUT, "dataset-latest.json"))
WEAPONS = DATASET["weapons"]
LINES = load_json(os.path.join(OUT, "weapon_lines.json"))
SPELLS = load_json(os.path.join(OUT, "spell_index.json"))
GEAR = load_json(os.path.join(OUT, "gear_lines.json"))
REPORT = load_json(os.path.join(OUT, "ranged_presence_report.json"))
INDEX = load_json(os.path.join(OUT, "builds_index.json"))
VALIDATION = load_json(os.path.join(OUT, "builds_validation.json"))
STATS = load_json(os.path.join(OUT, "item_stats.json"))["items"]

# ---- H.5 no attackrange -> ranged_presence shortcut --------------------------
# High basic-attack range with no curated AoE claim must yield NOTHING — the
# exact weapons the old rule wrongly benefited (§B).
wrongly_benefited = ["MAIN_CURSEDSTAFF", "MAIN_FROSTSTAFF_AVALON",
                     "2H_IRONCLADEDSTAFF", "2H_WARBOW", "2H_ARCANESTAFF"]
bad = []
for k in wrongly_benefited:
    w = WEAPONS[k]
    rng = (STATS.get(k, {}).get("stats") or {}).get("attackrange", 0)
    lo = w.get("loadout") or {}
    in_bundles = any(b.get("ranged_presence")
                     for slot in lo.get("slots", []) for b in slot)
    if w["capabilities"].get("ranged_presence") or \
            lo.get("always", {}).get("ranged_presence") or in_bundles:
        bad.append(k)
check("H5 long-autoattack weapons without AoE claims get no ranged_presence "
      "(incl. 1H Cursed, Chillhowl, Ironclad)", not bad, str(bad))
in_always = [k for k, w in WEAPONS.items()
             if (w.get("loadout") or {}).get("always", {}).get("ranged_presence")]
check("H5 ranged_presence never lives in loadout.always — it is a spell "
      "capability, not a weapon constant", not in_always, str(in_always[:5]))

# ---- H.6 every derived scoring capability carries evidence -------------------
granted = {k for k, w in WEAPONS.items()
           if w["capabilities"].get("ranged_presence")}
no_evidence = [k for k in granted
               if not (WEAPONS[k].get("evidence") or {}).get("ranged_presence")]
check("H6 every ranged_presence grant has an evidence record in the dataset",
      not no_evidence, str(no_evidence))
report_granted = set(REPORT["_meta"]["granted"])
check("H6 the dataset's grants equal the audit report's grants",
      granted == report_granted,
      f"dataset-only={sorted(granted - report_granted)[:3]} "
      f"report-only={sorted(report_granted - granted)[:3]}")
bad = []
for k in report_granted:
    for d in REPORT["weapons"][k]["decisions"]:
        if not d["granted"]:
            continue
        structural = (d["basis"] == "curated_burst_aoe+structural_range"
                      and d.get("cast_range") is not None)
        override = (d["basis"] == "curated_override_grant"
                    and (d.get("override") or {}).get("reason")
                    and (d.get("override") or {}).get("source"))
        if not (structural or override):
            bad.append((k, d["spell"], d["basis"]))
check("H6 every grant rests on structural facts or a cited curated override",
      not bad, str(bad[:3]))
denies = [d for wrec in REPORT["weapons"].values() for d in wrec["decisions"]
          if d["basis"] == "curated_override_deny"]
check("H6 curated denials carry reason + source citations",
      denies and all((d.get("override") or {}).get("reason")
                     and (d.get("override") or {}).get("source")
                     for d in denies), f"{len(denies)} denials")

# ---- H.7 stable spell-ID and item-ID resolution ------------------------------
bad = []
for ct, by_w in INDEX["by_content"].items():
    for w, variants in by_w.items():
        for v in variants:
            for slot, sid in (v.get("spells") or {}).items():
                if sid and sid not in SPELLS:
                    bad.append((v["build_id"], sid))
            for slot, key in (v.get("gear") or {}).items():
                if key and key not in GEAR:
                    bad.append((v["build_id"], key))
check("H7 every resolved spell/gear reference is a stable known UniqueName",
      not bad, str(bad[:3]))
sample = STATS["2H_LONGBOW"]
check("H7 the item bank preserves every tier's raw item id",
      sample.get("items", {}).get("4") == "T4_2H_LONGBOW"
      and len(sample.get("items", {})) >= 5)

# ---- H.8 spell equippability + bounds validation ------------------------------
spells, unknowns, quarantined = bl.resolve_spells(
    "2H_LONGBOW", {"q": 3, "w": 2, "p": 1}, LINES)
pools = LINES["2H_LONGBOW"]["spells"]
check("H8 numeric picks resolve to the exact pool entry (1-based, game order)",
      spells["q"] == pools["q"][2] and spells["w"] == pools["w"][1]
      and spells["passive"] == pools["passive"][0]
      and spells["e"] == pools["e"][0] and not quarantined)
spells, unknowns, quarantined = bl.resolve_spells(
    "2H_ENIGMATICORB_MORGANA", {"q": 2, "w": 5, "p": 5}, LINES)
check("H8 an out-of-pool index (Enigmatic p5) is quarantined as unknown, "
      "never clamped or swapped for option 1",
      spells["passive"] is None and quarantined
      and "passive" in unknowns, str(quarantined))
check("H8 the quarantine landed in the committed validation_result",
      any("passive: index 5" in f for q in VALIDATION["quarantined"]
          for f in q["fields"]))
# review 2026-08-19: a quarantined record must never BE the canonical
# default, whatever its comp-level approval says
bad = [(ct, w) for ct, by_w in INDEX["by_content"].items()
       for w, vs in by_w.items() for v in vs
       if v.get("canonical") and (v.get("status") == "quarantined"
                                  or v.get("quarantined_fields"))]
check("H8 no canonical default anywhere is a quarantined record", not bad,
      str(bad[:3]))
locus = next(p for p in VALIDATION["promotions"]
             if p["weapon"] == "2H_ENIGMATICORB_MORGANA"
             and p["content"] == "blackzone_roam")
check("H8 the quarantined Enigmatic p5 build lost its canonical promotion",
      locus["build_id"] is None
      and "quarantine" in locus["basis"].lower(), str(locus))
mb = yaml.safe_load(open(os.path.join(ROOT, "data", "published_builds",
                                      "metabattle.yaml"), encoding="utf-8"))
bad = []
for b in mb["builds"]:
    if not b["weapon"]:
        continue
    pools = LINES[b["weapon"]]["spells"]
    for slot, sid in b["spells"].items():
        if sid and sid not in pools.get(slot, []):
            bad.append((b["build_id"], slot, sid))
check("H8 every imported MetaBattle spell is equippable on its weapon at "
      "the attributed snapshot", not bad, str(bad[:3]))

# ---- H.9 tier/enchant/quality normalization ----------------------------------
axe = STATS["2H_AXE"]
check("H9 zero-to-nonzero tier transitions are preserved, not discarded",
      (axe.get("by_tier", {}).get("masterymodifier") or {}).get("4") == 0)
check("H9 nested enchantment item power is preserved per tier and level",
      len((axe.get("ip_ench") or {}).get("4", {})) >= 3)
check("H9 the armory import schema stores tier, enchant, quality and IP as "
      "separate fields (unknown allowed, merged never)",
      all(f in yaml.safe_load(open(os.path.join(
          ROOT, "data", "armory_imports", "example.yaml"),
          encoding="utf-8"))["builds"][0] for f in
          ("tier", "enchant", "quality", "ip")))

# ---- H.10 structured alternatives + unknown fields ----------------------------
dh = INDEX["by_content"]["large_scale_zvz"]
alts = dh.get("2H_FIRE_RINGPAIR_AVALON", [{}])[0]
check("H10 'Dawns/Rotcaller' became structured weapon alternatives",
      any(a.get("weapon") == "MAIN_CURSEDSTAFF_CRYSTAL"
          for a in (alts.get("alternatives", {}).get("weapons") or [])))
ga = next((v for vs in dh.values() for v in vs
           if (v.get("alternatives", {}).get("gear") or {}).get("offhand")), None)
check("H10 'Aegis/Taproot' became structured gear alternatives",
      ga is not None)
check("H10 unknown fields are stored explicitly, not omitted",
      any(v.get("unknowns") for vs in dh.values() for v in vs))

# ---- H.11 MetaBattle fixture parsing + CC BY-SA attribution -------------------
fx_dir = os.path.join(PIPELINE, "tests", "fixtures", "metabattle")
page = load_json(os.path.join(fx_dir, "page_7699.json"))
wikitext = page["parse"]["parse"]["wikitext"]["*"]
eq = metabattle.template_params(wikitext, "Build equipment")
check("H11 the wikitext template parser reads the checked-in fixture offline",
      eq and eq.get("main hand weapon") == "Elder's Longbow"
      and "Multishot" in eq.get("main hand weapon skills", ""))
check("H11 fixtures carry page id, revision id and revision timestamp",
      page["parse"]["parse"]["revid"] > 0
      and next(iter(page["revisions"]["query"]["pages"].values()))
      ["revisions"][0].get("timestamp"))
lic = (mb["source"].get("license") or "")
check("H11 CC BY-SA attribution travels on the batch and every record",
      ("CC BY-SA" in lic or "ShareAlike" in lic)
      and all((b.get("attribution") or {}).get("license")
              and (b.get("attribution") or {}).get("credit")
              for b in mb["builds"]))
check("H11 imported records begin as candidate (or quarantined), never "
      "approved",
      all(b["status"] in ("candidate", "quarantined") for b in mb["builds"])
      and all(b["approval"]["status"] == "candidate" for b in mb["builds"]))

# ---- H.12 manual Armory / caller import validation -----------------------------
check("H12 the Armory example file (example: true) is never ingested",
      not any((v.get("source") or {}).get("kind") == "armory_manual"
              for by_w in INDEX["by_content"].values()
              for vs in by_w.values() for v in vs))
caller_doc = yaml.safe_load(open(os.path.join(
    ROOT, "data", "published_comps",
    "timothy_blap_blackzone_roam_2026_08.yaml"), encoding="utf-8"))
check("H12 caller comp docs validate cleanly against the schema",
      bl.validate_comp_doc(caller_doc, LINES) == [])
broken = dict(caller_doc, source={"kind": "nonsense"}, approval={"status": "??"})
p = bl.validate_comp_doc(broken, LINES)
check("H12 a bad source kind / status / missing family is rejected",
      len(p) >= 3, f"{len(p)} problems")

# ---- H.13 source dedup + independence -----------------------------------------
same_family = [{"source": {"family": "caller:timothy"}},
               {"source": {"family": "caller:timothy"}}]
check("H13 records from the same author/family count once",
      len(bl.independent_families(same_family)) == 1)
ok, basis = bl.canonical_eligible([
    {"source": {"kind": "metabattle", "family": "metabattle"},
     "approval": {"status": "candidate"}}])
check("H13 a single-family candidate group cannot become canonical",
      not ok, basis)
ok, basis = bl.canonical_eligible([
    {"source": {"kind": "caller_sheet", "family": "caller:timothy"},
     "approval": {"status": "approved",
                  "basis": "shotcaller-authored sheet"}}])
check("H13 explicit shotcaller approval clears the gate", ok, basis)
ok, _ = bl.canonical_eligible([
    {"source": {"kind": "metabattle", "family": "metabattle"},
     "approval": {"status": "candidate"}},
    {"source": {"kind": "manual_link", "family": "albiononlinegrind"},
     "approval": {"status": "candidate"}}])
check("H13 two genuinely independent families clear the gate", ok)
zvz_canonicals = [p for p in VALIDATION["promotions"]
                  if p["content"] == "zvz" and p["build_id"]]
check("H13 the MetaBattle-only zvz records produced NO canonical defaults",
      not zvz_canonicals, str(zvz_canonicals[:2]))

# ---- H.14 party size / side size / fight size stay distinct --------------------
usage = load_json(os.path.join(OUT, "weapon_usage_v2.json"))
check("H14 the usage sample declares fight-size semantics",
      usage.get("sampling_frame", {}).get("axis") == "fight_size"
      and "PREVALENCE" in usage.get("semantics", ""))
check("H14 per-battle records keep party/side size explicitly unknown "
      "and fight size + observed roster distinct",
      usage["battles"]
      and all(b["party_size"] is None and b["side_size"] is None
              and isinstance(b["fight_size"], int)
              and b["observed_roster"] <= max(b["fight_size"], b["observed_roster"])
              for b in usage["battles"]))
check("H14 abilities are stored as unknown, never inferred",
      usage.get("abilities") == "unknown")
check("H14 battle-level aggregation exists beside correlated player counts",
      "buckets_battles" in usage and usage.get("players_with_swaps") is not None)

# ---- H.15 1v1 evidence has zero large-group eligibility -------------------------
ml_doc = {"kind": "published_comp", "id": "ml_test",
          "source": {"kind": "murderledger", "family": "murderledger"},
          "content": "duel", "party_size": {"min": 1, "max": 20},
          "approval": {"status": "candidate"}, "parties": []}
p = bl.validate_comp_doc(ml_doc, LINES)
check("H15 a 1v1 source claiming party sizes beyond 2 is rejected",
      any("solo/1v1" in x for x in p), str(p[:1]))
ml_doc["party_size"] = {"min": 1, "max": 2}
check("H15 the same source within solo bounds validates",
      not any("solo/1v1" in x for x in bl.validate_comp_doc(ml_doc, LINES)))

# ---- H.16 exact-weapon eligibility, no family-level leakage ---------------------
excluded = ["MAIN_CURSEDSTAFF", "2H_IRONCLADEDSTAFF", "MAIN_FROSTSTAFF_AVALON"]
leaks = []
for w in excluded:
    for ct, by_w in INDEX["by_content"].items():
        for v in by_w.get(w, []):
            leaks.append((w, ct, v["build_id"]))
check("H16 excluded exact weapons have no build records at all — cursed/"
      "frost FAMILY records never leak onto them", not leaks, str(leaks[:3]))
check("H16 family cousins legitimately keep their own records",
      "MAIN_CURSEDSTAFF_UNDEAD" in INDEX["by_content"]["large_scale_zvz"])
comp_cfg = yaml.safe_load(open(os.path.join(
    PIPELINE, "templates", "composition.yaml"), encoding="utf-8"))
excl = (comp_cfg.get("viability") or {}).get("exclusions") or []
check("H16 every composition exclusion carries an evidence record "
      "(reason, source, as_of, clears_when)",
      excl and all((e.get("evidence") or {}).get(f)
                   for e in excl
                   for f in ("reason", "source", "as_of", "clears_when")))
check("H16 the evidence gate ran (exclusion_gate list present, currently "
      "no contradiction)",
      VALIDATION.get("exclusion_gate") == [])

# ---- H.18 no imported popularity/observation data in Forge scoring -------------
sc = DATASET["scoring"]
scoring_yaml = yaml.safe_load(open(os.path.join(
    PIPELINE, "templates", "scoring.yaml"), encoding="utf-8"))
check("H18 the scoring meta prior is the hand-set scoring.yaml map, not the "
      "usage-derived bucketed prior",
      sc.get("meta_prior") == scoring_yaml.get("meta_prior")
      and set(sc.get("meta_prior", {})) != {"small", "mid", "large"})
check("H18 no usage/observation payload is embedded in the dataset",
      "usage" not in DATASET and "weapon_usage" not in DATASET
      and "builds_index" not in DATASET and "buckets" not in DATASET)

# ---- H.21 weapon style-fit identity (owner-specified 2026-08-23) ---------------
FIT_REPORT = load_json(os.path.join(OUT, "style_fit_report.json"))
STYLES_ = ("brawl", "clap", "kite", "brawl_clap", "clap_kite")
BANDS_ = ("trio", "gang", "group")
bad = []
for k, w in WEAPONS.items():
    sf = w.get("style_fit") or {}
    fit = sf.get("fit") or {}
    if (sf.get("delivery") not in ("melee", "flex", "ranged")
            or sf.get("damage_scale") not in ("none", "single", "group")
            or set(fit) != set(STYLES_)
            or any(set(fit[s]) != set(BANDS_) for s in fit)
            or any(fit[s][b] not in ("fits", "situational", "unfit")
                   for s in fit for b in fit[s])):
        bad.append(k)
check("H21 every weapon carries a well-formed style_fit "
      "(delivery / scale / style x band verdicts)", not bad, str(bad[:3]))
check("H21 the audit report and the dataset agree on every fit",
      all(FIT_REPORT["weapons"][k]["fit"] == WEAPONS[k]["style_fit"]["fit"]
          for k in WEAPONS))
rb = WEAPONS["2H_AXE_AVALON"]["style_fit"]
check("H21 Realmbreaker DERIVES as the all-rounder (flex delivery, group "
      "scale, fits everywhere) — no override needed",
      rb["delivery"] == "flex" and rb["damage_scale"] == "group"
      and all(rb["fit"][s][b] == "fits" for s in STYLES_ for b in BANDS_)
      and FIT_REPORT["weapons"]["2H_AXE_AVALON"]["basis"] == "derived",
      str(rb))
ba = FIT_REPORT["weapons"]["MAIN_AXE"]
check("H21 the Battleaxe owner ruling is applied via a CITED override "
      "(unfit as a group pick >3, trio untouched)",
      ba["basis"] == "curated_override"
      and (ba.get("override") or {}).get("reason")
      and (ba.get("override") or {}).get("source")
      and all(ba["fit"][s]["gang"] == "unfit"
              and ba["fit"][s]["group"] == "unfit"
              and ba["fit"][s]["trio"] == "fits" for s in STYLES_),
      str({s: ba['fit'][s]['gang'] for s in STYLES_}))
check("H21 utility exemption: Dagger Pair's single-scale damage degrades to "
      "situational, never unfit (T15: its value at scale is utility)",
      all(WEAPONS["2H_DAGGERPAIR"]["style_fit"]["fit"][s]["group"]
          == "situational" for s in STYLES_))
check("H21 style-flexible roles fit everywhere (Hallowfall)",
      all(WEAPONS["MAIN_HOLYSTAFF_AVALON"]["style_fit"]["fit"][s][b] == "fits"
          for s in STYLES_ for b in BANDS_))
check("H21 the MetaBattle cross-check (Q15) publishes a review queue, "
      "never silent fixes",
      isinstance(FIT_REPORT["_meta"].get("metabattle_review_queue"), list),
      str(FIT_REPORT["_meta"].get("metabattle_review_queue")))

# ---- companion observations normalize into the same schema ---------------------
party = load_json(os.path.join(PIPELINE, "tests", "fixtures",
                               "companion_party.json"))
obs = bl.normalize_companion_party(party, LINES, ingested="2026-08-19")
check("companion roster normalizes into loadout_observation records with "
      "exact spell ids and hashed identities",
      len(obs) == 3
      and obs[0]["weapon"] == "2H_MACE_MORGANA"
      and obs[0]["spells"]["q"] == "IRONBREAKER"
      and obs[0]["player"] != "TestCaller" and len(obs[0]["player"]) == 16
      and obs[0]["ip"] == 1387)
check("companion records keep unknowns explicit and never invent a weapon",
      "passive" in obs[0]["unknowns"] and obs[2]["weapon"] is None
      and set(obs[2]["unknowns"]) == {"q", "w", "e", "passive"})

# ------------------------------------------------------------------ summary
n_ok = sum(1 for _, ok in results if ok)
print("=" * 74)
print(f"{n_ok}/{len(results)} evidence-layer tests passed")
sys.exit(0 if n_ok == len(results) else 1)
