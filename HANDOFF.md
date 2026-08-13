# Handoff — Albion Online Composition Engine

Paste the prompt below into a new session with this repo folder connected.

---

I'm building an Albion Online dynamic party-composition recommendation engine.
Previous sessions completed the research, design, validation harness, the data
pipeline, the engine, a working dashboard — and as of 2026-08-12, **capability
sheets for all 137 combat weapons** (`release_clean: True`). Read these files
before doing anything:

1. `albion-comp-engine-design.md` — feasibility research + system design
   (data sources verified live, capability taxonomy incl. the 2026-08-12
   `anti_zone` and `damage_debuff` amendments, content templates, scoring
   algorithm, architecture)
2. `pipeline/README.md` — the pipeline workflow, current status, patch
   procedure (including the `effect_overrides.yaml` re-check step)
3. `tests/VALIDATION.md` — the test plan; Tier 1 passed, Tier 2 is the gate
4. `engine/engine.py` + `tests/test_golden.py` — the engine and its 9 golden
   regression cases

## Environment (Windows)

- Use `py -3`, **not** `python`/`python3` — those hit the Microsoft Store stub.
- `pyyaml` is installed. Node is available (used for ad-hoc data inspection).
- The ao-bin-dumps clone is not in the repo and is only needed after a game
  patch. See `pipeline/README.md` for the correct clone command.
- Work happens on branches; `weapon-curation-full-coverage` holds the
  full-coverage pass (2 commits) pending merge to `main`.

## Rebuild everything

```
py -3 pipeline/evidence_lint.py        # CI gate — exit 1 blocks release
py -3 pipeline/build_dataset.py        # sheets + templates -> out/dataset-latest.json
py -3 tests/test_golden.py             # must stay 9/9
py -3 tests/test_patch_history.py      # patch-diff + staleness units, no clone needed
py -3 pipeline/build_dashboard.py      # -> dashboard/index.html
py -3 pipeline/build_effect_review.py  # -> review/effects.html
```

## Current state (verified 2026-08-12, post full-coverage pass)

**One source of truth.** Capability numbers live only in `pipeline/sheets/*.yaml`.
The engine, the golden tests and the dashboard all consume
`out/dataset-latest.json`. All gates green: lint 0 errors across 60 sheet
files, golden 9/9, patch-history 14/14.

- **Curated: 137/137 combat weapons.** The remaining 24 catalog entries are
  vanity items / gathering tools — no sheets, on purpose. Drafts: 0.
  Illustrative placeholders: 0 (`sheets/illustrative/prototype_v0.yaml` is a
  tombstone record of the §2.3 prototype numbers and their corrections).
- **Line structure is the organizing principle**: all weapons in a line share
  the same Q/W spell pool; only the E differs. Line-mates carry identical
  QW-conditional scores (marked `(QW)` in comments); per-weapon files exist
  for the usage-order batches, `*_line*.yaml` files complete each tree.
- **`pipeline/effect_overrides.yaml`** documents every runtime correction to
  parser output: direction bugs ("your resistances" tagged ally), reference-
  chain artifacts (Iron Will's purge-immunity parsed as purges, Ghost Strike
  crediting its combo-condition spells), heal-flag reclassification
  (lifesteal = self_only, "negates Healing Received" = negate), and `add:`
  entries for real mechanics outside the structured vocabulary (absorb
  shields, ally-save pulls, drag-clumps, form payloads). MUST be re-checked
  after every ao-bin-dumps re-clone.
- `effect_lookup.py`: structured effects now SUPERSEDE direction-blind prose
  flags (ally-direction guard for the heal flag). Seeder and lint share it.
- Dashboard and effects review regenerate cleanly; both are self-contained.

## Non-negotiable rules established in review

- Every nonzero capability score cites its evidence spell; weapon sheets
  contain only the weapon's own kit; gear capabilities go on gear sheets.
- Effect direction matters: self-targeted abilities never ground enemy/ally-
  directed capabilities. Lifesteal is `self_sustain`, never `heal_sustain`.
- **Momentary-defensive ruling (2026-08-12):** personal channel/dash
  defensives (Parry, Deflecting Spin, Counter stance, Cartwheel, untargetable
  windows) do NOT ground `tankiness` — they were harvesting tank-floor relief
  and out-ranking real tanks. Sustained/identity durability (Giant Steps, the
  Runestone Golem form, tank-line `WEAPON_STATS`) does.
- Knock-ups and stuns HOLD clumps; only drag/pull mechanics CREATE them
  (Tackle, Onslaught, Vendetta, Black Hole, Positional Drift).
- Interrupts are not silences; charge-scaled burst is not execute (execute =
  health-threshold scaling, e.g. Bloodletter E).
- Hard floors in the scoring model are load-bearing; the 9 golden tests are a
  permanent regression suite; add a case whenever an expert corrects the engine.
- Never invent a capability to fill a gap. If the evidence isn't there, the
  score is 0. When the PARSER is wrong, fix it in `effect_overrides.yaml`
  with the dumps text cited — never by fudging a sheet.

## PROVISIONAL numbers awaiting the expert

- `castle_outpost.yaml` hard floor `heal_sustain.penalty_mult: 2.0` (raised
  from 1.5 when synergy+meta leakage out-ranked healers). Structural
  alternative worth testing after Tier-2: step-function floors (full penalty
  until `floor_units` met) — partial-credit relief is what let one point of
  pseudo-tankiness eat half the tank-floor penalty.
- `anti_zone` weight (sole supplier: Exalted Staff) and `damage_debuff`
  weight (scored on 6 defining carriers; small carriers like Weakening and
  Frost Beam held at 0 pending expert weighting).
- The ~15 `add:` entries in `effect_overrides.yaml` — each text-verified but
  judgment-flavored; SOUL_LINK→peel and HAMMERTACKLE→clump_create especially.
- Black Hands' E has an EMPTY dumps description; scores rest on structured
  effects, cross-checked against community sources (two-hit purge/knockback
  combo). The 2nd-hit knockback is unscored.

## Immediate next step: Tier-2 blind validation

Everything else is tuning noise until expert data arrives — floors, the
tankiness ruling, and score ladders all get adjudicated by this gate.

```
tests/tier2_form.md      # regenerated against all 137 weapons, seed 20260812
#   send the SAME file to 3+ shotcallers; it deliberately shows no engine output
py -3 tests/tier2_blindtest.py score tier2_form_filled.md
```

Gate: expert pick in engine top-3 on ≥70% of cases. V4 (meta-comp
reproduction) needs `tests/meta_comps.yaml` — a list of **real published**
comps from albioncompo or guild guides. Do not invent them.

## After Tier-2

- Expert correction pass over the proposed scores (headers on every sheet
  flag the judgment calls and draft corrections).
- Gear sheets (blocks archetype composition and the "cleanse if running X"
  conditional-capability UI). Default kits: Metabattle open MediaWiki API
  (~120 builds, CC BY-SA) + Albion Free Market (4,478 builds, game-native
  spell IDs; ask their Discord before bulk harvest); two-source agreement =
  high-confidence kit (design doc §2.4).
- More content templates (only `castle_outpost` at size 7 exists) and Phase 3
  battle-data ingestion for MetaPrior. Usage sample is still small (24
  battles / 359 players) — re-run at ~200 battles (VALIDATION V7).
