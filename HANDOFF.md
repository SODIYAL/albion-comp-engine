# Handoff — Albion Online Composition Engine

Paste the prompt below into a new session with the `Bion` folder connected.

---

I'm building an Albion Online dynamic party-composition recommendation engine. Previous sessions completed the research, design, validation, the data pipeline, the engine, and a working dashboard. Read these files in my connected Bion folder before doing anything:

1. `albion-comp-engine-design.md` — full feasibility research + system design (data sources verified live, capability taxonomy, content templates, scoring algorithm, MVP scope, architecture)
2. `pipeline/README.md` — the pipeline workflow, current status, and known gaps
3. `tests/VALIDATION.md` — the test plan; Tier 1 passed (9/9), Tier 2 is the next gate
4. `engine/engine.py` + `tests/test_golden.py` — the engine and its 9 golden regression cases

## Environment (Windows)

- Use `py -3`, **not** `python`/`python3` — those hit the Microsoft Store stub.
- `pyyaml` is installed. Node is available (used for ad-hoc data inspection).
- The ao-bin-dumps clone is not in the repo and is only needed after a game
  patch. See `pipeline/README.md` for the correct clone command — the
  `sparse-checkout set items.json …` form in older notes fails in cone mode.

## Rebuild everything

```
py -3 pipeline/evidence_lint.py        # CI gate — exit 1 blocks release
py -3 pipeline/build_dataset.py        # sheets + templates -> out/dataset-latest.json
py -3 tests/test_golden.py             # must stay 9/9
py -3 tests/test_patch_history.py      # patch-diff + staleness units, no clone needed
py -3 pipeline/build_dashboard.py      # -> dashboard/index.html
```

After a game patch: re-clone ao-bin-dumps WITH history (see pipeline/README.md)
and run `py -3 pipeline/patch_history.py <clone>` — the evidence lint then
warns on any curated sheet whose cited spells changed after its
`curated_as_of` date.

## Current state (verified 2026-08-12)

**One source of truth.** Capability numbers live only in `pipeline/sheets/*.yaml`.
The engine, the golden tests and the dashboard all consume
`out/dataset-latest.json`, built from those sheets. `build_dashboard.py` inlines
the Python engine's own output as a parity fixture, so the browser client
asserts against `engine.py` on every build.

- **Curated sheets: 6** — mace line (`MAIN_MACE`, `2H_MACE`), `2H_LONGBOW`,
  holy line (`MAIN_HOLYSTAFF_AVALON`, `2H_HOLYSTAFF_UNDEAD`),
  `2H_NATURESTAFF_HELL`. All lint-clean.
- **Illustrative placeholders: 8** in `sheets/illustrative/prototype_v0.yaml` —
  design-doc §2.3 numbers with no evidence. They keep the golden suite runnable
  and they block `release_clean`. Delete each block as its weapon gets curated.
- **Drafts awaiting curation: 34**, seeded in usage order, all lint-clean.
- **Dashboard**: `dashboard/index.html`, generated — capability bars vs target,
  weakness ranking, recommendation with Δ-term breakdown, evidence drawer,
  greedy-trap lookahead. Open the file directly; it is self-contained.
- **Effect map review**: `review/effects.html`, generated — every effect and
  what it grounds, by direction.
- `tests/prototype_engine.py` is superseded by `engine/engine.py` + 
  `tests/test_golden.py`, but kept as the historical record of the Tier-1 run.

Data sources verified live: official gameinfo killboard API (equipment per player; ActiveSpells confirmed empty at scale — 0/~2,000 fields across ~45 events, so spell choices are invisible in all battle data), api.albionbb.com (per-player weapon/role/damage/heal per battle, undocumented), ao-bin-dumps (weapon→spell lists + descriptions).

Default kits CAN be harvested (researched, not yet built): Metabattle's open MediaWiki API (~120 curated builds, per-slot spells in `{{Build equipment}}` wikitext, CC BY-SA) + Albion Free Market (4,478 builds, game-native spell IDs, SSR-scrapeable, ask Discord first). Two-source agreement = high-confidence default kit; see design doc §2.4.

