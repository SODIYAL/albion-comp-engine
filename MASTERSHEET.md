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
py -3 dashboard/build.py
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
| **Capability sheets** | The human judgment layer: what each weapon is actually good at, scored **1–7** (2 points = one supply unit; old 0–3 scores live on the even slots), with the exact spell cited as evidence. Shared Q/W spells are curated once per tree; each weapon's sheet carries only its E — the E is the weapon's identity | `pipeline/sheets/pools/` (tree Q/W), `pipeline/sheets/*.yaml` (the E) |
| **Delivery physics** | Auto-derived per capability from its evidence spell: area footprint, target cap, escalation — this is what makes an AoE slow count more than a self speed-buff in big fights | stamped into the dataset at build time |
| **Content templates** | What each content type demands: how much healing, catch, AoE damage etc. a castle fight vs a roads gank wants | `pipeline/templates/*.yaml` |
| **The dataset** | Everything above compiled into one file; the browser engine and the Python engine read this same file, verified identical to 9 decimal places | `out/dataset-latest.json` |

No score exists without a cited spell (the evidence lint blocks the build
otherwise), and no data ships unless its whole chain hash-verifies against
the pinned snapshot.

**Tiers and item power:** gear maps to item power exactly (T4 = 700; each
tier step or enchant = +100). Magnitudes scale ×1.0918 per 100 IP,
compounding (≈ ×1.42 at 4.4/7.1, ×2.02 at 8.4), further weighted by the
weapon family's ability-power coefficient (most 120; axes 138, crossbows
144 — shown as [AP n] tags on the chart). What does NOT scale with tier:
percentage effects, durations, distances, and any record the game flags
`ignoreabilitypowerscaling` — the chart tags those **tier-flat** (Primal
Slam's 18m wall is 18m at 4.1 and at 8.4, which is exactly what makes
flagged utility the cost-efficient pick and damage weapons tier-hungry).
The stat chart's Tier lens table carries the full multiplier row.

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
# 1-7 grading scale (2026-08-20): sheets grade every capability 1-7. Old
# 0-3 scores moved to the EVEN slots (1->2, 2->4, 3->6); odd slots are for
# finer rulings — 1 = weaker than anything previously scored, 7 = beyond
# the old top. score_unit = how many points make one supply unit; 2 keeps
# all template targets and floors calibrated exactly as before.
score_unit: 2

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
# Expert ruling 2026-08-20 (pinned by golden T19): Bedrock Mace is THE
# anti-dive pick at scale — Primal Slam's 18m CC-resist-ignoring throw
# leaves a PERSISTENT WALL (an extra peel layer, fire-and-forget), on a
# support-tank kit with Guard Rune; guild runs it double-CORE. Iron-clad's
# whirlwind must physically contact the diver while channeling — in large
# fights nobody uses it for this. The raw numbers alone (18m vs 12m) hid
# the delivery nuance; this is rubric Q2 reliability + Q8 kit fit.
MAIN_ROCKMACE_KEEPER:          # Bedrock Mace  (1-7 scale)
  anti_dive: 6
2H_IRONCLADEDSTAFF:            # Iron-clad Staff
  anti_dive: 2

# Expert ruling 2026-08-24 (round 7 E-audit follow-up): "fist of ava purge
# can be a 4." Purifying Fist strips ALL buffs from ALL enemies hit inside
# a 232-damage area punch — the true-purge benchmark delivered as a dive
# bomb, above the sheet's 3.
2H_KNUCKLES_AVALON:            # Fists of Avalon
  purge: 4

