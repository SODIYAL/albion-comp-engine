# MASTERSHEET — the control surface for the comp engine

This file is two things at once:

1. **The plain-language explanation** of where every number in the engine
   comes from and why a weapon ranks where it does.
2. **The control panel.** The yaml blocks below marked `tune:` are read at
   build time and **override** the underlying config files. Edit a value
   here, rebuild, and the engine — the live dashboard and the Python engine
   both — follows. You never have to hunt through the pipeline files.

To apply your edits:

```
py -3 pipeline/build_dataset.py
py -3 pipeline/build_dashboard.py
```

(Recommended after big edits: `py -3 tests/test_golden.py` and
`py -3 tests/test_js_parity.py` to confirm nothing structural broke.)

Safety: the build **fails loudly** on any mistake here — an unknown weapon
name, a capability a weapon doesn't have, a typo'd section — it will never
silently ignore your edit. And whatever is set here **wins** over the
underlying files, so this file is the single place to look when asking
"what is the engine actually using?"

---

## 1. Where the data comes from

The chain, start to finish:

| Layer | What it is | Where it lives |
| --- | --- | --- |
| **Game files** | The game's own data: every spell's numbers, areas, escalation flags — pinned to one exact game-data snapshot so results are reproducible | `out/dumps_cache/` (snapshot), `data/source_pins.yaml` (the pin) |
| **Parsed spells** | Each spell's damage, radius, max targets, escalation factors, cooldown, description | `out/spell_index.json` |
| **Capability sheets** | The human judgment layer: what each weapon is actually good at, scored 0–3 (soon 1–7), with the exact spell cited as evidence. Shared Q/W spells are curated once per tree; each weapon's sheet carries only its E — the E is the weapon's identity | `pipeline/sheets/pools/` (tree Q/W), `pipeline/sheets/*.yaml` (the E) |
| **Delivery physics** | Auto-derived per capability from its evidence spell: area footprint, target cap, escalation — this is what makes an AoE slow count more than a self speed-buff in big fights | stamped into the dataset at build time |
| **Content templates** | What each content type demands: how much healing, catch, AoE damage etc. a castle fight vs a roads gank wants | `pipeline/templates/*.yaml` |
| **The dataset** | Everything above compiled into one file; the browser engine and the Python engine read this same file, verified identical to 9 decimal places | `out/dataset-latest.json` |

No score exists without a cited spell (the evidence lint blocks the build
otherwise), and no data ships unless its whole chain hash-verifies against
the pinned snapshot.

## 2. Why a weapon ranks where it does

A candidate's score is **exactly how much the party's total comp score
changes if it joins**:

```
score = 0.55·(capability gain) + 0.20·(synergy gain) + 0.15·(meta prior)
        ± viability/duplication adjustments
```

What happens inside "capability gain", in order:

1. **One spell per slot.** The weapon is scored on its best single Q/W/E/passive
   loadout — never the whole spell menu at once.
2. **Geometry.** AoE-delivered utility (catch, peel, slow, stun, root,
   silence, displace) is multiplied by how many enemies the spell's real
   footprint reaches in this fight size and playstyle. A 7m Tornado ≈ 3× a
   self-only speed buff at 20-man; the gap closes in small gangs. Effects
   the game gives CC Escalation to (duration grows per target hit) get that
   on top — read per spell from the game files.
3. **Fight physics.** AoE damage escalates with clump size; stacked
   single-target damage is taxed by the game's Focus Fire protection
   (up to 75% at 26+ attackers).
4. **Demand.** What's left is compared against the content template: filling
   an empty need is worth the full weight, topping up a covered one is worth
   little (concave), and over-stacking costs.

The dashboard's "Why" panel shows these exact terms for any pick — the
numbers there ARE the scoring, not a summary of it.

