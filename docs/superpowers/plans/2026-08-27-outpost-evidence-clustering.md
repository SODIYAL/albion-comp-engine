# Castle Outpost Evidence + Clustering Implementation Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Content-labeled small-fight killboard sampling plus a deterministic comp-cluster miner for castle outposts, gated per step, ending with real cluster candidates ready for the owner's first blind ratification round.

**Architecture:** A sibling sampler (`sample_content_rosters.py`) caches small albionbb battles with their listing metadata, labels each battle's content from a committed zone-rule table (`content_zones.yaml`), and emits near-complete rosters with per-player kits/IP into `content_rosters.json`. A new builder (`build_comp_clusters.py`) refuses to run unless that artifact passes its contract, then mines rosters two-level (seat signature → greedy weapon cores) into `comp_clusters.json`, stamping input SHA-256s. Both artifacts are display/evidence only.

**Tech Stack:** Python 3 (stdlib only + PyYAML, matching the pipeline), script-style tests, `jsonfmt` shared serializer.

**Spec:** `docs/superpowers/specs/2026-08-27-castle-outpost-comp-book-design.md` (§3, §4, §8a items 1–2, §8c gates 1–2, §10 steps 1–3). Plan B (book, kits/budget, forge/UI, doctrine tests) is written after this plan lands and the first blind round runs.

## Global Constraints

- Run Python as `py -3`, never `python`/`python3` (Windows Store stubs).
- Every writer of a committed artifact opens with `newline="\n"` or uses `jsonfmt.dump` (LF discipline; CRLF churns the tree).
- Tests are script-style, run at import, `sys.exit` — NEVER run them via pytest. `py -3 tests/<file>.py`; exit 0 = pass.
- No network in tests or normal builds. The sampler's fetch mode is an explicit, user-invoked network step only; tests exercise offline analysis over fixtures.
- No wall-clock or randomness in any committed artifact (determinism: rebuilds must be byte-identical). Timestamps come from the data (`newest_event` pattern), never `datetime.now()`.
- Display/evidence only: nothing in `engine/` reads either new artifact. Unknown content is stored as `"unlabeled"`, never guessed.
- Org identifiers: `content_rosters.json` carries an org *hash* (audit), never raw alliance/guild names; `comp_clusters.json` carries counts and battle ids only (battle ids are public killboard keys and are needed for the book's evidence gate), never org identifiers or hashes.
- Commit messages: write to a temp file and `git commit -F <file>` (PowerShell 5.1 mangles quoted multi-line messages). If using the Bash tool, a heredoc into a file then `-F` is equally safe.
- Provisional mining thresholds may only be revisited with more data — never loosened until clusters appear (spec §4).

---

### Task 1: Scouting probe — go/no-go on zone segmentation

**Files:**
- Create: `<scratchpad>/probe_smallfights.py` (throwaway — NOT committed)
- Create: `docs/superpowers/plans/2026-08-27-outpost-evidence-notes.md` (findings — committed)

**Interfaces:**
- Consumes: `api.albionbb.com` (sanctioned endpoint; explicit network step).
- Produces: the findings doc later tasks argue from — exact field names for zone/cluster, equipment slots, and average item power in listing rows and kill events, plus the observed small-battle noise level.

This task is a spike inside the plan: its output is knowledge, not kept code.

- [ ] **Step 1: Write the probe script** (in the session scratchpad directory, not the repo)

```python
#!/usr/bin/env python3
"""THROWAWAY probe: what does albionbb expose for small fights?

Answers (spec §3): (a) battle-level fields (zone/cluster name?),
(b) noise level at minPlayers=14, (c) kill-event equipment + item power.
"""
import json, time, urllib.request

API = "https://api.albionbb.com/us"
UA = {"User-Agent": "albion-comp-engine probe "
      "(github.com/SODIYAL/albion-comp-engine)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


battles = get(f"{API}/battles?minPlayers=14&page=1") or []
print(f"listing rows: {len(battles)}")
if battles:
    print("=== battle listing row keys ===")
    print(json.dumps(battles[0], indent=1)[:2000])
small = [b for b in battles if b.get("totalPlayers", 99) <= 30]
print(f"rows with <=30 players: {len(small)} of {len(battles)}")
if small:
    b = small[0]
    time.sleep(0.5)
    ev = get(f"{API}/battles/kills?ids={b['albionId']}") or []
    print(f"=== kill events for battle {b['albionId']}: {len(ev)} ===")
    if ev:
        print(json.dumps(ev[0], indent=1)[:3000])
```

- [ ] **Step 2: Run it and capture output**

Run: `py -3 -u <scratchpad>/probe_smallfights.py > <scratchpad>/probe_out.txt` then read the file.
Expected: JSON key dumps for one listing row and one kill event.

- [ ] **Step 3: Record findings in the notes doc**

Create `docs/superpowers/plans/2026-08-27-outpost-evidence-notes.md` answering, with the literal field names seen:

```markdown
# Outpost evidence probe findings (2026-08-27 plan, Task 1)

- Zone/cluster field on battle listing rows: <field name, or NONE>
- Zone/cluster field on kill events: <field name, or NONE>
- Equipment slots present on Killer/Victim: <list, e.g. MainHand, OffHand, Head, Armor, Shoes, Cape>
- Item power field: <field name + which object it sits on, or NONE>
- Small-battle volume: <N> of <M> page-1 rows had <=30 players
- Example small battle id used: <albionId>
- GO/NO-GO on zone segmentation: <GO | NO-GO>
```

- [ ] **Step 4: GATE — go/no-go decision**

If NO zone/cluster field exists anywhere: **STOP the plan here** and report to the owner — the spec's fallback (owner-confirmed labeling of mined candidates, spec §1) activates and Tasks 2–3 need revision before proceeding. Do not improvise a different heuristic.

If a zone field exists: adjust the literal field names in Task 3's code to match the findings doc (the plan's code uses `clusterName` on listing rows as the working assumption — replace if the probe says otherwise), then continue.

- [ ] **Step 5: Commit the findings doc**

```bash
git add docs/superpowers/plans/2026-08-27-outpost-evidence-notes.md
printf 'Probe findings: albionbb small-fight fields for outpost evidence\n' > /tmp/cm.txt
git commit -F /tmp/cm.txt
```

---

### Task 2: `content_zones.yaml` + fail-closed rule loader

