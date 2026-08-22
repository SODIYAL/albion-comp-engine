# Albion Composition Engine

**Live planner: <https://sodiyal.github.io/albion-comp-engine/>**  
**How it works: <https://sodiyal.github.io/albion-comp-engine/how-it-works.html>**

Comp Forge is an Albion Online party-composition recommendation engine. Give it the content, expected party size, playstyle, and the weapons already in the group; it diagnoses the composition and recommends what should join next.

The product is built around a simple question:

> **What does this party need most right now, and which weapon fixes it best?**

It is a **capability model**, not a role checklist. Each weapon contributes to functional capabilities such as `engage`, `peel`, `clump_create`, `heal_sustain`, `cleanse`, `resist_shred`, `anti_heal`, and damage pressure. Content templates define how important those capabilities are for a particular fight, while playstyles change their emphasis. The engine scores the current party against that requirement profile and evaluates the marginal value of possible additions.

## What the live planner does

The current interface is deliberately decision-first. Rather than making the caller interpret a large score board before getting an answer, Comp Forge surfaces:

1. **Comp Status** — whether the roster has critical gaps, weaker areas, or excessive overlap.
2. **Biggest Need** — the most important problem in the current composition, with hard floors taking priority over softer deficits.
3. **Best Next Pick** — the weapon with the strongest marginal contribution to the party as it exists now.
4. **What it fixes** — the capabilities improved by that addition.
5. **What remains weak** — the next problem the party would still have after making the recommendation.
6. **Deeper diagnostics** — the weapon wheel, capability board, loadouts, evidence, formulas, and detailed weapon information remain available underneath the decision layer.

Recommendations are evaluated **one player ahead**. If the roster currently contains six players, the next-pick calculation asks what a seven-player composition requires so thresholds that become important at the next body can influence the recommendation before the player joins.

The planner also supports full-comp forging, per-member swap advice, role-ordered rosters, selectable Q/W/E loadouts, equipment information, shareable URL state, Discord-ready comp text, and detailed weapon dossiers.

## How recommendations work

A weapon is represented as a vector of capabilities. A content template supplies targets, floors, weights, scaling rules, and other composition requirements. The selected playstyle modifies **weights**, not the underlying meaning of the capabilities.

For a candidate weapon, the engine effectively asks:

```text
current party
    ↓
resolve selected weapon/spell contributions
    ↓
measure composition against the active content template
    ↓
identify hard failures and weighted deficits
    ↓
add candidate weapon
    ↓
recalculate the composition
    ↓
marginal gain = score after − score before
```

The highest marginal gain is the recommendation, subject to the engine's feasibility and composition rules.

This means a weapon is not recommended simply because it is labelled "tank", "healer", or "DPS". It is recommended because its actual capability contribution addresses what the current composition is missing.

## Spell and loadout awareness

Weapon identity alone is not enough in Albion Online. Q/W/E choices determine which capabilities a player actually brings.

The engine therefore tracks spell-level capability bundles and uses selected or resolved loadouts when evaluating compositions. Forge constraints that depend on capabilities are checked against the chosen spell kit rather than assuming every possible ability on the weapon is simultaneously available.

The planner also exposes equipment/build evidence where reliable records exist, while keeping weapon recommendation logic separate from unsupported assumptions about a complete gear set.

## Evidence is separate from scoring

Comp Forge intentionally separates three concepts:

| Layer | Purpose |
|---|---|
| **Game mechanics** | What abilities actually do: stun, purge, cleanse, displacement, damage, immunity, etc. |
| **Capability model** | What those mechanics mean to a composition: engage, peel, anti-zone, sustain, burst, etc. |
| **Observed evidence** | What builds, compositions, and weapons are seen in external or battle data. |

Observed popularity is **not automatically treated as strength**.

For example, killboard/battle sampling can tell the UI that a weapon is frequently seen in fights of a similar size. That is useful supporting evidence, but it does not currently add hidden points to the mechanical recommendation score.

Every nonzero curated capability score must also cite the spell/effect that supports it. `pipeline/evidence_lint.py` checks that the cited ability is actually equippable and can ground the claimed capability. This catches plausible-looking curation errors such as attributing purge, anti-heal, cleanse, or displacement to a weapon that cannot actually provide it.

## Current state — August 2026

The project has moved well beyond the original prototype described in early README versions.

- Capability sheets cover the combat weapon catalogue used by the engine.
- The dataset is provenance-aware and fails closed when pinned game-data inputs drift.
- Browser scoring and the Python engine are parity-tested.
- Golden, forge, interaction, provenance, build/evidence, patch-history, and loadout-codec test suites protect the current behaviour.
- Real composition records are stored as an evidence/calibration layer rather than being silently converted into recommendation truth.
- The public planner now uses the **decision-first** Comp Status → Biggest Need → Best Next Pick hierarchy.
- Capability constraints are combo-aware: selected spell kits matter.
- Composition targets are evaluated at the roster size actually present; next-pick advice evaluates one player ahead.
- The recommendation engine and the evidence/usage layers remain intentionally separable so empirical data can be validated before it is allowed to influence scoring.

The system should still be treated as a decision-support tool rather than an authoritative statement of the Albion meta. Capability grading, content calibration, and validation against experienced callers remain ongoing work.

