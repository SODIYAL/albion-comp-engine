# Coherent Builds + Style-Conditioned Kit Doctrine — Implementation Plan

> **STATUS 2026-09-08: EXECUTED.** Shipped the same day (R29–R33, R24b; VALIDATION.md index 09-08 "Coherent builds and style cells"). The checkboxes below are the plan as written.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the archetype chain carry a coherent build past the chest, and give every seat style-conditioned kit cells that fire on a DECLARED style only.

**Architecture:** The doctrine miner in `pipeline/build_dataset.py` keeps its shape; its chain guard is rescaled from counts to shares, and the miner gains a `style` parameter that filters the killboard builds to parties of one style (linked through a new tiny `pipeline/party_link.py`) and writes into `kit_styles.<style>` on the seat record. A new explicit step `pipeline/derive_party_styles.py` labels parties from the COMMITTED artifact with the engine's weapons-only identity. Both engine ports read the cell through the ONE doctrine reader `_seat_kit`, merged over the band.

**Tech Stack:** Python 3 (`py -3`), script-style tests (`py -3 tests/<file>.py`, exit 0 = pass, NOT pytest), the JS port in `engine/app_scoring.js` (binary to grep — use `Select-String` or the Read tool), `dashboard/build.py` bundler.

**Spec:** `notes/specs/2026-09-08-coherent-style-kits-design.md`

## Global Constraints

- Windows: `py -3`, never `python`. Commit messages via `git commit -F <file>` written BOM-less (`printf` from Git Bash is fine).
- Every writer of a committed artifact opens with `newline="\n"`.
- Never pipe a build through `grep`/`tail` in the pipeline you read `$LASTEXITCODE` from; redirect to a file.
- `build_dataset.py` fails closed (exit 2) on provenance drift; `problems.append(...)` is the release-blocking channel inside it.
- Change one engine port, change both, rerun `py -3 tests/test_js_parity.py`.
- Descriptive layers never score; kit doctrine is GENERATION evidence only; manual builds always score.
- Never invent a number to fill a hole: a thin cell is absent, never borrowed.
- Balanced never reads a style cell (owner, 2026-09-08).
- Tests pin MECHANISMS, never exact corpus counts (the harvest grows nightly).
- Branch: `blind-round-4-grading` already holds the spec commit; keep working on it (or branch `coherent-style-kits` from it) and open one PR at the end.
- Gate list to run before the PR (CLAUDE.md "Tests"): golden, forge, builds, interactions, provenance, patch_history, js_parity, `node tests/test_loadout_codec.js`, `node tests/test_display_math.js`, cohort_families (from PowerShell), roles, validation_modes, `tier2_blindtest.py v4`.

---

### Task 1: Rescale the chain guard

**Files:**
- Modify: `pipeline/build_dataset.py:1170-1245` (`_modal_build_chain`)
- Test: `tests/test_roles.py` (new `t_chain_guard`, registered in `__main__`)

**Interfaces:**
- Consumes: `_modal_build_chain(build_dicts, uni, effect_map, gear, normalize)` — `build_dicts` = list of `(gear_dict, weight, player)`; gear_dict keys are raw slot names (`"Armor"`, `"Head"`, ...); returns `{slot: [id, n, of]}`.
- Produces: same signature and return shape; two new module constants `CHAIN_POCKET_SHARE = 0.20`, `CHAIN_POCKET_VOTES = 20` (module level, next to `KIT_SLOT_MAP`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_roles.py` before `if __name__ == "__main__":`:

```python
def t_chain_guard():
    # R29 (2026-09-08, spec notes/specs/2026-09-08-coherent-style-kits-design.md
    # section 1): the archetype chain's "rare pocket" guard compares SHARES,
    # never a conditional count against an unconditional count, and a pocket
    # continues only while it holds >= 20% of the population or 20 votes.
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "bd", os.path.join(ROOT, "pipeline", "build_dataset.py"))
    bd = _ilu.module_from_spec(spec)
    spec.loader.exec_module(bd)
    gear = {g: {"gear_class": "plate"} for g in (
        "CHEST_A", "CHEST_B", "CHEST_C", "CHEST_D", "HELM_A", "HELM_X",
        "SHOES_A", "SHOES_X", "HELM_B", "HELM_Z", "SHOES_B", "SHOES_Z",
        "CAPE_B", "CAPE_Z")}
    ident = lambda v: v if v in gear else None
    # A: a 30% chest pocket whose wearers all share helmet + shoes; the
    # other 70 wear one helmet and one pair of shoes between them. The
    # old guard (30 < 0.5 x 70) stopped at the chest; shares pass.
    pop_a = []
    for i in range(30):
        pop_a.append(({"Armor": "CHEST_A", "Head": "HELM_A", "Shoes": "SHOES_A"},
                      1.0, f"a{i}"))
    for i, ch in enumerate(["CHEST_B"] * 25 + ["CHEST_C"] * 25 + ["CHEST_D"] * 20):
        pop_a.append(({"Armor": ch, "Head": "HELM_X", "Shoes": "SHOES_X"},
                      1.0, f"x{i}"))
    sel_a = bd._modal_build_chain(pop_a, {"plate"}, {}, gear, ident)
    # B: the 2026-09-04 Greataxe shape — chain narrows to an 8-build pocket
    # by the shoes step (8 of 74 = 11% < 20%, < 20 votes): the 7-of-8 cape
    # inside it is never picked.
    pop_b = []
    for i in range(30):
        pop_b.append(({"Armor": "CHEST_A", "Head": "HELM_Z", "Shoes": "SHOES_Z",
                       "Cape": "CAPE_Z"}, 1.0, f"b{i}"))
    for i in range(44):
        head = "HELM_B" if i < 20 else "HELM_Z"
        shoes = "SHOES_B" if i < 8 else "SHOES_Z"
        cape = "CAPE_B" if i < 7 else "CAPE_Z"
        pop_b.append(({"Armor": "CHEST_B", "Head": head, "Shoes": shoes,
                       "Cape": cape}, 1.0, f"c{i}"))
    sel_b = bd._modal_build_chain(pop_b, {"plate"}, {}, gear, ident)
    # C: a pick under half the unconditional modal's SHARE stops: helmet A
    # is 8 of the 30-build pocket (27%) while helmet X is 70% of everyone.
    pop_c = []
    for i in range(30):
        pop_c.append(({"Armor": "CHEST_A",
                       "Head": "HELM_A" if i < 8 else f"HELM_{'PQRSTUV'[i % 7]}"},
                      1.0, f"d{i}"))
    for i in range(70):
        pop_c.append(({"Armor": "CHEST_B", "Head": "HELM_X"}, 1.0, f"e{i}"))
    for extra in "PQRSTUV":
        gear[f"HELM_{extra}"] = {"gear_class": "plate"}
    sel_c = bd._modal_build_chain(pop_c, {"plate"}, {}, gear, ident)
    check("R29 chain guard: a 30% pocket carries its helmet and shoes; an "
          "11% pocket stops before its 7-of-8 cape; a pick under half the "
          "unconditional modal's share stops",
          list(sel_a) == ["armor", "head", "shoes"]
          and sel_a["armor"][0] == "CHEST_A" and sel_a["head"][0] == "HELM_A"
          and list(sel_b) == ["armor", "head", "shoes"]
          and "cape" not in sel_b and sel_b["shoes"][0] == "SHOES_B"
          and list(sel_c) == ["armor"],
          f"a={sel_a} b={sel_b} c={sel_c}")
