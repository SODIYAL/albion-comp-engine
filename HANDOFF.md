# Handoff — Albion Online Composition Engine

Paste the prompt below into a new session with this repo folder connected.

---

I'm building an Albion Online dynamic party-composition recommendation engine.
Previous sessions completed the research, design, validation harness, the data
pipeline, the engine, capability sheets for **all 137 combat weapons**
(`release_clean: True`) — and the product itself: **Comp Forge**, live at
<https://sodiyal.github.io/albion-comp-engine/>. Read these files before doing
anything:

1. `albion-comp-engine-design.md` — feasibility research + system design
   (data sources verified live, capability taxonomy incl. the `anti_zone` and
   `damage_debuff` amendments, content templates, scoring algorithm,
   architecture; dated amendments track what changed since)
2. `pipeline/README.md` — the pipeline workflow, current status, patch
   procedure (including the `effect_overrides.yaml` re-check step)
3. `tests/VALIDATION.md` — the test plan: Tier 1 passed, Tier 2 is the gate,
   and the first V4 baseline (with its three findings) is recorded there
4. `engine/engine.py` + `tests/test_golden.py` — the engine (it has a CLI:
   `py -3 engine/engine.py camlann hallowfall --content blackzone_roam
   --size 10 --style clap`) and its 15 golden regression cases

## Environment (Windows)

- Use `py -3`, **not** `python`/`python3` — those hit the Microsoft Store stub.
- `pyyaml` and `Pillow` are installed. Node is available (parity tests).
  `gh` is authenticated as SODIYAL (used for the Pages config).
- **Commit messages must go through `git commit -F <file>`** — PowerShell 5.1
  mangles here-strings containing double quotes into pathspec arguments.
- The ao-bin-dumps clone is not in the repo and is only needed after a game
  patch. See `pipeline/README.md` for the correct clone command.
- Day-to-day work lands on `main` in small verified slices (gates below);
  use a branch when a change is risky or needs review before it ships,
  because pushing `main` **deploys the public site**.

## Rebuild everything

```
py -3 pipeline/evidence_lint.py        # CI gate — exit 1 blocks release
py -3 pipeline/build_dataset.py        # sheets + templates + styles -> out/dataset-latest.json
py -3 tests/test_golden.py             # must stay 15/15
py -3 tests/test_js_parity.py          # browser scoring == engine.py (needs node)
py -3 tests/test_patch_history.py      # patch-diff + staleness units, no clone needed
py -3 pipeline/build_dashboard.py      # -> dashboard/index.html AND docs/index.html
py -3 pipeline/build_effect_review.py  # -> review/effects.html
py -3 pipeline/build_magnitude_review.py  # -> review/magnitude.html (score-vs-dumps audit boards)
py -3 pipeline/fetch_icons.py          # only after a patch ADDS weapons (cached; --force redownloads)
py -3 pipeline/sample_battles.py       # optional: refresh usage field reports
                                       # (albionbb API — gameinfo 504s at scale;
                                       # per-battle cache; display-only data)
```

**Deploy = rebuild + push.** GitHub Pages serves `main:/docs`;
`build_dashboard.py` writes `docs/index.html` (the doctype'd copy of the
dashboard) on every build, so pushing `main` updates the live site.

## RESUME HERE — Party Companion (2026-08-14, one live run from done)

`companion/` is a C# console app that reads your live Albion party (roster,
weapons, gear, spells) and serves it as JSON on `localhost:53321`; Comp Forge's
new "connect live party" button pulls it into a comp. **Read
`companion/README.md`'s "Status — pick up here" block first** — it has the exact
one-live-run checklist. Design + event map + legality: `COMPANION_SCOPE.md`.

Everything is BUILT and committed (tree clean — check `git status`). The whole
thing needs **one live in-game run** to confirm three things at once:

