# Raw expert answers

Filled blind forms land here verbatim, one file per expert per round —
`YYYY-MM-DD-<round>-<expert>.md` (e.g. `2026-09-02-v3r2-owner.md`).
Forms come from:

- `py -3 tests/tier2_blindtest.py generate` (next-pick rounds — richer
  fields: PRIMARY NEED / BEST PICK / OTHER GOOD PICKS / BAD PICK /
  CONFIDENCE / REASON)
- `py -3 tests/gear_blindtest.py generate` (gear doctrine cards)

Never edit a received file; corrections are new files. The structured
copies in `../cases.yaml` cite the raw file they were transcribed from.
The 2026-08-23 round 1 answers exist only as prose in
`tests/VALIDATION.md` (in-chat protocol) — cited there directly.
