# Composition Engine — Data Pipeline

This directory is the **engine domain's data layer**: it turns the pinned
game-data snapshot plus human curation into `out/dataset-latest.json`, the
single file both engine ports consume. It never renders UI (the frontend
bundler is `dashboard/build.py`) and never scores (that's `engine/`).

Windows note: use `py -3`, not `python`/`python3` — those resolve to the
Microsoft Store stub. Requires `pyyaml` (`py -3 -m pip install pyyaml`).

```text
data/source_pins.yaml     the ONE pinned ao-bin-dumps commit (chapter 2, §A)
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
out/weapon_usage_v2.json  FIGHT-SIZE equipment prevalence (albionbb; display only)
   │  py -3 pipeline/build_interactions.py   (interactions.yaml -> validated)
   ▼
out/interactions.json     spell-keyed PvP interaction records: duplicate
                          semantics, reflect/cleanse/purge per component, CC
                          classes, confidence provenance. Scoring reads ONLY
                          verified nonstacking_caps; unknown never scores.
   │  py -3 pipeline/seed_sheets.py 40
   ▼
sheets/draft/*.yaml       auto-seeded, lint-clean drafts (effect caps only)
   │  HUMAN CURATION — read the evidence first:
   │      py -3 pipeline/curate_helper.py --top 5
   │      py -3 pipeline/curate_helper.py 2H_POLEHAMMER
   │  adjust scores, add structural caps (engage/peel/clump/tankiness/...),
   │  then move the sheet to sheets/ and delete its draft
   ▼
sheets/*.yaml             curated sheets            (authoritative)
sheets/illustrative/      design-doc §2.3 placeholders — NOT a release
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

Rules enforced by `evidence_lint.py` (all born from real curation errors):

1. Every nonzero score cites an evidence spell (or `WEAPON_STATS`).
2. The spell must be equippable on that weapon — gear capabilities belong on
   gear sheets.
3. The spell must be able to GROUND the claimed capability, resolved through the
   structured effect map. Direction is built in, so an enemy-directed capability
   cannot cite a self-targeted effect.
4. Capabilities the effect layer cannot express get checks 1–2 only. That
   boundary is computed, not hardcoded: a capability is checked iff the map can
   produce it at all.

Rule 3 used to match description keywords, which saw a fraction of the game —
100 weapon lines apply a movespeed debuff and the `slow` regex matched almost
none of them.

## The evidence layer (chapter 2)

Build provenance lives in `data/` (see `data/README.md`): caller comps
(`published_comps/`), MetaBattle imports (`published_builds/metabattle.yaml`,
adapter: `py -3 pipeline/adapters/metabattle.py fetch|parse` — fetch is
explicit and never part of a normal build; v2 since 2026-08-26 captures
every group-PvP category — ZvZ, Hellgate 5v5/10v10, Crystal League/Arena,
Ganking — with `content` derived from each page's own mode category),
manual Armory imports (`armory_imports/`).
`py -3 pipeline/build_builds.py` validates + normalizes everything into
`out/builds_index.json` (§F selection order, canonical flags) and
`out/builds_validation.json` (problems, quarantines, promotion decisions).
`dashboard/build.py` inlines the index; nothing in it feeds scoring.

`gear_join.py` (2026-08-27) is the shared read-side of that evidence for
the dressed-validation layer: it reconstructs per-member ACTUAL kits from
`out/builds_index.json` (join key `comp_id:party_name:slot_index` over the
FULL slot list, battlemounts included; conservative id normalization
mirroring `build_dataset._normalize_gear_id` — unresolved pieces are
counted, never guessed) plus `doctrine_gears` (kit_variants v0). Consumers:
`tests/tier2_blindtest.py` (V3-D / V4 gear classes) and the dressed audits.

## Dressed audits (2026-08-27, report-only — never part of a build)

```text
py -3 pipeline/audit_validation_asymmetry.py  # legacy vs V3-W vs dressed top-3 diffs -> out/validation_asymmetry_probe.json
py -3 pipeline/audit_dressed_templates.py     # per-comp capability supply weapon/combo/dressed/doctrine vs targets, soft caps, floors -> out/dressed_template_audit.json
py -3 pipeline/audit_frontline_floor.py       # adversarial no-tank parties vs the tankiness hard floor -> out/frontline_floor_audit.json
py -3 pipeline/audit_gear_synergy.py          # gear-sourced synergy sides: measured + labeled hypotheticals -> out/gear_synergy_audit.json
```

None of these writes anything a build reads. Findings and the open owner
rulings live in `notes/findings/2026-08-27-*.md`; the tuning discipline
(train / validation / holdout) is a standing rule in `tests/VALIDATION.md`.
(The `calibration/` scaffold and `calibrate_scoring.py` were retired
2026-09-10: four train cases, empty validation and holdout, nothing in
the build or CI read them.)

## Moving to a new game patch

Update `data/source_pins.yaml` to the new ao-bin-dumps commit
(`https://api.github.com/repos/ao-data/ao-bin-dumps/commits/master`), then:

```text
py -3 pipeline/fetch_snapshot.py
py -3 pipeline/parse_dumps.py
py -3 pipeline/fetch_item_stats.py
py -3 pipeline/fetch_gear_lines.py
py -3 pipeline/fetch_icons.py       # only when the patch adds weapons/items (out/icon_data.json feeds the pages)
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
quote dumps text or spell behavior: `ranged_overrides.yaml` (gap-closer
denies), `heal_overrides.yaml` (heal-scale sub-effect corrections — Divine
Jump, Celestial Sphere), `style_overrides.yaml` (owner style rulings), and
the `CURSEDOT` non-stacking record in `interactions.yaml` (the "stacks up
to 4 times" wording it cites).

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
- Sheets declare `curated_as_of: YYYY-MM-DD`. `evidence_lint.py` WARNS (never
  blocks) when a cited evidence spell changed in a later patch;
  `curate_helper.py` shows the weapon's recent patch changes on its worksheet.
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

## Status (2026-08-12, full-coverage pass)

- Curated: **137 of 137 combat weapons** — every line complete;
  `release_clean: True`. The other 24 catalog entries are vanity items and
  gathering tools and get no sheets.
- Illustrative placeholders: 0 (all 8 replaced; `sheets/illustrative/` is a
  tombstone record of the §2.3 prototype numbers and their corrections).
- Drafts: 0. All scores are lint-clean and have been through the expert
  rounds recorded in `tests/VALIDATION.md`; the Tier-2 blind gate
  (`tests/tier2_blindtest.py v4`) now enforces via exit code.

## The effect layer

```text
py -3 pipeline/effect_catalogue.py <ao-bin-dumps path> --report
   -> out/effect_catalogue.json   51 combat effects reachable from EQUIPMENT
                                  (559 spells indexed: 367 weapon + 194 gear)
pipeline/effect_map.yaml                 effect x direction -> capabilities
pipeline/effect_lookup.py                shared: spell -> candidate capabilities
py -3 pipeline/build_effect_review.py    -> review/effects.html
py -3 pipeline/build_magnitude_review.py -> review/magnitude.html   (every score beside its dumps numbers)
py -3 pipeline/build_stat_chart.py       -> review/stat_chart.html + out/stat_chart.json (needs the dumps cache)
```

The boards are generated artifacts, not part of a build; regenerate them
after a ruling changes what they show.

**The catalogue covers GEAR as well as weapons** (2026-08-27). It indexed
weapon spells only for most of the project's life, so every gear-sheet claim
rested on prose + overrides and `evidence_lint.py` could not check a single
one. Gear actives *and* passives are now indexed the same way; each effect
records `gear_lines`/`gear_line_count` beside its weapon counts, and the gap
reports (unmapped / no-prose / needs-a-call) span both sources — an effect
that only ever appears on armor used to be invisible to all three. The first
covered run turned the lint from silently skipping gear into six grounded
errors, one of them a claim that was **backwards** (Demon Armor's aura buffs
allies' resistances while reducing the wearer's own; it was recorded as the
wearer's `tankiness`). Re-run the catalogue whenever the snapshot moves.

Two layers, deliberately not collapsed:

| layer | what | count | role |
| --- | --- | --- | --- |
| effects | game mechanics (`stun`, `movespeedbonus-`, `remove:buff`) | 51 combat effects reachable from equipment | evidence |
| capabilities | comp-level needs (design doc §2.2) | 31 curated, all scored by at least one template (`reveal` stays proposed-only) | scoring |

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
keep a score the data contradicts. Two 2026-08-27 cases set the precedent:
`reveal` was refused outright (every weapon source of `remove:invisibility` is
a purge spell — invisibility is a buff — so a reveal row would double-count
purge on seven lines, and the only two non-purge sources are gear), and five
gear claims were re-cited to what their effects actually support rather than
overridden (`mobility` claims on abilities with no speed component, an
`anti_dive` claim whose only enemy effect was forced movement).

Effects resolve **transitively**, and reference-following matches any attribute
whose value names a real spell — an allowlist of node types missed real links
(`DIVINE_JUMP` chains its enemy knockback through `dash @endeffect`, so
Hallowfall looked like it had no displacement at all).

Two sources, because neither is complete: structured nodes have high precision,
and the old prose regexes survive as a fallback in `effect_lookup.PROSE_FALLBACK`
(they are what caught Battle Howl's purge first). Since 2026-08-12 the
structured layer properly SUPERSEDES a prose flag when the spell has a
structured counterpart for the same mechanic (with an ally-direction guard for
the heal flag), and `effect_overrides.yaml` corrects the artifacts the parser
gets wrong — both layers feed the seeder and the lint identically.

**What the effect layer cannot see**, and therefore never seeds or blocks: raw
damage (`burst_st`/`burst_aoe`/`sustained_dps`/`execute` — damage is a plain
health change, not a typed effect), plus `zone_control`, `clump_create`,
`heal_burst`, `anti_dive`, `energy_drain`. Those stay entirely human.

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

- `pipeline/harvest_overnight.ps1` — "CompForge overnight harvest", daily
  at 03:00 AND 15:00 (the job CLAUDE.md names; twice since 2026-09-09
  because the 800-battle discovery list reaches back only ~13 h at the
  8-player floor, ~60 h at 25 — one pass a day saw every ZvZ fight and
  half the 8-24-player ones): `sample_parties.py` at the 25- and
  8-player floors, battles fetched four at a time (`--workers`, each pass
  ends with an event-coverage line and a request-miss tally; sequential
  baseline 0.987), against the OFFICIAL gameinfo API, whose `GroupMembers`
  carries the killer's party at kill time with gear → `out/party_cache/`
  and `out/party_rosters.json.gz`. This is the kit-doctrine and style × size
  evidence. Rerun order afterwards: audit -> derive_style_bands ->
  derive_party_styles -> derive_meta_prior -> build_dataset -> gates. A FOCUSED NIGHT takes a fight-size band
  (`-MinPlayers 10 -MaxPlayers 14` = the 5v5 / 7v7 band, owner 2026-09-08)
  and runs one pass over it; `sample_parties.py --max-players` is a local
  ceiling on albionbb's `totalPlayers`, so the budget goes only to fights
  in the band. The cache keeps every battle and the analysis reads all of
  it, so a focused night adds to the corpus, never narrows it.
- `pipeline/daily_fetch.ps1` — "AlbionCompForge Daily Fetch", daily 09:30:
  grows the albionbb battle caches with fresh GROUP fights
  (`sample_battles.py --min-players 10 --battles 120` — `--no-topup` skips
  the large-bucket top-up) and then restores `weapon_usage_v2.json` to its
  pre-run bytes. That artifact (prevalence, cohorts, families) is what this
  channel feeds. The `sample_rosters.py` sweep was dropped from the job
  2026-09-07: `roster_mixes.json` has no code reader (the need profiles it
  informed are owner-ruled constants); run it by hand if the evidence is
  ever wanted again. 1v1/2v2 content
(corrupted dungeons, mist duels) can never enter: the battles endpoint is
only queried with a total-player floor (10 / 40), and analysis buckets by
actual fight size besides. Log: `pipeline/out/fetch_logs/daily_fetch.log`
(gitignored). WEEKLY CADENCE (or before a blind round): re-analyze
offline (`sample_battles.py` re-reads `battles_cache/` without a flag;
`sample_rosters.py --pages 0` and `sample_parties.py --pages 0` for the
other two), review the numbers, rebuild
dependents, run the gate list, commit — analysis is always a deliberate,
reviewed step, never automated. Mind patch boundaries when reading
accumulated windows: the cache spans balance patches; slice by
`patch_history` dates before comparing metas.

## Known gaps / TODO

- ~~Gear items have no sheets yet~~ — closed in two steps: the full-build
  member model shipped the curated starter set (2026-08-20,
  `sheets/gear/core.yaml`), and the combat expansion completed the
  combat catalog (2026-08-27, `sheets/gear/combat_expansion.yaml`; 129
  pieces total in `dataset["gear"]`, scored by `build_extra` in both
  ports). The albionbb kill events carry `Equipment.MainHand` + `Mount`
  only, so worn kits are NOT harvestable from that endpoint — they come
  from the official API's `GroupMembers` via `sample_parties.py`
  (`out/party_rosters.json.gz`, 2026-09-01 onward), which is what the kit
  doctrine reads today, beside the published/reference builds.
- ~~Usage sample is small (24 battles)~~ — superseded 2026-08-13 by
  `sample_battles.py` (~200 battles from the albionbb API, size-bucketed,
  per-battle cache, V7 coverage stat in `out/weapon_usage_v2.json`).
  Display-only in the dashboard until validation admits it to scoring.
  Joined 2026-08-26 by `sample_rosters.py` (same endpoint, also explicit):
  kill-dense battles mined for NEAR-COMPLETE fight rosters (wiped sides
  attribute the whole roster) → `out/roster_mixes.json`, the evidence
  behind the owner-ruled `need_profiles`; `--pages 0` re-analyzes the
  cache offline.
- Structural capabilities (engage, peel, clump, tankiness…) are human-only by
  design; drafts contain effect capabilities only.
- Six content templates exist (`blackzone_roam` 20, `territory_defense` 20,
  `castle` 25, `faction_war` 15, `castle_outpost` 7, `roads` 7) plus the playstyle
  overlays in `templates/styles.yaml` and the GENERATED style × size rows
  in `templates/style_bands.yaml`. The content rows were comp-fitted
  2026-08-21, re-fitted to person units 2026-08-29 and to the MEDIAN of
  their comps 2026-09-10 (`refit_content_targets.py`, all rows together:
  `min` = least comp, `target` = median, `soft_cap` raised to 1.15 x most
  where a comp exceeded it, never lowered; each template's `fit:` block
  states comps and stat); territory_defense (2 comps) and roads (1) stay
  on the old minimum and say so; castle and faction_war rest on no comps.
  Since 2026-09-10 every target — band row or content row — is the TYPICAL
  winner, not the least any winner fielded (owner: "the data should come
  from the harvest median"); the band rows carry `min` (p10) beside it.
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
  (2026-08-12) after six poster-child weapons; template weight low/flat/
  PROVISIONAL like anti_zone's. Small carriers (Weakening, Frost Beam,
  Intimidating Presence) deliberately held at 0 pending expert weighting.

- ~~Shapeshifter weapons not ingested~~ — fixed 2026-08-12. They live under
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
- ~~Holy cleanse uncertainty~~ — settled 2026-08-12, and it is **per weapon, not
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

## Style x size rows (2026-09-04)

`derive_style_bands.py` reads `out/style_roster_evidence.json` (the
`audit_style_rosters.py` board) and writes `templates/style_bands.yaml`:
per declared playstyle x size band, target = 0.9 x p10 and soft cap =
1.15 x p90 of the dressed capability supply winning killer parties field
(person units). Cells with fewer than 40 distinct rosters borrow their
nearest filled cell (`borrowed_from`); a zero p10 writes a soft-cap-only
row (the content target stands), and so does a capability 5% or more of
the cell's winners field none of (`zero_share`, owner 2026-09-09: p10 on
the edge of the zero mass thrashes between folds — brawl|20 silence read
7.5 / 1.0 / 4.6); nothing is excluded (the movement four
were held back for an evening and admitted once measured — see
tests/VALIDATION.md). The audit reads `out/party_cache/` directly, not
the committed rosters artifact, so its board follows the cache; the fold
script re-derives the rosters first so both agree. `build_dataset`
validates the file (fail closed) and ships it as `style_bands`; the engine
reads it after the content row for a declared style at 10+. Explicit step:
`sample_parties` -> `audit_style_rosters` -> `derive_style_bands` ->
`derive_party_styles` -> `derive_meta_prior` -> `build_dataset` -> gates.

## The generated meta prior (2026-09-08)

Owner ruling ("sure" to one harvest prior replacing both hand lists):
the seven-weapon hand-set `meta_prior` in `templates/scoring.yaml` and
the viability `core` list in `templates/composition.yaml` are retired.
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
is the only dial. Explicit step, never part of a normal build:

```text
py -3 pipeline/derive_meta_prior.py
```

`parse_dumps` adapter 5 (same day) adds `caster_moves` to every indexed
spell — a `dash` node anywhere in the spell tree, the game's leap /
charge primitive. `derive_style_fit` reads it as the delivery rule
"payload reach, not travel": a caster-moving E's cast range counts toward
flex delivery only for a flex bomb (group payload at the job bar); a
standoff tool must move nothing.

## Party styles and style cells (2026-09-08)

`derive_party_styles.py` reads the COMMITTED `out/party_rosters.json.gz`,
labels every killer party of 10+ with `Engine.comp_identity` on its
weapons alone (naked matched the audit's dressed read 19/20 in blind round
4; the committed artifact carries no member kits), and writes
`out/party_styles.json` with the SHA-256 of the artifact it read.
`build_dataset` refuses a party-styles file derived from a different
artifact (exit 2); a missing file means no style cells that build.
`pipeline/party_link.py` links a build to its party: exactly through the
analyzer's `party` index (stamped since 2026-09-08 beside each party's
`index`), else by (battle, weapon) only when exactly one 10+ party in the
battle fields that weapon — never a guess. `derive_kit_doctrine(style=...)`
then mines one kit cell per style under each seat's `kit_styles` from the
linked builds, with the band's floors plus a 5-voter cell floor applied per
weapon, per slot (the slot's modal item) and to the chain's chest step;
thin cells and slots are absent, never filled. The engine's one doctrine
reader `_seat_kit` lays a DECLARED style's cell over the band; `balanced`
never reads a cell (owner 2026-09-08). Spec:
`notes/specs/2026-09-08-coherent-style-kits-design.md`.

**Seat pooling for thin slots** (same day, spec section 3; owner: "i leave
it up 2 you to get the best results"). Measured first: three players'
helmets predict a weapon's true modal 58% of the time, the seat's helmet
among builds wearing the SAME chest 80% (boots 48% -> 72%, cape 68% ->
81%); for potion and food the plain seat pool is right 95% / 82%. The
miner ships `kit_pool` (plain) and `kit_by_chest` (chest-conditioned) per
seat and band, player-counted, items with 5+ players, top 3 per slot, the
five poolable slots only. The kit reader in both ports treats a weapon
slot whose own modal carries under 5 votes as THIN and fronts the pool item
(same-chest for helmet / boots / cape, plain for potion / food), marked
`pooled` / `pooled_n`; chest and off-hand are never pooled; a 5+ vote
weapon modal is never overridden. The audits (R24, R24b, R28) skip a slot
whose killboard modal rests on fewer than 5 players — that slot is pooled,
not matched.

## One player, one vote (2026-09-04)

`sample_parties.py` stamps every harvested build with a hashed `player`
key (sha1 prefix of the name; the name stays in the cache). In
`derive_kit_doctrine` a player's k builds on a weapon weigh 1/k each, so
counts are votes; the noise floors (seat 3, weapon 2, a chain step 2)
count DISTINCT voters and the uniform extension needs 35 voters. Rows
ship rounded votes with `players` beside them and cite
`killboard:<votes>x/<players>p`; the compact `kit_weapon` tier rows are
`[id, count, players]` (2026-09-09; `players` absent on a reference-only
row) so the engine's thin-slot read counts people like every other
floor. Re-derive with `--pages 0` after changing the build record.

## Doctrine bands (2026-09-04)

`derive_kit_doctrine(band=...)` runs twice: `group` (killer parties of
10+, every curated content; the seat's top-level `kit*` keys, grading
overrides applied) and `gang` (parties of 4-9 plus the small-scale
curated contents; `kit_bands.gang`, no overrides). `DOCTRINE_BANDS` in
build_dataset.py is the table. The engine's `_seat_kit` picks the band by
party size (gang at <= 9). `roles_report.json` carries the gang detail
under `kit_doctrine_gang`.

## Per-item chest lean (2026-09-05)

`audit_style_rosters.py` also mines `out/chest_lean.json`: for every dps
chest, distinct wearers in WEAPONS-ONLY labelled clean cores (melee share
>= 0.65 brawl, <= 0.35 ranged); >= 20 wearers and >= 75% on one side
give the item a lean. `build_dataset` validates and ships it as
`chest_lean`; `comp_identity`'s kit tie-break reads the item lean first
and the class rule (leather -> brawl, cloth -> ranged) where an item has
none. Descriptive only. Because the audit writes it, the post-harvest
order is audit -> derive_style_bands -> derive_party_styles ->
derive_meta_prior -> build_dataset -> gates.
