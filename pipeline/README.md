# Composition Engine — Data Pipeline

Windows note: use `py -3`, not `python`/`python3` — those resolve to the
Microsoft Store stub. Requires `pyyaml` (`py -3 -m pip install pyyaml`).

```
ao-bin-dumps (git clone, see below)
   │  py -3 pipeline/parse_dumps.py <clone-path>
   ▼
out/weapon_lines.json     161 weapon lines: name + full Q/W/E/passive spell lists
out/spell_index.json      367 spells: function flags + target-direction hints
out/weapon_usage.json     usage ranking from albionbb battle sampling
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
out/dataset-<version>.json + dataset-latest.json    ← single source of truth
   │
   ├─ engine/engine.py            scoring engine (Python)
   ├─ tests/test_golden.py        9 golden regression cases
   └─ py -3 pipeline/build_dashboard.py → dashboard/index.html (dataset inlined)
```

**One source of truth.** Capability numbers live only in the YAML sheets. The
engine, the golden tests and the dashboard all read the built dataset. Before
this existed, the prototype kept its own inline copy and the two had already
diverged (Longbow `resist_shred` was 2 in the prototype, 1 in the curated
sheet). `build_dashboard.py` inlines the Python engine's own output as a parity
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

## Re-cloning ao-bin-dumps

Only needed after a game patch (`out/` is committed).

**After every re-clone + rebuild, re-check `pipeline/effect_overrides.yaml`.**
That file holds runtime corrections to parser output (direction bugs,
reference-chain artifacts, prose-flag misfires, and `add:` entries for
mechanics outside the structured vocabulary). Each entry cites the dumps text
it was verified against; an entry whose upstream bug gets fixed becomes
silently redundant — or wrong, if the spell was redesigned. Diff each entry's
spell against the fresh dumps text and delete entries the rebuild made
unnecessary.

```
git clone --depth 1 --filter=blob:none https://github.com/ao-data/ao-bin-dumps.git
```

For `patch_history.py` the clone needs HISTORY, so drop `--depth 1`:

```
git clone --filter=blob:none --no-checkout https://github.com/ao-data/ao-bin-dumps.git
```

(~3 MB of history; each diffed snapshot fetches its ~14 MB `spells.json` blob
on demand, so `--patches N` downloads N+1 blobs.)

## Patch history / staleness

```
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
- Drafts: 0. All scores are Claude-proposed and lint-clean; the expert
  correction pass and Tier-2 blind validation are the outstanding quality
  gates.

## The effect layer

```
py -3 pipeline/effect_catalogue.py <ao-bin-dumps path> --report
   -> out/effect_catalogue.json          64 effects reachable from weapons
pipeline/effect_map.yaml                 effect x direction -> capabilities
pipeline/effect_lookup.py                shared: spell -> candidate capabilities
py -3 pipeline/build_effect_review.py    -> review/effects.html
```

Two layers, deliberately not collapsed:

| layer | what | count | role |
|---|---|---|---|
| effects | game mechanics (`stun`, `movespeedbonus-`, `remove:buff`) | 64 reachable from weapons | evidence |
| capabilities | comp-level needs (design doc §2.2) | 28 | scoring |

**The map is many-to-many and keyed by target direction.** One effect can ground
several capabilities: 1H Mace's Deep Leap resolves to `dash` + `invincibility` +
five self-immunities, which together support `engage`, `disengage`, `tankiness`,
`mobility` and `catch`. The same immunity granted to an *ally* is `peel` instead.
An empty list is a real answer — a self-slow while channelling grounds nothing.

The effect layer yields **candidates**, never assertions. Whether a particular
weapon's 3m dash is really an engage tool is a curation judgement; the lint's
job is only to reject capabilities the spell cannot support at all.

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

## Known gaps / TODO

- **Gear items have no sheets yet** — needed before archetype composition
  (design doc §2.4). Killboard events DO record Head/Armor/Shoes/Cape/Potion/
  Food, so gear *popularity* can be harvested from data; gear *capability*
  still needs the same evidence-cited curation as weapons (one active spell per
  piece, so seeding should get close to complete).
- **Usage sample is small** (24 battles / 359 players, 2026-08-12) and skewed to
  10–60 player fights. Re-run at ~200 battles before trusting shares
  (VALIDATION V7). Measured coverage is far thinner than design doc §5 assumed:
  top-30 weapons cover 62% of observations, not >90%; 97 distinct weapons appear.
- Structural capabilities (engage, peel, clump, tankiness…) are human-only by
  design; drafts contain effect capabilities only.
- Only one content template exists (`castle_outpost`, validated at size 7 only).
  Other sizes are linear extrapolation and are labelled as such in the UI.
- Default-kit harvester not built: Metabattle (open MediaWiki API, CC BY-SA,
  ~120 builds with per-slot spells) + Albion Free Market (4,478 builds,
  game-native spell IDs, SSR-scrapeable — ask their Discord first). Two-source
  agreement = high-confidence kit; see design doc §2.4.

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
  |---|---|---|
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