**Known blind spots** (the improvement roadmap, in priority order):
damage magnitude is flat (a 1v1 weapon's AoE reads equal to Kingmaker's —
the 1–7 rubric in §7 fixes this); enabler value is missing (Soulscythe's
knockup line that makes everyone's damage land earns nothing yet); the
"who actually plays this at scale" reality-check exists but is unwired;
gear coherence (Heavy Mace on cloth) has no layer at all yet.

---

## 3. The dials — scoring

These values are LIVE: edit and rebuild. They currently mirror the tuned
defaults.

```yaml tune:scoring
weights:
  alpha: 0.55        # weight of raw capability gain
  beta: 0.20         # weight of synergy gain
  delta: 0.15        # weight of the meta prior
  gamma: 0.70        # concavity: how fast a filled need stops paying
  overstack_max: 0.5 # max penalty for over-stacking a capability
  rho: 0.25          # per-copy cost of duplicate weapons
  viability: 0.15    # bonus for core-listed weapons at large sizes
  headroom: 0.1      # small credit for supply between target and soft cap

# Pairs worth more across two players than their sum. Add a pair by copying
# a line; capability names must exist in the content template's demands.
capability_synergies:
  - {a: clump_create,   b: burst_aoe,      bonus: 1.5}
  - {a: engage,         b: catch,          bonus: 0.8}
  - {a: resist_shred,   b: burst_st,       bonus: 0.8}
  - {a: heal_reduction, b: sustained_dps,  bonus: 0.8}

# Hand-set "people actually play this" nudges, 0–1 per weapon.
# Real win-rate data replaces these in Phase 3.
meta_prior:
  MAIN_HOLYSTAFF_AVALON: 1.0   # Hallowfall
  2H_MACE:               1.0   # Heavy Mace
  2H_HAMMER:             0.8   # Great Hammer
  2H_ICECRYSTAL_UNDEAD:  0.8   # Permafrost Prism
  2H_HOLYSTAFF:          0.6   # Great Holy Staff
  2H_LONGBOW:            0.6   # Longbow
  MAIN_MACE:             0.6   # Mace
```

## 4. The dials — fight physics

```yaml tune:mechanics
aoe_geometry:
  # How many enemies an area of a given radius realistically affects
  # (step table: the largest radius <= the spell's radius wins).
  radius_targets:
    0: 1
    2: 2
    3.5: 3
    5: 4
    6.5: 6
    8: 8
  # Which capabilities scale with targets reached. zone_control is excluded
  # on purpose — area already IS its identity.
  geometric_caps: [catch, peel, slow, stun, root, silence, knockback_displace]
  # Which of those also get the game's CC Escalation (longer duration per
  # target hit) when the spell carries the flag in the game files.
  cc_duration_caps: [stun, root, silence]
  escalation_cap_targets: 8
  # THE ANCHOR: the clump size at which an AoE utility spell counts exactly
  # its sheet score. 2 = "a small skirmish". Raise it and AoE utility gets
  # weaker everywhere; lower it and AoE utility gets stronger everywhere.
  reference_clump: 2
```

## 5. Per-content demand overrides

Adjust what a content type demands without touching the template files.
Empty = no overrides. Example (uncomment and edit):

```yaml tune:templates
# castle:
#   catch:   {weight: 5, target: 3.5}   # castle wants more catch
# blackzone_roam:
#   burst_st: {weight: 0}               # zero out single-target at roam
```

Valid fields per capability: `target`, `weight`, `soft_cap`, `scales`.
Contents: `blackzone_roam`, `castle`, `castle_outpost`, `faction_war`,
`roads`, `territory_defense`.

## 6. Per-weapon score overrides

Your expert rulings, applied instantly without editing sheets. You can
**re-rank** a capability the weapon already has, or **remove** it
(score 0). You cannot invent a new capability here — that needs a sheet
row with spell evidence, which keeps the no-score-without-proof rule
intact. Empty = no overrides. Example:

```yaml tune:sheets
# 2H_TWINSCYTHE_HELL:          # Soulscythe
#   knockback_displace: 2      # the line knockup is undervalued at 1
# 2H_DOUBLEBLADEDSTAFF:
#   catch: 1                   # gank kit, not ZvZ catch — down from 2
```

Weapon keys are the game's unique names — see any weapon's dossier in the
dashboard, or `pipeline/sheets/*.yaml`.

## 7. The 1–7 ability rubric (designed, not yet wired)

The 0–3 scale is being replaced by a 1–7 score per (spell, capability),
judged on eleven questions: raw magnitude · reliability · controllability ·
ease of execution · uptime economy · cost of use · counterability ·
kit/role fit · purpose fit · payload/follow-up · **team enablement** (does
it make everyone else's damage land — the Soulscythe question). Targets
count and content-fit are deliberately NOT in the rubric: geometry and
templates already compute those, and scoring them twice would double-count.
When this lands, question 1 is pre-filled from the game files and the
boards in `review/magnitude.html` become the judging instrument.

## 8. Guild-approved builds

Paste the guild announcement here as data (any structure — weapon names,
armor, roles, notes). It ships into the dataset verbatim as a **guideline
layer**: visible in tooling, usable as a validation reference, never a
hard rule the scorer enforces. Empty until provided:

```yaml tune:guild_builds
```

---

## 9. House rules (how this stays trustworthy)

- **No score without a cited spell.** The evidence lint fails the build on
  any capability score that can't point at an equippable spell.
- **The game files are the authority** on magnitudes, areas, and escalation
  — patch data beats wiki notes beats memory.
- **Every expert ruling becomes a pinned test** (the golden suite, 26 cases)
  so later changes can't silently undo it.
- **Browser and Python engines are bit-identical** (parity gate, 60 cases at
  1e-9) — what the dashboard shows is what the engine computed.
- **Fail closed.** Broken provenance, lint errors, or a bad edit in this
  file stop the build; they never ship quietly.
