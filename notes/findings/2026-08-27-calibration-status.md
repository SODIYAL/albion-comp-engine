# Calibration status — every tunable (2026-08-27)

Findings record. Artifact: `pipeline/out/calibration_report.json`
(`py -3 pipeline/calibrate_scoring.py --golden`). Headline: a SENSITIVITY
MAP, not a calibration.

## Context

Train n=4 (one caller, one content, answers given under the legacy
harness); validation and holdout splits EMPTY (`calibration/README.md`).
Under the calibration discipline no coefficient may move on this evidence.
Every value below is therefore kept at its shipped setting and marked
PROVISIONAL; "stable region" claims wait for populated validation and
holdout splits.

## Finding: per-tunable status

| tunable | current | swept | train signal | golden robustness | status |
|---|---|---|---|---|---|
| alpha | 0.55 | 0.30–0.80 | flat (top3 0.25, rank ~28 throughout) | 0 regressions anywhere | PROVISIONAL, keep |
| beta | 0.20 | 0.00–0.50 | flat | 0 regressions | PROVISIONAL, keep |
| delta | 0.15 | 0.00–0.30 | flat (rank drifts ~1) | 0 regressions | PROVISIONAL, keep |
| rho | 0.25 | 0.00–0.75 | flat | **1 regression at rho=0** (duplicate-penalty pin, by design) | PROVISIONAL, keep; rho=0 is structurally excluded |
| viability | 0.15 | 0.00–0.30 | flat | 0 regressions | PROVISIONAL, keep |
| gamma / headroom / overstack_max | 0.70 / 0.1 / 0.5 | self-check probes only | — | — | PROVISIONAL; Phase-10 ladders generated, awaiting caller answers |
| synergy bonuses (4 pairs) | 1.5 / 0.8 / 0.8 / 0.8 | 0–3.0 flip-point map | see below | — | PROVISIONAL, keep |
| style multipliers | styles.yaml | not swept | no styled caller picks exist | — | directional hypotheses (Phase 12 waits) |
| content targets / soft caps / floors | templates | not swept (comp-fitted 2026-08-21; outside the sweep by rule) | — | — | see the dressed-template audit: the unit scale predates dressed supply — a category-5 question for the validation rounds |

Two structural results hold even on thin data:

1. **The golden suite is coefficient-robust.** Across the entire Phase-8A sweep box, golden pins hold everywhere except rho=0 killing the duplicate-penalty pin. The suite pins structure, not coefficient knife-edges; future calibration inside these ranges will not fight the regression floor.
2. **Synergy bonuses cannot flip a pick contest even at 3.0** (≈2–4× current values) on the auto-constructed two-member discrimination parties: the specialist never overtakes the generic breadth pick for any pair. Caveat: those constructions are small and fitness-dominated. The real question ("does excellent AoE follow-up beat better generic coverage on a clump-strong comp?") is written into the report as `expert_question` per pair for the Phase-9 validation round. If callers systematically pick the specialist, the current magnitudes are too small — that would be the first genuine category-5 finding.

## Evidence: curve probes (Phase 10 scaffolding)

`curve_probes` in the artifact: 0/1/2/3-source ladders for purge, heal_sustain, engage, peel, clump_create, heal_reduction, resist_shred, sustained_dps, each with the engine's current marginal fitness of the next source and the question put to callers. Caveat recorded in the artifact context: engine marginals are full-body marginals (the supplying weapon's other caps and floor lifts ride along) — the questions isolate the concept; diminishing-return inference happens against the answers, not against these confounded engine numbers.

## What unblocks real calibration

1. A fresh V3-D validation round on the richer form (validation cases, then a holdout round).
2. The Phase-9/10 discrimination questions put to experienced callers.
3. The tankiness/frontline decision first — it dominates dressed behavior and would contaminate any coefficient fit run before it. Taken the same day: Option C (`2026-08-27-tankiness-frontline-finding.md`).

## Changes

None. No coefficient, target, floor, weight or score moved; the artifact is the only output.