# 2H_TWINSCYTHE_HELL:          # Soulscythe
#   knockback_displace: 4      # the line knockup is undervalued at 2
# 2H_DOUBLEBLADEDSTAFF:
#   catch: 2                   # gank kit, not ZvZ catch — down from 4
```

Weapon keys are the game's unique names — see any weapon's dossier in the
dashboard, or `pipeline/sheets/*.yaml`.

## 7. The 1–7 ability rubric (canonical, 2026-08-20 — scale is LIVE)

Sheets now grade 1–7 (the old 0–3 sits on the even slots; odd slots are
for finer rulings, 7 = beyond the old top; `score_unit: 2` in §3 keeps all
calibration intact). The rubric below is how new 1–7 judgments are made,
refined against the worked case that proved raw magnitude alone misleads:
Bedrock's Primal Slam (18m throw + a wall that persists 4s, ground-cast
from 18m, ignores CC resistance, on a kit with Guard Rune / Snare Charge /
Defensive Slam) vs Iron-clad's whirlwind (12m, but the caster must
physically contact the diver while channeling). Every line of that
contrast is its own question.

Markers: ◆ pre-filled from the game files · ◇ data-assisted · ● judgment.

**Spell × capability (eight questions, 1–7 each):**

1. **S1 ◆ Raw magnitude** — size per application, ranked WITHIN its own
   effect type's ladder (meters vs meters, seconds vs seconds — never
   across units; the cross-type exchange is S7's judgment).
2. **S2 ◆ Persistence** — does it keep working after the cast with no
   further input? 1 = only during contact/channel · 4 = one instant
   application · 7 = leaves a lasting structure or zone (the 4s wall).
3. **S3 ◇ Delivery demand & pilot dependence** — 1 = must physically
   touch a moving enemy while channeling, or full value only under
   exceptional piloting (Bow's +280% AA window is huge on paper; landing
   sustained single-target autos on a priority target through a ZvZ is a
   skill few bring — score the value an AVERAGE competent player gets) ·
   3 = skillshot · 5 = targeted click · 7 = ground-cast fire-and-forget.
4. **S4 ◆ Cast position** — 1 = must stand inside enemy threat range,
   out of formation · 7 = castable from your own line (18m cast range).
5. **S5 ◆ Counter-immunity** — the flags are in the data: ignores CC
   resistance / ignores DR / purge- and cleanse-exposure. 1 = negated by
   standard kit · 7 = all-flags (Primal Slam class).
6. **S6 ◆ Economy vs job cadence** — cooldown measured against how often
   THIS capability's job recurs (27.5s CD vs a dive window every ~30s =
   always available; the same CD can mean one chance per fight for a
   different job). Numbers auto, cadence judgment.
7. **S7 ● Purpose fit** — does the effect's SHAPE do this capability's
   job (a knockback that pushes divers out is ideal anti_dive, mediocre
   catch; stasis denies a dive but also protects the target from damage).
8. **S8 ● Team enablement** — does it make teammates' damage/CC land
   (Soulscythe's line knockup) or deny the enemy team's follow-up (the
   wall splitting a dive from its support)?

**Weapon × role (three questions):**

1. **W1 ◇ Kit reinforcement & cross-slot combos** — do the slot-mates the
   role actually equips amplify the same job, or MULTIPLY the E?
   (Bedrock: Defensive Slam Q + Guard Rune / Snare Charge W — every slot
   serves anti-dive tanking. Longbow: Rain of Arrows E × Explosive Arrows
   W — the W makes the E's clump damage bigger, and the 15s E cycles the
   combo fast. Bow: the same W cannot turn a single-target AA window into
   AoE — same tree, no combo.) 1H weapons add the OFFHAND as a free
   amplifier slot (Hallowfall + healing offhand) — judged coarsely until
   gear sheets land. The loadout model supplies the candidates.
2. **W2 ● Identity density** — how many capabilities does the E cover AT
   QUALITY in one button? (Primal Slam: displacement + zone + peel
   simultaneously.)
3. **W3 ◇ Role placement & practice** — does the role's position/build
   put the spell where its job happens, and does reality agree (guild
   CORE lists, usage data)?

Targets-hit and content-fit are deliberately NOT in the rubric: the
geometric layer and the templates already compute those — scoring them
here would double-count. Combining: S1/S3/S7 are gates (a huge, reliable
effect with the wrong shape is still wrong for the job); the rest are
weighted modifiers with capability-specific weights.

The judging instruments: `review/stat_chart.html` (real numbers per
capability, spell-keyed, typed sub-groups, plus the per-spell fact line —
persistence, delivery, cast range, counter-immunity flags) and
`review/magnitude.html` (score-vs-dumps-text audit boards). Rebuild after
sheet edits: `py -3 pipeline/build_stat_chart.py`.

### Rescore pass 1 — applied 2026-08-20 (34 rulings, in the sheets)

First board-by-board pass over the outlier worklist (measured rank vs
curated score within typed unit groups). Conservative movement: mostly
into the odd slots; grounds = S1 ladder position + S2–S6 facts + guild
doctrine (W3). Highlights — full list in the sheet diffs of the rescore
commit:

- **Soulscythe Tornado** catch/peel/displace 2→4 (80%×~3s slow on a 25m
  line, ignores CCR, team-enabling hold — the session's founding case).
- **Double Bladed** catch 4→2 (gap-close catches one target — gank kit).
- **Snare Charge** root 2→5 (5.1s ranged ground root on 15s CD — the
  strongest root in the game; guild names it on CORE builds).
- **Occult's corridor** slow 2→4 (8s persistent zone @25m — the kite
  requirement); **Grailseeker's Soulshaker** catch 2→4; **Dreadstorm's
  fragment storm** catch/slow/shred 2→4 (1.5s CD spam).
- **Crossbow-line ranged CC** up (Silencing Bolt 4, ranged knockback 4 —
  ladder-consistent with Great Holy's 10m rung).
- Damage boards: Clarent charge burst_st 4, Dagger Pair execute 4, Heron
  throw 3; shreds (axe W, arcane Frazzle) 3.
- **One ruling HELD by the validation gate**: Hoarfrost's Avalanche
  measures 280/cast (top-20% of the burst_aoe board) and argues for 3 —
  but even +0.5 unit pushes the frontline pick out of a brawl comp's
  tank slot in the V4 blind test (69% vs the 70% gate; verified by
  isolating the single ruling). Held at 2 with the tension noted in the
  sheet — revisit when V4b/win-lift can adjudicate. Healer boards
  deliberately untouched this pass (V4 measures healer slots and the
  saturation artifact already dominates those misses — MECHANICS_TODO
  Q18).

## 8. The full-build member model (gear layer, 2026-08-20)

A member is no longer just weapon + weapon spells. The engine now models:

> **person contribution** = weapon loadout + helmet ability + armor ability
> + shoes ability + cape + offhand + potion + food — every slot's
> capabilities, through the same physics (a Force Field's 6m AoE shove
> scales geometrically like any weapon AoE; gear abilities carry the same
> delivery facts and rank on the same stat-chart boards).

- **Gear sheets**: `pipeline/sheets/gear/*.yaml` — same rules as weapon
  sheets (1–7 scale, no score without evidence; the evidence is the item's
  ability id, or `GEAR_STATS` for statless items like capes/potions/food).
  Starter set = the items your doctrine names in §9; ~40 items curated
  from the dumps descriptions. Add items by copying an entry.
- **One ability per piece** — the loadout rule applies to gear too; the
  engine scores the chosen (or best) ability per slot.
- **Item stats modify the person** (`build_stats` in the §4 mechanics
  dial): absolute defense (armor+MR, CC-resist) adds tankiness units;
  percentage stats MULTIPLY the member's own capabilities — Robe of
  Purity's +50% damage turns a DPS's damage supply ×1.5 and gives a
  control tank with no damage caps nothing, while plate's 287 armor
  points add tankiness either way. "Heavy Mace on cloth defeats its
  purpose" is now a computable statement (golden T21 pins it).
- **Engine**: `build_extra(weapon, combo, gear)` is a full member;
  `fitness/comp_score(party, combos, gears)` price full builds. Weapon-only
  calls are unchanged — gear is additive. Both engines verified identical
  (parity includes full-build cases); golden T20 pins a doctrine build.
- **The kit advisor** — `engine.kit_options(weapon, party=...)` returns
  the ideal kit and ranked alternatives PER SLOT for the player of that
  weapon in this content/style. Without a party it ranks by template
  weights; with the rest of the comp it ranks by exact fitness deltas, so
  the kit answers what THIS comp still needs, and role adaptation is
  emergent (the stat channel makes cloth worth 1.5x a DPS's damage and
  ~nothing on a control tank). Golden T22 pins the role differentiation.
  Since the role layer (2026-08-25/26) it is DOCTRINE-LED: the chest
  pool hard-gates to the weapon's seat uniform, every other slot ranks
  what the seat's real reference builds actually wore — the weapon's
  OWN observed kit first (with its honest sample size), the seat pool
  behind it — and effect-carrier chests (Demon / Judicator / Guardian /
  Royal / Hellion) are treated as comp-level allocations, never weapon
  identity: the dashboard shows the observed per-roster quota for each
  effect against the chests your roster has set.
- **Known model-vs-doctrine tension** (recorded, not hidden): in a
  4-healer comp the advisor does NOT surface Robe of Purity for healers,
  because template healing is COVERAGE-based and covered — while the
  doctrine runs Purity for healing THROUGHPUT beyond coverage. Deciding
  whether raw throughput deserves value past the target is an expert
  call for the templates (a `heal_throughput` capability or a softer
  heal soft-cap), queued for the next tuning pass.
- **Not yet**: gear inside the forge/recommend loops (the advisor and
  the loadout panel are live in the page, and kit_options IS mirrored
  and parity-checked in both engines — the remaining gap is the forge
  pricing gear while it generates).

### 8b. The role layer & forge structure — where those dials live

The forge no longer builds from capability math alone; it builds toward
an owner-ruled STRUCTURE. Those dials deliberately do NOT live in this
file — they live beside the role book, and every entry is cited:

| Dial | What it rules | Where |
| --- | --- | --- |
| Role book | seats, function roles, every weapon membership (evidence-cited) | `pipeline/roles.yaml` `roles:` |
| Kit-pool rulings | drop/add on the mined kit pools, per seat or per weapon | `pipeline/roles.yaml` `kit_doctrine.overrides` |
| Gear affinity rulings | replace a derived item-to-seat affinity | `pipeline/roles.yaml` `gear_affinity_overrides` |
| **Need profiles** | fine-seat bands + function coverage the forge must field (engage 2-3 / stopper 1-2 default, terry stopper-heavy; pierce & heal-cut always) | `pipeline/roles.yaml` `need_profiles` |
| Style role bands | healers/frontline/ranged-core per style & size (clap/clap_kite ranged core 7 at 20) | `pipeline/templates/styles.yaml` `constraint_overrides` |

Same safety promise as this file: the build fails loudly on an unknown
weapon, item, role or content id — a stale ruling never silently
no-ops. The grading board (`out/roles_report.json`) audits every mined
pool and override; `out/roster_mixes.json` holds the killboard roster
evidence the profiles were ruled against. Like every generation
constraint: these shape what the forge PRODUCES, never what a manual
party may score.

## 9. Guild-approved builds

The guild announcement, recorded 2026-08-20, structured but in the guild's
own words and weapon names. It ships into the dataset verbatim as a
**guideline layer**: visible in tooling, usable as a validation reference,
never a hard rule the scorer enforces. (Mapping the guild's weapon names to
game ids is a separate wiring step.)

```yaml tune:guild_builds
source: guild announcement — approved builds, group content
recorded: 2026-08-20
scope: castle/outpost content, everything listed is regear-eligible
status: guideline, not hard rules — "if your build isn't listed, ask"

legend:
  CORE: first choice — if you don't know what to play, play this
  APPROVED: regear-eligible, but don't bring it while a CORE slot is open
  size_tags:
    "5": best small-scale (5-10)
    "10": comes online at 10+
    "20": needs 20+ to matter
    bomb: bomb squad — spec-gated, not main zerg
    untagged: works at any size

standard_kit:
  cape: Smugglers 4.3 always; Lymhurst on healers with no Chariot
  potions: Gigantify — no choice, no substitutes
  food: >
    Ava Pork Omelette 7.1 default; Ava Beef Sandwich acceptable; brawl DPS
    run Beef Stew 8.1+; support tanks on Demon may run regular Beef Sandwich.
    7.1 food / 4.3 cape is the cost-efficient line.
  shoes: >
    Blink shoes standard in brawl and clap, Stalker usually favored.
    Exceptions: healers and some tanks run Royal Shoes (NOT Sandals).
  fallback_helm: >
    Melee and unsure? Cleric Cowl. Not always ideal, never wrong.

comp_rules:
  - "Under 10: at least 1 healer, at least 1 tank; don't stack all-melee or
    all-range; everything approved at larger sizes is approved here."
  - "10-man: minimum 2 healers, 3-4 tanks, rest DPS. Unusual picks genuinely
    work here (Primal Staff as a main is fine)."
  - "10-20 FILL ORDER: healer first, tanky support second, DPS last. Do not
    bring the 5th DPS while the 3rd healer slot is open — support needs grow
    faster than damage needs. Most common way comps go wrong."
  - "20+: caller declares clap/kite or brawl. 6 tanks minimum, 4 healers
    minimum, then DPS."
  - "Kite comps need at least 1 Occult Staff."
  - "Brawl zergs always, always run a Carving (as pierce tank)."
  - "Kite zergs practically never run Carving — Spirit Hunter or Damnation."
  - "Royal armor: minimum 2 Royals per 10 people for mana; can cut if
    there's a Chariot."
  - "Bomb squad is a separate group, spec-gated (~100 spec floor, often the
    whole tree). Join when the caller asks, not because it looks fun."

bomb_weapons: [Brimstone, Blazing, Wildfire, Infernal, Energy Shaper (most
  common), Weeping Repeater, Siegebow, Heavy Crossbow, Arclight Blasters]

roles_20plus:
  clump_tank:
    count: 1
    core: [Hand of Justice, Earthrune (Golem), 1H Mace]

  support_tanks_clap_kite:
    count: 5
    core:
      - Bedrock Mace x2 (Guard Rune, now hits 10)
      - Polehammer (Groundbreaker, 20m — longest-reach hard CC in the game)
      - Great Arcane (silence)
    armor: >
      Head Judicator Helm or Cleric Cowl; chest Knight, Demon, or
      Duskweaver; blink shoes (some zergs GG Boots or Boots of Valor).
    approved: [Grail Seeker, 1H Hammer, 1H Arcane, Icicle, Stillgaze,
      Black Monk Stave, Camlann Mace, Dreadstorm Monarch, Truebolt Hammer,
      Grovekeeper, Soulscythe, Primal Staff, "Forge Hammer (5, disrupt)"]

  tanky_support_pierce_clap_kite:
    count: 2
    core: [Spirit Hunter, Damnation]
    approved: [Oathkeepers, Life Curse, "Rootbound (midline — keeps the
      frontline topped, opens a retreat path)", Shadowcaller, Hoarfrost,
      "Locus (backline tank / cleanse bot)", "Occult (20+)"]

  support_tanks_brawl:
    count: 5
    core: ["1H Mace (offhand Kaitiff Shield or Astral Aegis)", Heavy Mace,
      Great Hammer, Staff of Balance]
    armor_split: >
      THE RULE, not a suggestion: roughly 50/50 Hellion Hoods and Judicator
      Helms, leaning toward extra Hellion Hoods. Most Hellion Hood tanks run
      Duskweaver armor; other tanks Judicator or Guardian. Blink shoes
      standard, Stalker usually favored. Unsure? Cleric Cowl.
    approved: [Grail Seeker, 1H Hammer, Bedrock Mace, Polehammer,
      Black Monk Stave, Camlann Mace, Dreadstorm Monarch, Truebolt Hammer,
      Grovekeeper, Soulscythe, Icicle, Stillgaze, Primal Staff,
      "Forge Hammer (5, disrupt)"]

  tanky_support_pierce_brawl:
    count: 2
    core: [Carving Sword, Oathkeepers]
    armor: >
      Support tank weapons run Judicator or Demon armor almost without
      exception (Oathkeepers, Life Curse, Rootbound, Shadowcaller,
      Hoarfrost, Locus).
    approved: [Life Curse, Rootbound, Shadowcaller, Hoarfrost, Locus,
      "Occult (20+)"]

  healers:
    minimum: 4
    filled_first: true
    core_holy: [Hallowfall, Redemption]
    core_nature: [Blight, Rampant]
    approved: ["Exalted (20+, required in some larger comps)", Forgebark,
      Fallen, Wild Staff, "1H Nature (5)", "Divine (5)", "Great Holy (5)"]
    never: [1H Holy, Lifetouch, Druidic Staff, Ironroot, Great Nature]

  dps_clap_kite:
    requirement: at least 1 Occult Staff in kite comps
    core: [Permafrost, Spirit Hunter, Rift Glaive, Realm Breaker,
      Spiked Gauntlets, Damnation, Rotcaller, Witchwork]
    scaling: "As the party grows: add Wailing and more Rift Glaives;
      possibly an off-timer Spiked for extra pierce."
    approved: ["Dawnsong (the one common zerg fire staff)", Astral,
      Evensong, Icicle, Hoarfrost, Arctic, Glacial, Mistpiercer, Badon,
      Skystrider, Lightcaller, Hellfire Staff, "Wailing (20+)"]

  dps_brawl:
    core: [Battle Bracers, Infernal Scythe, Realm Breaker, Ursine Maulers,
      Astral, Bloodletter, Demonfang, Galatine Pair, Bear Paws,
      Spiked Gauntlets, Hellfire Hands]
    note: "Demonfang is extremely strong right now — many brawl zergs run
      2, 3, or more. Don't treat it as a niche pick."
    scaling: "As the party grows: more of the above; possibly a Witchwork,
      Wailing, Permafrost, or a small kite/clap pocket for burst."
    approved: ["Carving Sword (fine as straight damage, but pierce tank is
      the better use)", Kingmaker, Dual Swords, Infinity Blade,
      Clarent Blade, Great Axe, Brawler Gloves, Spear, Heron Spear,
      Daybreaker, Hellspawn Staff, Quarterstaff, "Blood Moon (5)",
      "Demonic (5)"]

gear_sets:
  supports_not_support_tanks: >
    Usually Occult. Assassin Hood, Royal Jacket (no swaps allowed), blink
    shoes, Smugglers 4.3.
  healers_clap_kite: >
    Head depends on battlemounts — with Chariot at least 1 Assassin + 1
    Guardian; without, at least 2 Druid Cowls. Chest Robe of Purity or
    Feyscale, no real alternative (Cleric Robe under 10). Blink shoes
    (Merc/Stalker/Cleric/Royal). Smugglers 4.3, swap Lymhurst if no
    Chariot. Ava Pork Omelette, Gigantify.
  healers_brawl: >
    Same as clap/kite except: Judicator chest, Lymhurst cape priority,
    offhand Shield or Blueflame Torch.
  dps_clap_kite: >
    Head mostly Assassin for the reset, some swap to cleanse; 1 Knight
    Helmet; Mistwalker for melee DPS. Chest Scholar, Feyscale, Robe of
    Purity, or Royal Jacket. Blink shoes, sometimes Feyscale. Smugglers
    4.3, Gigantify, food Beef Stew or Ava Pork Omelette — check with
    caller.
  dps_brawl: >
    Head almost always Cleric (Soldier occasionally, Cleric just better).
    Chest Hellion almost always; Soldier for specific roles; Royal for
    mana with no Chariot. Stalker shoes for damage (Boots of Valor okay,
    Stalker almost always better). Smugglers 4.3, Beef Stew 8.1+,
    Gigantify.

battlemounts:
  status: not running them until we get better
  priority: [Chariot, Behemoth / Beetle, Eagle / Bastion / Ballista]
  build: >
    Same on all: Mace or Bloodletter, offhand Aegis or Mistcaller, chest
    Judicator or Guardian as high tier as affordable (T9 ideal, best
    defence per silver), helmet Soldier or Mistwalker (Soldier = more
    health), Feyscale Sandals 4.4 (cheapest optimal, no real alternative;
    4.3 fine).
```

---

## 10. House rules (how this stays trustworthy)

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
