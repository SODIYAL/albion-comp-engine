# Albion Composition Engine

**Live planner: <https://sodiyal.github.io/albion-comp-engine/>**

A recommendation engine for Albion Online party composition. Given the content
type, the party size and who is already in the group, it proposes the next
player — and explains why in terms of what the composition is actually missing.

It is a **capability model**, not a role checklist. A weapon is a vector of
functional scores (`peel`, `heal_sustain`, `clump_create`, `resist_shred`, …),
a content type is a set of weighted targets for those capabilities, and the
recommendation is the archetype with the highest marginal gain against the gap.
Roles fall out of the vector rather than being assigned to it.

```
Party: Longbow, Witchwork Staff, Permafrost Prism      Castle Outpost, size 7
Fitness 25.0 / 107

Biggest weaknesses
  heal_sustain    0 / 3.0   −10.0
  tankiness       0 / 4.0    −9.0
  engage          0 / 2.0    −7.0

Recommend: Hallowfall
  +27.53  heal_sustain: 0 → 2 (target 3.0)
  + 6.00  heal_burst:   0 → 3 (target 2.0)
  + 3.00  mobility:     0 → 3 (target 2.0)
Alternatives: Exalted Staff, Great Holy Staff, Redemption Staff
```

## Status (2026-08-12)

**Fully curated, pre-validation. Do not trust the numbers yet.**

- **All 137 combat weapons have curated, evidence-linted capability sheets**
  (`release_clean: True`; the other 24 catalog entries are vanity items and
  gathering tools). Weapons in a line share their Q/W pool, so line-mates
  carry identical pool scores and differ only in their E — sheets are
  organized accordingly.
- **Six content templates** — Blackzone Roam (20), Territory Defense (20),
  Castle Fight (25), Faction War Red Zone (15), Castle Outpost (7), Roads of
  Avalon (7, in-game party cap) — and
  **five playstyles** (balanced / brawl / clap / kite / brawl-clap) that
  reweight any template toward the caller's plan. The 2026-08-13 templates
  and all style multipliers are PROVISIONAL until the expert pass; role
  calibration for the 20-size pair came from two real shotcaller comps
  (`data/published_comps/` — the evidence layer, chapter 2).
- **`dashboard/index.html` (Comp Forge) is the product page** — pick the
  content and playstyle, set the party size to however many actually show
  up (targets, floors and scaling adapt from 2 to 60), build the party in
  numbered slots or let **forge a full comp** greedy-build one, and read
  fitness, floor alarms, needed-now vs nice-to-have gaps, and the
  recommended next pick with its reasoning, formula, caller loadout and
  evidence. Weapon detail drawer shows every weapon's real Q/W/E/passive
  options by in-game name. Party state lives in the URL hash (copy share
  link); "copy comp text" exports a Discord-ready roster. Self-contained;
  open it directly. In-browser scoring is `pipeline/app_scoring.js`, a
  line-for-line port of the Python engine held equal by
  `tests/test_js_parity.py` (60/60 random parties across all templates and
  styles, 1e-9) plus a build-time parity fixture checked on every load.
- **Real-usage field reports**: `pipeline/sample_battles.py` samples recent
  battles from the official gameinfo killboard API and counts weapons per
  fight-size bucket; the page quotes "seen on X% of players in fights your
  size". Display evidence only — it does not feed the scoring until
  validation says it may.
- **Per-member swap advisor** — each party member's weapon is valued exactly
  as the recommender would value it as a pick into the rest of the party,
  ranked against all 137 alternatives at the current content and size, and
  members with markedly better options get multiple concrete suggestions
  (click to swap in place). Rankings are size-aware: floors arm only above
  their `min_party_size`, and the focus-fire physics boosts single-target
  damage below a template's base size — so a 3-man missing a healer reads
  as a gap, while a 7-man missing one reads as broken.
- The scoring model passes 24/24 golden regression tests against the full
  dataset — that validates its *shape*, not its recommendation quality.
- Every score is a Claude proposal grounded in the game's own spell text and
  passed through the evidence lint, plus the first owner corrections (glove
  kidnap). The **full expert correction pass has not happened**, and several
  template numbers are marked PROVISIONAL (`anti_zone`, `damage_debuff`
  weights; heal-floor `penalty_mult`; both 20-size templates).
- **Tier-2 validation has not run.** The real accuracy gate is a blind test
  against experienced shotcallers (≥70% top-3 agreement); the form is
  generated at `tests/tier2_form.md` against the full weapon pool. Until it
  passes, treat output as a plausible hypothesis.

## The two-layer design

