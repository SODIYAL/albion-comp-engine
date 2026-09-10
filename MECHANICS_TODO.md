# Game-Mechanics Modeling — the Q ledger

Goal: teach the engine real fight mechanics (Focus Fire / Resilience, AoE
escalation, Disarray, …) via numbers supplied by the expert. They modify
**capability supply vs target** in `engine/engine.py` +
`engine/app_scoring.js` (change one, change both, rerun parity).

Status: the three ZvZ mechanics are WIRED as supply-side effectiveness
multipliers since 2026-08-13, the geometric AoE utility scaling since
2026-08-20, per-weapon Resilience Penetration since 2026-08-25. Canonical
data home: [pipeline/templates/mechanics.yaml](pipeline/templates/mechanics.yaml)
(the Focus-Fire / Resilience and AoE-Escalation tables in it are
OWNER-VERIFIED against the live wiki, 2026-08-25 — "single target damage
is punished in large groups and aoe damage is rewarded in larger groups";
patches through 31.030.1 touched none of them) and
`pipeline/resilience_penetration.yaml` (the cited 69-row melee table).

This file is the ledger the code cites by Q-number: the standing geometric
ruling, what is deliberately not wired, and one line per closed question.
Open mechanics work is in `BACKLOG.md` (per-spell `burst_aoe` gating Q9/Q10,
the enemy model Q2/Q5, asymmetric numbers Q11/Q13, the dive style, the
magnitude audit queues).

## Standing ruling — geometric AoE utility scaling (expert, 2026-08-20)

Kept in full because `engine/engine.py` (`_geo_mult`) and
`mechanics.yaml` cite it here. Trigger: Soulscythe (catch 1, from
Tornado's 80% AoE slow) ranked level with Battleaxe (catch 1, from a
self-haste W) as a catch alternative in a large comp. The cheap fix (bump
Soulscythe to catch 2) was REJECTED as papering over the structural gap:
the engine had no multi-target term for utility capabilities at all.

Four decisions, all confirmed by the expert:

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
4. **Q9 approved**: extract per-spell escalation eligibility from
   ao-bin-dumps; wiki lists serve as validation, not source of truth.

Shipped the same day in both ports (T18/T18b): AoE-delivered supply for
`geometric_caps` scales with min(style clump, spell reach) /
min(`reference_clump`, reach), with CC-duration escalation composing where
the spell carries a dumps factor. `reference_clump: 2` anchors the unit at
small-gang scale — the (balanced, base_size) anchor was measured DEAD
(base clumps exceed every spell's reach, so it could never up-rate AoE at
the calibrated sizes). Soulscythe catch: 1.5x@roads5 → 3.0x@20+ vs
Battleaxe's flat 1.0 — the motivating failure.

## Not wired (deliberate)

- Disarray: recorded in mechanics.yaml only — cancels in a mirror fight
  (Q11); revisit if templates gain an expected-enemy-size field.
- CC Escalation: `stun` IS wired (geometric transform + the dumps-derived
  duration factor, Q8 — `mechanics.yaml` `cc_duration_caps`); only
  `clump_create` stays untouched.
- Per-spell `burst_aoe` escalation eligibility: extracted, NOT wired —
  BACKLOG.md.
- Mob HP bonus (+10% max HP per player over a per-mob-type threshold):
  PvE, out of scope.

## Closed — one line each

- **Q1** form of numbers — global tables in mechanics.yaml, per-spell parts through sheets/overrides (2026-08-13).
- **Q3** which focus-fire mechanic — overkill saturation via the Resilience table, a supply-side transform, not a synergy (2026-08-13).
- **Q4 / Q12** Disarray numbers and table staleness — answered, recorded in mechanics.yaml, unwired (2026-08-13 / 2026-08-25).
- **Q6** AoE escalation magnitudes — 8%/target from 2, cap 56% at 8, after buffs, bypasses the soft cap (2026-08-13).
- **Q7** Resilience Penetration — WIRED 2026-08-25 as a supply-side rebate on burst_st/execute at the style's grown focus count, the owner-approved "partial rebate" ("single target is just a non pick at 20+ usually ... you can wire it as partial rebate"); F20 pins it. Optional: dumps cross-check of the wiki values.
- **Q8** CC Escalation duration curve — from the dumps, same per-target factor as damage (0.08; Spirit Animal 0.25); published nowhere else (2026-08-20).
- **Q9** per-spell escalation eligibility — extracted from the dumps, 174/559 (2026-08-20).
- **Q10** uniform AoE-class escalation — REFUTED (2026-08-20); see open item 1.
- **Q14** per-style mechanics numbers — owner-delegated with the ordering rule (2026-08-25); see open item 2.
- **Q15** weapon playstyle affinity — derive + curate exceptions (owner 2026-08-23): `derive_style_fit` + `style_overrides.yaml`; audit `out/style_fit_report.json`.
- **Q16** content-absolute physics — the `size_physics` tables (`st_value_mult`, `count_mult`, composition.yaml) received owner sign-off 2026-08-25 ("ok that seems fair"); F8/T15/T16 pin them. The 2026-08-14 `grow()` build was superseded 2026-08-18.
- **Q17** usage-derived MetaPrior — SUPERSEDED 2026-09-08: the meta prior is GENERATED from the killer-party harvest (`derive_meta_prior.py`, one player one vote, per size bucket, T46/H18); the usage_v2 build and its artifact are gone.
- **Q18** breadth/redundancy scoring penalty — INVESTIGATED + REJECTED 2026-08-14 (a rho sweep never earned its place; the engine already de-ranks breadth picks by context). The *descriptive* decomposition shipped later as `pick_report`.
- **Q19** one-spell-per-slot loadout model + single-target recalibration — SHIPPED 2026-08-14 (T14/T15); the Dagger-Pair-at-scale case fixed here (#3 → #33).
- **Geometric AoE utility scaling** — expert ruling 2026-08-20, shipped the same day (spell-level sheets, delivery physics from dumps, the transform in both ports; T18/T18b).
- **First wiring checklist** (2026-08-13): mechanics.yaml shipped in the dataset; supply-side multipliers per style normalized to balanced; both ports; T11 family.
- **Magnitude RULE queue** — adjudicated wholesale 2026-08-25 ("the batch is fine, just test it internally"), one reversal (Rotcaller keeps the line's 4: "1 hand allows for adding an offhand, which can INCREASE damage"); `knockback_displace` ladder done earlier (T13).
- **Gear sheets** — `pipeline/sheets/gear/core.yaml` (2026-08-20) + `combat_expansion.yaml` (2026-08-27, 129 pieces).
- **Stage 2 — live companion** — LIVE-CONFIRMED end to end 2026-08-23 (`companion/README.md`); inspect parsing + worn kits into loadouts 2026-09-06.
- **Spell picks into scoring** — live sync maps real Q/W into the loadouts (2026-08-23), worn kits too (2026-09-06).
- **Reliability roadmap layering** (2026-08-13) — mechanism (sheets + lint), physics (mechanics + size tables), empirics (parked, Q17), expert loop (running: every correction becomes a golden case). Weapon tagging reliability = cross-source agreement (sheets × killboard role × MetaBattle tags), never authorship.