**Files:**
- Create: `pipeline/content_zones.yaml`
- Create: `pipeline/content_zones.py`
- Test: `tests/test_content_rosters.py` (first checks land here; Task 3 extends the same file)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `content_zones.load(path) -> dict` returning `{"castle_outpost_zones": set[str], "max_side": int, "min_side": int, "table_sha256": str}`; raises `SystemExit(2)` with a loud message on any malformed/unknown key. Task 3 calls `load()` and `verdict(zone, side_sizes, rules) -> str` (returns `"castle_outpost"` or `"unlabeled"`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_rosters.py`:

```python
#!/usr/bin/env python3
"""Content-roster evidence contracts — step-1 stage gate (spec §8c.1).

Zone rules are fail-closed (unknown keys block, never mislabel); content
verdicts come only from the ruled table; unlabeled is never guessed;
offline re-analysis is deterministic and LF-only.

Run:  py -3 tests/test_content_rosters.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PIPE = os.path.join(ROOT, "pipeline")
sys.path.insert(0, PIPE)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run_zone_loader_checks():
    import content_zones
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "zones.yaml")
        write(good, "castle_outpost_zones: [FIXTURE OUTPOST EAST]\n"
                    "max_side: 9\nmin_side: 5\n")
        rules = content_zones.load(good)
        check("loader returns the ruled zone set",
              rules["castle_outpost_zones"] == {"FIXTURE OUTPOST EAST"}
              and rules["max_side"] == 9 and rules["min_side"] == 5)
        check("loader stamps the table hash (64 hex chars)",
              len(rules.get("table_sha256", "")) == 64)

        bad = os.path.join(td, "bad.yaml")
        write(bad, "castle_outpost_zones: [X]\nmax_side: 9\nmin_side: 5\n"
                   "surprise_key: 1\n")
        try:
            content_zones.load(bad)
            check("unknown key fails closed (exit 2)", False, "no exit")
        except SystemExit as e:
            check("unknown key fails closed (exit 2)", e.code == 2)

        empty = os.path.join(td, "empty.yaml")
        write(empty, "castle_outpost_zones: []\nmax_side: 9\nmin_side: 5\n")
        r = content_zones.load(empty)
        check("empty zone list loads (labels nothing, honestly)",
              r["castle_outpost_zones"] == set())

    check("verdict: outpost zone + legal sides -> castle_outpost",
          content_zones.verdict("FIXTURE OUTPOST EAST", [7, 7],
                                {"castle_outpost_zones":
                                 {"FIXTURE OUTPOST EAST"},
                                 "max_side": 9, "min_side": 5})
          == "castle_outpost")
    check("verdict: oversized side -> unlabeled, never guessed",
          content_zones.verdict("FIXTURE OUTPOST EAST", [7, 12],
                                {"castle_outpost_zones":
                                 {"FIXTURE OUTPOST EAST"},
                                 "max_side": 9, "min_side": 5})
          == "unlabeled")
    check("verdict: unknown zone -> unlabeled",
          content_zones.verdict("SOMEWHERE ELSE", [7, 7],
                                {"castle_outpost_zones":
                                 {"FIXTURE OUTPOST EAST"},
                                 "max_side": 9, "min_side": 5})
          == "unlabeled")


def run():
    run_zone_loader_checks()
    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, det in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}"
              + (f"\n      {det}" if det and not ok else ""))
    print("=" * 74)
    print(f"{passed}/{len(results)} content-roster tests passed")
    return passed, len(results)


if __name__ == "__main__":
    p, n = run()
    sys.exit(0 if p == n else 1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `py -3 tests/test_content_rosters.py`
Expected: `ModuleNotFoundError: No module named 'content_zones'` (import error is the failure — fine for script-style).

- [ ] **Step 3: Write the zone table and loader**

Create `pipeline/content_zones.yaml`:

```yaml
# Content-segmentation rule table (spec §3). AUDITABLE AND CORRECTABLE —
# the effect_overrides.yaml spirit: every label the sampler emits traces
# to a rule here. An empty zone list means the sampler labels NOTHING
# castle_outpost (honest empty), it never guesses.
#
# Seeding: populate from Task 1 probe observations + owner confirmation.
# Zone names must match the killboard field byte-for-byte.
castle_outpost_zones: []
# side-size rule: castle_outpost = zone match AND every attributed side
# within [min_side, max_side] (7-man content; 9 allows late joiners).
max_side: 9
min_side: 5
```

Create `pipeline/content_zones.py`:

```python
"""Fail-closed loader for the content-segmentation rule table (spec §3).

Unknown keys, wrong types, or an unreadable file are a loud exit 2 —
never a silent partial ruleset (a malformed table must not mislabel).
"""
import hashlib
import sys

import yaml

ALLOWED = {"castle_outpost_zones", "max_side", "min_side"}


def load(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        doc = yaml.safe_load(raw.decode("utf-8"))
    except Exception as e:
        sys.exit(2 if print(f"FAIL content_zones: unreadable {path}: {e}",
                            file=sys.stderr) is None else 2)
    if not isinstance(doc, dict):
        print(f"FAIL content_zones: {path} is not a mapping",
              file=sys.stderr)
        sys.exit(2)
    unknown = set(doc) - ALLOWED
    missing = ALLOWED - set(doc)
    if unknown or missing:
        print(f"FAIL content_zones: unknown keys {sorted(unknown)}, "
              f"missing keys {sorted(missing)}", file=sys.stderr)
        sys.exit(2)
    zones = doc["castle_outpost_zones"]
    if not isinstance(zones, list) or \
            not all(isinstance(z, str) and z for z in zones):
        print("FAIL content_zones: castle_outpost_zones must be a list "
              "of non-empty strings", file=sys.stderr)
        sys.exit(2)
    if not (isinstance(doc["max_side"], int)
            and isinstance(doc["min_side"], int)
            and 0 < doc["min_side"] <= doc["max_side"]):
        print("FAIL content_zones: side bounds must be ints with "
              "0 < min_side <= max_side", file=sys.stderr)
        sys.exit(2)
    return {"castle_outpost_zones": set(zones),
            "max_side": doc["max_side"], "min_side": doc["min_side"],
            "table_sha256": hashlib.sha256(raw).hexdigest()}


def verdict(zone, side_sizes, rules):
    """Content verdict for one battle. Only ever the ruled label or
    'unlabeled' — a battle the rules don't cover is stored unknown."""
    if zone in rules["castle_outpost_zones"] and side_sizes and \
            all(rules["min_side"] <= s <= rules["max_side"]
                for s in side_sizes):
        return "castle_outpost"
    return "unlabeled"
```

Note the loader's error style: print FAIL + `sys.exit(2)` (the pipeline's fail-closed idiom). Fix the clumsy first `sys.exit` line if you prefer — any form that prints and exits 2 passes the test.

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3 tests/test_content_rosters.py`
Expected: exit 0, all checks PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/content_zones.yaml pipeline/content_zones.py tests/test_content_rosters.py
printf 'Content zones: fail-closed segmentation rule table + loader\n' > /tmp/cm.txt
git commit -F /tmp/cm.txt
```

---

### Task 3: `sample_content_rosters.py` — the labeled small-fight sampler

**Files:**
- Create: `pipeline/sample_content_rosters.py`
- Modify: `tests/test_content_rosters.py` (extend with sampler checks)

**Interfaces:**
- Consumes: `content_zones.load/verdict` (Task 2); `sample_rosters.get_json` (existing, importable); `pipeline/out/dataset-latest.json` (weapon catalog).
- Produces: `pipeline/out/content_rosters.json` with the schema below; cache dir `pipeline/out/content_cache/` where each file is `{"battle": <listing row>, "events": [<kill events>]}`. CLI: `--pages N` (fetch; 0 = offline), `--server us`, `--cache DIR`, `--zones FILE`, `--out FILE` (the last three default to real paths and exist so tests can run hermetically).

Artifact schema (consumed by Task 4 — copy exactly):

```json
{
 "_meta": {
  "schema": 1,
  "source": "api.albionbb.com kill events (sanctioned endpoint)",
  "zone_table_sha256": "<64 hex>",
  "battles_cached": 0, "battles_labeled": 0, "newest_event": "",
  "bias": "near-complete = deaths seen for >= 80% of the side's attributed players (wiped sides). Winner rosters stay partial and are NOT emitted. Sides are alliance-level. Mount carriers show carried weapons. Rosters describe what is FIELDED, never what wins. DISPLAY/EVIDENCE ONLY."
 },
 "rosters": [
  {"battle": 123, "content": "castle_outpost", "zone": "...",
   "org": "<12-hex org hash>", "n": 7, "wiped": true,
   "avg_ip": 1250.0,
   "members": [{"weapon": "<catalog key>",
                "kit": {"head": "...", "armor": "...", "shoes": "...",
                        "cape": "..."}}]}
 ]
}
```

`avg_ip` is `null` when events carry no item power; `kit` values are raw killboard `Type` strings (normalization happens at cluster time); `members` sorted by (weapon, then kit armor) for determinism; `rosters` sorted by (battle, org).

- [ ] **Step 1: Extend the test with sampler checks (failing first)**

Add to `tests/test_content_rosters.py`, before `run()`'s print block — a fixture cache of one synthetic outpost battle (7v7, one side wiped) and one oversized battle, then offline runs:

```python
def fixture_event(killer_name, killer_org, killer_weap, victim_name,
                  victim_org, victim_weap, ts):
    def player(nm, org, wt):
        return {"Name": nm, "AllianceName": org, "GuildName": org,
                "AverageItemPower": 1250.0,
                "Equipment": {
                    "MainHand": {"Type": wt},
                    "Head": {"Type": "T8_HEAD_CLOTH_SET3"},
                    "Armor": {"Type": "T8_ARMOR_CLOTH_SET3"},
                    "Shoes": {"Type": "T8_SHOES_CLOTH_SET3"},
                    "Cape": {"Type": "T8_CAPEITEM_FW_MARTLOCK"}}}
    # NOTE: adjust the equipment/IP field names to the Task 1 findings doc
    # if the probe reported different ones.
        return None  # unreachable — structure above returns via dict
    return {"TimeStamp": ts,
            "Killer": player(killer_name, killer_org, killer_weap),
            "Victim": player(victim_name, victim_org, victim_weap)}


def run_sampler_checks():
    with open(os.path.join(PIPE, "out", "dataset-latest.json"),
              encoding="utf-8") as f:
        wkeys = sorted(json.load(f)["weapons"])
    # any two real catalog keys make valid fixture weapons
    wa, wb = f"T8_{wkeys[0]}", f"T8_{wkeys[1]}"
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "cache")
        os.makedirs(cache)
        zones = os.path.join(td, "zones.yaml")
        write(zones, "castle_outpost_zones: [FIXTURE OUTPOST EAST]\n"
                     "max_side: 9\nmin_side: 5\n")
        # battle 1: 7v7 in the outpost zone, side B fully wiped
        evs = []
        for i in range(7):
            evs.append(fixture_event(f"A{i}", "ALLIA", wa,
                                     f"B{i}", "ALLIB", wb,
                                     f"2026-08-20T12:{i:02d}:00Z"))
        write(os.path.join(cache, "1001.json"), json.dumps(
            {"battle": {"albionId": 1001,
                        "clusterName": "FIXTURE OUTPOST EAST"},
             "events": evs}))
        # battle 2: same zone but a 12-strong side -> unlabeled
        evs2 = []
        for i in range(12):
            evs2.append(fixture_event(f"C{i}", "ALLIC", wa,
                                      f"D{i % 12}", "ALLID", wb,
                                      f"2026-08-20T13:{i:02d}:00Z"))
        write(os.path.join(cache, "1002.json"), json.dumps(
            {"battle": {"albionId": 1002,
                        "clusterName": "FIXTURE OUTPOST EAST"},
             "events": evs2}))

        outp = os.path.join(td, "content_rosters.json")
        cmd = [sys.executable, os.path.join(PIPE,
               "sample_content_rosters.py"), "--pages", "0",
               "--cache", cache, "--zones", zones, "--out", outp]
        r1 = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8")
        check("sampler offline run exits 0", r1.returncode == 0,
              r1.stdout + r1.stderr)
        with open(outp, "rb") as f:
            first = f.read()
        subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8")
        with open(outp, "rb") as f:
            second = f.read()
        check("offline re-analysis is byte-identical and LF-only",
              first == second and b"\r" not in first)

        doc = json.loads(first.decode("utf-8"))
        check("_meta carries schema 1 + zone table hash",
              doc["_meta"]["schema"] == 1
              and len(doc["_meta"]["zone_table_sha256"]) == 64)
        labeled = [r for r in doc["rosters"]
                   if r["content"] == "castle_outpost"]
        check("wiped 7-man side in the ruled zone is labeled and emitted",
              len(labeled) == 1 and labeled[0]["n"] == 7
              and labeled[0]["wiped"] is True
              and labeled[0]["battle"] == 1001)
        check("oversized battle is unlabeled, never guessed",
              all(r["content"] == "unlabeled" for r in doc["rosters"]
                  if r["battle"] == 1002))
        check("no raw org names anywhere in the artifact",
              b"ALLIA" not in first and b"ALLIB" not in first)
        check("members carry weapon keys resolved against the catalog",
              all(m["weapon"] in set(wkeys)
                  for r in doc["rosters"] for m in r["members"]))
        check("kits carry raw Type strings; avg_ip present from fixture",
              labeled[0]["members"][0]["kit"]["armor"]
              == "T8_ARMOR_CLOTH_SET3"
              and labeled[0]["avg_ip"] == 1250.0)