1. **Spells resolve** to sheet-matching UniqueNames in `/party` (`SpellDb.cs`).
2. **Auto-calibration binds** — `/status` `detected_codes` shows e.g.
   `NewCharacter:29`. Events now dispatch by parameter SHAPE, not hardcoded
   numbers, so a patch that renumbers events self-heals.
3. **Connect button works end-to-end** — in Comp Forge's left rail; polls
   `/party`, lists the party, "load party into comp" fills slots. Verified
   against a mock; needs the live companion to confirm.

- Run the exe **as Administrator** (`run-companion.bat` rebuilds + self-elevates).
  Needs .NET 8 SDK (installed).
- **Key facts** (COMPANION_SCOPE.md / companion/README.md): current Albion uses
  Photon **Protocol18** (stock NuGet parser is Protocol16, decodes nothing) —
  working parser vendored under `companion/photon/` (GPL-3.0; companion binary
  is GPL, Comp Forge unaffected). Item/spell indices shift per patch (delete the
  cache to re-pull); event codes now self-heal via shape detection.
- Commits this session: `907ee88` mechanics+corrections · `953244b` UI ·
  `6a75dc3` companion core · `a50e620` spell resolution · `4e1e779` shape
  auto-calibration · `afa0f62` connect button. None pushed (public site
  untouched).

## Current state (verified 2026-08-13)

**One source of truth.** Capability numbers live only in `pipeline/sheets/*.yaml`;
global combat-mechanics numbers live only in `pipeline/templates/mechanics.yaml`.
The engine, the golden tests and the page all consume `out/dataset-latest.json`.
All gates green: lint 0 errors across 60 sheet files, golden 18/18, JS/Python
parity 60/60 across all templates × styles at 1e-9, patch-history 14/14.

- **Curated: 137/137 combat weapons.** The remaining 24 catalog entries are
  vanity items / gathering tools — no sheets, on purpose. Drafts: 0.
  Illustrative placeholders: 0 (`sheets/illustrative/prototype_v0.yaml` is a
  tombstone record of the §2.3 prototype numbers and their corrections).
- **Five content templates, sizes set by the content**: `blackzone_roam` (20),
  `territory_defense` (20), `castle` (25), `faction_war` (15),
  `castle_outpost` (7) — plus **five playstyles** in `templates/styles.yaml`
  (balanced/brawl/clap/kite/brawl_clap) that multiply capability WEIGHTS on
  top of any template (floors and over-stack stay on base weight — T10 caught
  the alternative punishing a clap comp for stacking bombs). Party size is
  free-form (2–60): effective size = max(planned, roster).
- **The product page is `dashboard/index.html` — "Comp Forge"**, public at
  <https://sodiyal.github.io/albion-comp-engine/>. Generated by
  `build_dashboard.py` from `_shell.html` (markup/CSS) + `_app.js`
  (rendering only). Features: content + playstyle pickers, adaptive party
  size, numbered slots with role tally and per-member fitness contribution
  ("least load-bearing" / "comp gains without it"), tree + text weapon
  filters, "forge a full comp" greedy auto-build, needed-now vs nice-to-have
  gap split, full capability board with evidence drawer, weapon detail
  drawer (real Q/W/E/passive pools by in-game name + caller loadouts from
  the `skills` columns in `tests/meta_comps.yaml`), killboard meta strip +
  per-weapon field reports (display-only), embedded item icons (136/137 —
  Black Hands is missing from the render service itself), share-link hash
  state, localStorage restore, Discord comp export. Scoring runs in the
  browser via `pipeline/app_scoring.js` — a line-for-line port of
  `engine/engine.py`; **change one, change both, rerun parity**. A
  build-time fixture re-checks parity on every page load (masthead chip).
  A short-lived duplicate app (`app/`, 2026-08-12) was folded back in —
  don't recreate it.
- **Real-usage data**: `out/weapon_usage_v2.json` — 149 battles / 1,252
  players / **99.4% weapon attribution (V7 gate ≥85%: PASS)**, bucketed
  small (<12) / mid (12–30) / large (>30). Zero unknown weapon keys — the
  catalog covered everything seen in the wild. Large bucket is thin (6
  battles); a `--force`-free rerun tops it up when the albionbb API isn't
  throttling. **Display-only by rule** until validation admits it to scoring.
