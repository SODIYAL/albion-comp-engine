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
# Rule: a quarantined record must never BE the canonical default,
# whatever its comp-level approval says
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
check("H14 the cohort axis is party size, apart from the fight-size axis, "
      "and side size stays explicitly unknown",
      usage.get("cohort_frame", {}).get("axis") == "party_size"
      and usage.get("side_size") == "unknown"
      and all(isinstance(c["size"], int) and c["size"] >= 2
              and ("small" if 2 * c["size"] < 12 else
                   "mid" if 2 * c["size"] <= 30 else "large") == b
              for b, rows in usage["cohorts"].items() for c in rows))
check("H14 abilities and loadout swaps are stored as unknown, never inferred",
      usage.get("abilities") == "unknown"
      and usage.get("loadout_swaps") == "unknown")
check("H14 battle-level aggregation exists beside correlated player counts",
      "buckets_battles" in usage
      and all(n <= usage["meta"][b]["battles"]
              for b, m in usage["buckets_battles"].items() for n in m.values()))
check("H14 the cohort sample states the parties it was drawn from",
      all(m["cohorts"] == len(usage["cohorts"][b])
          and m["cohorts"] <= m["parties_in_window"]
          for b, m in usage["cohort_meta"].items()))

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
# What silently re-admits an excluded weapon is an APPROVED/CANONICAL record,
# which is exactly what composition.yaml's documented exit path watches for:
# the evidence gate flags any excluded weapon that gains a CURRENT approved
# canonical large-group build, so the entry can be lifted — the data clears
# the gate, not a code change. A CANDIDATE record from a real published comp
# is not a leak and not a re-admission: it is the evidence accumulating,
# which the design expects.
#
# This assertion used to be "no build records AT ALL", which was true only
# while the corpus was small. The albioncompo ingest (23 comps) brought
# one genuine candidate record (below), so the check now separates
# the two cases instead of failing on expected evidence.
KNOWN_CANDIDATE_EVIDENCE = {
    # weapon -> build_id. OPEN QUESTION: this record CONTRADICTS the stated
    # reason for excluding the weapon (no caller sheet, published build or
    # observation fields them at party size >= 10). AvA Raid is a published
    # 10-man that fields it. Still candidate, so the exclusion stands and the
    # gate has not fired — but the premise is now weaker than when it was
    # written. Flagged for a maintainer decision, not silently lifted.
    "MAIN_FROSTSTAFF_AVALON": {"albioncompo_ava_raid_2026_05:comp:6"},
}
leaks, readmit = [], []
for w in excluded:
    for ct, by_w in INDEX["by_content"].items():
        for v in by_w.get(w, []):
            bid, appr = v["build_id"], v.get("approval")
            if appr in ("approved", "canonical"):
                readmit.append((w, ct, bid, appr))
            elif bid not in KNOWN_CANDIDATE_EVIDENCE.get(w, set()):
                leaks.append((w, ct, bid, appr))
check("H16 no excluded weapon carries an APPROVED/CANONICAL record — that "
      "is what would silently re-admit it; lifting goes through the "
      "exclusion gate and a maintainer decision", not readmit,
      str(readmit[:3]))
check("H16 no UNEXPECTED records on excluded weapons — cursed/frost FAMILY "
      "records never leak onto them, and new candidate evidence must be "
      "recorded deliberately", not leaks, str(leaks[:3]))
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

# ---- H.18 the meta prior is GENERATED from the harvest, never hand-set ----------
# Rule (T46/H18): one harvest prior replaces both hand lists —
# scoring.meta_prior is the size-bucketed map derive_meta_prior.py
# wrote from the COMMITTED party_rosters.json.gz (hash-gated), scoring.yaml and
# MASTERSHEET carry no hand-set map, composition.yaml's viability core list is
# empty, and the dataset embeds the aggregate only — never raw observations.
import hashlib as _hl
sc = DATASET["scoring"]
scoring_yaml = yaml.safe_load(open(os.path.join(
    PIPELINE, "templates", "scoring.yaml"), encoding="utf-8"))
prior_doc = load_json(os.path.join(OUT, "meta_prior.json"))
mp = sc.get("meta_prior") or {}
sys.path.insert(0, PIPELINE)
import rosters_io  # noqa: E402
_rosters_sha = rosters_io.sha256(rosters_io.path(OUT))
check("H18 the scoring meta prior is the GENERATED bucketed harvest prior "
      "(out/meta_prior.json, hash-gated to the committed party_rosters.json.gz); "
      "scoring.yaml carries no hand-set map; every value in (0, 1] with the "
      "bucket's top weapon at 1.0",
      set(mp) == {"small", "mid", "large"}
      and not scoring_yaml.get("meta_prior")
      and (prior_doc.get("_source") or {}).get("party_rosters_sha256") == _rosters_sha
      and all(0.0 < v <= 1.0 for rows in mp.values() for v in rows.values())
      and all(max(rows.values()) == 1.0 for rows in mp.values() if rows)
      and all(mp[b] == {w: v for w, v in prior_doc["meta_prior"][b].items()
                        if w in DATASET["weapons"]} for b in mp),
      f"buckets={ {b: len(r) for b, r in mp.items()} }")
