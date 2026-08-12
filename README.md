# Albion Composition Engine

A recommendation engine for Albion Online party composition. Given the content
type, the party size and who is already in the group, it proposes the next
player — and explains why in terms of what the composition is actually missing.

It is a **capability model**, not a role checklist. A weapon is a vector of
functional scores (`peel`, `heal_sustain`, `clump_create`, `resist_shred`, …),
a content type is a set of weighted targets for those capabilities, and the
recommendation is the archetype with the highest marginal gain against the gap.
Roles fall out of the vector rather than being assigned to it.

```
Party: Longbow, Witchwork, Permafrost      Castle Outpost, size 7
Fitness 18.8 / 104

Biggest weaknesses
  heal_sustain    0 / 3.0   −10.0
  peel            0 / 3.0    −8.0
  engage          0 / 2.0    −7.0

Recommend: Hallowfall
  +22.53  heal_sustain: 0 → 2 (target 3.0)
  + 8.00  peel:         0 → 3 (target 3.0)
  + 6.00  heal_burst:   0 → 3 (target 2.0)
```

## Status

**Pre-validation. Do not trust the numbers yet.**

- The scoring model passes 9/9 golden regression tests — that validates its
  *shape*, not its recommendation quality.
- 6 weapons have curated, evidence-checked capability sheets. 34 more are
  auto-seeded drafts awaiting human curation. 8 are placeholder numbers that
  block a clean release.
- One content template exists (Castle Outpost), fitted at size 7 only.
- **Tier-2 validation has not run.** The real accuracy gate is a blind test
  against experienced shotcallers (≥70% top-3 agreement). Until that passes,
  treat output as a plausible hypothesis.

## The two-layer design

| layer | what it holds | source | count |
|---|---|---|---|
| **effects** | game mechanics: `stun`, `movespeedbonus-`, `remove:buff` | derived from game data | 64 reachable from weapons |
| **capabilities** | what a composition needs: `peel`, `engage`, `heal_sustain` | human taxonomy | 28 |

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
weapon line that has no cleanse anywhere in its kit. The lint catches that class
of mistake without waiting for a human to notice.

## Running it

Requires Python 3 and `pyyaml`. On Windows use `py -3`.

```bash
py -3 pipeline/evidence_lint.py      # CI gate — exit 1 blocks a release
py -3 pipeline/build_dataset.py      # sheets + templates -> out/dataset-latest.json
py -3 tests/test_golden.py           # 9 golden regression cases
py -3 pipeline/build_dashboard.py    # -> dashboard/index.html (self-contained)
```

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
tests/                         golden regression suite + Tier-2 harness
dashboard/, review/            generated single-file pages
```

`pipeline/README.md` covers the data pipeline in detail; `tests/VALIDATION.md`
covers what has been tested and what has not.

## Attribution and data

Game data is parsed from [ao-data/ao-bin-dumps](https://github.com/ao-data/ao-bin-dumps),
a community mirror of Albion Online's client data files. Files under
`pipeline/out/` are derived from it and include ability names and descriptions
that are © Sandbox Interactive GmbH. This project is unofficial and not
affiliated with or endorsed by Sandbox Interactive.

The capability sheets, effect map, content templates and scoring model are the
original work of this repository.

*No license file yet — until one is added, default copyright applies.*
