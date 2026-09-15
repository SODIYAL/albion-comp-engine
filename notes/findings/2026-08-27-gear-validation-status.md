# Gear validation report — status (2026-08-27)

Findings record. **Status: RETIRED 2026-09-10 — the cards, generator and answer key were deleted; `test_roles.py` R24 grades the kit advisor against the killboard modal item per slot continuously, which supersedes 16 hand-answered cards.** (Original status: cards generated, awaiting caller answers; nothing could be validated until a validation round ran.)

## Context — what existed

- **16 blind cards** (`tests/gear_form.md`, from `py -3 tests/gear_blindtest.py generate`) covering the Task-6A matrix: engage-tank head/shoes (brawl), stopper-tank cape/offhand, main-healer offhand/potion, clap ranged-DPS chest/shoes, brawl-DPS chest, kite-DPS shoes, anti-heal head/chest, pierce-support head/chest, defensive-support head/chest. Each card: a real published-comp roster as context, a role-book representative weapon, 3 doctrine-tier options + 1 off-tier distractor, deterministic letter shuffle. **The engine's answer never appears in the form** (asserted at generation); the hidden key was `tests/out/gear_form_answers.json`.
- **Relative-ranking scoring** (`score <filled form>`): engine-top agreement plus per-item preferred/acceptable/situational/bad ratings collected into `tests/out/gear_ratings.json` — the Task-6B philosophy (Cleric Cowl > Graveguard for this seat; never "2.3 points").

## Standing inputs queued for the same validation round

- The combat-expansion sheet's judgment scores flagged for review in `sheets/gear/combat_expansion.yaml`, and the potion rows — queued since T22 (2026-08-27).
- The synergy-source question (Model 1 vs 2) has its own finding; a card validation round can carry the discrimination question.

## Rules for processing answers

Disagreements are doctrine/capability review items that need a maintainer decision — a mechanical disagreement (a stat or ability misread) may fix a sheet with citation; a taste disagreement becomes a doctrine-tier decision (`kit_doctrine.overrides` / `gear_affinity_overrides`), recorded as curation judgment. **Never** an automatic capability-score change. Caller ratings land in `calibration/expert_answers/` and structured copies in `calibration/cases.yaml` (kind: `gear_slot`).

## Changes

None from this record; the card machinery was retired 2026-09-10 in favour of R24.