- **First V4 baseline exists** (`py -3 tests/tier2_blindtest.py v4`):
  role-level 18/26 = **69%** (gate 70%), weapon-level 9%, over 70
  leave-one-out slots. Three findings recorded in VALIDATION.md: leave-one-
  out degenerates at full-party saturation; breadth-over-depth wins the
  saturated margin; dedicated support never reproduces (undervalued at the
  margin). **Nothing was retuned** — these comps calibrated the templates
  (circularity), so the findings await the expert and independent comps.
- **Game-mechanics layer (2026-08-13)**: `pipeline/templates/mechanics.yaml`
  holds the wiki-sourced ZvZ mechanics (Focus Fire/Resilience tables, AoE
  Escalation curve, Disarray — the last recorded but UNWIRED: it cancels in
  a mirror fight). Styles carry `mechanics: {expected_aoe_targets,
  focus_attackers}`; the engine turns these into effectiveness multipliers
  on `burst_aoe` (escalation) and `burst_st`/`execute` (Resilience),
  NORMALIZED so balanced ≡ identity — template calibration untouched, V4
  baseline unchanged by construction. Golden T11 pins the directions.
  Open questions + provisional numbers tracked in `MECHANICS_TODO.md`.
- **Line structure is the organizing principle**: all weapons in a line share
  the same Q/W spell pool; only the E differs. Line-mates carry identical
  QW-conditional scores (marked `(QW)` in comments).
- **`pipeline/effect_overrides.yaml`** documents every runtime correction to
  parser output (direction bugs, reference-chain artifacts, heal-flag
  reclassification, `add:` entries for real mechanics outside the structured
  vocabulary). MUST be re-checked after every ao-bin-dumps re-clone.
- `effect_lookup.py`: structured effects SUPERSEDE direction-blind prose
  flags (ally-direction guard for the heal flag). Seeder and lint share it.

## Non-negotiable rules established in review

- Every nonzero capability score cites its evidence spell; weapon sheets
  contain only the weapon's own kit; gear capabilities go on gear sheets.
- Effect direction matters: self-targeted abilities never ground enemy/ally-
  directed capabilities. Lifesteal is `self_sustain`, never `heal_sustain`.
- **Momentary-defensive ruling:** personal channel/dash defensives (Parry,
  Deflecting Spin, Counter stance, Cartwheel, untargetable windows) do NOT
  ground `tankiness`. Sustained/identity durability does.
- Knock-ups, knockbacks and stuns HOLD (or scatter) clumps; only drag/pull
  mechanics CREATE them (Onslaught, Vendetta, Black Hole, Triple Kick's
  kidnap). Great Hammer's Tackle is a knockback, NOT a clump creator —
  expert-corrected 2026-08-13, pinned by golden T12.
- **Magnitude, not existence — ALL capabilities** (expert, 2026-08-13):
  every score encodes impact magnitude; a token effect is not the same
  number as a battle-shaping one. First applied to `knockback_displace`
  (golden T13): 3 = battle-shaping (≥12m or kit-wide, CC-resist-ignoring);
  2 = real AoE travel; 1 = minor/incidental (single-target bolts, small
  scatters, ALL knock-ups/air-throws — no travel, control value lives in
  peel/stun); 0 = trivial in group fights (healer self-peel nudges, AA
  passives). Never score the same control twice across
  clump_create/peel/knockback_displace. The dataset-wide audit runs
  through `review/magnitude.html` (`py -3 pipeline/build_magnitude_review.py`
  — per-capability boards with dumps numbers beside every score; RULE/PASV/
  TOP flags). Open queue in MECHANICS_TODO.md. When a shared QW spell's
  score is topped up by an E contribution, the sheet comment MUST say so —
  a same-spell score mismatch without that comment is a bug.