```

Register it: in the `if __name__ == "__main__":` block add `t_chain_guard()` after `t_doctrine_bands()`.

Note for the C population: the chest pocket must be CHEST_A (30) vs CHEST_B (70) — CHEST_B is modal at 70%, so the chain picks CHEST_B and its helmet is HELM_X 70/70 — that would NOT stop. Fix the population so CHEST_A is the modal chest: give the 70 others three different chests (`CHEST_B` x 25, `CHEST_C` x 25, `CHEST_D` x 20) all wearing `HELM_X`. Then chest A (30%) is modal, its pocket helmet HELM_A holds 8/30 = 0.27 against HELM_X's unconditional share 0.70 (half = 0.35) — stops. Write the C loop as:

```python
    for i, ch in enumerate(["CHEST_B"] * 25 + ["CHEST_C"] * 25 + ["CHEST_D"] * 20):
        pop_c.append(({"Armor": ch, "Head": "HELM_X"}, 1.0, f"e{i}"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; grep R29 "$SCRATCH/roles.log"`
Expected: `FAIL  R29 ...` with `a={'armor': ['CHEST_A', 30, 100]}` (old guard stops at the chest).

- [ ] **Step 3: Implement the rescaled guard**

In `pipeline/build_dataset.py`, add next to `KIT_SLOT_MAP` (line ~1067):

```python
# Chain pocket floor (2026-09-08, spec notes/specs/2026-09-08-coherent-
# style-kits-design.md): the conditional pool keeps chaining only while it
# holds CHAIN_POCKET_SHARE of the weapon's population or CHAIN_POCKET_VOTES
# votes — the 2026-09-04 Greataxe pocket (8 of ~74) stops, a 311-vote
# Keeper pocket carries its helmet and boots.
CHAIN_POCKET_SHARE, CHAIN_POCKET_VOTES = 0.20, 20
```

In `_modal_build_chain`, replace the block from `uncond_top = ...` through the `sel[slot] = ...` line with:

```python
    total_w = sum(wgt for _b, wgt, _p in pool)
    # unconditional modal SHARE per slot: a chain step may only pick an
    # item whose share of the pocket is at least half the slot modal's
    # share of the whole population — shares against shares (2026-09-08;
    # the old count-against-count form failed by construction once the
    # pocket was under half the population, stopping 69 of 118 weapons
    # after one or two slots)
    uncond_share = {slot: (max(c.values()) / total_w if total_w else 0.0)
                    for slot, c in uncond.items()}
    sel = {}
    for slot in SLOT_ORDER:
        pool_w = sum(wgt for _b, wgt, _p in pool)
        if pool_w < CHAIN_MIN_POOL:
            break
        if (pool_w < CHAIN_POCKET_SHARE * total_w
                and pool_w < CHAIN_POCKET_VOTES):
            break   # the pocket is too small a slice of the population
        counts, players = {}, {}
        for b, wgt, player in pool:
            gid = b.get(slot)
            if not gid:
                continue
            if slot == "armor" and \
                    (gear[gid].get("gear_class") or "") not in uni:
                continue
            counts[gid] = counts.get(gid, 0.0) + wgt
            players.setdefault(gid, set()).add(player)
        if not counts:
            continue
        gid, n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if (len(players[gid]) < 2 or n < CHAIN_MIN_SHARE * pool_w
                or n / pool_w < 0.5 * uncond_share.get(slot, 0.0)):
            break
        sel[slot] = [gid, int(round(n)), int(round(pool_w))]
        pool = [(b, wgt, pl) for b, wgt, pl in pool
                if b.get(slot) in (gid, None)]
    return sel
```

Update the function docstring's last paragraph: replace the sentence about "later slots fall back to plain ranking rather than a rare build's tail" with: "The pocket floor and the share-against-share guard are the 2026-09-08 rescale (spec notes/specs/2026-09-08-coherent-style-kits-design.md); measured on the 2,042-battle harvest they lift weapons reaching 4+ slots from 6 to 37."

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R29|passed" "$SCRATCH/roles.log"`
Expected: `PASS  R29 ...` and `29/29 role-layer tests passed`, exit 0.

- [ ] **Step 5: Rebuild the dataset and measure**

Run: `py -3 pipeline/build_dataset.py > "$SCRATCH/build.log" 2>&1; echo $?` — expected exit 0 and `release_clean: true` in the log.

Measure depth (throwaway, scratchpad only):

```python
import json, collections
d = json.load(open('pipeline/out/dataset-latest.json', encoding='utf-8'))
w = collections.Counter(len(s) for r in d['roles'] for s in (r.get('kit_weapon_build') or {}).values())
print(dict(sorted(w.items())))
```

Expected: the 4+ bucket well above the previous 6 (the spec measured 37 for the probe's population; the miner's own uniform gating may differ by a few). Record the printed distribution for the VALIDATION entry (Task 7).

- [ ] **Step 6: Run the kit-affected gates**

Run each, redirect to a file, read the exit code:
`py -3 tests/test_roles.py`, `py -3 tests/test_golden.py`, `py -3 tests/test_forge.py`, `py -3 tests/test_validation_modes.py`.
Expected: all exit 0. If a golden or forge pin moves because a kit chest changed, STOP and report the exact pin and the two items (old chain vs new chain) — do not retune the guard to satisfy a pin; that is an owner call.

- [ ] **Step 7: Commit**

```bash
printf '%s\n' "Chain guard rescaled: shares against shares, pocket floor (spec 2026-09-08)" "" "The archetype chain stopped after one or two slots for 92 of 118 weapons" "because a conditional count was compared with the unconditional modal's" "count. Shares now, plus a pocket floor (20% of the population or 20" "votes) that still stops the 2026-09-04 Greataxe pocket. R29 pins the" "mechanism on synthetic populations." "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add pipeline/build_dataset.py tests/test_roles.py pipeline/out/dataset-latest.json pipeline/out/roles_report.json
git commit -F "$SCRATCH/c.txt"
```

(Add any other `pipeline/out/*.json` the rebuild changed — check `git status --short` first; every changed committed artifact from this rebuild belongs in this commit.)

---

### Task 2: Party link — `party_link.py` + the harvest analyzer's `index` / `party`

**Files:**
- Create: `pipeline/party_link.py`
- Modify: `pipeline/sample_parties.py:296-330` (party records) and `:349-382` (builds)
- Test: `tests/test_roles.py` (new `t_party_link`)

**Interfaces:**
- Produces `pipeline/party_link.py`:
  - `parties_by_battle(doc) -> {battle: [party_record, ...]}` — each party record gets an `"index"` key: the record's own `index` when present, else its ordinal among the battle's parties in the artifact's `parties` list order (the fallback for artifacts harvested before this change).
  - `link_build(build, parties_by_battle, min_size=10) -> int | None` — the party index the build belongs to: `build["party"]` when present; else the index of the ONLY party of `>= min_size` members in that battle whose `weapons` contains `build["weapon"]`; `None` when zero or several match.
- Produces in the analyzer: each party record carries `"index"` (0-based per battle, cluster order); each build carries `"party"` (that index, or `None` when the member's name is in no cluster).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_roles.py`:

```python
def t_party_link():
    # R31 (2026-09-08, spec section 2 "Linkage"): a build links to its party
    # exactly through the analyzer's `party` index, and — for artifacts
    # harvested before the index existed — through (battle, weapon) only
    # when exactly one 10+ party in that battle fields that weapon.
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import party_link
    doc = {"parties": [
        {"battle": 1, "size": 12, "weapons": ["2H_LONGBOW", "MAIN_MACE"]},
        {"battle": 1, "size": 11, "weapons": ["2H_LONGBOW", "2H_AXE"]},
        {"battle": 2, "size": 15, "weapons": ["2H_AXE"], "index": 4},
        {"battle": 2, "size": 5, "weapons": ["MAIN_MACE"], "index": 0},
    ]}
    pb = party_link.parties_by_battle(doc)
    idx_b1 = [p["index"] for p in pb[1]]
    idx_b2 = [p["index"] for p in pb[2]]
    exact = party_link.link_build({"battle": 1, "weapon": "2H_AXE", "party": 0}, pb)
    unique = party_link.link_build({"battle": 1, "weapon": "MAIN_MACE"}, pb)
    ambiguous = party_link.link_build({"battle": 1, "weapon": "2H_LONGBOW"}, pb)
    small = party_link.link_build({"battle": 2, "weapon": "MAIN_MACE"}, pb)
    check("R31 party link: ordinal fallback per battle, recorded index kept, "
          "exact `party` wins, unique (battle, weapon) links, ambiguous and "
          "under-size parties never link",
          idx_b1 == [0, 1] and idx_b2 == [4, 0] and exact == 0
          and unique == 0 and ambiguous is None and small is None,
          f"b1={idx_b1} b2={idx_b2} exact={exact} unique={unique} "
          f"amb={ambiguous} small={small}")
    # the analyzer stamps both sides: run it on one synthetic cache record
    import tempfile, json as _json, importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "sp", os.path.join(ROOT, "pipeline", "sample_parties.py"))
    sp = _ilu.module_from_spec(spec)
    spec.loader.exec_module(sp)
    tmp = tempfile.mkdtemp()
    cache = os.path.join(tmp, "party_cache")
    os.makedirs(cache)
    members_a = [{"name": f"a{i}", "weapon": "2H_LONGBOW", "guild": "G"}
                 for i in range(10)]
    members_b = [{"name": f"b{i}", "weapon": "MAIN_MACE", "guild": "H"}
                 for i in range(4)]
    rec = {"battle": 77, "total_players": 14, "kill_events": 2,
           "events_fetched": 2, "roster": [{"name": m["name"]}
                                            for m in members_a + members_b],
           "participant_sets": [],
           "parties": [{"members": members_a, "seen_in_events": 1},
                       {"members": members_b, "seen_in_events": 1}],
           "builds": [{"name": "a3", "seen_as": "killer", "item_power": 1300,
                       "slots_filled": 6,
                       "gear": {"MainHand": "T8_2H_LONGBOW@1",
                                "Armor": "T8_ARMOR_LEATHER_SET3"}},
                      {"name": "b1", "seen_as": "killer", "item_power": 1200,
                       "slots_filled": 6,
                       "gear": {"MainHand": "T7_MAIN_MACE",
                                "Armor": "T7_ARMOR_PLATE_SET2"}}]}
    with open(os.path.join(cache, "77.json"), "w", encoding="utf-8") as f:
        _json.dump(rec, f)
    sp.CACHE, sp.OUT = cache, tmp
    sp.analyze({"2H_LONGBOW", "MAIN_MACE"})
    out = _json.load(open(os.path.join(tmp, "party_rosters.json"),
                          encoding="utf-8"))
    by_w = {b["weapon"]: b for b in out["builds"]}
    idx = {tuple(p["weapons"])[0]: p["index"] for p in out["parties"]}
    check("R31b analyzer stamps `index` on parties and `party` on builds "
          "(cluster order per battle; a member's build carries its party)",
          idx.get("2H_LONGBOW") == 0 and idx.get("MAIN_MACE") == 1
          and by_w["2H_LONGBOW"]["party"] == 0
          and by_w["MAIN_MACE"]["party"] == 1,
          f"idx={idx} builds={{w: b.get('party') for w, b in by_w.items()}}")
```

Register `t_party_link()` in `__main__` after `t_chain_guard()`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; grep -E "R31|Error|Traceback" "$SCRATCH/roles.log" | head`
Expected: `ModuleNotFoundError: No module named 'party_link'` (the script dies at import — that is the failure; fine).

- [ ] **Step 3: Create `pipeline/party_link.py`**

```python
"""Build -> party linkage over the committed harvest artifact
(out/party_rosters.json). Spec: notes/specs/2026-09-08-coherent-style-
kits-design.md, section 2 "Linkage".

Two link paths, exact first, never a guess:
  1. the analyzer's `party` index on the build (sample_parties.analyze
     stamps it since 2026-09-08) matched to the party's `index`;
  2. for artifacts harvested before the index existed: (battle, weapon)
     when EXACTLY ONE party of >= min_size members in that battle fields
     that weapon. Zero or several -> None (the build joins no style cell;
     it stays in the band pool).
Party records without an `index` get their ordinal among the battle's
parties in artifact order, so both readers (derive_party_styles.py and
build_dataset.py) key the same party the same way.
"""


def parties_by_battle(doc):
    """{battle: [party, ...]} with every party carrying an `index`."""
    out = {}
    for p in doc.get("parties") or []:
        out.setdefault(p.get("battle"), []).append(p)
    for battle, ps in out.items():
        for i, p in enumerate(ps):
            if p.get("index") is None:
                p["index"] = i
    return out


def link_build(build, by_battle, min_size=10):
    """The index of the build's party in its battle, or None."""
    if build.get("party") is not None:
        return build["party"]
    cands = [p for p in by_battle.get(build.get("battle")) or []
             if (p.get("size") or 0) >= min_size
             and build.get("weapon") in (p.get("weapons") or [])]
    return cands[0]["index"] if len(cands) == 1 else None
```

- [ ] **Step 4: Stamp `index` and `party` in the analyzer**

In `pipeline/sample_parties.py`, in the cluster loop (line ~316) replace:

```python
        for c in clusters:
            p = c["party"]
            ws = [m["weapon"] for m in p["members"] if m["weapon"]]
            parties.append({
                "battle": rec["battle"],
```

with:

```python
        # PARTY INDEX (2026-09-08, pipeline/party_link.py): each cluster's
        # ordinal in this battle, stamped on the party record AND on every
        # member's build (`party`) so a build links to its party exactly —
        # the (battle, weapon) fallback in party_link is for artifacts
        # harvested before this field existed. A name seen in several
        # clusters keeps the largest (the same rule size_by_name uses).
        party_of_name = {}
        for idx, c in enumerate(clusters):
            for nm in c["names"]:
                if nm and nm not in party_of_name:
                    party_of_name[nm] = idx   # clusters are size-descending
        battle_party_index[rec["battle"]] = party_of_name
        for idx, c in enumerate(clusters):
            p = c["party"]
            ws = [m["weapon"] for m in p["members"] if m["weapon"]]
            parties.append({
                "battle": rec["battle"],
                "index": idx,
```

Add `battle_party_index = {}` beside `battles, parties = [], []` at the top of `analyze`. In the builds loop (line ~370) add the field after `"party_size"`:

```python
                "party": battle_party_index.get(rec["battle"], {}).get(nm),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R31|passed" "$SCRATCH/roles.log"`
Expected: `PASS  R31 ...`, `PASS  R31b ...`, exit 0.

- [ ] **Step 6: Commit**

```bash
printf '%s\n' "Party link: index on parties, party on builds, one linkage module" "" "sample_parties.analyze stamps each deduplicated party's ordinal and each" "member build's party; pipeline/party_link.py links builds exactly through" "it, or by (battle, weapon) only when exactly one 10+ party fields the" "weapon — for artifacts harvested before the field existed. R31 pins both." "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add pipeline/party_link.py pipeline/sample_parties.py tests/test_roles.py
git commit -F "$SCRATCH/c.txt"
```

---

### Task 3: `derive_party_styles.py` → `out/party_styles.json`

**Files:**
- Create: `pipeline/derive_party_styles.py`
- Create (generated, committed): `pipeline/out/party_styles.json`
- Test: `tests/test_roles.py` (new `t_party_styles`)

**Interfaces:**
- Consumes: `party_link.parties_by_battle`; `Engine(content="territory_defense", size=N).comp_identity(weapon_ids)["style"|"strength"]`.
- Produces `out/party_styles.json`:

```json
{"_generated": "YYYY-MM-DD",
 "_source": {"party_rosters_sha256": "<hex of the artifact bytes>"},
 "_engine": "comp_identity, weapons only, territory_defense at party size",
 "_min_size": 10,
 "parties": [{"battle": 1439160917, "index": 0, "size": 20,
              "style": "clap", "strength": "strong"}, ...]}
```

  `style`/`strength` are `null` when the engine returns no style or fewer than 3 catalog weapons are known. Sorted by (battle, index). Written with `newline="\n"`, `indent=1`, `sort_keys=True`.
- Produces a callable `derive(doc, engine_factory) -> dict` (the whole document minus `_generated`) so a test can run it on a synthetic artifact, and `sha256_of(path) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def t_party_styles():
    # R32 (2026-09-08, spec section 2 "Labels"): parties of 10+ in the
    # committed artifact are labelled with the engine's weapons-only
    # identity; smaller parties and forming rosters get null; the file
    # records the artifact hash it was derived from.
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import derive_party_styles as dps
    clap = ["2H_FIRE_RINGPAIR_AVALON", "2H_SHAPESHIFTER_KEEPER",
            "2H_HOLYSTAFF_CRYSTAL", "MAIN_CURSEDSTAFF_UNDEAD", "2H_LONGBOW",
            "2H_BOW_AVALON", "MAIN_NATURESTAFF", "2H_DUALMACE_AVALON",
            "2H_ICECRYSTAL_UNDEAD", "2H_AXE_AVALON", "2H_HOLYSTAFF_UNDEAD",
            "2H_HARPOON_HELL", "2H_BOW_HELL"]        # round-4 roster 16
    doc = {"parties": [
        {"battle": 5, "size": 13, "weapons": sorted(clap)},
        {"battle": 5, "size": 4, "weapons": ["MAIN_MACE"] * 4},
        {"battle": 6, "size": 10, "weapons": ["NOT_A_WEAPON"] * 10, "index": 3},
    ]}
    out = dps.derive(doc, lambda size: Engine(content="territory_defense",
                                              size=size))
    rows = {(r["battle"], r["index"]): r for r in out["parties"]}
    check("R32 party styles: a 13-stack labels clap, a 4-man is skipped, "
          "an unknown-weapon roster is null, rows keep the recorded index",
          rows[(5, 0)]["style"] == "clap" and (5, 1) not in rows
          and rows[(6, 3)]["style"] is None and out["_min_size"] == 10,
          f"rows={ {k: v['style'] for k, v in rows.items()} }")
    ps_path = os.path.join(ROOT, "pipeline", "out", "party_styles.json")
    pr_path = os.path.join(ROOT, "pipeline", "out", "party_rosters.json")
    have = os.path.exists(ps_path)
    live = (json.load(open(ps_path, encoding="utf-8")) if have else {})
    check("R32b committed party_styles.json matches the committed artifact "
          "hash and uses LF",
          have and live["_source"]["party_rosters_sha256"] == dps.sha256_of(pr_path)
          and b"\r\n" not in open(ps_path, "rb").read(),
          f"have={have}")
```

(`json` is imported at the top of `test_roles.py` — check; if not, `import json`.) Register `t_party_styles()` after `t_party_link()`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; grep -E "R32|No module" "$SCRATCH/roles.log" | head -3`
Expected: `ModuleNotFoundError: No module named 'derive_party_styles'`.

- [ ] **Step 3: Create the script**

```python
"""Party style labels from the COMMITTED harvest artifact.

Spec: notes/specs/2026-09-08-coherent-style-kits-design.md, section 2.
Every killer party of MIN_SIZE+ members in out/party_rosters.json gets the
engine's WEAPONS-ONLY identity (Engine.comp_identity — the same label the
blind rounds grade; naked matched the audit's dressed read 19/20 in round
4). The dressed label would need member kits the committed artifact does
not carry, so this runs on any machine and is byte-reproducible.

Reads committed files only; never the raw cache. Explicit step, never part
of a normal build. Rerun order after a harvest: sample_parties ->
audit_style_rosters -> derive_style_bands -> derive_party_styles ->
build_dataset -> gates. build_dataset.py refuses a party_styles.json whose
recorded artifact hash does not match the artifact on disk.

    py -3 pipeline/derive_party_styles.py
"""
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARTIFACT = os.path.join(OUT, "party_rosters.json")
TARGET = os.path.join(OUT, "party_styles.json")
CONTENT = "territory_defense"   # identity is content-blind; the audit's choice
MIN_SIZE = 10                   # the group band's party floor (KB_MIN_PARTY)
MIN_KNOWN = 3                   # comp_identity's IDENTITY_MIN_MEMBERS

sys.path.insert(0, HERE)
import party_link  # noqa: E402


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def derive(doc, engine_factory):
    """Label every MIN_SIZE+ party. `engine_factory(size)` returns an
    Engine already set to CONTENT at that size."""
    by_battle = party_link.parties_by_battle(doc)
    rows = []
    engines = {}
    for battle in sorted(by_battle):
        for p in by_battle[battle]:
            size = p.get("size") or 0
            if size < MIN_SIZE:
                continue
            row = {"battle": battle, "index": p["index"], "size": size,
                   "style": None, "strength": None}
            e = engines.get(size)
            if e is None:
                e = engines[size] = engine_factory(size)
            ws = [w for w in (p.get("weapons") or []) if w in e.weapons]
            if len(ws) >= MIN_KNOWN:
                ci = e.comp_identity(ws)
                row["style"] = ci.get("style")
                row["strength"] = ci.get("strength") if ci.get("style") else None
            rows.append(row)
    rows.sort(key=lambda r: (r["battle"], r["index"]))
    return {"_source": {"party_rosters_sha256": None},
            "_engine": f"comp_identity, weapons only, {CONTENT} at party size",
            "_min_size": MIN_SIZE, "parties": rows}


def main():
    if not os.path.exists(ARTIFACT):
        sys.exit("no out/party_rosters.json — run sample_parties.py first")
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
    from engine import Engine  # noqa: E402
    with open(ARTIFACT, encoding="utf-8") as f:
        doc = json.load(f)
    out = derive(doc, lambda size: Engine(content=CONTENT, size=size))
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    labelled = sum(1 for r in out["parties"] if r["style"])
    print(f"party_styles: {len(out['parties'])} parties of {MIN_SIZE}+, "
          f"{labelled} labelled -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
```

Check `Engine(content=..., size=...)` is a valid constructor call (test_roles uses `Engine(content="territory_defense", size=20, style="clap")` — yes).

- [ ] **Step 4: Generate the artifact and run the test**

Run: `py -3 pipeline/derive_party_styles.py` — expected a line like `party_styles: 2696 parties of 10+, ~2450 labelled`.
Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R32|passed" "$SCRATCH/roles.log"`
Expected: both R32 checks PASS, exit 0.

- [ ] **Step 5: Determinism check**

Run the script twice and compare bytes: `py -3 pipeline/derive_party_styles.py; cp pipeline/out/party_styles.json "$SCRATCH/ps1.json"; py -3 pipeline/derive_party_styles.py; cmp pipeline/out/party_styles.json "$SCRATCH/ps1.json" && echo IDENTICAL`
Expected: `IDENTICAL` (the `_generated` date is the same day; note in the docstring that only the date field moves across days).

- [ ] **Step 6: Commit**

```bash
printf '%s\n' "derive_party_styles: weapons-only identity per 10+ party, from the committed artifact" "" "Reads out/party_rosters.json, labels every party of 10+ with" "comp_identity, records the artifact hash it read. Explicit step in the" "post-harvest order; R32 pins the labelling and the hash contract." "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add pipeline/derive_party_styles.py pipeline/out/party_styles.json tests/test_roles.py
git commit -F "$SCRATCH/c.txt"
```

---

### Task 4: Style cells in the doctrine miner

**Files:**
- Modify: `pipeline/build_dataset.py` — `derive_kit_doctrine` signature and body (lines 1277-1640), the call site (1922-1936), the `roles_report.json` writer (search `"kit_doctrine_gang"` to find it), the provenance read of `party_styles.json` (next to the `chest_lean.json` read, line ~2227).
- Test: `tests/test_roles.py` (new `t_style_cells`)

**Interfaces:**
- Consumes: `party_link.parties_by_battle`, `party_link.link_build`, `derive_party_styles.sha256_of`, `out/party_styles.json`.
- Produces on each seat record (group band only): `kit_styles: {style: {kit, kit_weapon, kit_weapon_build, kit_build, kit_weapon_uniform}}` — every key optional, only styles with any evidence present. `roles_report.json` gains `kit_doctrine_styles: {style: <same detail shape as kit_doctrine>}`.
- New signature: `derive_kit_doctrine(book, gear, problems, overrides=None, effect_map=None, band="group", style=None, party_styles=None)` where `party_styles` is `{(battle, index): style}`; with `style` set, `by_content` is emptied (curated builds carry no style), `kept` keeps only builds linking to a party of that style, weapons with fewer than `STYLE_CELL_MIN_VOTERS` (5) distinct players in the cell are dropped, the target becomes `r.setdefault("kit_styles", {}).setdefault(style, {})`, and overrides are NOT applied (they were ruled on the band).

- [ ] **Step 1: Write the failing test**

```python
def t_style_cells():
    # R30 (2026-09-08, spec section 2 "Doctrine"): the group band carries
    # per-style kit cells mined from builds linked to labelled parties with
    # the band's own floors plus a 5-voter cell floor; a cell is absent,
    # never filled; the gang band carries none; the party-styles hash the
    # dataset read matches the artifact.
    e = Engine(content="territory_defense", size=20)
    styles_seen, cells, gang_cells = set(), 0, 0
    for rid, rec in e.roles.items():
        ks = rec.get("kit_styles") or {}
        styles_seen |= set(ks)
        cells += sum(1 for st, cell in ks.items() if cell.get("kit_weapon"))
        gang_cells += len(((rec.get("kit_bands") or {}).get("gang") or {})
                          .get("kit_styles") or {})
    rep = json.load(open(os.path.join(ROOT, "pipeline", "out",
                                      "roles_report.json"), encoding="utf-8"))
    det = rep.get("kit_doctrine_styles") or {}
    thin = []
    for st, seats in det.items():
        for sid, d in seats.items():
            for w, slots in (d.get("by_weapon") or {}).items():
                voters = max((row.get("players") or 0)
                             for rows in slots.values() for row in rows)
                if voters < 5:
                    thin.append(f"{st}/{sid}/{w}:{voters}")
    check("R30 style cells: only the five styles, at least two seats carry "
          "two or more cells, every cell weapon has >= 5 voters, the gang "
          "band carries no cells",
          styles_seen and styles_seen <= set(e.IDENTITY_STYLES) and cells >= 4
          and sum(1 for r in e.roles.values()
                  if len(r.get("kit_styles") or {}) >= 2) >= 2
          and not thin and gang_cells == 0,
          f"styles={sorted(styles_seen)} cells={cells} thin={thin[:3]} "
          f"gang={gang_cells}")
```

Register `t_style_cells()` after `t_party_styles()`. (`e.roles` is the seat book keyed by id — confirm the attribute name used elsewhere in test_roles, e.g. in `t_doctrine_bands`; use that.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; grep -E "R30" "$SCRATCH/roles.log"`
Expected: `FAIL  R30 ...` with `styles=[] cells=0`.

- [ ] **Step 3: Read the party-styles file in `main()` with the hash gate**

Next to the `chest_lean.json` read (line ~2227) add:

```python
    # party style labels (derive_party_styles.py -> out/party_styles.json,
    # 2026-09-08): optional; a file derived from a DIFFERENT artifact than
    # the one on disk blocks the release (fail closed, loudly)
    party_styles = {}
    ps_path = os.path.join(OUT, "party_styles.json")
    if os.path.exists(ps_path):
        from derive_party_styles import sha256_of
        with open(ps_path, encoding="utf-8") as f:
            ps_doc = json.load(f) or {}
        want = (ps_doc.get("_source") or {}).get("party_rosters_sha256")
        have = sha256_of(os.path.join(OUT, "party_rosters.json"))
        if want != have:
            problems.append("party_styles.json was derived from a different "
                            "party_rosters.json — rerun derive_party_styles.py")
        else:
            party_styles = {(r["battle"], r["index"]): r.get("style")
                            for r in ps_doc.get("parties") or []
                            if r.get("style")}
    else:
        print("party_styles.json missing — no style cells this build "
              "(run derive_party_styles.py after a harvest)")
```

`problems` must already exist at that point in `main()` — locate where it is created (`problems = []`) and place this read after it; `sys.path` must include `HERE` for the import (check the top of the file; `sys.path.insert(0, HERE)` if absent).

- [ ] **Step 4: Extend `derive_kit_doctrine`**

Change the signature:

```python
def derive_kit_doctrine(book, gear, problems, overrides=None,
                        effect_map=None, band="group", style=None,
                        party_styles=None):
```

Add to the docstring's end:

```
    STYLE CELLS (2026-09-08, spec notes/specs/2026-09-08-coherent-style-
    kits-design.md): with `style` set (group band only) the killboard
    builds are filtered to those linked (party_link) to a party labelled
    that style, curated reference builds drop out (they carry no style),
    a weapon needs STYLE_CELL_MIN_VOTERS distinct players in the cell,
    overrides do not apply (ruled on the band), and everything the miner
    ships lands under the seat's `kit_styles.<style>` — absent where thin,
    never filled from the band or another style.
```

Add the constant next to `CHAIN_POCKET_SHARE`:

```python
STYLE_CELL_MIN_VOTERS = 5   # distinct players before a weapon has a style cell
```

Right after `with open(bi_path ...) as f: by_content = ...` add:

```python
    if style is not None:
        by_content = {}           # curated builds carry no style label
```

Right after `kept = [b for b in ... ]` add:

```python
        if style is not None:
            import party_link
            by_battle = party_link.parties_by_battle(kb_doc)
            kept = [b for b in kept
                    if (party_styles or {}).get(
                        (b.get("battle"),
                         party_link.link_build(b, by_battle, KB_MIN_PARTY)))
                    == style]
            voters = {}
            for i, b in enumerate(kept):
                voters.setdefault(b["weapon"], set()).add(
                    b.get("player") or f"?{i}")
            kept = [b for b in kept
                    if len(voters[b["weapon"]]) >= STYLE_CELL_MIN_VOTERS]
```

Change the target selection:

```python
        if style is not None:
            tgt = r.setdefault("kit_styles", {}).setdefault(style, {})
        else:
            tgt = (r if band == "group"
                   else r.setdefault("kit_bands", {}).setdefault(band, {}))
```

Change the override application so cells skip it:

```python
        applied = ([] if style is not None else _apply_kit_overrides(
            r["id"], uni, kit, det, w_det, kit_weapon, gear,
            (overrides or {}).get(r["id"]) or {}, problems))
```

At the end of the per-seat loop body (after the `detail[r["id"]] = ...` block), drop empty cells:

```python
        if style is not None and not tgt:
            r["kit_styles"].pop(style, None)
            if not r["kit_styles"]:
                r.pop("kit_styles", None)
```

The stale-override check at the end (`for rid in sorted(set(overrides or {}) - seats_seen)`) must not run for cells — wrap it in `if style is None:`.

- [ ] **Step 5: Call it per style and ship the detail**

At the call site (line ~1922) after `kit_detail_gang = ...` add:

```python
    # STYLE CELLS (2026-09-08): one cell per declared style on the group
    # band, from builds linked to labelled parties; absent where thin
    kit_detail_styles = {}
    if party_styles:
        for st in ("brawl", "clap", "kite", "brawl_clap", "clap_kite"):
            d = derive_kit_doctrine(book, gear, problems, None, effect_map,
                                    band="group", style=st,
                                    party_styles=party_styles)
            if d:
                kit_detail_styles[st] = d
```

`party_styles` must be in scope: it is read in `main()` — if `derive_kit_doctrine` is called from a helper that `main()` calls, thread `party_styles` through that helper's parameters (find the enclosing function of line 1922 and add a `party_styles=None` parameter; pass it from `main()`).

Find the `roles_report.json` writer (search for `"kit_doctrine_gang":`) and add `"kit_doctrine_styles": kit_detail_styles,` beside it.

- [ ] **Step 6: Rebuild and run the test**

Run: `py -3 pipeline/build_dataset.py > "$SCRATCH/build.log" 2>&1; echo $?` — expected 0, `release_clean: true`.
Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R30|passed" "$SCRATCH/roles.log"`
Expected: `PASS  R30 ...`, exit 0.

- [ ] **Step 7: Hash-gate check (throwaway)**

Edit `pipeline/out/party_styles.json` so the recorded hash is wrong (change one hex digit), run `py -3 pipeline/build_dataset.py > "$SCRATCH/build.log" 2>&1; echo $?` — expected exit 2 with the "derived from a different party_rosters.json" problem in the log. Then `git checkout pipeline/out/party_styles.json` and rebuild clean (exit 0).

- [ ] **Step 8: Run the affected gates**

`py -3 tests/test_golden.py`, `py -3 tests/test_forge.py`, `py -3 tests/test_validation_modes.py`, `py -3 tests/test_provenance.py` — all exit 0 (the engine does not read cells yet, so kits are unchanged; provenance checks the rebuild is byte-identical — run the builder twice if it asks).

- [ ] **Step 9: Commit**

```bash
printf '%s\n' "Style cells: per-style kit doctrine under the group band (spec 2026-09-08)" "" "derive_kit_doctrine takes a style: builds linked to a labelled party of" "that style, the band's floors plus a 5-voter cell floor, no curated" "builds, no overrides, written under kit_styles.<style>; absent where" "thin. build_dataset refuses a party_styles.json derived from another" "artifact. R30 pins the contract." "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add pipeline/build_dataset.py tests/test_roles.py pipeline/out/dataset-latest.json pipeline/out/roles_report.json
git commit -F "$SCRATCH/c.txt"
```

(Again add any other changed `pipeline/out/*.json` from the rebuild.)

---

### Task 5: The engines read the cell — `_seat_kit` merge, both ports

**Files:**
- Modify: `engine/engine.py:1401-1412` (`_seat_kit`), `:1660` (the `observed_build` annotation)
- Modify: `engine/app_scoring.js:1226-1234` (`_seatKit`), the `observed_build` annotation (search `observed_build` with `Select-String`)
- Test: `tests/test_roles.py` (new `t_style_cell_reader`), `tests/test_js_parity.py` (kit cases under a declared style)

**Interfaces:**
- `_seat_kit(rec)` → unchanged signature; with `self.style` in `IDENTITY_STYLES` and `rec["kit_styles"][self.style]` present (and size above the gang max), returns a NEW dict: the band record's doctrine keys with the cell's entries laid over them (`kit`: per slot; `kit_weapon`, `kit_weapon_build`, `kit_weapon_uniform`: per weapon, whole entry; `kit_build`: whole), plus `"_style_arch": {"weapons": [ids whose chain came from the cell], "seat": bool}`.
- `kit_options` output: an option that received `observed_build` from a cell chain also carries `"observed_style": self.style`.

- [ ] **Step 1: Write the failing tests**

```python
def t_style_cell_reader():
    # R33 (2026-09-08, spec section 2 "Engine"): a DECLARED style dresses a
    # weapon from its style cell where one exists; balanced and a missing
    # cell fall back to the band; the annotation names the style. Pinned on
    # mechanism: the fixture is whichever weapon's clap and brawl cells
    # both exist and disagree on the chest with the band.
    band = Engine(content="territory_defense", size=20)
    pick = None
    for rid, rec in band.roles.items():
        ks = rec.get("kit_styles") or {}
        for w, chain in ((ks.get("clap") or {}).get("kit_weapon_build") or {}).items():
            bch = ((ks.get("brawl") or {}).get("kit_weapon_build") or {}).get(w) or {}
            band_ch = (rec.get("kit_weapon_build") or {}).get(w) or {}
            if (chain.get("armor") and bch.get("armor")
                    and chain["armor"][0] != bch["armor"][0]
                    and band.primary_seat(w) == rid
                    and not band.weapons[w].get("two_handed") is None):
                pick = (rid, w, chain["armor"][0], bch["armor"][0],
                        (band_ch.get("armor") or [None])[0])
                break
        if pick:
            break
    ok = pick is not None
    detail = f"pick={pick}"
    if pick:
        rid, w, clap_chest, brawl_chest, band_chest = pick
        kc = Engine(content="territory_defense", size=20, style="clap").kit_options(w)
        kb = Engine(content="territory_defense", size=20, style="brawl").kit_options(w)
        kx = band.kit_options(w)
        got = (kc["kit"].get("armor", {}).get("gear"),
               kb["kit"].get("armor", {}).get("gear"),
               kx["kit"].get("armor", {}).get("gear"))
        styled = kc["kit"].get("armor", {}).get("observed_style")
        ok = (got[0] == clap_chest and got[1] == brawl_chest
              and got[2] == band_chest and styled == "clap"
              and "observed_style" not in kx["kit"].get("armor", {}))
        detail += f" got={got} styled={styled}"
    check("R33 style cell reader: clap and brawl dress from their cells, "
          "balanced from the band, the option names its style",
          ok, detail)
```

Note: the brawl cloth gate in `kit_options` removes cloth chests for non-healers under brawl — if the picked weapon's brawl cell chest is cloth the gate would hide it. Add `and not brawl_chest.startswith("ARMOR_CLOTH")` to the fixture filter (replace the odd `two_handed` clause with that). Register `t_style_cell_reader()` after `t_style_cells()`.

Parity: open `tests/test_js_parity.py` `make_cases` (around lines 140-230) and find where each case's `style` is set. If cases already draw from the five styles plus balanced, nothing to add. If every case is balanced, change the kit cases (`i % KIT_EVERY == KIT_OFFSET`) to set `style` from `("clap", "brawl", "kite", "brawl_clap", "clap_kite")[i % 5]` — the same field the JS runner reads for `set_content`. The fixture is regenerated by the test itself, so the check is that `py -3 tests/test_js_parity.py` still passes at 1e-9 AFTER the JS mirror lands (Step 5).

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; grep -E "R33" "$SCRATCH/roles.log"`
Expected: `FAIL  R33 ...` with `got=(band, band, band) styled=None`.

- [ ] **Step 3: Python `_seat_kit`**

Replace `_seat_kit` in `engine/engine.py`:

```python
    def _seat_kit(self, rec):
        """The seat's doctrine for THIS party size and DECLARED style
        (2026-09-04 size bands; 2026-09-08 style cells, spec notes/specs/
        2026-09-08-coherent-style-kits-design.md): below DOCTRINE_GANG_MAX+1
        members the gang band when the seat has one; else, under a declared
        style with a cell, the cell laid over the band (the band fills every
        weapon and slot the cell lacks); else the band. `balanced` NEVER
        reads a cell (owner 2026-09-08) — the detected identity is
        descriptive and stays out of generation. Every doctrine reader goes
        through here."""
        if self.size <= self.DOCTRINE_GANG_MAX:
            gang = (rec.get("kit_bands") or {}).get("gang")
            if gang:
                return gang
        cell = ((rec.get("kit_styles") or {}).get(self.style)
                if self.style in self.IDENTITY_STYLES else None)
        if not cell:
            return rec
        merged = dict(rec)
        kit = dict(rec.get("kit") or {})
        kit.update(cell.get("kit") or {})
        merged["kit"] = kit
        for key in ("kit_weapon", "kit_weapon_build", "kit_weapon_uniform"):
            per_w = dict(rec.get(key) or {})
            per_w.update(cell.get(key) or {})
            merged[key] = per_w
        if cell.get("kit_build"):
            merged["kit_build"] = cell["kit_build"]
        merged["_style_arch"] = {
            "weapons": sorted(cell.get("kit_weapon_build") or {}),
            "seat": bool(cell.get("kit_build"))}
        return merged
```

In `kit_options`, where `arch`/`arch_seat` are built (line ~1519), capture the provenance right after the loop:

```python
            styled = seat_rec.get("_style_arch") or {}
            arch_styled = {slot for slot in arch
                           if (slot in wb and weapon in styled.get("weapons", ()))
                           or (slot in arch_seat and styled.get("seat"))}
```

(`arch_styled = set()` before the `if role is not None:` block so it exists on every path.) At the annotation (line ~1660) add one line after `rr["observed_build"] = [a[1], a[2]]`:

```python
                        if slot in arch_styled:
                            rr["observed_style"] = self.style
```

- [ ] **Step 4: Run the Python test**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R33|R24|passed" "$SCRATCH/roles.log"`
Expected: `PASS  R33`, R24 still PASS (it runs balanced), exit 0.

- [ ] **Step 5: JS mirror**

In `engine/app_scoring.js` replace `_seatKit`:

```javascript
  CompEngine.prototype._seatKit = function (rec) {
    /* the seat's doctrine for THIS party size and DECLARED style (mirrors
       engine.py _seat_kit): the gang band below 10 members; else a declared
       style's cell laid over the band (band fills what the cell lacks);
       `balanced` never reads a cell (owner 2026-09-08). */
    if (this.size <= DOCTRINE_GANG_MAX) {
      var gang = (rec.kit_bands || {}).gang;
      if (gang) return gang;
    }
    var cell = IDENTITY_STYLES.indexOf(this.style) >= 0
      ? (rec.kit_styles || {})[this.style] : null;
    if (!cell) return rec;
    var merged = {}, k;
    for (k in rec) merged[k] = rec[k];
    var kit = {};
    for (k in (rec.kit || {})) kit[k] = rec.kit[k];
    for (k in (cell.kit || {})) kit[k] = cell.kit[k];
    merged.kit = kit;
    var keys = ["kit_weapon", "kit_weapon_build", "kit_weapon_uniform"], ki;
    for (ki = 0; ki < keys.length; ki++) {
      var perW = {};
      for (k in (rec[keys[ki]] || {})) perW[k] = rec[keys[ki]][k];
      for (k in (cell[keys[ki]] || {})) perW[k] = cell[keys[ki]][k];
      merged[keys[ki]] = perW;
    }
    if (cell.kit_build) merged.kit_build = cell.kit_build;
    var sw = [];
    for (k in (cell.kit_weapon_build || {})) sw.push(k);
    sw.sort();
    merged._style_arch = { weapons: sw, seat: !!cell.kit_build };
    return merged;
  };
```

Check `IDENTITY_STYLES` exists as a JS constant (Select-String for `IDENTITY_STYLES`); if the JS port names it differently, use that name, and if absent define `var IDENTITY_STYLES = ["brawl", "clap", "kite", "brawl_clap", "clap_kite"];` beside `DOCTRINE_GANG_MAX`.

In `kitOptions` after the `arch`/`archSeat` loops (line ~1303):

```javascript
    var archStyled = {};
    if (role !== null) {
      var styledArch = seatRec._style_arch || { weapons: [], seat: false };
      for (aslot in arch) {
        if ((wbArch[aslot] && styledArch.weapons.indexOf(weapon) >= 0)
            || (archSeat[aslot] && styledArch.seat)) archStyled[aslot] = true;
      }
    }
```

At the annotation site (search `observed_build = [av[1], av[2]]` or the equivalent assignment near line 1431-1445) add after it:

```javascript
            if (archStyled[slot]) rr.observed_style = this.style;
```

(use the same variable name the loop uses for the option object.)

- [ ] **Step 6: Parity + dashboard**

Run: `py -3 tests/test_js_parity.py > "$SCRATCH/parity.log" 2>&1; echo $?; tail -3 "$SCRATCH/parity.log"` — expected exit 0, 60/60 at 1e-9 (the kit cases serialize `gear/value/doctrine/carries/passive`; a drift shows as a kit mismatch — fix the port, never the test).
Run: `node tests/test_loadout_codec.js; node tests/test_display_math.js` — exit 0.
Run: `py -3 dashboard/build.py > "$SCRATCH/dash.log" 2>&1; echo $?` — exit 0 (the page's inlined parity fixture asserts against engine.py on load).

- [ ] **Step 7: Commit**

```bash
printf '%s\n' "Engines read the style cell: _seat_kit merges a declared style over the band, both ports" "" "Under a declared style with a cell, the one doctrine reader lays the" "cell's per-weapon entries over the band; balanced never reads a cell" "(owner 2026-09-08). kit_options names the style on options that came" "from a cell chain (observed_style). R33 pins it; parity 60/60." "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add engine/engine.py engine/app_scoring.js tests/test_roles.py tests/test_js_parity.py dashboard/index.html docs/
git commit -F "$SCRATCH/c.txt"
```

---

### Task 6: R24 audit becomes style-aware

**Files:**
- Modify: `tests/test_roles.py:788-857` (`t_kit_audit_agreement`)

**Interfaces:**
- Consumes: `party_link.parties_by_battle`, `party_link.link_build`, `out/party_styles.json`, `Engine(..., style="clap").kit_variants(w)`.

- [ ] **Step 1: Add the styled pass**

After the existing balanced `check("R24 ...")` in `t_kit_audit_agreement`, add:

```python
    # R24b (2026-09-08, spec section "Tests"): under a DECLARED style the
    # modal the forge must match is the STYLE CELL's — the modal among the
    # weapon's builds linked to parties labelled that style — wherever the
    # cell exists (>= 5 voters); weapons without a clap cell are skipped.
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import party_link
    ps = _json.load(open(os.path.join(ROOT, "pipeline", "out",
                                      "party_styles.json"), encoding="utf-8"))
    label = {(r["battle"], r["index"]): r["style"] for r in ps["parties"]
             if r.get("style")}
    by_battle = party_link.parties_by_battle(doc)
    es = Engine(content="territory_defense", size=20, style="clap")
    by_ws, per_s = {}, {}
    for r in doc.get("builds") or []:
        if r.get("weapon") in es.weapons and r.get("gear") \
                and (r.get("party_size") or 0) >= 10:
            idx = party_link.link_build(r, by_battle, 10)
            if label.get((r["battle"], idx)) != "clap":
                continue
            k = (r["weapon"], r.get("player"))
            per_s[k] = per_s.get(k, 0) + 1
            by_ws.setdefault(r["weapon"], []).append(r)
    total_s = agree_s = bad_s = 0
    detail_s = []
    for w in pick:
        rows = by_ws.get(w) or []
        if len({r.get("player") for r in rows}) < 5:
            continue          # no clap cell for this weapon
        v0 = {}
        for g in (es.kit_variants(w)[0][1] or []):
            v0[es.gear[g]["slot"]] = g
        for slot, kb in slot_kb:
            if slot == "offhand" and es.weapons[w].get("two_handed"):
                continue
            c = _Counter()
            for r in rows:
                v = r["gear"].get(kb)
                c[(es.gear_key(v) or v) if v else "-"] += \
                    1.0 / per_s[(w, r.get("player"))]
            n = sum(c.values())
            items = [(k, x) for k, x in c.most_common() if k != "-"]
            if not items or items[0][0] not in es.gear:
                continue
            modal, mn = items[0]
            eng = v0.get(slot)
            share = (c.get(eng, 0) / n) if eng else 0.0
            total_s += 1
            if eng == modal:
                agree_s += 1
            elif share < 0.5 * (mn / n):
                bad_s += 1
                detail_s.append(f"{w}:{slot}:{eng}<{modal}")
    check("R24b styled kit audit: under a declared clap the forge kit "
          "matches the clap cell's modal item in >= 85% of audited slots "
          "and never picks an item worn < half as often",
          total_s >= 10 and agree_s >= 0.85 * total_s and bad_s == 0,
          f"agree={agree_s}/{total_s} bad={bad_s} {detail_s[:4]}")
```

- [ ] **Step 2: Run it**

Run: `py -3 tests/test_roles.py > "$SCRATCH/roles.log" 2>&1; echo $?; grep -E "R24|passed" "$SCRATCH/roles.log"`
Expected: both R24 checks PASS. If R24b fails on `bad` items, the cell chain fronted an item outside the band's evidence band — that is the `in_band` rule reading the BAND's `wslot` counts against a CELL chain; fix by making `in_band` in `kit_options` read the merged `kit_weapon` (already the cell's per-weapon counts after the merge) — verify which counts `wslot` came from before changing anything. If it fails on agreement below 85%, report the numbers; do not lower the bar.

- [ ] **Step 3: Commit**

```bash
printf '%s\n' "R24b: the kit audit judges a declared clap against the clap cell's modal" "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add tests/test_roles.py
git commit -F "$SCRATCH/c.txt"
```

---

### Task 7: Display, docs, full gates, PR

**Files:**
- Modify: `dashboard/_loadout.js` or `dashboard/_app.js` (wherever `observed_build` is rendered — `Select-String -Path dashboard/_*.js -Pattern observed_build`)
- Modify: `pipeline/README.md` (rerun order), `HANDOFF.md` ("The kit audit" section + "Open work"), `CLAUDE.md` ("Kits are what winners wear" invariant + Build chain), `tests/VALIDATION.md` (new dated section), `MECHANICS_TODO.md` untouched.
- Regenerate: `pipeline/out/*.json`, `dashboard/index.html`, `docs/`.

- [ ] **Step 1: Display the style on the kit tile**

Where the page renders an option's `observed_build` (a hover or tag like "worn n of m"), append the style when `observed_style` is present, e.g. `` ` · ${o.observed_style} build` `` inside the same title/text. Translation only — no computation. Rebuild: `py -3 dashboard/build.py > "$SCRATCH/dash.log" 2>&1; echo $?`.

- [ ] **Step 2: Docs**

- `pipeline/README.md`: in the post-harvest rerun order add `derive_party_styles.py` between `derive_style_bands` and `build_dataset`, one sentence on what it writes and the hash gate.
- `CLAUDE.md`: in the "Kits are what winners wear" invariant append: "**Style cells** (2026-09-08, spec `notes/specs/2026-09-08-coherent-style-kits-design.md`): the group band carries `kit_styles.<style>` mined from builds linked (`pipeline/party_link.py`) to parties `derive_party_styles.py` labelled weapons-only; `_seat_kit` lays a DECLARED style's cell over the band, `balanced` never reads a cell (owner 2026-09-08), a thin cell (< 5 voters) is absent, never filled. The chain guard compares shares, never counts, with a 20%-or-20-votes pocket floor (R29)." In the Build chain / rerun-order sentence add `derive_party_styles`.
- `HANDOFF.md`: under "The kit audit and the style × size rows" add a bullet dated 2026-09-08 with the before/after chain depth table (from Task 1 Step 5) and the cell counts (from Task 4's R30 detail); in "Open work → Role layer" note increment 3b's remaining half (carrier floors) and the five deferred levers.
- `tests/VALIDATION.md`: append `### Coherent builds and style cells (2026-09-08, owner: "go ahead with your recommendations")` — the owner's words, the seven-lever list with the two chosen, the measured depth before/after, cell counts, the balanced ruling, what R29–R33 and R24b pin, gates green.

- [ ] **Step 3: Full gate list**

From PowerShell (cohort_families needs it), each redirected to a file, exit codes read bare:

```
py -3 pipeline/evidence_lint.py
py -3 tests/test_golden.py
py -3 tests/test_forge.py
py -3 tests/test_builds.py
py -3 tests/test_interactions.py
py -3 tests/test_provenance.py
py -3 tests/test_patch_history.py
py -3 tests/test_js_parity.py
node tests/test_loadout_codec.js
node tests/test_display_math.js
py -3 tests/test_cohort_families.py
py -3 tests/test_roles.py
py -3 tests/test_validation_modes.py
py -3 tests/tier2_blindtest.py v4
```

Expected: every exit 0. `tier2_blindtest v4` gates actual_gear role-level at 70% — style cells change nothing there unless the fixtures declare a style; if it moves, report the number, do not touch the gate.

- [ ] **Step 4: Commit and PR**

```bash
git status --short   # every regenerated artifact + docs
printf '%s\n' "Coherent builds and style cells: docs, display, full gates" "" "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" > "$SCRATCH/c.txt"
git add -A
git commit -F "$SCRATCH/c.txt"
git push -u origin <branch>
gh pr create --base main --title "Coherent builds and style-conditioned kits (owner 2026-09-08)" --body-file "$SCRATCH/pr.md"
```

PR body: the two findings, the depth table, cell counts, the balanced ruling, R29–R33 + R24b, gate results, and "🤖 Generated with [Claude Code](https://claude.com/claude-code)".

---

## Self-review

- Spec coverage: §1 guard → Task 1; §2 labels → Task 3; linkage → Task 2; doctrine cells → Task 4; engine both ports + annotation → Task 5; provenance hash gate → Task 4 step 3/7; tests R29/R30/R24b/parity → Tasks 1/4/6/5; rerun order + docs → Task 7. Deferred items stay deferred.
- Names used consistently: `party_link.parties_by_battle`, `party_link.link_build(build, by_battle, min_size)`, `derive_party_styles.derive(doc, engine_factory)`, `derive_party_styles.sha256_of(path)`, `STYLE_CELL_MIN_VOTERS`, `CHAIN_POCKET_SHARE`, `CHAIN_POCKET_VOTES`, seat key `kit_styles`, merged marker `_style_arch`, option key `observed_style`.
- Known fragility to watch: Task 4 Step 5 assumes `derive_kit_doctrine` is called inside a function `main()` can pass `party_styles` to — thread the parameter through whatever function encloses line 1922.