## Non-negotiable rules established in review

- Every nonzero capability score cites its evidence spell; weapon sheets contain only the weapon's own kit; gear capabilities go on gear sheets, composed via archetypes
- Effect direction matters: self-targeted abilities (self-knockback, self-cleanse) never ground enemy/ally-directed capabilities
- Hard floors in the scoring model (healing/frontline) are load-bearing — first prototype run failed 4/9 without them
- The 9 golden tests are a permanent regression suite; add a case whenever a human expert corrects the engine
- Prefer prose explanations generated from score deltas, never canned text
- Never invent a capability to fill a gap. If the evidence isn't there, the score is 0.

## Immediate next step: continue curation (batch 2)

Curate in **usage order**, not draft order — `pipeline/out/weapon_usage.json`
ranks them. Per batch of 3–5:

```
py -3 pipeline/curate_helper.py --top 5      # every equippable spell + its description
```

Claude proposes structural capability scores (engage/peel/clump_create/
tankiness/burst_aoe…, which the seeder deliberately never guesses) with an
evidence spell for each; the human corrects as domain expert; lint validates;
the sheet moves to `sheets/` and its draft is deleted (the seeder now does that
automatically on re-run).

Next by usage: `2H_ICECRYSTAL_UNDEAD` (12), `2H_POLEHAMMER` (11),
`2H_DUALAXE_KEEPER` (10), `MAIN_RAPIER_MORGANA` (9), `2H_BOW_AVALON` (9).

**Settled — cleanse is per weapon, not per line.** The shared holy Q/W pool has
no cleanse, so it is never a holy build choice. But two holy staves have it
inherent on their E: Lifetouch (`MAIN_HOLYSTAFF_MORGANA`, `HOLYTOUCH`) and
Fallen (`2H_HOLYSTAFF_HELL`, `HOLY_ULTIMATE`). Hallowfall, Redemption, Great
Holy and Exalted have none — so `cleanse 0` on the curated sheets is right, and
**gear is not a Tier-2 blocker**. Cleanse is also a W option across the whole
nature line (`CLEANSEHEAL`) and arcane line (`CLEANSESPEED2`, incl. Witchwork),
where it is conditional. Score those with QW provenance when curating them.

**Settled — `anti_zone` is its own capability** (design doc §2.2, now 27 caps).
Removing enemy ground areas is not `purge` (buffs off enemy units) and not
`cleanse` (CC off allies). Implemented end to end: flag, lint rule, seeder,
template, dashboard. Its template weight in `castle_outpost.yaml` is marked
PROVISIONAL and set low (target 1, weight 3) — it needs expert tuning, since
anti-zone value is enemy-dependent (design doc §4.4.5). Only
`2H_HOLYSTAFF_CRYSTAL` supplies it so far.

## After curation

**Tier-2 validation (the real accuracy gate) — harness is built and tested:**

```
py -3 tests/tier2_blindtest.py generate --n 12 --out tier2_form.md
#   send the SAME file to 3+ shotcallers; it deliberately shows no engine output
py -3 tests/tier2_blindtest.py score tier2_form_filled.md
```

Gate: expert pick in engine top-3 on ≥70% of cases. `tests/tier2_form.md` is
already generated (12 cases, seed 20260812). V4 (meta-comp reproduction) needs
`tests/meta_comps.yaml` — a list of **real published** comps from albioncompo or
guild guides. Do not invent them.

Then: gear sheets (blocks archetype composition and the "cleanse if running X"
conditional-capability UI), more content templates (only `castle_outpost` at
size 7 exists and is validated), and Phase 3 battle-data ingestion for MetaPrior.

## Correction to the design doc's MVP scope

Design doc §5 assumes ~60 weapons cover >90% of usage. Measured against the
current sample that is wrong: top-30 covers **62%**, and 97 distinct weapons
appear in 359 observations. 59 weapons seen in the data still have no sheet at
all. Caveat: the sample is small and skewed to 10–60 player fights, so
re-measure at ~200 battles (VALIDATION V7) before re-planning scope around it.