```

Call `run_sampler_checks()` from `run()` after `run_zone_loader_checks()`. (Fix `fixture_event` while implementing: the inner `player` helper should simply `return` the dict — the sketch above shows the shape; make it clean code.)

- [ ] **Step 2: Run to verify the new checks fail**

Run: `py -3 tests/test_content_rosters.py`
Expected: zone-loader checks PASS, sampler checks FAIL (script missing).

- [ ] **Step 3: Write the sampler**

Create `pipeline/sample_content_rosters.py`:

```python
#!/usr/bin/env python3
"""Content-labeled SMALL-fight rosters — the castle-outpost evidence
layer (spec 2026-08-27 §3; step 1 of the comp-book stage-gate chain).

Sibling of sample_rosters.py, kept separate so roster_mixes.json stays
byte-stable. Differences: listing filter drops to minPlayers=14 (outpost
fights are ~14-20 players), each cache entry keeps the LISTING ROW
(zone name) alongside the kill events, and every battle gets a content
verdict from the committed rule table (content_zones.yaml) — the ruled
label or "unlabeled", never a guess.

Biases (recorded in _meta, same discipline as sample_rosters.py):
near-complete = wiped sides; winners stay partial and are NOT emitted;
sides are alliance-level; mount carriers show carried weapons. Rosters
describe what is FIELDED, never what wins.

DISPLAY/EVIDENCE ONLY. Explicit network step; --pages 0 re-analyzes the
cache offline, deterministically.

Usage:  py -3 pipeline/sample_content_rosters.py [--pages 40] [--server us]
        py -3 pipeline/sample_content_rosters.py --pages 0   (offline)
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import content_zones  # noqa: E402
import jsonfmt  # noqa: E402
from sample_rosters import get_json  # noqa: E402

MAX_TOTAL = 30       # listing cap: outpost-scale fights only
MIN_TOTAL = 10
KILL_DENSITY = 0.5   # totalKills >= this * totalPlayers (small-fight scale)
WIPE = 0.8           # deaths seen for >= this share of a side = wiped


def fetch(api, pages, cache):
    os.makedirs(cache, exist_ok=True)
    fetched = 0
    for page in range(1, pages + 1):
        listing = get_json(f"{api}/battles?minPlayers=14&page={page}") or []
        time.sleep(0.45)
        for b in listing:
            if not (MIN_TOTAL <= b.get("totalPlayers", 0) <= MAX_TOTAL) \
                    or b.get("totalKills", 0) < \
                    KILL_DENSITY * b["totalPlayers"]:
                continue
            path = os.path.join(cache, f"{b['albionId']}.json")
            if os.path.exists(path):
                continue
            ev = get_json(f"{api}/battles/kills?ids={b['albionId']}") or []
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"battle": b, "events": ev}, f)
            fetched += 1
            time.sleep(0.45)
        print(f"  page {page}: cache {len(os.listdir(cache))} battles",
              flush=True)
    print(f"fetched {fetched} new battles")


def org_hash(name):
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=40)
    ap.add_argument("--server", default="us")
    ap.add_argument("--cache", default=os.path.join(OUT, "content_cache"))
    ap.add_argument("--zones",
                    default=os.path.join(HERE, "content_zones.yaml"))
    ap.add_argument("--out",
                    default=os.path.join(OUT, "content_rosters.json"))
    args = ap.parse_args()
    rules = content_zones.load(args.zones)
    if args.pages > 0:
        fetch(f"https://api.albionbb.com/{args.server}", args.pages,
              args.cache)
    if not os.path.isdir(args.cache) or not os.listdir(args.cache):
        sys.exit("no cache — run with --pages N first")

    with open(os.path.join(OUT, "dataset-latest.json"),
              encoding="utf-8") as f:
        weapons = set(json.load(f)["weapons"])

    def weapon_key(t):
        if not t:
            return None
        k = t.split("@")[0]
        if "_" in k and k.split("_")[0].startswith("T"):
            k = k.split("_", 1)[1]
        return k if k in weapons else None

    def kit_of(eq):
        return {slot.lower(): ((eq.get(slot) or {}).get("Type") or "")
                for slot in ("Head", "Armor", "Shoes", "Cape")}

    rosters, newest, labeled_battles = [], "", set()
    for name in sorted(os.listdir(args.cache)):
        with open(os.path.join(args.cache, name), encoding="utf-8") as f:
            entry = json.load(f)
        listing, events = entry.get("battle") or {}, entry.get("events") or []
        bid = listing.get("albionId") or int(name.split(".")[0])
        zone = listing.get("clusterName") or ""  # Task 1 findings: adjust
        players = {}
        for e in events:
            newest = max(newest, e.get("TimeStamp") or "")
            for side, is_k in (("Killer", True), ("Victim", False)):
                p = e.get(side) or {}
                nm = p.get("Name")
                wk = weapon_key(((p.get("Equipment") or {})
                                 .get("MainHand") or {}).get("Type"))
                if not nm or not wk:
                    continue
                grp = p.get("AllianceName") or p.get("GuildName") or "?"
                rec = players.setdefault(
                    nm, {"org": grp, "weapon": wk,
                         "kit": kit_of(p.get("Equipment") or {}),
                         "ip": p.get("AverageItemPower"),
                         "kills": 0, "deaths": 0})
                rec["kills" if is_k else "deaths"] += 1
        by_side = {}
        for rec in players.values():
            by_side.setdefault(rec["org"], []).append(rec)
        content = content_zones.verdict(
            zone, [len(ms) for ms in by_side.values()], rules)
        if content != "unlabeled":
            labeled_battles.add(bid)
        for grp, ms in sorted(by_side.items()):
            deaths_seen = sum(1 for m in ms if m["deaths"])
            wiped = deaths_seen >= WIPE * len(ms)
            if not wiped:
                continue    # winners stay partial — never emitted
            ips = [m["ip"] for m in ms if isinstance(m["ip"], (int, float))]
            members = sorted(
                ({"weapon": m["weapon"], "kit": m["kit"]} for m in ms),
                key=lambda m: (m["weapon"], m["kit"]["armor"]))
            rosters.append({
                "battle": bid, "content": content, "zone": zone,
                "org": org_hash(grp), "n": len(ms), "wiped": True,
                "avg_ip": round(sum(ips) / len(ips), 1) if ips else None,
                "members": members})
    rosters.sort(key=lambda r: (r["battle"], r["org"]))

    doc = {"_meta": {
        "schema": 1,
        "source": "api.albionbb.com kill events (sanctioned endpoint)",
        "zone_table_sha256": rules["table_sha256"],
        "battles_cached": len(os.listdir(args.cache)),
        "battles_labeled": len(labeled_battles),
        "newest_event": newest,
        "bias": ("near-complete = deaths seen for >= 80% of the side's "
                 "attributed players (wiped sides). Winner rosters stay "
                 "partial and are NOT emitted. Sides are alliance-level. "
                 "Mount carriers show carried weapons. Rosters describe "
                 "what is FIELDED, never what wins. DISPLAY/EVIDENCE "
                 "ONLY.")},
        "rosters": rosters}
    jsonfmt.dump(doc, args.out)
    n_lab = sum(1 for r in rosters if r["content"] != "unlabeled")
    print(f"rosters: {len(rosters)} wiped sides, {n_lab} content-labeled "
          f"-> {os.path.relpath(args.out, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3 tests/test_content_rosters.py`
Expected: exit 0, all checks PASS (zone loader + sampler).

- [ ] **Step 5: Run the full standing gate list to prove nothing regressed**

Run each of: `py -3 tests/test_golden.py`, `py -3 tests/test_forge.py`, `py -3 tests/test_provenance.py`, `py -3 tests/test_js_parity.py`.
Expected: all exit 0 (this task touches no engine/scoring path — a failure means an accident; investigate before continuing).

- [ ] **Step 6: Commit**

```bash
git add pipeline/sample_content_rosters.py tests/test_content_rosters.py
printf 'Sampler: content-labeled small-fight rosters (castle outpost evidence)\n' > /tmp/cm.txt
git commit -F /tmp/cm.txt
```

---

### Task 4: `build_comp_clusters.py` — two-level miner with stage gate

**Files:**
- Create: `pipeline/build_comp_clusters.py`
- Test: `tests/test_comp_clusters.py`

**Interfaces:**
- Consumes: `pipeline/out/content_rosters.json` (Task 3 schema — validated before use, exit 2 on violation); `pipeline/out/dataset-latest.json` (weapon catalog + `role_menu`/`role_hint` per weapon, the `seats_of` pattern).
- Produces: `pipeline/out/comp_clusters.json`:

```json
{
 "_meta": {"schema": 1,
  "inputs": {"content_rosters.json": "<sha256>",
             "dataset-latest.json": "<sha256>"},
  "params": {"min_rosters": 5, "min_orgs": 3, "min_battles": 3,
             "min_lift": 1.2, "alt_share": 0.3},
  "semantics": "Candidate comp kinds mined from near-complete (wiped-side) rosters. Describes what is FIELDED, never what wins. DISPLAY/EVIDENCE ONLY — never a scoring input. Cluster ids are stable only against the input hashes above; the comp book's evidence gate re-checks them."},
 "contents": {"castle_outpost": {"clusters": [
   {"id": "castle_outpost-001", "signature": {"main_healer": 1, "...": 0},
    "core": ["..."], "rosters": 9, "orgs": 4, "battles": 7,
    "wiped_share": 1.0, "battle_ids": [1, 2],
    "ip": {"p25": 1100.0, "median": 1250.0, "p75": 1380.0},
    "seats": {"main_healer": {"weapons": [{"weapon": "...", "share": 0.9}],
              "kits": {"armor": [{"item": "ARMOR_CLOTH_SET3",
                                  "share": 0.8}]}}}}],
   "unassigned": 0}}}
```

CLI: `--rosters FILE`, `--dataset FILE`, `--out FILE` (defaults to the real paths; overridable for hermetic tests).

**Mining algorithm (spec §4, made exact):**

1. Use only rosters with `content != "unlabeled"`; group by content.
2. Seat of a weapon = `role_menu[0]`, else `"unseated_" + role_hint` (the `sample_rosters.seats_of` rule). Signature = sorted `(seat, count)` tuple.
3. Group rosters by signature. Merge pass: order signatures by (-support, lexicographic); a signature with the same total size differing from an already-kept group's signature by exactly one substitution (multiset L1 distance == 2) merges into that group. Deterministic, single pass.
4. Within each group, mine cores greedily and disjointly: find the best anchor pair exactly as `build_cohort_families.mine_bucket` does (same support/org/battle/lift gates, lexicographic tie-break) — then EXTEND: repeatedly scan weapons in lexicographic order, adding the one that maximizes `(support, orgs, battles)` while support stays ≥ MIN_ROSTERS and org/battle gates hold; stop when no extension qualifies. Members = rosters containing every core weapon. Emit cluster; remove members; repeat until no anchor qualifies.
5. Per cluster: per-seat weapon alternatives with shares (≥ ALT_SHARE of members' players in that seat, floor 2 observations); per-seat kit aggregates for head/armor/shoes/cape — normalize raw Type by stripping `@N` and a leading `T<d>_` prefix, count, emit top 3 with shares; IP p25/median/p75 over members' `avg_ip` (skip nulls; emit null if none); `wiped_share` = share of member rosters with `wiped == true`; sorted `battle_ids`.
6. Cluster ids: `f"{content}-{i:03d}"` in emission order (support desc, then anchor lexicographic). `_meta.semantics` states ids are stable only against the recorded input hashes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_comp_clusters.py` (mirrors `test_cohort_families.py` structure; hermetic fixtures):

```python
#!/usr/bin/env python3
"""Comp-cluster artifact contracts — stage gate 2 (spec §8a/§8c.2).

