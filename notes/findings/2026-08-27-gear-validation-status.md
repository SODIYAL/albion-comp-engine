# Gear Validation Report — status

**Date:** 2026-08-27 · **Status: cards generated, awaiting expert answers.** Nothing can be "expert-approved" until a human round runs — this report will be completed then.

## What exists now

- **16 blind cards** (`tests/gear_form.md`, from `py -3 tests/gear_blindtest.py generate`) covering the Task-6A matrix: engage-tank head/shoes (brawl), stopper-tank cape/offhand, main-healer offhand/potion, clap ranged-DPS chest/shoes, brawl-DPS chest, kite-DPS shoes, anti-heal head/chest, pierce-support head/chest, defensive-support head/chest. Each card: a real published-comp roster as context, a role-book representative weapon, 3 doctrine-tier options + 1 off-tier distractor, deterministic letter shuffle. **The engine's answer never appears in the form** (asserted at generation); the hidden key is `tests/out/gear_form_answers.json`.
- **Relative-ranking scoring** (`score <filled form>`): engine-top agreement plus per-item preferred/acceptable/situational/bad ratings collected into `tests/out/gear_ratings.json` — the Task-6B philosophy (Cleric Cowl > Graveguard for this seat; never "2.3 points").

## Standing inputs already queued for the same round

- The combat-expansion sheet's judgment scores flagged "owner review" (`sheets/gear/combat_expansion.yaml`) and the potion rows — queued since the 2026-08-27 T22 session.
- The synergy-source question (Model 1 vs 2) has its own finding; a card round can carry the discrimination question.

## Rules for processing answers

Disagreements are doctrine/capability **review items for the owner** — mechanical disagreements (a stat or ability misread) may fix a sheet with citation; taste disagreements become doctrine-tier rulings (`kit_doctrine.overrides` / `gear_affinity_overrides`). **Never** an automatic capability-score change. Expert ratings land in `calibration/expert_answers/` and structured copies in `calibration/cases.yaml` (kind: `gear_slot`).
