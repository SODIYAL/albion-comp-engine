# Calibration Report — status of every tunable

**Date:** 2026-08-27 · **Artifact:** `pipeline/out/calibration_report.json` (`py -3 pipeline/calibrate_scoring.py --golden`) · **Headline: SENSITIVITY MAP, NOT A CALIBRATION.**

Data situation: train n=4 (one expert, one content, answers given under the legacy harness), validation and holdout EMPTY (`calibration/README.md`). Under the work-order rules no coefficient may move on this evidence. Every value below is therefore **kept at its shipped setting and marked PROVISIONAL**; "stable region" claims must wait for populated validation/holdout splits.

## Per-tunable status

| tunable | current | swept | train signal | golden robustness | status |
|---|---|---|---|---|---|
| alpha | 0.55 | 0.30–0.80 | flat (top3 0.25, rank ~28 throughout) | 0 regressions anywhere | PROVISIONAL, keep |
| beta | 0.20 | 0.00–0.50 | flat | 0 regressions | PROVISIONAL, keep |
| delta | 0.15 | 0.00–0.30 | flat (rank drifts ~1) | 0 regressions | PROVISIONAL, keep |
| rho | 0.25 | 0.00–0.75 | flat | **1 regression at rho=0** (duplicate-penalty pin, by design) | PROVISIONAL, keep; rho=0 is structurally excluded |
| viability | 0.15 | 0.00–0.30 | flat | 0 regressions | PROVISIONAL, keep |
| gamma / headroom / overstack_max | 0.70 / 0.1 / 0.5 | self-check probes only | — | — | PROVISIONAL; Phase-10 ladders generated, awaiting expert answers |
| synergy bonuses (4 pairs) | 1.5 / 0.8 / 0.8 / 0.8 | 0–3.0 flip-point map | see below | — | PROVISIONAL, keep |
| style multipliers | styles.yaml | not swept | no styled expert picks exist | — | directional hypotheses (Phase 12 waits) |
| content targets / soft caps / floors | templates | not swept (owner-ruled 2026-08-21) | — | — | see dressed-template audit: unit scale predates dressed supply — a category-5 question for the rounds |

Two structural results worth keeping even from thin data:

1. **The golden suite is coefficient-robust.** Across the entire Phase-8A sweep box, golden pins hold everywhere except rho=0 killing the duplicate-penalty pin. The suite pins structure, not coefficient knife-edges — future calibration inside these ranges will not fight the regression floor.
2. **Synergy bonuses cannot flip a pick contest even at 3.0** (≈2–4× current values) on the auto-constructed two-member discrimination parties: the specialist never overtakes the generic breadth pick for any pair. Caveat honestly: those constructions are small and fitness-dominated; the real question ("does excellent AoE follow-up beat better generic coverage on a clump-strong comp?") is written into the report as `expert_question` per pair for the Phase-9 round. If experts systematically pick the specialist, the current magnitudes are too small — that would be the first genuine category-5 finding.

## Curve probes (Phase 10 scaffolding)

`curve_probes` in the artifact: 0/1/2/3-source ladders for purge, heal_sustain, engage, peel, clump_create, heal_reduction, resist_shred, sustained_dps, each with the engine's current marginal fitness of the next source and the expert question. Caveat recorded in-artifact context: engine marginals are full-body marginals (the supplying weapon's other caps and floor lifts ride along) — the expert questions isolate the concept; diminishing-return inference happens against their answers, not against these confounded engine numbers.

## What unblocks real calibration

1. A fresh V3-D round on the richer form (validation cases, then a holdout round).
2. The Phase-9/10 discrimination questions put to experienced callers.
3. The tankiness/frontline ruling first — it dominates dressed behavior and would contaminate any coefficient fit run before it.
