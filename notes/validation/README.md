# notes/validation — the ruling log archive

The full text of every validation round, owner ruling and finding, moved here
verbatim from `tests/VALIDATION.md` on 2026-09-10 when that file became the
index. Nothing was condensed in the move; the files are the history.

```text
2026-08-12-plan.md   the original tiered plan (V1–V8), written before building
2026-08.md           2026-08-13 → 2026-08-29: V3/V4 rounds, the role layer, gear,
                     the unit re-fit, the killboard party harvest
2026-09a.md          2026-09-01 → 2026-09-05: fail-closed kits, the kit audit,
                     identity blind rounds 1–3, style x band rows, gang band
2026-09b.md          2026-09-07 → 2026-09-10: cost gate retired, blind round 4,
                     style cells, the generated meta prior, the folds, R36/F29
```

Rules for this directory:

- **Append-only.** New rounds and rulings go at the bottom of the newest file,
  dated, with the owner's words quoted and the pin (golden T / forge F / roles R
  / validation-modes V) named. Start a new file when the newest passes ~1,000
  lines; name it by the date range it covers.
- **Every entry gets an index row** in `tests/VALIDATION.md` the same day: date,
  the ruling in a line, what it governs, the pin, and the file + section here.
- **Never edit a past entry.** A ruling that is later overruled gets a new entry
  and the index row says `superseded`; history is data.
- Code and yaml cite entries as `VALIDATION.md <date>` or by section title;
  the index resolves both. Do not rename section headings.
