# pipeline/sheets — capability curation

Weapon sheets (`*.yaml`, one per weapon, carrying its E — the weapon's
identity), tree-shared Q/W pools (`pools/`), and gear sheets (`gear/`).
Every nonzero score cites an evidence spell the lint can ground
(`pipeline/evidence_lint.py`); `curated_as_of` lets `patch_history` flag a
sheet whose cited spell a later patch changed. Expert score overrides live
in `MASTERSHEET.md` (`tune:sheets`), never edited into a sheet after the fact.

Scale: 1–7, `score_unit: 2` — two sheet points are one supply unit. The old
0–3 ordinals sit on the even slots (1→2, 2→4, 3→6); odd slots are for finer
rulings (1 = weaker than anything previously scored, 7 = beyond the old top).
Coarse on purpose: finer granularity is false precision.

## The rubric (canonical, 2026-08-20)

Sheets now grade 1–7 (the old 0–3 sits on the even slots; odd slots are
for finer rulings, 7 = beyond the old top; `score_unit: 2` in `templates/scoring.yaml` keeps all
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

Judging instruments: `review/stat_chart.html` (`py -3 pipeline/build_stat_chart.py`)
and `review/magnitude.html` (`py -3 pipeline/build_magnitude_review.py`).
Worked cases and every magnitude ruling: the `tests/VALIDATION.md` index.