| layer | what it holds | source | count |
|---|---|---|---|
| **effects** | game mechanics: `stun`, `movespeedbonus-`, `remove:buff` | derived from game data | 64 reachable from weapons |
| **capabilities** | what a composition needs: `peel`, `engage`, `heal_sustain` | human taxonomy | 29 |

They are deliberately not collapsed. The map between them is many-to-many and
direction-aware: 1H Mace's Deep Leap resolves to `dash` + `invincibility` + five
self-immunities, which together ground `engage`, `disengage`, `tankiness`,
`mobility` and `catch` — while that same immunity granted to an *ally* is `peel`
instead. Keeping the layers separate is what lets the capability taxonomy
survive balance patches: a patch changes effects, not what a composition needs.

## The evidence rule

Every nonzero capability score must cite the specific spell that provides it,
and `pipeline/evidence_lint.py` mechanically verifies that the spell is
equippable on that weapon and can actually ground the claim. Uncited scores are
invalid by definition.

This exists because hand-curation produced real errors that all looked
plausible: a purge attributed to a weapon whose kit has none; a knockback that
displaces the *caster* filed as enemy displacement; a cleanse credited to a
weapon line that has no cleanse anywhere in its kit. The full-coverage pass
found the same class in the original hand-sketched sheets themselves — a
dedicated anti-heal weapon whose kit contains no anti-heal, an energy drain
that no spell provides. The lint catches that class of mistake without waiting
for a human to notice; `pipeline/effect_overrides.yaml` documents the cases
where the *parser* is the one that is wrong.

## Running it

Requires Python 3 and `pyyaml`. On Windows use `py -3`.

```bash
py -3 pipeline/evidence_lint.py      # CI gate — exit 1 blocks a release
py -3 pipeline/fetch_item_stats.py   # ao-bin-dumps -> out/item_stats.json (the numbers)
py -3 pipeline/fetch_gear_lines.py   # item_stats -> out/gear_lines.json (loadout catalogue)
py -3 pipeline/fetch_icons.py        # render service -> out/icon_data.json (weapon + gear art)
py -3 pipeline/build_dataset.py      # sheets + templates + stats -> out/dataset-latest.json
py -3 tests/test_golden.py           # golden regression cases (24)
py -3 tests/test_js_parity.py        # JS scoring == Python engine (needs node)
py -3 tests/test_patch_history.py    # patch-diff + staleness unit tests
node tests/test_loadout_codec.js     # loadout permalink round-trip (12)
py -3 pipeline/build_dashboard.py    # -> dashboard/index.html (the product page)
```

After a game patch, `pipeline/patch_history.py` diffs ao-bin-dumps git history
into `out/patch_history.json`; the lint then warns when a sheet's cited
evidence spell changed after the sheet's `curated_as_of` date, so curation
staleness is detected mechanically instead of noticed by accident. See
`pipeline/README.md` § *Patch history / staleness*.

`dashboard/index.html` and `review/effects.html` are generated, single-file
pages — open them directly, no server needed.

Regenerating the game data (only needed after a balance patch) additionally
requires a clone of [ao-data/ao-bin-dumps](https://github.com/ao-data/ao-bin-dumps);
see `pipeline/README.md`.

## Layout

```
albion-comp-engine-design.md   research + system design (data sources, taxonomy,
                               scoring algorithm, architecture, MVP scope)
engine/engine.py               scoring engine — consumes the built dataset
pipeline/                      game data -> capability sheets -> dataset
  sheets/                      curated capability sheets (the hand-made part)
  effect_map.yaml              effect x direction -> capabilities
  templates/                   content requirements + scoring weights, as data
  app_scoring.js               JS port of the engine (parity-tested)
tests/                         golden suite + Tier-2 harness + meta comps
dashboard/                     Comp Forge, the product page (generated, single file)
review/                        effects review page (generated)
```

`pipeline/README.md` covers the data pipeline in detail; `tests/VALIDATION.md`
covers what has been tested and what has not.

## Attribution and data

Game data is parsed from [ao-data/ao-bin-dumps](https://github.com/ao-data/ao-bin-dumps),
a community mirror of Albion Online's client data files. Files under
`pipeline/out/` are derived from it and include ability names and descriptions
that are © Sandbox Interactive GmbH. Item icons are fetched once by
`pipeline/fetch_icons.py` from the official Albion Online Render Service
(render.albiononline.com) and embedded in the generated pages; the artwork is
© Sandbox Interactive GmbH. This project is unofficial and not affiliated
with or endorsed by Sandbox Interactive.

The capability sheets, effect map, content templates and scoring model are the
original work of this repository.

*No license file yet — until one is added, default copyright applies.*