The builder must refuse malformed input (fail closed, exit 2), rebuild
byte-identically, enforce its published support gates, keep clusters
disjoint, stamp input hashes, and leak no org identifiers.

Run:  py -3 tests/test_comp_clusters.py
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PIPE = os.path.join(ROOT, "pipeline")
BUILDER = os.path.join(PIPE, "build_comp_clusters.py")
DATASET = os.path.join(PIPE, "out", "dataset-latest.json")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def fixture_rosters(wa, wb, wc, wd):
    """9 labeled 4-man rosters across 4 orgs / 7 battles sharing a core
    (wa, wb), plus noise. Small n keeps the fixture readable; the miner
    has no size-7 assumption."""
    rs = []
    for i in range(9):
        rs.append({"battle": 100 + i % 7, "content": "castle_outpost",
                   "zone": "Z", "org": f"{'abcd'[i % 4]:0>12}", "n": 4,
                   "wiped": True, "avg_ip": 1200.0 + 10 * i,
                   "members": [
                       {"weapon": wa, "kit": {"head": "T8_HEAD_PLATE_SET1",
                        "armor": "T8_ARMOR_PLATE_SET1",
                        "shoes": "T8_SHOES_PLATE_SET1", "cape": "T8_CAPE"}},
                       {"weapon": wb, "kit": {"head": "T8_HEAD_CLOTH_SET1",
                        "armor": "T8_ARMOR_CLOTH_SET1",
                        "shoes": "T8_SHOES_CLOTH_SET1", "cape": "T8_CAPE"}},
                       {"weapon": wc, "kit": {"head": "T8_HEAD_CLOTH_SET2",
                        "armor": "T8_ARMOR_CLOTH_SET2",
                        "shoes": "T8_SHOES_CLOTH_SET2", "cape": "T8_CAPE"}},
                       {"weapon": wd, "kit": {"head": "T8_HEAD_LEATHER_SET1",
                        "armor": "T8_ARMOR_LEATHER_SET1",
                        "shoes": "T8_SHOES_LEATHER_SET1",
                        "cape": "T8_CAPE"}}]})
    rs.append({"battle": 300, "content": "unlabeled", "zone": "",
               "org": "e" * 12, "n": 4, "wiped": True, "avg_ip": None,
               "members": rs[0]["members"]})
    return rs


