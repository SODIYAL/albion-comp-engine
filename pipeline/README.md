# Composition Engine — Data Pipeline

This directory is the **engine domain's data layer**: it turns the pinned
game-data snapshot plus human curation into `out/dataset-latest.json`, the
single file both engine ports consume. It never renders UI (the frontend
bundler is `dashboard/build.py`) and never scores (that's `engine/`).

Windows note: use `py -3`, not `python`/`python3` — those resolve to the
Microsoft Store stub. Requires `pyyaml` (`py -3 -m pip install pyyaml`).

```text
data/source_pins.yaml     the ONE pinned ao-bin-dumps commit (data/README.md "Provenance")
   │  py -3 pipeline/fetch_snapshot.py     ← the only network step for dumps
   ▼
out/dumps_cache/<sha12>/  raw snapshot, cached BY COMMIT (gitignored)
out/source_manifest.json  repository/commit/timestamps/patch + SHA-256 per file
   │  py -3 pipeline/parse_dumps.py        (reads the pinned snapshot)
   │  py -3 pipeline/fetch_item_stats.py
   │  py -3 pipeline/fetch_gear_lines.py
   ▼
out/weapon_lines.json     161 weapon lines: name + full Q/W/E/passive spell lists
out/spell_index.json      367 spells: function flags, direction hints, and
                          structural AREA GEOMETRY (radius/max targets)
out/item_stats.json       base stats + per-tier/per-enchant item power
out/weapon_usage_v2.json  FIGHT-SIZE equipment prevalence + killer-party cohorts
                          (derive_usage.py, from the party harvest; display only)
   │  py -3 pipeline/build_interactions.py   (interactions.yaml -> validated)
   ▼
out/interactions.json     spell-keyed PvP interaction records: duplicate
                          semantics, reflect/cleanse/purge per component, CC
                          classes, confidence provenance. Scoring reads ONLY
                          verified nonstacking_caps; unknown never scores.
   │  py -3 pipeline/seed_sheets.py 40
   ▼
sheets/draft/*.yaml       auto-seeded drafts (effect caps only; lint-clean once curated into the tree sheet)
   │  HUMAN CURATION — read the evidence first:
   │      py -3 pipeline/curate_helper.py --top 5
   │      py -3 pipeline/curate_helper.py 2H_POLEHAMMER
   │  adjust scores, add structural caps (engage/peel/clump/tankiness/...),
   │  then move the entry into its tree's sheet and delete its draft
   ▼
sheets/<tree>.yaml        curated weapon entries, one file per weapon tree (authoritative)
sheets/pools/<tree>.yaml  the tree's shared Q/W/passive rows, composed into its entries
sheets/gear/<slot>.yaml   curated gear, one file per slot (shared actives: gear/pools/)
sheets/illustrative/      placeholder sheets, when any exist (none do) — NOT a release
   │  py -3 pipeline/evidence_lint.py      ← CI gate, exit 1 blocks release
   │  py -3 pipeline/build_dataset.py
   ▼
out/dataset-latest.json                             ← single source of truth
   │
   ├─ engine/engine.py            scoring engine (Python)
   ├─ tests/test_golden.py        golden regression cases
   └─ py -3 dashboard/build.py → dashboard/index.html (Comp Forge,
            the product page; dataset inlined, scoring runs in-browser via
            engine/app_scoring.js — a port of engine.py that tests/test_js_parity.py
            holds equal. Change one, change both, rerun parity.)
```

**One source of truth.** Capability numbers live only in the YAML sheets. The
engine, the golden tests and the dashboard all read the built dataset. Before
this existed, the prototype kept its own inline copy and the two had already
diverged (Longbow `resist_shred` was 2 in the prototype, 1 in the curated
sheet). `dashboard/build.py` inlines the Python engine's own output as a parity
fixture, so the browser client asserts against `engine.py` on every build.

Rules enforced by `evidence_lint.py` (all born from real curation errors),
numbered as the lint's docstring numbers them. Every nonzero score cites an
evidence spell, or its layer's stat sentinel (`WEAPON_STATS` on weapons,
`GEAR_STATS` on gear), and the rows are checked as the build composes them
(an entry's own rows plus the tree-pool rows that apply to it):

1. The weapon line (gear item) exists in the parsed game data.
2. The spell must be equippable on that weapon (on the gear item's menu) —
   gear capabilities belong on gear sheets.
3. The spell must be able to GROUND the claimed capability, resolved through the
   structured effect map. Direction is built in, so an enemy-directed capability
   cannot cite a self-targeted effect. Rule 3's boundary is computed: a
   capability is checked iff the effect map or the prose fallback can produce
   it, less the four damage capabilities; the rest get checks 1–2 only (the
   lint's first output line prints that set).

4–11. The sheet contract: known keys only, an integer score 1–7, the
capability taxonomy, no duplicate row or except, every except live, one
definition per weapon and gear key, an ISO `curated_as_of`, a known
`role_hint` and gear `slot`, placement (`pipeline/sheets/README.md`
"Layout").

Rule 3 used to match description keywords, which saw a fraction of the game —
100 weapon lines apply a movespeed debuff and the `slow` regex matched almost
none of them.

## The evidence layer

Build provenance lives in `data/` — record conventions, source kinds,
statuses, quarantine and the promotion gate are in `data/README.md`: caller
comps (`published_comps/`) and MetaBattle imports
(`published_builds/metabattle.yaml`, adapter:
`py -3 pipeline/adapters/metabattle.py fetch|parse` — fetch is explicit and
never part of a normal build; adapter v2 captures every group-PvP category —
ZvZ, Hellgate 5v5/10v10, Crystal League/Arena, Ganking — with `content`
derived from each page's own mode category).
`py -3 pipeline/build_builds.py` validates + normalizes
everything into `out/builds_index.json` (the selection order, canonical
flags) and `out/builds_validation.json` (problems, quarantines, promotion
decisions). `dashboard/build.py` inlines the index; nothing in it feeds
scoring.

`gear_join.py` is the shared read-side of that evidence for the
dressed-validation layer: it reconstructs per-member ACTUAL kits from
`out/builds_index.json` (join key `comp_id:party_name:slot_index` over the
FULL slot list, battlemounts included; conservative id normalization
mirroring `build_dataset._normalize_gear_id` — unresolved pieces are
counted, never guessed) plus `doctrine_gears` (kit_variants v0). Consumers:
`tests/tier2_blindtest.py` (V3-D / V4 gear classes) and the dressed audits.

## Dressed audits (report-only — never part of a build)

```text
py -3 pipeline/audit_validation_asymmetry.py  # legacy vs V3-W vs dressed top-3 diffs -> out/validation_asymmetry_probe.json
py -3 pipeline/audit_dressed_templates.py     # per-comp capability supply weapon/combo/dressed/doctrine vs targets, soft caps, floors -> out/dressed_template_audit.json
py -3 pipeline/audit_frontline_floor.py       # adversarial no-tank parties vs the tankiness hard floor -> out/frontline_floor_audit.json
py -3 pipeline/audit_gear_synergy.py          # gear-sourced synergy sides: measured + labeled hypotheticals -> out/gear_synergy_audit.json
py -3 pipeline/audit_forge_quality.py         # the forge button's rosters, planner grid + portal pools, graded against the harvest -> review/forge_quality/
```

None of these writes anything a build reads. The gear-synergy finding is
`notes/findings/2026-08-27-gear-synergy-finding.md`; the other findings of
that audit round are logged in `notes/validation/2026-08.md` (their files
are pruned, see `notes/validation/README.md`); the tuning discipline (train /
validation / holdout) is a standing rule in `tests/VALIDATION.md`. (The
`calibration/` scaffold and `calibrate_scoring.py` are retired: four train
cases, empty validation and holdout, nothing in the build or CI read them.)
The forge-quality sweep's finding is
`notes/findings/2026-10-09-forge-quality.md`; its first run on an artifact
parses the roster artifact and caches the parties it grades against.

## Mechanics

Fight mechanics — Focus Fire / Resilience, AoE escalation, Disarray, the
geometric AoE transform, Resilience Penetration — modify **capability supply
vs target** in `engine/engine.py` and `engine/app_scoring.js` (change one,
change both, rerun parity). Canonical data home:
`pipeline/templates/mechanics.yaml` (its Focus-Fire / Resilience and
AoE-Escalation tables match the wiki's pages — single-target damage is
punished in large groups and AoE damage is rewarded in larger groups; balance
patches through 31.030.1 touched none of them); per-weapon Resilience
Penetration is the pinned snapshot's own item stat
(`@focusfireprotectionpenetration`, read into `out/item_stats.json`; zero on
every item of the pinned snapshot, F20).

State: the three ZvZ mechanics are WIRED as supply-side effectiveness
multipliers, per style, normalized to the balanced style (golden T11 pins the
directions); the geometric AoE utility scaling is wired in both ports
(T18/T18b); per-weapon Resilience Penetration is wired as a supply-side rebate
(F20). Open mechanics work is in `BACKLOG.md` (per-spell `burst_aoe` gating
Q9/Q10, the enemy model Q2/Q5, asymmetric numbers Q11/Q13, the dive style, the
magnitude audit queues).

### Geometric AoE utility scaling (standing rule)

Implemented by `engine/engine.py` `_geo_mult` and `mechanics.yaml`
`geometric_caps`; pinned by T18/T18b. Motivating case: Soulscythe (catch 1,
from Tornado's 80% AoE slow) ranked level with Battleaxe (catch 1, from a
self-haste W) as a catch alternative in a large comp. The cheap fix (bump
Soulscythe to catch 2) was REJECTED as papering over the structural gap: the
engine had no multi-target term for utility capabilities at all.

1. **Model = geometric + escalation.** An AoE effect's supply scales with
   expected targets hit (slowing 8 people is 8 targets' worth of work —
   independent of any in-game bonus); escalation-eligible spells get the
   in-game bonus ON TOP. Single-target effects stay flat. The in-game CC
   Escalation covers only AoE root/stun/silence DURATION — slows and
   knockbacks get no in-game bonus, but still scale geometrically.
2. **Expected targets = style clump × spell radius.** The style/size clump
   physics (expected_aoe_targets × count_mult) capped by what the spell's
   actual area can plausibly hit — per-spell shape/radius from
   `out/spell_index.json`.
3. **Catch quality has four factors, ALL count**: AoE CC on the clump,
   CC-resist-ignoring displacement (Tornado air-throw), dismount potential
   (mounted Resilience column; forced-dismount immunity gone at 21+), self
   gap-close/speed (real but flat — does not scale with fight size).
4. **Per-spell escalation eligibility comes from ao-bin-dumps** (Q9); wiki
   lists serve as validation, not source of truth.

Implementation, both ports: AoE-delivered supply for `geometric_caps` scales
with min(style clump, spell reach) / min(`reference_clump`, reach), with
CC-duration escalation composing where the spell carries a dumps factor.
`reference_clump: 2` anchors the unit at small-gang scale — the (balanced,
base_size) anchor was measured DEAD (base clumps exceed every spell's reach,
so it could never up-rate AoE at the calibrated sizes). Soulscythe catch:
1.5x@roads5 → 3.0x@20+ vs Battleaxe's flat 1.0 — the motivating failure.

### Deliberately not wired

- Disarray: recorded in mechanics.yaml only — cancels in a mirror fight
  (Q11); revisit if templates gain an expected-enemy-size field.
- CC Escalation: `stun` IS wired (geometric transform + the dumps-derived
  duration factor, Q8 — `mechanics.yaml` `cc_duration_caps`); only
  `clump_create` stays untouched.
- Per-spell `burst_aoe` escalation eligibility: extracted, NOT wired —
  `BACKLOG.md`.
- Mob HP bonus (+10% max HP per player over a per-mob-type threshold):
  PvE, out of scope.

### Mechanics questions, by number

Code and yaml cite these by Q-number. Every question is closed unless
`BACKLOG.md` lists it; the dated decisions are in `tests/VALIDATION.md`.

- **Q1** form of numbers — global tables in mechanics.yaml, per-spell parts through sheets/overrides.
- **Q2 / Q2b / Q5** the enemy model (attackers per target, expected targets hit) — OPEN, `BACKLOG.md`.
- **Q3** which focus-fire mechanic — overkill saturation via the Resilience table, a supply-side transform, not a synergy.
- **Q4 / Q12** Disarray numbers and table staleness — answered, recorded in mechanics.yaml, unwired.
- **Q6** AoE escalation magnitudes — 8%/target from 2, cap 56% at 8, after buffs, bypasses the soft cap.
- **Q7** Resilience Penetration — WIRED as a supply-side rebate on burst_st/execute at the style's grown focus count (a partial rebate: single-target damage is usually a non-pick at 20+, the rebate keeps what high penetration retains); F20 pins it. Optional: dumps cross-check of the wiki values (`BACKLOG.md`).
- **Q8** CC Escalation duration curve — from the dumps, same per-target factor as damage (0.08; Spirit Animal 0.25); published nowhere else.
- **Q9** per-spell escalation eligibility — extracted from the dumps, 174/559.
- **Q10** uniform AoE-class escalation — REFUTED; per-spell gating is the open item in `BACKLOG.md`.
- **Q11 / Q13** asymmetric numbers at 21+ — CLOSED under standing rule 11 (the planner assumes a mirror fight, where Disarray is a no-op); recorded in mechanics.yaml, unwired; an enemy-size input, if one is ever added, reopens it.
- **Q14** per-style mechanics numbers — delegated to curation under the ordering rule (attackers-per-target and expected-targets-hit are style properties); the enemy model in `BACKLOG.md`.
- **Q15** weapon playstyle affinity — derive + curate exceptions: `derive_style_fit` + `style_overrides.yaml`; audit `out/style_fit_report.json`; MetaBattle cross-check in `build_dataset.py`.
- **Q16** content-absolute physics — the `size_physics` tables (`st_value_mult`, `count_mult`, composition.yaml) match the wiki's Resilience and AoE Escalation pages (25% ST value at 20-man, 20% at 30+; ×1.6 clump at 20, ×2.0 at 40+); F8/T15/T16 pin them. The earlier `grow()` build is superseded.
- **Q17** usage-derived MetaPrior — SUPERSEDED: the meta prior is GENERATED from the killer-party harvest (`derive_meta_prior.py`, one player one vote, per size bucket, T46/H18); the usage_v2 build and its artifact are gone.
- **Q18** breadth/redundancy scoring penalty — INVESTIGATED + REJECTED (a rho sweep never earned its place; the engine already de-ranks breadth picks by context). The *descriptive* decomposition shipped later as `pick_report`.
- **Q19** one-spell-per-slot loadout model + single-target recalibration — SHIPPED (T14/T15); the Dagger-Pair-at-scale case fixed here (#3 → #33).
- **First wiring checklist** — mechanics.yaml shipped in the dataset; supply-side multipliers per style normalized to balanced; both ports; T11 family.
- **Magnitude RULE queue** — adjudicated wholesale, one reversal (Rotcaller keeps the line's 4: a 1H weapon adds an offhand, which can INCREASE damage — standing rule 12, no automatic 1H damage discount); `knockback_displace` ladder done earlier (T13).
- **Gear sheets** — `pipeline/sheets/gear/<slot>.yaml`, one file per slot (head, armor, shoes, offhand, cape, potion, food; 135 pieces); the tree-shared actives once in `sheets/gear/pools/<tree>.yaml`, composed into every item whose dumps menu carries the spell (`sheets_lib.compose_gear`; the item's own row wins a tie, `except:` opts out; `evidence_lint` checks each pool row sits on a menu in its tree). The layout and its lint checks: `pipeline/sheets/README.md` "Layout".
- **Gear-active doctrine** — the active a piece SCORES is the one the recording published builds equip (`build_builds` carries each build's `gear_spells`: the Character Builder's UniqueNames and MetaBattle's named actives, kept only as ids on the worn item's menu; `build_dataset.resolve_active_doctrine` stamps `doctrine_active` at two votes, by gang/group band too), else the item's own active (`assumed`), never the template argmax across the menu; an active with no scored row is an empty bundle. Both engine ports read the stamp (`default_gear_choice`; F36, H23, VALIDATION.md 10-03).
- **Stage 2 — live companion** — LIVE-CONFIRMED end to end (`companion/README.md`); inspect parsing + worn kits into loadouts.
- **Spell picks into scoring** — live sync maps real Q/W into the loadouts, worn kits too.
- **Reliability roadmap layering** — mechanism (sheets + lint), physics (mechanics + size tables), empirics (parked, Q17), the validation loop (running: every correction becomes a golden case). Weapon tagging reliability = cross-source agreement (sheets × killboard role × MetaBattle tags), never authorship.

## Moving to a new game patch

Update `data/source_pins.yaml` to the new ao-bin-dumps commit
(`https://api.github.com/repos/ao-data/ao-bin-dumps/commits/master`), then:

```text
py -3 pipeline/fetch_snapshot.py
py -3 pipeline/parse_dumps.py
py -3 pipeline/fetch_item_stats.py
py -3 pipeline/fetch_gear_lines.py
py -3 pipeline/fetch_icons.py       # only when the patch adds weapons/items (out/icon_data.json feeds the pages)
py -3 pipeline/effect_catalogue.py pipeline/out/dumps_cache/<sha12> --report
py -3 pipeline/evidence_review.py   # STALE ids: re-read every row citing each, fix the sheets,
                                    # then --accept ID; new citations: --accept-unrecorded
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_interactions.py
py -3 pipeline/build_builds.py
py -3 pipeline/build_dataset.py     # verifies the chain; exit 2 = blocked
py -3 pipeline/build_cohort_families.py
```

then the full gate list in CLAUDE.md ("Tests"). `build_dataset.py` accepts
`--skip-lint` and `--skip-provenance` for local experiments only — a
release never uses them (the provenance gate is the point). `build_dataset.py` fails closed if
any input is missing, hash-drifted, adapter-stale, or from a different
commit than the others.

## Re-cloning ao-bin-dumps

Only needed for `patch_history.py` (it walks git history; the pinned
snapshot fetch covers everything else).

**After every snapshot move + rebuild, re-check `pipeline/effect_overrides.yaml`.**
That file holds runtime corrections to parser output (direction bugs,
reference-chain artifacts, prose-flag misfires, and `add:` entries for
mechanics outside the structured vocabulary). Each entry cites the dumps text
it was verified against; an entry whose upstream bug gets fixed becomes
silently redundant — or wrong, if the spell was redesigned. Diff each entry's
spell against the fresh dumps text and delete entries the rebuild made
unnecessary.

The same re-check applies to the other cited-override files whose entries
quote dumps text or spell behavior: `ranged_overrides.yaml` (the cited
exceptions to the gap-closer rule, both ways), `heal_overrides.yaml` (heal-scale sub-effect corrections — Divine
Jump, Celestial Sphere), `style_overrides.yaml` (cited style-fit
overrides), and the `CURSEDOT` non-stacking record in `interactions.yaml`
(the "stacks up to 4 times" wording it cites).

`patch_history.py` needs a clone WITH HISTORY:

```text
git clone --filter=blob:none --no-checkout https://github.com/ao-data/ao-bin-dumps.git
```

(~3 MB of history; each diffed snapshot fetches its ~14 MB `spells.json` blob
on demand, so `--patches N` downloads N+1 blobs.)

## Patch history / staleness

```text
py -3 pipeline/patch_history.py <ao-bin-dumps clone> [--patches 8]
   -> out/patch_history.json
```

Every game patch is a commit in ao-bin-dumps; diffing `spells.json` between
consecutive commits gives exactly which spells changed, in the pipeline's own
spell IDs. This is the design doc's risk-9 ("patch drift") mitigation: curated
numbers go stale silently, and this makes the staleness mechanical.

- Changes resolve **transitively** (same rule as the effect layer): the
  2026-05-26 Incubus Mace nerf lives in `SHRINKINGSMASH_EFFECT_DEBUFF`
  (`buffovertime[5].value: -0.25 -> -0.20`), a child node — it still maps back
  to the equippable `SHRINKINGSMASH` and from there to the weapon line.
- Changes whose every attribute path is vfx/audio/controller metadata are kept
  but flagged `balance_relevant: false` (the 2026-04-13 patch stamped gamepad
  metadata on 280 of its 311 weapon-spell changes; only 31 were real).
- Staleness itself is read snapshot against snapshot, not by date:
  `pipeline/sheets/reviewed_evidence.json` keeps the fingerprint of every
  cited evidence id's facts (its `out/spell_index.json` record and
  structured effects; a shapeshifter E's form abilities with it, from
  `out/weapon_lines.json` `form_spells`; an item's `out/item_stats.json`
  record behind a WEAPON_STATS / GEAR_STATS row) from when the rows citing
  it were last read, for weapons, pools and gear alike
  (`evidence_review.py`). After a
  snapshot move, `evidence_lint.py` FAILS on every id whose facts changed
  until its rows are re-read and the new facts accepted. `curated_as_of`
  records when an entry was curated; `curate_helper.py` shows the weapon's
  recent patch changes on its worksheet.
- Commit dates match the forum "Combat Balance Changes" threads one-for-one
  (2026-06-29 ↔ "[29. June 2026] Radiant Wilds Patch 3"), so the date joins to
  the human prose. The forum itself is Cloudflare-blocked to scripts, like the
  wiki — the git history needs no scraping at all.
- **Patch history is metadata, never evidence.** The evidence rule still
  requires every nonzero score to cite an equippable spell through the effect
  map; this file only says when to re-read one.

Do **not** use `git sparse-checkout set items.json spells.json ...` — in cone
mode those paths are treated as directories and the command fails. Either take
the full checkout (as above) or use `sparse-checkout set --no-cone /items.json
/spells.json /localization.json /formatted/items.json`.

## Curation status

- Curated: **137 of 137 combat weapons** — every line complete;
  `release_clean: True`. The other 24 catalog entries are vanity items and
  gathering tools and get no sheets.
- Illustrative placeholders: 0 (all 8 design-doc §2.3 blocks replaced; their
  corrections are in the git history of
  `sheets/illustrative/prototype_v0.yaml`).
- Drafts: 0. All scores are lint-clean and have been through the validation
  rounds recorded in `tests/VALIDATION.md`; the Tier-2 blind gate
  (`tests/tier2_blindtest.py v4`) enforces via exit code.

## The effect layer

```text
py -3 pipeline/effect_catalogue.py <ao-bin-dumps path> --report
   -> out/effect_catalogue.json   51 combat effects reachable from EQUIPMENT
                                  (559 spells indexed: 367 weapon + 194 gear)
pipeline/effect_map.yaml                 effect x direction -> capabilities
pipeline/effect_lookup.py                shared: spell -> candidate capabilities
py -3 pipeline/build_effect_review.py    -> review/effects.html    (local board)
py -3 pipeline/build_magnitude_review.py -> review/magnitude.html  (every score beside its dumps numbers; local board)
py -3 pipeline/build_stat_chart.py       -> review/stat_chart.html + review/stat_chart.json (vs-players numbers; needs the dumps cache; local board)
```

The boards are generated locally into `review/`, which is gitignored; they
are not part of a build. Regenerate them after a score or rule change alters
what they show.

**The catalogue covers GEAR as well as weapons.** It indexed weapon spells
only for most of the project's life, so every gear-sheet claim rested on
prose + overrides and `evidence_lint.py` could not check a single one. Gear
actives *and* passives are indexed the same way; each effect records
`gear_lines`/`gear_line_count` beside its weapon counts, and the gap reports
(unmapped / no-prose / needs-a-call) span both sources — an effect that only
ever appears on armor used to be invisible to all three. The first covered
run turned the lint from silently skipping gear into six grounded errors, one
of them a claim that was **backwards** (Demon Armor's aura buffs allies'
resistances while reducing the wearer's own; it was recorded as the wearer's
`tankiness`). Re-run the catalogue whenever the snapshot moves.

Two layers, deliberately not collapsed:

| layer | what | count | role |
| --- | --- | --- | --- |
| effects | game mechanics (`stun`, `movespeedbonus-`, `remove:buff`) | 51 combat effects reachable from equipment | evidence |
| capabilities | comp-level needs (design doc §2.2) | 31 sheet capabilities (`evidence_lint.CAPABILITIES`), every one but `reflect` scored by at least one template (the `effect_map.yaml` reflect note); `ranged_presence` is derived by the build; `reveal` stays proposed-only | scoring |

**The map is many-to-many and keyed by target direction.** One effect can ground
several capabilities: 1H Mace's Deep Leap resolves to `dash` + `invincibility` +
five self-immunities, which together support `engage`, `disengage`, `tankiness`,
`mobility` and `catch`. The same immunity granted to an *ally* is `peel` instead.
An empty list is a real answer — a self-slow while channelling grounds nothing.

The effect layer yields **candidates**, never assertions. Whether a particular
weapon's 3m dash is really an engage tool is a curation judgement; the lint's
job is only to reject capabilities the spell cannot support at all.

When the lint rejects a claim, **the default answer is to drop or re-cite the
claim, not to reach for `effect_overrides.yaml`.** The override channel is for
demonstrable parser misreads with the reason written down; it is not a way to
keep a score the data contradicts. Two cases set the precedent: `reveal` was
refused outright (every weapon source of `remove:invisibility` is a purge
spell — invisibility is a buff — so a reveal row would double-count purge on
seven lines, and the only two non-purge sources are gear), and five gear
claims were re-cited to what their effects actually support rather than
overridden (`mobility` claims on abilities with no speed component, an
`anti_dive` claim whose only enemy effect was forced movement).

Effects resolve **transitively**, and reference-following matches any attribute
whose value names a real spell — an allowlist of node types missed real links
(`DIVINE_JUMP` chains its enemy knockback through `dash @endeffect`, so
Hallowfall looked like it had no displacement at all).

Two sources, because neither is complete: structured nodes have high precision,
and the old prose regexes survive as a fallback in `effect_lookup.PROSE_FALLBACK`
(they are what caught Battle Howl's purge first). The structured layer
SUPERSEDES a prose flag when the spell has a structured counterpart for the
same mechanic (with an ally-direction guard for the heal flag), and
`effect_overrides.yaml` corrects the artifacts the parser gets wrong — both
layers feed the seeder and the lint identically.

**What the effect layer cannot see**: raw damage
(`burst_st`/`burst_aoe`/`sustained_dps`/`execute`; a plain health change, not
a typed effect). The seeder never proposes those, nor `zone_control`,
`clump_create`, `heal_burst` or `anti_dive` (`seed_sheets.HUMAN_ONLY`); rule 3
cannot block the four damage capabilities, `zone_control`, `interrupt` or
`max_health_cut` (the lint prints the computed set on its first line).

**Form abilities sit behind the E.** A shapeshifter staff's E transforms the
wielder; the form's two abilities and its passive carry their own names and
descriptions in `spells.json` but sit on no equip menu. `parse_dumps.py`
records them per shapeshifter line (`weapon_lines.json` `form_spells`, by
the form's name prefixes: the dumps link a form to its abilities in a file
the snapshot does not carry) and indexes them, the effect catalogue maps
their effects, and the evidence review fingerprints them into the E's
facts, so a numeric change to a form ability stales the rows on the E. A
sheet scores them on the E (the row cites the `SHAPESHIFT_*` spell, an
`add:` entry in `effect_overrides.yaml` quotes the form ability's text);
`curate_helper.py` prints equippable spells only, and
`audit_form_abilities.py` prints every form's ability text with the numbers
resolved beside the rows the sheet cites on the E:

```text
py -3 pipeline/audit_form_abilities.py   -> review/form_abilities.md  (report-only; needs the dumps cache)
```

A reworked ability keeps its id and points at a new description
(`@descriptionlocatag`); the audit reads that tag first, as `parse_dumps.py`
does. The same audit lists the ally-protection class of the anti-dive rule:
`anti_dive` counts an effect landed on the diver (the map's enemy rows) and a
protection placed on other allies: an absorb shield, a damage immunity or a
damage redirection on an ally, and a protective zone or aura (an area that
stays and raises the damage resistances of the allies inside it). Each claim
the map does not already offer is added per spell in `effect_overrides.yaml`.
A resistance buff on one targeted ally stays `buff_allies`.

## Where the numbers come from

`parse_dumps.py` resolves the placeholder tags in spell descriptions (`{0}`,
`$path$`, `$$SPELL.path$`) against the effect tree, so curation reads real
values instead of `$directattributechange.change$`:

> Battle Howl — "silencing all enemies hit for **2.33** and Purging all buffs
> from them."

83% of ~1,640 tags resolve; the rest are geometry details (`radius_start`) that
don't move a capability score. These are **base** values — the in-game number is
item-power scaled, and the wiki quotes tier-specific figures. Base values are
the right unit for curation, which compares spells against each other.

**The wiki is not machine-readable from here.** `wiki.albiononline.com` returns
HTTP 403 to automated requests (Cloudflare), including its `api.php` MediaWiki
endpoint — same bot protection that blocks MurderLedger (design doc §1.3). Its
content is still reachable through web search, and it is a good human reference,
but it cannot be a pipeline input. Design doc §1.5 calls the wiki "consistent
MediaWiki HTML, scrapeable" — that is now falsified for automated access. Since
the dumps are the game's own data and resolve to the same numbers, the wiki is
not needed as a source.

## Scheduled killboard fetches (cache-only)

Two scheduled jobs, two APIs, two caches — neither rebuilds or commits.
The fold is `pipeline/fold_harvest.ps1` (PowerShell, weekly): rosters
from the cache -> the derive chain -> dataset -> pages -> every gate ->
`pipeline/compare_fold.py`, which writes the before/after report to
`notes/findings/<date>-fold-report.md` against the previous fold at
HEAD (`--base` for another revision). Review the report, then commit.
The fold and `refresh_portal.ps1` refuse to start while a harvest runs
(`pipeline/harvest_guard.ps1`: a "CompForge ... harvest" task Running, or a
`harvest_overnight.ps1` / `sample_parties.py --battles` process), since each
harvest pass ends by rewriting `out/party_rosters.json.gz` from the cache and
a fold would lose the artifact its tables were derived from.

- `pipeline/harvest_overnight.ps1` — "CompForge overnight harvest", daily
  at 03:00 AND 15:00 (the job CLAUDE.md names; twice daily because the
  800-battle discovery list reaches back only ~13 h at the 8-player floor,
  ~60 h at 25 — one pass a day saw every ZvZ fight and half the
  8-24-player ones): `sample_parties.py` at the 25- and 8-player floors,
  battles fetched four at a time (`--workers`, each pass ends with an
  event-coverage line and a request-miss tally; sequential baseline 0.987),
  against the OFFICIAL gameinfo API, whose `GroupMembers` carries the
  killer's party at kill time with gear → `out/party_cache.sqlite` (one
  SQLite file, one row per battle, the record zlib-compressed; the
  `party_store.py` module is the only reader and writer, and
  `py -3 pipeline/party_store.py` prints the count by source) and
  `out/party_rosters.json.gz`. This is the kit-doctrine and style × size
  evidence. The committed artifact keeps the populations the build reads,
  every battle-list battle and every Dragon Portal battle
  (`rosters_io.committed`); the same pass writes every record, the
  kill-feed poll's open-world fights included, to
  `out/party_rosters_full.json.gz`, which stays local (gitignored: two
  thirds of the builds, past GitHub's 100 MiB file limit) and which
  `derive_usage.py` alone reads. Rerun order afterwards: audit -> derive_style_bands ->
  derive_portal_rows -> derive_party_styles -> derive_meta_prior -> derive_role_counts ->
  derive_skeletons -> build_dataset -> gates. A FOCUSED NIGHT takes a
  fight-size band (`-MinPlayers 10 -MaxPlayers 14` = the 5v5 / 7v7 band)
  and runs one pass over it; `sample_parties.py --max-players` is a local
  ceiling on albionbb's `totalPlayers`, so the budget goes only to fights
  in the band. The cache keeps every battle and the analysis reads all of
  it, so a focused night adds to the corpus, never narrows it. After the
  passes the run BACKS UP the cache, the one copy of the evidence (the
  kill feed serves no history): `pipeline/backup_cache.py` writes a
  consistent copy (SQLite's online backup, checked, then renamed over the
  last copy) to the folder `-BackupDir` names, else the
  `COMPFORGE_BACKUP_DIR` environment variable (a synced folder or a second
  drive, set once per machine); with neither set, no copy. A backup is
  never a build input; a fresh machine copies it to
  `out/party_cache.sqlite` and re-derives.
- `pipeline/poll_events.ps1` — "CompForge kill-feed poll", every 3 minutes:
  `sample_parties.py --poll-events` reads the newest ~1,000 kill events off
  the official feed (the killer's party and every combat role's equipment
  ride the list itself), groups them by battle and merges them into
  per-battle cache records (`source: events_poll`, deduplicated by EventId
  across polls; the roster is rebuilt from the events, so coverage is
  against the seen set). Cache only. This is the discovery for the Ancient
  Lands portal pools (2-3, 4-5, 5-7): their fights are 4-14 players, which
  the battle list never surfaces, and portals open on 30 / 60 / 180 minute
  locks, so the kills arrive in bursts. A later battle-list harvest of the
  same battle replaces the poll record with the official-roster one.
  CONTENT TAG: every event's `KillArea` (the content classifier the API
  exposes; `Location` and `Category` are null on current traffic) is
  recorded per event, tallied per battle and per party, and kept per
  build; `analyze()` stamps `content` on every battle, party and build
  (`open_world`, the lower-cased KillArea of an instanced content, or
  `unknown` for records written before the tally). The tag exists so a
  derive step can select one content's parties; nothing filters on it.
  CONTENT MARKER: the API labels every Ancient Lands kill OPEN_WORLD, so
  the tag also reads the VICTIM's inventory: the Ancient Bone
  (`QUESTITEM_TOKEN_DRAGONS`, a quest item spent inside) and the two Drake
  shards (measured against the bone: the same item-power profile, half of
  them in a battle that also holds a bone victim, about a fifth more
  portal battles and mostly group fights) mark a kill; a victim carrying
  one died there, and a battle holding one such event is an
  `ancient_lands` battle (`content_marks` beside `kill_areas`, with a
  per-item tally under `content:item`; an instanced KillArea outranks the
  marker). Undercounts, never invents. Every record keeps its slimmed
  events, so a marker added later is a `--retag` away.
  `--retag` rebuilds every kill-feed record from its stored events when
  a marker is added; `--remark` re-fetches the events of battle-list
  records harvested before the marker existed (network, a one-off). A
  battle-list harvest that replaces a kill-feed record carries its marks
  and stored events forward. POPULATION: `rosters_io.load()` defaults to the
  battle-list records only, the population every shipped table was
  fitted on; the poll's records are reached by `source="events_poll"` /
  `"all"` and `content="ancient_lands"`. STORAGE: kill-feed records keep
  slimmed events (tens of MB a day, not hundreds); every cache write is
  atomic; an unreadable file is skipped and reported; a battle-list
  harvest that finds the official record lagging keeps the poll record.
  DRAGON PORTAL STATS: `build_portal_stats.py` reads the `ancient_lands`
  records (`rosters_io.load(source="all", content="ancient_lands")`) and
  writes `out/portal_stats.json`, per matchmaking pool (solo, 2-3, 4-5,
  6-7, 15-20): the weapons winning parties carry (parties, share, distinct
  players, dominant share = the party took no deaths in its battle, K/D,
  median item power), the modal winning build per weapon and slot (one
  player one vote, from three votes), and the comps seen twice or more
  with every weapon known. Pools of six and more also carry SHAPES (the
  party's members per role class, each weapon read through its primary
  seat; a row from two sightings with its dominant share, K/D and the
  weapons fielded per class) and a roster `profile` (the quartiles of each
  class's count over the full parties and the weapons that fill each
  class): an exact comp stops recurring past five members (93 distinct in
  95 full 15-20 parties), the shape and the ranges do. `dashboard/build.py` embeds it in
  `portal.html`. DISPLAY ONLY: nothing scores on it, and the planner does
  not read it. Regenerated by the fold after the cohort families, and
  between folds by `refresh_portal.ps1` (rosters from the cache, the
  stats, the pages, the portal and layout gates; never commits): commit
  `out/portal_stats.json` and the two `portal.html` files alone, never the
  rosters artifact, which the fold commits together with the prior, bands
  and skeletons derived from it. The page's artifact may run ahead of the
  rosters because it sits outside the provenance chain.
  DRAGON PORTAL ROWS: `derive_portal_rows.py` reads the same records and
  writes `templates/ancient_lands.yaml`, the one way the portal harvest
  reaches the engine. The evidence unit is the dominant killer party of
  the pool's size (no deaths, a kill, every weapon known) on the training
  split, floor 40 distinct rosters per pool. The base rows are fitted on
  the 4-5 pool (the template's base size); the 2-3 and 6-7 pools carry
  rows of their own under `pool_rows`, which both engine ports read at a
  size inside the pool, scaled from the pool's `ref_size` (weights stay
  the base rows'). Target is the median, soft cap 1.15 x p90, min the p10
  of the supply dressed in doctrine kits; a capability the median winner
  does not field is no requirement: a demand ramp in the base rows, and in
  a pool's rows an OPTIONAL row where the p90 winner fields it (one
  winning party in ten: target and soft cap read over the parties that
  field it, no minimum; bringing it earns its coverage, not bringing it is
  not a hole) and `none` below that. The fitted 4-5 pool reads the base
  rows and carries its optional rows alone under `pool_rows`. The pools'
  ROLE COUNTS come from the same unit (`derive_role_counts.py` `pools`:
  the median count of healer / frontline / support at the exact size, and
  zero where the p75 winner fields none), so generation keeps the winners'
  shape while the optional rows price what a frontline brings.
  The 15-20 pool carries rows of its own as well; inside it both engine
  ports read them ahead of the style x size rows (a pool's own row
  outranks the cell). A pool under the floor reads the base rows scaled
  and the style x size rows at 10+. The step also writes `pool_fielded`
  (not for the 15-20 pool, whose 40 rosters are too few to gate on):
  per pool at the floor, the weapons its dominant winners field (at least
  5 distinct rosters across 3 guild-sets, the honesty gate of the pair
  prior, and 5% of the rosters of the pool's most fielded weapon, the
  prior's signal floor). Both engine ports read it as a suggestion gate
  at a size inside the pool; scoring never reads it. `build_dataset`
  validates the pool rows and the fielded lists (fail closed); `tests/tier2_blindtest.py v4h --harvest-source all
  --harvest-content ancient_lands --dominant` is the holdout read of the
  same unit, and `fit_choice_weights.py` takes the same flags. Run by the
  fold after derive_style_bands; `--rosters` names a git-shown copy of the
  artifact when the poll has rewritten the working file.
- `pipeline/derive_usage.py` — the observed-evidence artifact
  (`out/weapon_usage_v2.json`: the prevalence strip, the cohorts, and
  through `build_cohort_families.py` the observed families), derived
  offline from the full artifact, `party_rosters_full.json.gz` (every
  population, local; it fails closed without it). The party harvest is the one
  killboard sampler; the two albionbb samplers it replaced were weaker
  views of the same fights. The frame: every harvested battle of 6+
  players that started in the 28 days before the NEWEST battle in the
  artifact (anchored on the data, never on the clock, so a rebuild is
  byte-identical). 1v1/2v2 content (corrupted dungeons, mist duels) is a
  battle of 2-4 and never enters. Prevalence is by FIGHT size over
  combatants with a build (killers, victims, kill participants). A cohort
  is one KILLER PARTY as the kill event lists it, bucketed by PARTY size (a
  party of N keys to the bucket a fight of 2N falls in), at most 1,000 per
  bucket spread evenly over the window. WEEKLY CADENCE (or before a
  validation round): `fold_harvest.ps1` runs it after `build_dataset`;
  the fold has no network step. Review the numbers, rebuild dependents,
  run the gate list, commit — analysis is always a deliberate, reviewed
  step, never automated. `Get-ScheduledTask` should list the two CompForge
  jobs (the overnight harvest and the kill-feed poll). Mind patch
  boundaries when reading the window: it can span a balance patch; slice
  by `patch_history` dates before comparing metas.
- `out/roster_mixes.json` is FROZEN: the near-complete wiped-side rosters
  behind the curated `need_profiles` in `roles.yaml`. Its sampler is
  retired (the artifact has no code reader, and the party harvest records
  killer parties, never a side that scored no kill); the record stays as
  the evidence the profiles cite.

## Known gaps / TODO

- ~~Gear items have no sheets yet~~ — closed in two steps: the full-build
  member model shipped a curated starter set, and the combat expansion
  completed the combat catalog (`sheets/gear/<slot>.yaml`, one file per
  slot; 135 pieces in `dataset["gear"]`, scored by `build_extra` in both
  ports). The albionbb
  kill events carry `Equipment.MainHand` + `Mount` only, so worn kits are
  NOT harvestable from that endpoint — they come from the official API's
  `GroupMembers` via `sample_parties.py` (`out/party_rosters.json.gz`), which
  is what the kit doctrine reads today, beside the published/reference
  builds.
- ~~Usage sample is small (24 battles)~~ — superseded by `derive_usage.py`
  (every harvested group fight of the last 28 days, size-bucketed, in
  `out/weapon_usage_v2.json`). Display-only in the dashboard until
  validation admits it to scoring.
- Structural capabilities (engage, peel, clump, tankiness…) are human-only by
  design; drafts contain effect capabilities only.
- Six content templates exist (`blackzone_roam` 20, `territory_defense` 20,
  `castle` 25, `faction_war` 15, `castle_outpost` 7, `roads` 7) plus the playstyle
  overlays in `templates/styles.yaml` and the GENERATED style × size rows
  in `templates/style_bands.yaml`. The content rows were comp-fitted, then
  re-fitted to person units (standing rule 9) and to the MEDIAN of their
  comps (standing rule 17; `refit_content_targets.py`, all rows together:
  `min` = least comp, `target` = median, `soft_cap` raised to 1.15 x most
  where a comp exceeded it, never lowered; each template's `fit:` block
  states comps and stat); territory_defense (2 comps) and roads (1) stay
  on the old minimum and say so; castle and faction_war rest on no comps.
  Every target — band row or content row — is the TYPICAL winner, not the
  least any winner fielded; the band rows carry `min` (p10) beside it.
  Sizes off the validated list are linear extrapolation and labelled as
  such in the UI.
- ~~Default-kit harvester not built~~ — the MetaBattle adapter (46 pages,
  all group-PvP categories) + the caller comps now feed the mined
  kit-doctrine pools (`roles_report` `kit_doctrine`, per seat AND per
  weapon). Albion Free Market (4,478 builds, game-native spell IDs,
  SSR-scrapeable — ask their Discord first) remains the untapped
  second source; two-source agreement = high-confidence kit (§2.4).

### Resolved

- ~~Taxonomy gap: "remove enemy ground areas"~~ — resolved as `anti_zone`
  (design doc §2.2 amendment); scored on the Exalted Staff, still the sole
  supplier. Its template weight remains PROVISIONAL.
- ~~`damage_debuff` proposed but unpromotable~~ — promoted into §2.2
  after six poster-child weapons; template weight low/flat/
  PROVISIONAL like anti_zone's. Small carriers (Weakening, Frost Beam,
  Intimidating Presence) deliberately held at 0 pending a validated weighting.

- ~~Shapeshifter weapons not ingested~~ — fixed. They live under
  `transformationweapon` in items.json and are now merged before `by_name` is
  built (their `@reference` chains point at siblings in that category). Added 8
  lines, changed 0 existing ones. They matter: as a family they were the
  second-most-used weapon group in the usage sample and were entirely invisible.
- ~~`parse_dumps.py` crashed on Windows~~ — `open()` defaulted to cp1252; all
  file I/O now passes `encoding="utf-8"`.
- ~~Knockback flag missed common phrasings~~ — the pattern required
  `knock(s|ed)` immediately followed by "back", so it silently missed
  "knock**ing** back" and "Knocks **you** back". A spell literally named
  *Knockback Shot* had no knockback flag. Since evidence_lint rule 3 requires
  the flag, this **blocked** curators from scoring real displacement. Fixed and
  re-measured: 16 spells gained the flag, 0 lost one. Frost Shot now correctly
  flags knockback with direction `[enemy, self]`, which makes the lint raise its
  "verify WHO gets knocked back" warning — the exact check that caught the
  original Longbow error, now firing automatically.
- ~~Holy cleanse uncertainty~~ — settled, and it is **per weapon, not
  per line**. The shared holy Q/W pool contains no cleanse, so no holy staff
  gets cleanse as a build choice. But two holy staves have it built into their
  **E**, where it is guaranteed rather than optional:

  | Weapon | Cleanse | Source |
  | --- | --- | --- |
  | Hallowfall `MAIN_HOLYSTAFF_AVALON` | no | — |
  | Redemption `2H_HOLYSTAFF_UNDEAD` | no | — |
  | Great Holy `2H_HOLYSTAFF` | no | — |
  | Exalted `2H_HOLYSTAFF_CRYSTAL` | no | E is `anti_zone`, not cleanse |
  | **Lifetouch `MAIN_HOLYSTAFF_MORGANA`** | **yes** | E: `HOLYTOUCH` |
  | **Fallen `2H_HOLYSTAFF_HELL`** | **yes** | E: `HOLY_ULTIMATE` (Salvation) |

  Cleanse is also a W-slot option on the whole nature line (`CLEANSEHEAL`) and
  the whole arcane line (`CLEANSESPEED2` — including Witchwork), which makes it
  conditional there. `cleanse 0` on the curated holy sheets is correct, and gear
  is **not** a Tier-2 blocker.

## Style x size rows

`derive_style_bands.py` reads `out/style_roster_evidence.json` (the
`audit_style_rosters.py` board) and writes `templates/style_bands.yaml`:
per declared playstyle x size band, `min` = p10, target = the median (p50)
and soft cap = 1.15 x p90 of the dressed capability supply winning killer
parties field (person units; standing rule 17). Cells with fewer than 40
distinct rosters borrow their nearest filled cell (`borrowed_from`); a zero
p10 writes a soft-cap-only row (the content target stands), and so does a
capability 5% or more of the cell's winners field none of (`zero_share`:
p10 on the edge of the zero mass thrashes between folds — brawl|20 silence
read 7.5 / 1.0 / 4.6 across three folds); nothing is excluded (the movement
four were admitted once measured — see tests/VALIDATION.md). The audit reads
`out/party_cache.sqlite` directly, not the committed rosters artifact, so its
board follows the cache; the fold script re-derives the rosters first so
both agree. `build_dataset` validates the file (fail closed) and ships it as
`style_bands`; the engine reads it after the content row for a declared
style at 10+. Explicit step: `sample_parties` -> `audit_style_rosters` ->
`derive_style_bands` -> `derive_portal_rows` -> `derive_party_styles` -> `derive_meta_prior` ->
`derive_role_counts` -> `derive_skeletons` -> `build_dataset` -> gates.

## The generated seat skeleton, plan minima and copy allowances

Standing rule 18 extended to seats and plan tools; spec
`notes/specs/2026-09-15-skeleton-first-generation-design.md`.
`derive_skeletons.py` reads the COMMITTED `out/party_rosters.json.gz` and
`out/party_styles.json` on the TRAINING split (`battle % 5 != 0`, the meta
prior's rule), one DISTINCT fully-known roster (guild set + weapon multiset)
one vote, and writes `out/skeletons.json`:

- **seats**: per exact size at 10+, pooled and per declared style, the
  p10 / p50 / p90 count of every PRIMARY SEAT (`Engine.seat_of`, the
  first uniformed menu role — the role-class read), a cell pooling a
  ±1 then ±2 size window until 40 rosters; `typical` = round(p50) where
  p50 >= 1, an EMPTY row where the cell exists and the style fields none
  (no demand) — only an ABSENT row falls back to the pooled cell;
- **plan**: the same shape for plan tools — today `standoff`, the count
  of `style_fit.standoff_e` carriers, the fact the identity read defines
  a kiting plan by; the engine reads it as a generation MINIMUM;
- **minima**: per style x band (10-14 / 15-19 / 20+) and pooled, the
  p10 / p50 / p90 count of every generated band minimum's carriers per
  roster — today `ranged_aoe_core`, a weapon some combo of which meets the
  predicate (`Engine._pred_possible`, the forge's own test) — and the
  minimum the forge reads, round(p50) where p50 >= 1 (the standoff rule),
  an EMPTY row where the cell exists and most winners field none (no
  minimum); a style's band under 40 rosters borrows its nearest filled
  cell by the style rows' rule (same style, nearest band; else the parent
  style), stated as `borrowed_from` with its own count, and a style with
  none filled reads the pooled row. The engine lays the declared style's
  row (else pooled; `balanced` reads pooled) on the band at 10+, replacing
  the key; below 10 there is none;
- **copies**: per style x band (10-14 / 15-19 / 20+) and pooled, for every
  weapon fielded by >= 40 rosters: copies p50 / p90, the shares with 2+
  and 3+, `free` = round(p50), `max` = ceil(p90) — the allowance the
  forge's redundancy term and copy cap read (the declared style's row
  laid over the pooled row at `set_content`);
- **distinct**: distinct weapons per roster per band, a report line.

`build_dataset` hash-gates it to the two artifacts, refuses an
all-battles derivation, a hand `composition.duplication.per_weapon` and a
hand `ranged_aoe_core` minimum in any `constraint_bands` or
`constraint_overrides` row, validates every seat against `roles.yaml`,
every weapon against the catalogue and every minima row against the bands
(the pooled row must carry every band), and ships `composition.skeleton`
(seats, plan, minima) + `duplication.per_weapon_cells`.
Gate: `tests/test_skeletons.py`.

```text
py -3 pipeline/derive_skeletons.py
```

## The generated meta prior

One harvest-generated prior replaces both hand lists: the seven-weapon
hand-set `meta_prior` in `templates/scoring.yaml` and the viability `core`
list in `templates/composition.yaml` are retired (H18 / H18b).
`derive_meta_prior.py` reads the COMMITTED `out/party_rosters.json.gz` and
writes `out/meta_prior.json`: per engine size bucket (party 2-5 small,
6-15 mid, 16+ large — `Engine.size_bucket`'s axis, mirrored by
`bucket_of()` and pinned equal in golden T46), a weapon's share of the
bucket's DISTINCT PLAYERS (one player, one vote; a victim carries no
party and casts none), shrunk `n / (n + 8)`, normalized so the bucket's
top weapon is 1.0, rows under 0.05 omitted (no signal, never a penalty).
`build_dataset` attaches it to `scoring.meta_prior`, refuses a file
derived from a different artifact than the one on disk, and refuses a
hand-set map anywhere in the config (fail closed, loudly). The engine
detects the bucketed shape by its keys and reads it through
`size_bucket()` at roster size; the recommendation weight `delta` (0.15)
is the only dial. The same script also writes `meta_pairs` (one killer
PARTY, one vote per distinct pair it fields; a row only across >= 3
guild-sets and >= 5 parties; `s = clamp(log2 lift, 0, 3) / 3 x n / (n +
8)`, lift <= 1 reads 0) and BOTH tables learn from `battle % 5 != 0` only
— the `% 5 == 0` fifth is `tier2_blindtest v4h`'s holdout; `--all-battles`
writes an audit copy `build_dataset` refuses. The engine blends per member
under `weights.meta_pair` (0.5): solo share and best observed partner on
the roster (standing rule 7). Explicit step, never part of a normal build:

```text
py -3 pipeline/derive_meta_prior.py
```

## The typical role count

Standing rule 18 (motivating case: castle_outpost clap at 7 forged two
healers and left damage short): a body beyond the TYPICAL count for its
role is generated only when a minimum only that role can meet still
demands it. The composition bands carry min / max per role;
`derive_role_counts.py` supplies the middle line the supply rows carry —
standing rule 17 applied to bodies — in three tables in
`out/role_counts.json` (hash-gated to `party_rosters.json` and
`party_styles.json`), resolved by the engine's `_role_typical` for its
content, style and size:

- **below 10**: `comps[content][size]` — the median role counts of the
  published comps the content's targets were fitted from (the dressed
  audit's parties), where the content has >= 3 comps at that size (the
  `stat: median` bar); healer / frontline / support. castle_outpost 7:
  healer 1, frontline 2 (2/2/3), support p50 0 -> no row. Else the
  pooled harvest row, HEALER ONLY: killer parties below 10 are
  open-world squads — style-labelled or not, their frontline p50 at 7 is
  1 (p90 2) where every published 7-man comp fields 2-3 — so tanks and
  supports there are never derived from the harvest. Their healer count
  agrees (one in 67% of 658 at 7).
- **10+**: `styles[style][size]` — the DECLARED identity style's cell,
  per exact size, from the labelled parties; a cell pools a +-1 then +-2
  size window until it holds 40 rosters (`window` stated) and a style
  that never reaches it at that size has no cell (brawl_clap). Else
  `pooled[size]` — every winner at the size, any style; `balanced` never
  reads a cell (the kit rule). healer / frontline / support.
- dps is never gated: the residual role, and gating all four could make
  a size infeasible (p50s do not sum to the size). A zero p50 writes
  nothing; sizes the harvest does not reach (21+) carry no harvest row.

`build_dataset` refuses a missing or stale file or a row that is not a
positive integer count of a gated role, and ships the tables as
`composition.role_typical`. Both ports lay `typical` onto the band, and
the forge's prune, per-combo evaluation, 1-opt and 2-opt read one
predicate (`_typ_ok`): WITHIN the typical slots a pick is refused when
it would leave more unmet exclusive need (`primary_heal` -> healers; a
seat -> its class) than slots remain — the one healer slot is never
spent on a hybrid that forces a full healer on top; OVER the typical
count a pick passes only while the role's own minimum is unmet or an
unmet exclusive predicate is one this pick carries on the combo it
equips. The per-five healer minimum stays a minimum with no maximum;
where it exceeds the typical count the minimum wins. Manual parties
score anything. Gates: forge F31a-k, golden T48. Explicit step, never
part of a normal build:

```text
py -3 pipeline/derive_role_counts.py
```

`parse_dumps` adapter 5 adds `caster_moves` to every indexed spell — a
`dash` node anywhere in the spell tree, the game's leap / charge
primitive. `derive_style_fit` reads it as the delivery rule "payload
reach, not travel": a caster-moving E's cast range counts toward flex
delivery only for a flex bomb (group payload at the job bar); a standoff
tool must move nothing. `derive_ranged_presence` reads it as the
gap-closer rule: a caster-moving spell's area lands where the wielder
lands, so it grounds no `ranged_presence`; `ranged_overrides.yaml` holds
the cited exceptions (H6c).

## Party styles and style cells

`derive_party_styles.py` reads the COMMITTED `out/party_rosters.json.gz`,
labels every killer party of 10+ with `Engine.comp_identity` on its
weapons alone (naked matched the audit's dressed read 19/20 in validation
round 4; the committed artifact carries no member kits), and writes
`out/party_styles.json` with the SHA-256 of the artifact it read.
`build_dataset` refuses a party-styles file derived from a different
artifact (exit 2); a missing file means no style cells that build.
`pipeline/party_link.py` links a build to its party: exactly through the
analyzer's `party` index (stamped beside each party's `index`), else by
(battle, weapon) only when exactly one 10+ party in the battle fields that
weapon — never a guess. `derive_kit_doctrine(style=...)` then mines one kit
cell per style under each seat's `kit_styles` from the linked builds, with
the band's floors plus a 5-voter cell floor applied per weapon, per slot
(the slot's modal item) and to the chain's chest step; thin cells and slots
are absent, never filled. The engine's one doctrine reader `_seat_kit` lays
a DECLARED style's cell over the band; `balanced` never reads a cell. Spec:
`notes/specs/2026-09-08-coherent-style-kits-design.md`.

**Seat pooling for thin slots** (spec section 3). Measured first: three
players' helmets predict a weapon's true modal 58% of the time, the seat's
helmet among builds wearing the SAME chest 80% (boots 48% -> 72%, cape 68%
-> 81%); for potion and food the plain seat pool is right 95% / 82%. The
miner ships `kit_pool` (plain) and `kit_by_chest` (chest-conditioned) per
seat and band, player-counted, items with 5+ players, top 3 per slot, the
five poolable slots only. The kit reader in both ports treats a weapon
slot whose own modal carries under 5 votes as THIN and fronts the pool item
(same-chest for helmet / boots / cape, plain for potion / food), marked
`pooled` / `pooled_n`; chest and off-hand are never pooled; a 5+ vote
weapon modal is never overridden. The audits (R24, R24b, R28) skip a slot
whose killboard modal rests on fewer than 5 players — that slot is pooled,
not matched.

## One player, one vote

`sample_parties.py` stamps every harvested build with a hashed `player`
key (sha1 prefix of the name; the name stays in the cache). In
`derive_kit_doctrine` a player's k builds on a weapon weigh 1/k each, so
counts are votes; the noise floors (seat 3, weapon 2, a chain step 2)
count DISTINCT voters and the uniform extension needs 35 voters. Rows
ship rounded votes with `players` beside them and cite
`killboard:<votes>x/<players>p`; the compact `kit_weapon` tier rows are
`[id, count, players]` (`players` absent on a reference-only row) so the
engine's thin-slot read counts people like every other floor. Re-derive
with `--pages 0` after changing the build record.

## Doctrine bands

`derive_kit_doctrine(band=...)` runs twice: `group` (killer parties of
10+, every curated content; the seat's top-level `kit*` keys, grading
overrides applied) and `gang` (parties of 4-9 plus the small-scale
curated contents; `kit_bands.gang`, no overrides). `DOCTRINE_BANDS` in
build_dataset.py is the table. The engine's `_seat_kit` picks the band by
party size (gang at <= 9). `roles_report.json` carries the gang detail
under `kit_doctrine_gang`.

## Per-item chest lean

`audit_style_rosters.py` also mines `out/chest_lean.json`: for every dps
chest, distinct wearers in WEAPONS-ONLY labelled clean cores (melee share
>= 0.65 brawl, <= 0.35 ranged); >= 20 wearers and >= 75% on one side
give the item a lean. `build_dataset` validates and ships it as
`chest_lean`; `comp_identity`'s kit tie-break reads the item lean first
and the class rule (leather -> brawl, cloth -> ranged) where an item has
none. Descriptive only. Because the audit writes it, the post-harvest
order is audit -> derive_style_bands -> derive_portal_rows ->
derive_party_styles -> derive_meta_prior -> derive_role_counts -> derive_skeletons ->
build_dataset -> gates.