check("H18b the hand-listed viability core is retired (empty), so the "
      "viability term reads 0 for every weapon",
      not any((comp_cfg.get("viability") or {}).get("core", {}).values()))
check("H18 no raw usage/observation payload is embedded in the dataset "
      "(the prior is an aggregate: weapon -> value per bucket)",
      "usage" not in DATASET and "weapon_usage" not in DATASET
      and "builds_index" not in DATASET and "buckets" not in DATASET
      and all(isinstance(v, float) for rows in mp.values() for v in rows.values()))

# ---- H.21 weapon style-fit identity (derived from the E's own payload) ---------
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
check("H21 the Battleaxe verdict is applied via a CITED override "
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

# ---- H.23 gear actives: the recorded choice per worn piece --------------------
# Rule: a build's head / armor / shoes active is kept only as a spell id
# that sits on the WORN item's dumps menu — the Character Builder's
# UniqueNames read directly, MetaBattle's "Active, Passive" names through
# the spell index (an ambiguous name resolves to nothing); anything else
# is None, never a guess. The dataset's gear-active doctrine votes on it.
import build_builds as bb  # noqa: E402
_si = {"ICEBLOCK2": {"name": "Ice Block"}, "PBAOE_KNOCKBACK": {"name": "Force Field"},
       "DODGE": {"name": "Dodge"}, "TWIN_A": {"name": "Twin"}, "TWIN_B": {"name": "Twin"}}
_menus = {"HEAD_CLOTH_SET2": {"actives": ["ENERGY_BARRIER", "PBAOE_KNOCKBACK", "ICEBLOCK2"]},
          "SHOES_CLOTH_SET1": {"actives": ["CHANNELED_RUN", "DODGE", "SPRINTEOT"]},
          "ARMOR_CLOTH_SET1": {"actives": ["SPEEDCASTER", "FROSTSHIELD", "OUTOFCOMBATHEAL"]}}
_cb = bb.gear_spell_picks(
    {"gear": {"head": "HEAD_CLOTH_SET2", "armor": "ARMOR_CLOTH_SET1", "shoes": "T8_SHOES_CLOTH_SET1"},
     "gear_spells_verbatim": {"head": {"actives": {"1": "ICEBLOCK2"}},
                              "armor": {"actives": {"1": "FROSTSHIELD"}},
                              "shoes": {"actives": {"1": "BLINK"}}}},
    _si, _menus)
check("H23 Character Builder UniqueNames read directly; a tiered worn key reads tierless; "
      "an active NOT on the worn item's menu is None",
      _cb == {"head": "ICEBLOCK2", "armor": "FROSTSHIELD", "shoes": None}, str(_cb))
_mb = bb.gear_spell_picks(
    {"gear": {"head": "HEAD_CLOTH_SET2", "shoes": "SHOES_CLOTH_SET1", "armor": "ARMOR_CLOTH_SET1"},
     "gear_spells_raw": {"head": "Force Field, Balanced Mind", "shoes": "Dodge, Aggression",
                         "armor": "Twin, Toughness"}},
    _si, _menus)
check("H23 MetaBattle names resolve through the spell index (first name is the active); "
      "a name two spells share resolves to None",
      _mb == {"head": "PBAOE_KNOCKBACK", "shoes": "DODGE", "armor": None}, str(_mb))
check("H23 a record with no gear-spell source carries None, not an empty dict",
      bb.gear_spell_picks({"gear": {"head": "HEAD_CLOTH_SET2"}}, _si, _menus) is None)
_bi = load_json(os.path.join(OUT, "builds_index.json"))
_recs = [v for c in _bi["by_content"].values() for w in c.values() for v in w]
_withgs = [v for v in _recs if v.get("gear_spells")]
_offmenu = [v["build_id"] for v in _withgs for s, sid in v["gear_spells"].items()
            if sid and sid not in ((load_json(os.path.join(OUT, "gear_spells.json")).get(
                v["gear"].get(s) or "") or {}).get("actives") or [])]
check("H23 the index carries gear_spells for every recording build (the Character Builder "
      "comps and the MetaBattle batch) and every kept id sits on the worn item's menu",
      len(_withgs) >= 70 and not _offmenu
      and all(set(v["gear_spells"]) == {"head", "armor", "shoes"} for v in _withgs),
      f"recording={len(_withgs)} off_menu={_offmenu[:3]}")
_da = {k: g.get("doctrine_active") for k, g in DATASET["gear"].items()
       if g.get("slot") in ("head", "armor", "shoes")}
check("H23 every head / armor / shoes item in the dataset carries doctrine_active with "
      "source observed (votes at the floor) or assumed (the item's own active, votes under it)",
      _da and all(d and d.get("id") and d.get("source") in ("observed", "assumed")
                  and (d["source"] == "observed") == (d.get("votes", 0) >= 2)
                  for d in _da.values()),
      str([k for k, d in _da.items() if not d][:5]))
check("H23 the Cleric Cowl's doctrine is the observed Ice Block, unanimous",
      (_da.get("HEAD_CLOTH_SET2") or {}).get("id") == "ICEBLOCK2"
      and _da["HEAD_CLOTH_SET2"]["source"] == "observed"
      and _da["HEAD_CLOTH_SET2"]["votes"] == _da["HEAD_CLOTH_SET2"]["of"] >= 2,
      str(_da.get("HEAD_CLOTH_SET2")))

# ---- the evidence lint holds the sheets README contract, failing closed ------
# Rule: a typo in a sheet is an ERROR, never a silent no-op. The
# lint_contract_* fixtures under pipeline/tests/ carry the defects their
# comments name; the lint must report every one, and the committed sheets
# must pass the same checks.
import glob as _glob  # noqa: E402
import evidence_lint as el  # noqa: E402
import mastersheet  # noqa: E402
_fx = os.path.join(PIPELINE, "tests")
_sheet_fx = os.path.join(_fx, "lint_contract_sheet.yaml")
_sheet_err, _sheet_warn = el.lint_sheet(_sheet_fx)
_sheet_err = _sheet_err + el.lint_corpus([_sheet_fx])[0]
_gear_err = el.lint_gear([os.path.join(_fx, "lint_contract_gear.yaml")])[0]
_pool_err = el.lint_pools([os.path.join(_fx, "lint_contract_pool.yaml")])[0]


def _says(errors, *parts):
    return any(all(p in e for p in parts) for e in errors)


def _check_quiet(name, ok, detail):
    """check() that prints the detail only when the check fails."""
    return check(name, ok, "" if ok else detail)


for _name, _errors, _parts in (
        ("an unknown entry key", _sheet_err, ("2H_MACE:", "unknown key", "evidense")),
        ("an unknown row key", _sheet_err, ("MAIN_MACE.root:", "unknown key", "scroe")),
        ("a row without a score", _sheet_err, ("MAIN_MACE.root:", "no score")),
        ("score 9", _sheet_err, ("MAIN_MACE.stun:", "score 9 is outside 1-7")),
        ("score 2.5", _sheet_err, ("MAIN_MACE.engage:", "score 2.5 is not an integer")),
        ("score 0", _sheet_err, ("MAIN_MACE.mobility:", "score 0", "tune:sheets")),
        ("score true", _sheet_err, ("MAIN_MACE.catch:", "score True is not an integer")),
        ("an unknown cap 'peal'", _sheet_err, ("MAIN_MACE.peal:", "unknown capability 'peal'")),
        ("a duplicate row", _sheet_err, ("MAIN_MACE.tankiness:", "duplicate row")),
        ("a duplicate except", _sheet_err, ("MAIN_MACE:", "duplicate except (slow, SACRED_GROUND)")),
        ("a dead except (no such pool row)", _sheet_err,
         ("MAIN_MACE:", "except (purge, HAMMERTACKLE) names no row")),
        ("an inert except (the weapon cannot equip the spell)", _sheet_err,
         ("2H_IRONGAUNTLETS_HELL:", "except (engage, DASHKICK) is inert", "cannot equip")),
        ("an inert except (an own row already overrides the pair)", _sheet_err,
         ("MAIN_MACE:", "except (peel, GUARDRUNE) is inert", "own row")),
        ("a wrong-file placement", _sheet_err,
         ("MAIN_MACE:", "belongs in sheets/mace.yaml")),
        ("an impossible curated_as_of", _sheet_err,
         ("2H_MACE:", "'2026-13-45' is not an ISO date")),
        ("a curated_as_of that is not ISO", _sheet_err,
         ("2H_IRONGAUNTLETS_HELL:", "'2026-8-1' is not an ISO date")),
        ("a missing curated_as_of", _sheet_err, ("2H_MACE:", "missing curated_as_of")),
        ("a bad role_hint", _sheet_err, ("2H_MACE:", "role_hint 'dps'")),
        ("a weapon key defined twice", _sheet_err, ("2H_MACE:", "defined 2 times")),
        ("a gear slot outside the vocabulary", _gear_err,
         ("gear/HEAD_PLATE_KEEPER:", "slot 'helmet'")),
        ("a gear slot the game data contradicts", _gear_err,
         ("gear/ARMOR_PLATE_HELL:", "disagrees with the game data's slot armor")),
        ("a gear entry in the wrong file", _gear_err,
         ("gear/ARMOR_PLATE_HELL:", "belongs in sheets/gear/armor.yaml")),
        ("the weapon sentinel on a gear row", _gear_err,
         ("gear/ARMOR_PLATE_HELL.tankiness:", "WEAPON_STATS is the weapon sentinel")),
        ("a self cost above the scale", _gear_err,
         ("gear/ARMOR_PLATE_HELL self_costs.tankiness:", "points 9 is outside 1-7")),
        ("a gear item the game data does not carry", _gear_err,
         ("gear/HEAD_PLATE_UNLISTED:", "unknown gear item")),
        ("a dead gear except", _gear_err,
         ("gear/SHOES_CLOTH_SET2:", "except (disengage, BLINK) names no row")),
        ("a gear key defined twice", _gear_err, ("SHOES_CLOTH_SET2:", "defined 2 times")),
        ("an unknown pool key", _pool_err, ("unknown key", "capabilites")),
        ("a pool outside pools/<subcategory>.yaml", _pool_err,
         ("the mace pool belongs in sheets/pools/mace.yaml",)),
        ("a pool score 2.5", _pool_err, ("pools/mace.root:", "score 2.5 is not an integer")),
        ("an unknown pool cap", _pool_err, ("pools/mace.peal:", "unknown capability")),
        ("an unknown pool row key", _pool_err, ("pools/mace.slow:", "unknown key", "evidense")),
        ("a duplicate pool row", _pool_err, ("pools/mace.peel:", "duplicate row"))):
    _check_quiet(f"lint: {_name} is an ERROR", _says(_errors, *_parts),
                 "; ".join(_errors)[:300])
_check_quiet("lint: an own row identical to the pool row it shadows is a "
             "WARNING, not an ERROR",
             _says(_sheet_warn, "MAIN_MACE.peel:", "row it shadows")
             and not _says(_sheet_err, "MAIN_MACE.peel:"), str(_sheet_warn))
_legacy = el.lint_sheet(os.path.join(_fx, "bad_sheet_fixture.yaml"))[0]
_check_quiet("lint: the grounding error classes of bad_sheet_fixture.yaml all "
             "fail (rule 2 equippability, rule 3 grounding)",
             _says(_legacy, "MAIN_MACE.purge:", "cannot ground purge")
             and _says(_legacy, "MAIN_MACE.cleanse:", "NOT equippable")
             and _says(_legacy, "2H_LONGBOW.knockback_displace:", "cannot ground")
             and _says(_legacy, "2H_LONGBOW.resist_shred:", "cannot ground"),
             "; ".join(_legacy)[:300])
_run = el.run(sorted(_glob.glob(os.path.join(PIPELINE, "sheets", "*.yaml"))))
_committed = [e for _, errors, _ in _run for e in errors]
_check_quiet("lint: the committed sheets, pools and templates pass every "
             "check (0 errors)", not _committed, "; ".join(_committed[:3]))

# MASTERSHEET tune:sheets: an int 0-7 under a weapon key, else the parse fails
_tune = "```yaml tune:sheets\n{}\n```\n"


def _tune_error(body):
    try:
        mastersheet.parse(_tune.format(body))
    except ValueError as exc:
        return str(exc)
    return None


for _body, _expect in (("MAIN_MACE: {stun: 9}", "MAIN_MACE.stun: 9 is outside 0-7"),
                       ("MAIN_MACE: {stun: -1}", "MAIN_MACE.stun: -1 is outside 0-7"),
                       ("MAIN_MACE: {stun: 2.5}", "not an integer score"),
                       ("MAIN_MACE: {stun: true}", "not an integer score"),
                       ("main_mace: {stun: 2}", "not a weapon key"),
                       ("MAIN_MACE: 3", "must map capabilities to scores")):
    _check_quiet(f"MASTERSHEET tune:sheets rejects {_body!r}",
                 _expect in (_tune_error(_body) or ""), str(_tune_error(_body)))
try:
    mastersheet.load()
    _committed_tune_error = None
except ValueError as _exc:
    _committed_tune_error = str(_exc)
_edge_error = _tune_error("MAIN_MACE: {stun: 0, peel: 7}")
_check_quiet("MASTERSHEET tune:sheets accepts 0 (removes the row) and 7, and "
             "the committed MASTERSHEET.md parses",
             _edge_error is None and _committed_tune_error is None,
             f"{_edge_error} / {_committed_tune_error}")

# ------------------------------------------------------------------ summary
n_ok = sum(1 for _, ok in results if ok)
print("=" * 74)
print(f"{n_ok}/{len(results)} evidence-layer tests passed")
sys.exit(0 if n_ok == len(results) else 1)
