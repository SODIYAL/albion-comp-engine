# Calibration layer — expert cases, splits, and discipline

**Created 2026-08-27 (dressed validation & calibration hardening pass).**
This directory is the durable home for expert-labeled recommendation
cases and the train/validation/holdout discipline that keeps accuracy
claims meaningful. `pipeline/calibrate_scoring.py` consumes it and
writes `pipeline/out/calibration_report.json`.

## Files

- `cases.yaml` — every expert case, one record each (schema below).
  Cases are append-only; a case whose answer is later overruled keeps
  the original blind answer and gains a `superseded:` note — history is
  data.
- `train_cases.yaml` / `validation_cases.yaml` / `holdout_cases.yaml` —
  split manifests (lists of case ids). A case id appears in exactly one.
- `expert_answers/` — raw filled blind forms (tier2 V3 forms, gear card
  forms) as received, one file per expert per round. The YAML cases cite
  them.

## Case schema

```yaml
- id: v3r1-case2                # unique, stable
  kind: next_pick               # next_pick | gear_slot | need_diagnosis
  source: "tests/VALIDATION.md 2026-08-23 round 1 (in-chat, n=1 owner)"
  content: castle_outpost
  size: 7
  style: balanced
  party: [KEY, KEY, ...]        # incumbent weapon keys
  gears: null                   # per-member kits where the case records them
                                # (null = none recorded; scoring modes decide
                                # doctrine vs naked, and record which they used)
  expert:
    need: null                  # PRIMARY NEED, expert's words (or null)
    best: 2H_CURSEDSTAFF        # resolved weapon key
    good: []                    # acceptable alternatives
    bad: null                   # veto pick
    confidence: null            # high | medium | low | null
    reason: "…verbatim where documented…"
  superseded: null              # later owner ruling, verbatim + date, if any
  notes: null
```

## The discipline (Phase 7A — read before touching any split)

- **TRAIN** — may be inspected freely while changing the model. Every
  case that has ever been discussed in a session, converted to a golden
  test, or used to motivate a change is train-contaminated and can never
  leave train.
- **VALIDATION** — used to COMPARE candidate parameter settings during a
  sweep. Look at aggregate metrics, not individual cases; a validation
  case that gets individually debugged moves to train.
- **HOLDOUT** — **never examined while tuning.** Collected in fresh
  expert rounds, scored only when a tuning round is declared finished,
  and reported separately. Do not convert holdout misses into golden
  tests until the evaluation round is complete (work-order rule). After
  a holdout set has been scored against and iterated on, it is spent —
  retire it to validation and collect a new one.
- **Anti-circularity bridge** (tests/VALIDATION.md standing rule): cases
  derived from comps that calibrated a template must be marked in
  `notes:` and never drive retuning of that template's numbers.
- Golden tests remain the regression floor and are all
  train-contaminated by definition.

## Current state (2026-08-27, honest)

- 4 seeded train cases transcribed from the one V3 round that has run
  (2026-08-23, n=1 expert — the owner — castle_outpost only, mostly
  role-level answers; only the named-weapon answers are seeded).
  The round's aggregate (12/12 role-level, engine top-3) is recorded in
  VALIDATION.md; the 8 cases without documented per-case answers are NOT
  seeded — nothing is invented.
- **Validation and holdout are EMPTY.** They can only be filled by new
  expert rounds (fresh seeds, more contents/sizes/styles, and ideally
  experts beyond the owner). Until they exist, every sweep in
  `calibration_report.json` is a SENSITIVITY MAP, not a calibration —
  no coefficient may move on train evidence alone.