def doc_for(rosters):
    return {"_meta": {"schema": 1, "source": "fixture",
                      "zone_table_sha256": "0" * 64,
                      "battles_cached": 8, "battles_labeled": 7,
                      "newest_event": "2026-08-20T12:00:00Z",
                      "bias": "fixture"},
            "rosters": rosters}


def run():
    with open(DATASET, encoding="utf-8") as f:
        wkeys = sorted(json.load(f)["weapons"])
    wa, wb, wc, wd = wkeys[0], wkeys[1], wkeys[2], wkeys[3]
    with tempfile.TemporaryDirectory() as td:
        rp = os.path.join(td, "content_rosters.json")
        op = os.path.join(td, "comp_clusters.json")
        with open(rp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc_for(fixture_rosters(wa, wb, wc, wd)), f)
        cmd = [sys.executable, BUILDER, "--rosters", rp,
               "--dataset", DATASET, "--out", op]

        r1 = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8")
        check("builder exits 0 on valid input", r1.returncode == 0,
              r1.stdout + r1.stderr)
        with open(op, "rb") as f:
            first = f.read()
        subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8")
        with open(op, "rb") as f:
            second = f.read()
        check("rebuild is byte-identical (deterministic, LF-only)",
              first == second and b"\r" not in first)

        doc = json.loads(first.decode("utf-8"))
        co = doc["contents"]["castle_outpost"]
        p = doc["_meta"]["params"]
        check("fixture core is mined into exactly one cluster",
              len(co["clusters"]) == 1
              and set(co["clusters"][0]["core"]) >= {wa, wb},
              json.dumps(co)[:300])
        c = co["clusters"][0]
        check("published gates hold on every emitted cluster",
              c["rosters"] >= p["min_rosters"]
              and p["min_orgs"] <= c["orgs"] <= c["rosters"]
              and p["min_battles"] <= c["battles"] <= c["rosters"])
        check("disjoint: cluster rosters + unassigned = labeled rosters",
              c["rosters"] + co["unassigned"] == 9)
        check("input hashes stamped (64 hex each)",
              all(len(h) == 64 for h in doc["_meta"]["inputs"].values()))
        check("no org identifiers in the artifact",
              b'"org"' not in first and b"abcd" not in first)
        check("ip quartiles present and ordered",
              c["ip"]["p25"] <= c["ip"]["median"] <= c["ip"]["p75"])
        check("kit aggregates normalized (no tier prefix, no enchant)",
              all(not it["item"].startswith("T8_")
                  for s in c["seats"].values()
                  for sl in s["kits"].values() for it in sl))
        check("unlabeled rosters never enter mining",
              "300" not in json.dumps(c["battle_ids"]))

        # fail-closed: schema violation exits 2
        bad = doc_for(fixture_rosters(wa, wb, wc, wd))
        del bad["_meta"]["zone_table_sha256"]
        with open(rp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(bad, f)
        r3 = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8")
        check("stage gate: malformed rosters artifact -> exit 2",
              r3.returncode == 2, f"rc={r3.returncode}")

        # below-gate support yields no cluster, honestly
        thin = doc_for(fixture_rosters(wa, wb, wc, wd)[:3])
        with open(rp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(thin, f)
        subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8")
        with open(op, encoding="utf-8") as f:
            thin_doc = json.load(f)
        check("below-gate sample yields zero clusters (gates never loosen)",
              thin_doc["contents"]["castle_outpost"]["clusters"] == [])

    print("=" * 74)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, det in results:
        print(f"{'PASS' if ok else 'FAIL':4}  {name}"
              + (f"\n      {det}" if det and not ok else ""))
    print("=" * 74)
    print(f"{passed}/{len(results)} comp-cluster tests passed")
    return passed, len(results)


if __name__ == "__main__":
    p, n = run()
    sys.exit(0 if p == n else 1)
```

Fixture care while implementing: the four fixture weapons come from the real catalog, so their seats are whatever the dataset says — the test asserts core membership and gate math, never specific seat names. If `wkeys[0..3]` happen to share a seat, that's fine (signature `{seat: 4}`).

- [ ] **Step 2: Run to verify it fails**

Run: `py -3 tests/test_comp_clusters.py`
Expected: FAIL — builder script missing (subprocess non-zero).

- [ ] **Step 3: Write the builder**

Create `pipeline/build_comp_clusters.py`. Full structure (implement exactly; the mining core adapts `build_cohort_families.mine_bucket`):

```python
#!/usr/bin/env python3
"""Candidate comp kinds per content, mined from near-complete rosters
(spec 2026-08-27 §4; stage 2 of the comp-book chain).

Two levels: seat SIGNATURE first (role_menu primary seat per weapon —
weapon-exact clustering over-fragments), then greedy DISJOINT weapon
cores within each signature group (the cohort-families algorithm,
extended beyond pairs because wiped-side rosters are near-complete).

STAGE GATE (fail closed, exit 2): refuses to run unless the rosters
artifact passes its schema contract and the dataset exists; stamps the
SHA-256 of every input into _meta so the comp book's evidence citations
can chain back (spec §8c.3).

Stated bias: wiped-side rosters are the comps that DIED. Clusters
describe what the community fields, never what wins. DISPLAY/EVIDENCE
ONLY — nothing in scoring reads this artifact.

Run:  py -3 pipeline/build_comp_clusters.py     (after build_dataset.py)
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402

# PROVISIONAL (spec §4): revisit with a bigger sample, never loosen
# until clusters appear. Mirrors cohort-families' committed gates.
MIN_ROSTERS = 5
MIN_ORGS = 3
MIN_BATTLES = 3
MIN_LIFT = 1.2
ALT_SHARE = 0.3     # per-seat alternative floor (share of seat players)
KIT_TOP = 3         # kit items reported per slot

ROSTER_KEYS = {"battle", "content", "zone", "org", "n", "wiped",
               "avg_ip", "members"}
META_KEYS = {"schema", "source", "zone_table_sha256", "battles_cached",
             "battles_labeled", "newest_event", "bias"}


def fail(msg):
    print(f"FAIL build_comp_clusters: {msg}", file=sys.stderr)
    sys.exit(2)


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_rosters(path):
    if not os.path.exists(path):
        fail(f"{path} missing — run sample_content_rosters.py first")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    meta = doc.get("_meta") or {}
    if meta.get("schema") != 1 or set(meta) != META_KEYS:
        fail("rosters _meta violates schema 1 contract")
    rows = doc.get("rosters")
    if not isinstance(rows, list):
        fail("rosters list missing")
    for r in rows:
        if set(r) != ROSTER_KEYS or not isinstance(r["members"], list):
            fail(f"roster row violates contract: battle {r.get('battle')}")
    return rows


def norm_item(t):
    k = (t or "").split("@")[0]
    if "_" in k and k.split("_")[0].startswith("T"):
        k = k.split("_", 1)[1]
    return k


def quart(vals):
    vs = sorted(v for v in vals if isinstance(v, (int, float)))
    if not vs:
        return None
    def q(p):
        i = p * (len(vs) - 1)
        lo, hi = int(i), min(int(i) + 1, len(vs) - 1)
        return round(vs[lo] + (vs[hi] - vs[lo]) * (i - lo), 1)
    return {"p25": q(0.25), "median": q(0.5), "p75": q(0.75)}


def mine_content(rows, seat_of):
    """rows: labeled roster dicts. Returns (clusters, unassigned)."""
    sig_of = {}
    for i, r in enumerate(rows):
        sig = tuple(sorted(collections.Counter(
            seat_of(m["weapon"]) for m in r["members"]).items()))
        sig_of[i] = sig
    # signature grouping + one-substitution merge (spec §4.3)
    support = collections.Counter(sig_of.values())
    ordered = sorted(support, key=lambda s: (-support[s], s))
    group_of, groups = {}, []
    for sig in ordered:
        merged = False
        for gi, base in enumerate(groups):
            if sum(n for _, n in sig) == sum(n for _, n in base):
                a, b = dict(sig), dict(base)
                l1 = sum(abs(a.get(k, 0) - b.get(k, 0))
                         for k in set(a) | set(b))
                if l1 == 2:
                    group_of[sig] = gi
                    merged = True
                    break
        if not merged:
            group_of[sig] = len(groups)
            groups.append(sig)
    by_group = collections.defaultdict(list)
    for i in sig_of:
        by_group[group_of[sig_of[i]]].append(i)

    clusters, assigned = [], set()
    for gi in sorted(by_group, key=lambda g: (-len(by_group[g]),
                                              groups[g])):
        remaining = [i for i in by_group[gi]]
        while len(remaining) >= MIN_ROSTERS:
            core = best_anchor(remaining, rows)
            if core is None:
                break
            core = extend_core(core, remaining, rows)
            members = [i for i in remaining
                       if set(core) <= {m["weapon"]
                                        for m in rows[i]["members"]}]
            clusters.append(emit(core, members, rows, groups[gi],
                                 seat_of))
            assigned.update(members)
            remaining = [i for i in remaining if i not in members]
    clusters.sort(key=lambda c: (-c["rosters"], c["core"]))
    for i, c in enumerate(clusters):
        c["id"] = f"castle_outpost-{i + 1:03d}"
    return clusters, len(rows) - len(assigned)
```

`best_anchor` is `build_cohort_families.mine_bucket`'s pair search verbatim (same gates, same lexicographic tie-break, lift over the group's remaining rosters). `extend_core(core, remaining, rows)`:

```python
def extend_core(core, remaining, rows):
    core = list(core)
    while True:
        members = [i for i in remaining
                   if set(core) <= {m["weapon"]
                                    for m in rows[i]["members"]}]
        cand = sorted({m["weapon"] for i in members
                       for m in rows[i]["members"]} - set(core))
        best = None
        for w in cand:
            sub = [i for i in members
                   if w in {m["weapon"] for m in rows[i]["members"]}]
            orgs = {rows[i]["org"] for i in sub}
            bats = {rows[i]["battle"] for i in sub}
            if len(sub) < MIN_ROSTERS or len(orgs) < MIN_ORGS \
                    or len(bats) < MIN_BATTLES:
                continue
            key = (len(sub), len(orgs), len(bats))
            if best is None or key > best[0]:
                best = (key, w)
        if best is None:
            return sorted(core)
        core.append(best[1])
```

`emit(core, member_idx, rows, signature, seat_of)` builds the cluster dict from the Interfaces schema: counts, sorted `battle_ids`, `wiped_share`, `quart` of members' `avg_ip`, per-seat weapon shares (floor `max(2, ALT_SHARE * seat_player_count)`) and per-slot normalized kit top-`KIT_TOP` with shares. No org identifiers — orgs are counted, never emitted.

`main()`: argparse (`--rosters`, `--dataset`, `--out` with real defaults), `load_rosters`, dataset existence check (`fail` if missing), `seat_of` closure from dataset weapons (`role_menu[0]` else `"unseated_" + role_hint`, mirroring `sample_rosters.seats_of`), group rows by `content` (skip `"unlabeled"`), mine each, then `jsonfmt.dump` the artifact with `_meta.inputs` = SHA-256 of both input files and the `params`/`semantics` from the Interfaces block. Note: with multiple contents later, the id prefix comes from the content key — write `f"{content}-{i + 1:03d}"`, not the literal.

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3 tests/test_comp_clusters.py`
Expected: exit 0, all checks PASS. Debug determinism failures first (they poison everything downstream): the usual causes are set iteration reaching output or an unsorted tie.

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_comp_clusters.py tests/test_comp_clusters.py
printf 'Comp clusters: two-level miner with stage gate + contracts\n' > /tmp/cm.txt
git commit -F /tmp/cm.txt
```

---

### Task 5: Wire-up — docs, gate list, and the real first sample

**Files:**
- Modify: `CLAUDE.md` (Tests section + Build chain section)
- Modify: `pipeline/README.md` (pipeline steps)
- Modify: `HANDOFF.md` (current-state)
- Create: `pipeline/out/content_rosters.json` + `pipeline/out/comp_clusters.json` (first real committed artifacts)

**Interfaces:**
- Consumes: everything above.
- Produces: the blind-round input (real cluster candidates) and the documented gate chain.

- [ ] **Step 1: Check the published-comp content vocabulary**

Run: `py -3 -c "import re; s=open('pipeline/build_builds.py',encoding='utf-8').read(); print([l for l in s.splitlines() if 'content' in l.lower()][:20])"` and read the relevant lines.
If `content:` values are validated against a fixed list, add `castle_outpost` to it (and only it); if free-form (the observed records suggest so), do nothing. Either way note the finding in the Task 1 findings doc.

- [ ] **Step 2: Seed `content_zones.yaml` with observed outpost zones**

From the Task 1 probe (re-run the probe listing over a few pages if needed), collect zone names of ≤30-player battles that match known castle-outpost clusters. **This seeding is owner-reviewable data curation**: put the candidate zone list in the findings doc, add the confident ones to `castle_outpost_zones`, and flag the list for the owner at the blind round (a wrong zone yields mislabeled evidence — the honest failure is a SHORTER list).

- [ ] **Step 3: Fetch the first real sample** (explicit network step)

Run: `py -3 -u pipeline/sample_content_rosters.py --pages 40`
Expected: cache populates under `pipeline/out/content_cache/`; artifact reports labeled roster counts. If zero battles get labeled, widen `--pages` before concluding the zone list is wrong — outpost fights are timer-driven and sparse per page.

- [ ] **Step 4: Build clusters over the real sample**

Run: `py -3 pipeline/build_comp_clusters.py`
Expected: exit 0. Zero clusters on a thin first sample is an HONEST result (gates never loosen) — report the support numbers as-is; the blind round waits for more sample, not for looser gates.

- [ ] **Step 5: Run the new gate pair + full standing list**

Run: `py -3 tests/test_content_rosters.py`, `py -3 tests/test_comp_clusters.py`, then the full CLAUDE.md test list.
Expected: all exit 0.

- [ ] **Step 6: Update docs**

- `CLAUDE.md` Tests block, after the `test_cohort_families.py` line:
  ```text
  py -3 tests/test_content_rosters.py # content-labeled small-fight roster contracts (outpost evidence)
  py -3 tests/test_comp_clusters.py   # comp-cluster mining contracts (stage-gated, display-only)
  ```
- `CLAUDE.md` Build chain note (network steps sentence): add `sample_content_rosters.py` beside `sample_rosters.py` as an explicit network step.
- `pipeline/README.md`: a short section "Content evidence (comp book chain, steps 1–2)" describing sampler → rosters → clusters with the stage-gate rule (each builder refuses unverified input) and a pointer to the spec.
- `HANDOFF.md`: current-state entry — Plan A landed; next step is the first blind ratification round (Plan B's precondition).

- [ ] **Step 7: Commit artifacts + docs**

```bash
git add pipeline/out/content_rosters.json pipeline/out/comp_clusters.json pipeline/content_zones.yaml CLAUDE.md pipeline/README.md HANDOFF.md docs/superpowers/plans/2026-08-27-outpost-evidence-notes.md
printf 'Outpost evidence: first labeled sample + clusters, gate chain documented\n' > /tmp/cm.txt
git commit -F /tmp/cm.txt
```

Do NOT commit `pipeline/out/content_cache/` if it is large; check `.gitignore` — `roster_cache` precedent decides (mirror whatever `sample_rosters.py`'s cache does today).

- [ ] **Step 8: Report readiness for the blind round**

Summarize for the owner: labeled roster count, cluster count with support numbers, the seeded zone list awaiting their review, and (if clusters exist) the case cards are ready to present blind — owner's calls BEFORE engine labels, per spec §5. Plan B gets written after that round.

---

## Self-Review (completed at write time)

- **Spec coverage:** §3 sampler + zone table → Tasks 2–3; §3 scouting → Task 1; §4 miner → Task 4; §8a gates 1–2 → the two test files; §8c gates 1–2 → schema contract + exit-2 checks; §10 steps 1–3 → Tasks 1–5. §3's albioncompo/MetaBattle tag mapping is deferred to Plan B except the vocabulary check (Task 5 step 1) — deliberate: no albioncompo scaling happens before ratification exists.
- **Placeholder scan:** no TBDs; two intentional adjust-points are tied to the Task 1 findings doc (`clusterName`, equipment/IP field names) with the literal working assumption written into the code.
- **Type consistency:** artifact schemas appear once in each producing task's Interfaces block and are consumed by name in the next task's test fixtures; `content_zones.load` return shape matches all three call sites.