- Interrupts are not silences; charge-scaled burst is not execute (execute =
  health-threshold scaling, e.g. Bloodletter E).
- Hard floors are load-bearing; the golden suite (15 cases) is permanent —
  add a case whenever an expert corrects the engine and is right.
- Never invent a capability to fill a gap. If the evidence isn't there, the
  score is 0. When the PARSER is wrong, fix it in `effect_overrides.yaml`
  with the dumps text cited — never by fudging a sheet.
- Meta comps (`tests/meta_comps.yaml`) and caller loadouts are **real data
  only, never invented**; killboard usage stays display-only pre-validation.

## PROVISIONAL numbers awaiting the expert

- `castle_outpost.yaml` heal floor `penalty_mult: 2.0` (raised from 1.5 when
  synergy+meta leakage out-ranked healers). Structural alternative worth
  testing after Tier-2: step-function floors (no partial-credit relief).
- The entire requirement sets of `blackzone_roam`, `territory_defense`,
  `castle`, `faction_war` — calibrated first drafts, reasoning in headers.
- Every multiplier in `templates/styles.yaml` — golden T10 pins only the
  style DIRECTIONS, not magnitudes.
- `anti_zone` weight (sole supplier: Exalted Staff) and `damage_debuff`
  weight (6 defining carriers; small carriers held at 0).
- The ~15 `add:` entries in `effect_overrides.yaml` — text-verified but
  judgment-flavored; SOUL_LINK→peel especially (HAMMERTACKLE→clump_create
  was expert-adjudicated 2026-08-13: removed, tombstoned in the overrides).
- The per-style `mechanics` parameters in `styles.yaml`
  (`expected_aoe_targets`, `focus_attackers`) — research-derived, not
  expert numbers yet (`MECHANICS_TODO.md` Q14; curves themselves are wiki
  data in `mechanics.yaml` and are NOT provisional).
- Black Hands: empty dumps description AND missing from the render service;
  scores rest on structured effects + community sources.
- From the V4 baseline: support undervaluation at the margin and a possible
  redundancy/diversity term for the saturated range — expert questions, not
  numbers to tweak blind.

## Immediate next step: Tier-2 blind validation (V3)

Everything else is tuning noise until expert data arrives — floors, style
magnitudes, template weights and score ladders all get adjudicated by this.

```
tests/tier2_form.md      # seed 20260812, generated against all 137 weapons
#   send the SAME file to 3+ shotcallers; it deliberately shows no engine output
py -3 tests/tier2_blindtest.py score tier2_form_filled.md
```

Gate: expert pick in engine top-3 on ≥70% of cases. Every miss where the
expert is right becomes a golden case.

**V4 has its baseline** (69% role-level, see VALIDATION.md) but it's
weak-form: the 20-size templates were calibrated on the same two comps. The
single highest-value data acquisition is **one more real comp from a caller
who didn't shape the templates** — that turns V4 into real evidence. More
caller loadout sheets (like Timothy's q/w/p columns) extend the in-app spell
suggestions to more content types for free.

## After Tier-2

- Expert correction pass over proposed scores (sheet headers flag every
  judgment call), template weights, style magnitudes, and the V4 findings.
- Gear sheets — the biggest remaining build item; blocks archetype
  composition and the "cleanse if running X" conditional-capability UI.
  Default kits: Metabattle open MediaWiki API (~120 builds, CC BY-SA) +
  Albion Free Market (4,478 builds; ask their Discord before bulk harvest);
  two-source agreement = high-confidence kit (design doc §2.4). Gear icons
  come free from the same render service once gear item IDs exist.
- More content templates (Hellgate 5v5, Roads 7) and a V4b runner that
  reconstructs the last ~5 slots instead of leave-one-out at saturation.
- Phase 3 proper: battle-data ingestion for MetaPrior (replace the hand-set
  guard values), content labeling (V6), win-lift backtest (V8).