## Experimental work

Two feature branches are currently being evaluated separately from the live planner:

### Killboard affinity / partial-comp evidence — PR #5

This work extends battle sampling beyond generic weapon prevalence. Because a kill feed does not reliably identify actual parties, it groups observed players conservatively by organization cohort (alliance, with guild fallback) rather than pretending everyone on the same battle record was on the same team.

The goal is to calculate:

- weapon co-occurrence counts,
- conditional pairing frequency,
- affinity/lift so globally popular weapons do not dominate merely because they appear everywhere,
- partial-roster matches that can show weapons observed alongside several of the user's selected weapons.

This remains **display/evidence only** until the data has been refreshed and validated. It does not modify mechanical recommendation scores.

### Player weapon pools + swap impact — PR #6

This work adds a caller-oriented constraint: instead of asking only "what is theoretically best?", a player can provide the weapons they actually play and the engine can rank recommendations inside that pool.

It also adds before/after swap analysis so callers can evaluate a replacement before committing it, including fitness movement, capability changes, and the biggest weakness that would remain after the swap.

This branch reuses the existing recommendation and swap scoring paths rather than introducing a second scoring model.

## Validation philosophy

There are several different things worth validating, and they should not be confused:

- **Mechanical correctness** — does the weapon actually have the effect we claim?
- **Implementation correctness** — do Python and browser scoring produce the same result?
- **Regression safety** — do known compositions and engine behaviours remain stable when code changes?
- **Recommendation quality** — do experienced Albion callers agree with the engine's choices?
- **Empirical relevance** — do observed real-world compositions support, contradict, or add context to the model?

A green unit test suite proves implementation behaviour, not that every recommendation is strategically correct. Expert blind testing and real-comp evidence are the important external checks.

See `tests/VALIDATION.md` for the validation history and gates.

## Rebuilding the project

On Windows, use `py -3` rather than `python`/`python3`.

The authoritative full command list is maintained in `HANDOFF.md` and `pipeline/README.md`. The main day-to-day gates include:

```bash
py -3 pipeline/evidence_lint.py
py -3 pipeline/build_builds.py
py -3 pipeline/build_dataset.py
py -3 tests/test_golden.py
py -3 tests/test_forge.py
py -3 tests/tier2_blindtest.py v4
py -3 tests/test_js_parity.py
node tests/test_loadout_codec.js
py -3 tests/test_patch_history.py
py -3 tests/test_provenance.py
py -3 tests/test_builds.py
py -3 pipeline/build_interactions.py
py -3 tests/test_interactions.py
py -3 pipeline/build_dashboard.py
```

`pipeline/sample_battles.py` is optional and network-dependent. It refreshes observational battle evidence; it is not required for the mechanical scoring engine to function.

After a game patch, follow the pinned-snapshot procedure in `pipeline/README.md`: update the ao-bin-dumps source pin, rebuild the derived game-data layers, then run the complete release gates before shipping regenerated outputs.

## Repository map

```text
MASTERSHEET.md                 expert control surface / tuning rulings
HANDOFF.md                     current project state + development handoff
albion-comp-engine-design.md   research, architecture, taxonomy and design history

engine/
  engine.py                    canonical Python scoring engine

pipeline/
  sheets/                      capability sheets
  templates/                   content requirements
  app_scoring.js               browser scoring twin
  build_dataset.py             builds the release dataset
  build_dashboard.py           builds Comp Forge + Pages output
  sample_battles.py            observational battle sampler
  out/                         generated data/evidence artifacts

tests/
  test_golden.py               recommendation regression cases
  test_forge.py                forge/constraint contracts
  test_js_parity.py            Python ↔ browser scoring parity
  VALIDATION.md                validation record and external-quality gates

dashboard/
  index.html                   generated local product page
  _explainer.html              source for How It Works
  how-it-works.html            generated/local explainer copy

docs/
  index.html                   GitHub Pages product output
  how-it-works.html            GitHub Pages explainer

review/                        generated audit/review boards
```

## Recommended roadmap

Near-term product work is focused on making the engine more useful to an actual caller without prematurely teaching the score to imitate popularity:

1. validate and ship player weapon pools + swap impact,
2. add a fight-chain explanation such as Engage → Clump → Pierce → Burst → Secure → Reset,
3. infer composition identity and detect internally conflicted rosters,
4. surface negative recommendations and redundancy warnings,
5. support locked players/slots and constrained reforging,
6. save player/guild weapon profiles,
7. validate killboard affinity and partial-composition neighbours,
8. cluster recurring observed composition families,
9. add enemy-comp / counter-drafting analysis,
10. build expert blind-validation tooling before allowing empirical evidence to influence recommendation scoring.

## Attribution and data

Game data is parsed from the community-maintained `ao-data/ao-bin-dumps` mirror of Albion Online client data. Derived files may include ability names and descriptions owned by Sandbox Interactive GmbH. Item artwork comes from Albion Online's render service and is also owned by Sandbox Interactive GmbH.

This project is unofficial and is not affiliated with or endorsed by Sandbox Interactive.

The capability taxonomy, content templates, scoring model, evidence architecture, and application code are the work of this repository.

*No license file is currently included; default copyright therefore applies.*
