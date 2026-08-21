#!/usr/bin/env python3
"""
Provenance + reproducibility gates (changeschapter2.md §A / §H 1-4, 17, 20).

Offline by design: everything here reads committed files and fixtures; no
test touches the network. The destructive release-failure case (H.3) tampers
with a COPY of the manifest through the provenance module's path attribute
and restores it in `finally`.

Run:  py -3 tests/test_provenance.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PIPELINE = os.path.join(ROOT, "pipeline")
OUT = os.path.join(PIPELINE, "out")
sys.path.insert(0, PIPELINE)

import yaml  # noqa: E402
import provenance  # noqa: E402
import build_interactions as bi  # noqa: E402
import fetch_item_stats as fis  # noqa: E402
import parse_dumps as pd  # noqa: E402

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


PIN = yaml.safe_load(open(os.path.join(ROOT, "data", "source_pins.yaml"),
                          encoding="utf-8"))["ao-bin-dumps"]
DATASET = load_json(os.path.join(OUT, "dataset-latest.json"))
MANIFEST = load_json(provenance.MANIFEST_PATH)

INPUTS = ["weapon_lines.json", "spell_index.json", "item_stats.json",
          "gear_lines.json", "gear_spells.json", "interactions.json"]
VERSIONS = {
    "weapon_lines.json": (pd.ADAPTER, pd.ADAPTER_VERSION),
    "spell_index.json": (pd.ADAPTER, pd.ADAPTER_VERSION),
    "item_stats.json": (fis.ADAPTER, fis.ADAPTER_VERSION),
    "gear_lines.json": ("fetch_gear_lines", "2"),
    "gear_spells.json": (pd.ADAPTER, pd.ADAPTER_VERSION),
    "interactions.json": (bi.ADAPTER, bi.ADAPTER_VERSION),
}

# ---- H.1 atomic pinned snapshot + hash verification -------------------------
problems = provenance.verify_derived(INPUTS, VERSIONS)
check("H1 derived chain verifies against the committed manifest",
      problems == [], "; ".join(problems))
check("H1 manifest snapshot is the pinned commit",
      MANIFEST["sources"]["commit"] == PIN["commit"]
      and len(PIN["commit"]) == 40)
check("H1 manifest carries SHA-256 + size for every pinned file",
      set(MANIFEST["sources"]["files"]) == set(PIN["files"])
      and all(len(v["sha256"]) == 64 and v["bytes"] > 0
              for v in MANIFEST["sources"]["files"].values()))
check("H1 manifest records repository, commit timestamp, fetch timestamp, "
      "environment, game patch",
      all(MANIFEST["sources"].get(k) for k in
          ("repository", "commit_timestamp", "fetch_timestamp_utc",
           "environment", "game_patch")))
# The manifest hashes raw bytes, and .gitattributes normalizes the repo to
# LF — so a CRLF artifact hashes differently on disk than the checkout any
# other machine gets, and H1 breaks everywhere but the generating machine
# (bitten 2026-08-21: git pull rewrote spell_index.json to LF, manifest
# held the Windows CRLF hash, release blocked).
crlf = [name for name in INPUTS + ["source_manifest.json"]
        if b"\r\n" in open(os.path.join(OUT, name), "rb").read()]
check("H1 hashed artifacts are LF-only (byte-stable across git checkout)",
      crlf == [], str(crlf))

# ---- H.3 release fails closed on missing / mixed / stale inputs -------------
real_path = provenance.MANIFEST_PATH
backup = real_path + ".test_backup"
shutil.copyfile(real_path, backup)
try:
    doctored = json.loads(json.dumps(MANIFEST))
    doctored["derived"]["item_stats.json"]["sha256"] = "0" * 64
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f, indent=1, sort_keys=True)
    p = provenance.verify_derived(INPUTS, VERSIONS)
    check("H3 hash drift on an input is detected",
          any("stale or hand-edited" in x for x in p))

    doctored = json.loads(json.dumps(MANIFEST))
    doctored["derived"]["spell_index.json"]["source_commit"] = "f" * 40
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f, indent=1, sort_keys=True)
    p = provenance.verify_derived(INPUTS, VERSIONS)
    check("H3 mixed snapshot commits across inputs are detected",
          any("mixed source commits" in x for x in p))

    doctored = json.loads(json.dumps(MANIFEST))
    del doctored["derived"]["gear_lines.json"]
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f, indent=1, sort_keys=True)
    p = provenance.verify_derived(INPUTS, VERSIONS)
    check("H3 a missing provenance record is detected",
          any("no provenance record" in x for x in p))

    doctored = json.loads(json.dumps(MANIFEST))
    doctored["derived"]["item_stats.json"]["adapter_version"] = "0"
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f, indent=1, sort_keys=True)
    p = provenance.verify_derived(INPUTS, VERSIONS)
    check("H3 a stale adapter version is detected",
          any("rebuild" in x for x in p))

    # end-to-end: a tampered manifest must make the release build fail closed
    doctored = json.loads(json.dumps(MANIFEST))
    doctored["derived"]["item_stats.json"]["sha256"] = "0" * 64
    with open(real_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f, indent=1, sort_keys=True)
    proc = subprocess.run(
        [sys.executable, os.path.join(PIPELINE, "build_dataset.py"),
         "--skip-lint"], capture_output=True, text=True)
    ds_bad = load_json(os.path.join(OUT, "dataset-latest.json"))
    check("H3 build_dataset exits non-zero and marks release_clean false",
          proc.returncode == 2
          and ds_bad["_meta"]["release_clean"] is False
          and ds_bad["_meta"]["provenance"]["verified"] is False,
          f"exit={proc.returncode}")
finally:
    shutil.copyfile(backup, real_path)
    os.remove(backup)
    subprocess.run([sys.executable, os.path.join(PIPELINE, "build_dataset.py")],
                   capture_output=True, text=True, check=False)

# ---- H.2 deterministic regeneration -----------------------------------------
ds_path = os.path.join(OUT, "dataset-latest.json")
with open(ds_path, "rb") as f:
    first = f.read()
subprocess.run([sys.executable, os.path.join(PIPELINE, "build_dataset.py")],
               capture_output=True, text=True, check=False)
with open(ds_path, "rb") as f:
    second = f.read()
check("H2 build_dataset regenerates byte-identically", first == second)

bi_path = os.path.join(OUT, "builds_index.json")
with open(bi_path, "rb") as f:
    first = f.read()
subprocess.run([sys.executable, os.path.join(PIPELINE, "build_builds.py")],
               capture_output=True, text=True, check=False)
with open(bi_path, "rb") as f:
    second = f.read()
check("H2 build_builds regenerates byte-identically", first == second)

DATASET = load_json(ds_path)   # reload post-rebuild

# ---- H.4 full curated weapon/item coverage -----------------------------------
stats = load_json(os.path.join(OUT, "item_stats.json"))["items"]
lines = load_json(os.path.join(OUT, "weapon_lines.json"))
missing_stats = [k for k, w in DATASET["weapons"].items()
                 if w["status"] == "curated" and w["in_game_data"]
                 and not w.get("removed") and k not in stats]
missing_lines = [k for k, w in DATASET["weapons"].items()
                 if w["status"] == "curated" and not w.get("removed")
                 and k not in lines]
check("H4 every curated weapon is covered by the item-stats bank",
      not missing_stats, str(missing_stats[:5]))
check("H4 every curated weapon exists in the parsed game data",
      not missing_lines, str(missing_lines[:5]))
check("H4 the item bank is internally consistent (slot/category per line)",
      load_json(os.path.join(OUT, "item_stats.json"))["_meta"]["inconsistent"] == [])

# ---- H.17 catalog inclusion independent of icon availability -----------------
gear = load_json(os.path.join(OUT, "gear_lines.json"))
icons = load_json(os.path.join(OUT, "icon_data.json"))
artless = sorted(k for k in gear if k not in icons)
with open(os.path.join(ROOT, "dashboard", "index.html"), encoding="utf-8") as f:
    page = f.read()
check("H17 the gear catalogue contains entries with no packed icon",
      len(artless) > 0, f"{len(artless)} artless entries e.g. {artless[:3]}")
check("H17 an artless entry still ships in the dashboard GEAR catalogue",
      all(f'"{k}"' in page for k in artless[:5]))

# ---- H.20 generated output carries source + patch provenance -----------------
prov = DATASET["_meta"]["provenance"]
check("H20 dataset embeds the pinned source commit and game patch",
      prov["source_commit"] == PIN["commit"]
      and (prov.get("game_patch") or {}).get("date")
      and prov["verified"] is True)
check("H20 dataset provenance lists a verified hash per input",
      set(prov["inputs"]) == set(INPUTS)
      and all(isinstance(v, str) and len(v) == 64
              for v in prov["inputs"].values()))
bi = load_json(bi_path)
some = next(iter(bi["by_content"]["blackzone_roam"].values()))[0]
check("H20 build variants carry source, patch and approval provenance",
      some.get("source", {}).get("kind") and some.get("patch")
      and some.get("approval"))

# ---- offline fixture units: normalization stays structurally correct --------
inc = []
t = fis.item_tier({"@uniquename": "T10_TEST_ITEM", "@tier": "10"}, inc)
check("unit @tier attribute beats a single-digit name regex",
      t == "10" and inc == [])
t = fis.item_tier({"@uniquename": "T4_X", "@tier": "8"}, inc)
check("unit tier disagreement is reported, never silently resolved",
      t == "8" and len(inc) == 1)
ench = fis.enchant_ip({"enchantments": {"enchantment": [
    {"@enchantmentlevel": "1", "@itempower": "800"},
    {"@enchantmentlevel": "2", "@itempower": "900"}]}})
check("unit nested enchantment records are preserved",
      ench == {"1": 800, "2": 900})
check("unit keyframed geometry values resolve to their maximum",
      pd.kf_max("A 0:4;0.8:4;0.81:0") == 4.0 and pd.kf_max("5") == 5.0
      and pd.kf_max("junk") is None)
reg = {"S": {"@uniquename": "S", "channelingspell": {
    "directattributechange": {"@attribute": "health", "@change": "-99",
                              "@target": "enemy", "@effectarearadius": "5",
                              "@maxeffectareatargets": "7"}}}}
g = pd.spell_geometry("S", reg)
check("unit spell geometry extracts radius and max targets from damage nodes",
      g["radius"] == 5.0 and g["max_targets"] == 7)

# ------------------------------------------------------------------ summary
n_ok = sum(1 for _, ok in results if ok)
print("=" * 74)
print(f"{n_ok}/{len(results)} provenance tests passed")
sys.exit(0 if n_ok == len(results) else 1)
