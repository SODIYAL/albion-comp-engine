# Finding: should gear-sourced capabilities trigger synergy pairs?

**Date:** 2026-08-27 · **Status:** MEASURED, recommendation below · **Owner decision required before any implementation.**

Evidence artifact: `pipeline/out/gear_synergy_audit.json` (report-only; the "if gear counted" numbers are labeled hypotheticals computed by mirroring the engine's own pair rule — no scoring path was touched).

## 1. Current semantics (deliberate, from the dressed-forge design)

`comp_score` = alpha·fitness(party, combos, **gears**) + beta·synergy(party, combos) — fitness prices the full build, synergy prices weapons only (`synergy()` has no gears parameter; J, the largest single member's joint supply, reads `member_extra`, also weapon-only). So Hood of Tenacity's heal cut never feeds `heal_reduction × sustained_dps`, a Judicator wearer's engage never feeds `engage × catch`.

## 2. What was measured

**Minimal constructions** (blackzone_roam, pair active, one side supplied ONLY by a worn item on a cap-neutral weapon):

| pair (bonus) | forgone pair units, gear-A side | gear-B side |
|---|---|---|
| clump_create × burst_aoe (1.5) | 2.25 | 2.12 |
| engage × catch (0.8) | 1.20 | 0.80 |
| resist_shred × burst_st (0.8) | 0.68 | 0.68 |
| heal_reduction × sustained_dps (0.8) | 1.20 | 0.00 |

At beta 0.20 the forgone score is **0.14–0.45** per construction — real but small next to typical pick marginals. (Side note captured in the artifact: the weapon+weapon heal_reduction×sustained_dps case pays 0 even naked — the best sustained-damage carriers also carry heal-cut, so J swallows the pair; a pre-existing formula quirk, not a gear issue.)

**Real-comp practice check** (blap, 20 members, actual recorded kits): if gear counted, total pair value would **fall by 0.56 units (−0.112 score)**. Mechanism: on a real comp the pair sides are already capped at their targets, so gear adds nothing to `min(sides)` — but members' dressed vectors now hold both halves personally (a clump weapon whose kit adds burst), so **J rises** and the subtraction deepens. Under the current formula, gear participation is not "more synergy credit"; on saturated real comps it is *less*.

## 3. Options

**Model 1 — capability synergy (gear triggers).** Philosophically consistent with the capability model, and gear actives genuinely perform these game actions. But the measurement shows it is **not a toggle**: with the current J-subtraction it produces perverse negative movement on real comps, so adopting it means redesigning J's semantics for dressed vectors (a category-3 mechanical-model change) plus recalibrating beta/bonuses — none of which has expert evidence yet.

**Model 2 — weapon-interaction synergy (status quo, documented honestly).** The pairs encode *play patterns between members' jobs* (clump-maker sets up the bomber; engage sets up the catch). A member's weapon is that job; worn-gear caps are garnish with small magnitudes (the four pairs' gear suppliers are 1–8 items scoring 2–4). Keeps the seam the dressed-forge design chose deliberately. Costs nothing now; forgoes at most ~0.45 score in adversarial minimal cases and nothing (negative) on the real comp measured.

**Model 3 — source-specific per pair.** More machinery with no mechanical justification measured today.

## 4. Recommendation

**Model 2 — keep synergy weapon-only, and rename/document the concept as "weapon-interaction synergy"** (scoring.yaml comment block, engine READMEs, HANDOFF) so it is never again read as generic capability synergy. Revisit Model 1 only through the calibration path: Phase-9 discrimination cases can put "does a gear-sourced heal-cut make the sustained-damage pick better?" to experts, and any adoption must co-design the J rule for dressed vectors. No code change now; documentation lands with this pass.

## 5. Decision needed from the owner

1. Confirm Model 2 (weapon-only synergy) as the documented semantic — or direct the Model-1 redesign onto the calibration backlog.
2. The J-quirk noted above (self-supplied pairs swallowing genuinely paired parties on the heal-cut pair) is logged for the synergy-bonus calibration phase; no action proposed now.
