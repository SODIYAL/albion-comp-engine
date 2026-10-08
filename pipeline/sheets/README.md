# pipeline/sheets — capability curation

Weapon sheets (one file per weapon tree, each entry carrying its weapon's
E — the weapon's identity), the trees' shared Q/W/passive pools (`pools/`),
and gear sheets (`gear/`). Every nonzero score cites an evidence spell the
lint can ground (`pipeline/evidence_lint.py`). `reviewed_evidence.json`
keeps the fingerprint of every cited spell's facts (and each item's base
stats behind a stat row) from when the rows citing it were last read; when
the game-data snapshot moves, the lint fails on every row whose evidence
changed until it is re-read and accepted (`pipeline/evidence_review.py`).
`curated_as_of` records when an entry was curated. Score overrides live in
`MASTERSHEET.md` (`tune:sheets`), never edited into a sheet after the fact.

Scale: 1–7, `score_unit: 2` — two sheet points are one supply unit. The old
0–3 ordinals sit on the even slots (1→2, 2→4, 3→6); odd slots are for finer
judgments (1 = weaker than anything previously scored, 7 = beyond the old top).
Coarse on purpose: finer granularity is false precision.

## Layout

- `<tree>.yaml` — one file per weapon tree, named like its pool: the
  tree's subcategory in `out/weapon_lines.json` (`mace.yaml`, `bow.yaml`,
  `shapeshifterstaff.yaml`). A list of entries, one per weapon: its own rows
  (the E, and any override of a shared row), its `except:` list and its
  fields (`curated_as_of`, `role_hint`, `removed`).
- `pools/<tree>.yaml` — the tree's shared rows, curated once and composed
  into every weapon of the tree that can equip the evidence spell
  (`sheets_lib.compose`). A weapon whose own tree pool reaches none of its
  menu spells takes the spell rows of the pools whose spells it equips
  (Black Hands: knuckles subcategory, dagger menu; `sheets_lib.pool_rows_for`).
  An entry's own row with the same capability and evidence replaces the
  pool row (and must differ from it); an `except:` item declines one.
- `gear/<slot>.yaml` — one file per gear slot (`head`, `armor`, `shoes`,
  `offhand`, `cape`, `potion`, `food`); the actives an armor tree shares sit
  in `gear/pools/<slot>_<class>.yaml`, composed by `sheets_lib.compose_gear`.
- `illustrative/` — placeholder sheets without evidence, when any exist
  (none do): a curated entry shadows one, the lint does not read them, and
  the dataset is not a release while one is present.

## How rows score

Every composed row scores on its OWN spell's loadout bundle
(`build_dataset.build_loadout`): a player equips one spell per slot, and a
row counts when its spell is equipped (base-stat rows, `WEAPON_STATS` /
`GEAR_STATS`, are always on, and so is a potion's or meal's row, which
cites the spell the item casts: `gear_spells.json` `consume`, on no active
or passive menu). A score is the weapon's (or gear item's)
TOTAL for that capability with the spell equipped, not a per-spell
increment, so two rows of one capability on one weapon or gear item never
add: the item supplies the larger (`engine._merge_max`, both ports). An E
row and a shared Q/W row of the same capability on different spells
therefore both stand (an own row on the same spell replaces the shared
one); an E-row
comment that names a Q/W spell marks that spell's share of the E's score,
and the named spell's own shared row still scores on its own slot.
Different items and different members add as before. An `except:` item is
a deliberate non-take: a shared row this weapon does not receive
(curation judgment, stated in its comment). A MASTERSHEET override
re-ranks the weapon's own rows of the capability (a weapon with no own row
of it takes the re-rank on its shared rows); a zero removes the capability
from every row.

`evidence_lint.py` checks the layout beside the evidence (its rules 4–11;
an error blocks the release): the schema (known keys only, a score an
integer 1–7), the capability taxonomy (`CAPABILITIES`; the templates and the
effect map name nothing outside it), no duplicate row or `except:` item,
every `except:` item naming a pool row the entry would otherwise receive,
no own row repeating the shared row it shadows at the same score,
one definition per weapon key and per gear key, and placement (a weapon
entry in `sheets/<its subcategory>.yaml`, a gear entry in
`gear/<its slot>.yaml`, every `sheets/*.yaml` named after a weapon tree);
`curated_as_of` an ISO date, `role_hint` one of melee / range / tank /
healer / support, a gear `slot` one of the seven and the game data's own; a
weapon entry carries `weapon`, `curated_as_of`, `role_hint` and
`capabilities`, a gear entry `gear`, `slot`, `curated_as_of` and
`capabilities`, for a gear key the game data carries; either may carry
`self_costs` (what the item costs its own wearer, in sheet points, each
citing its spell: a weapon's cites its E, the one spell always equipped);
a pool file is named
after its tree and has the tree's sheet beside it; each layer cites its own
stat sentinel (`WEAPON_STATS` on weapon rows, `GEAR_STATS` on gear rows and
self costs).

## The rubric

Sheets grade 1–7 (the old 0–3 sits on the even slots; odd slots are for
finer judgments, 7 = beyond the old top; `score_unit: 2` in
`templates/scoring.yaml` keeps all calibration intact). The rubric below is
how new 1–7 judgments are made, refined against the worked case that proved
raw magnitude alone misleads: Bedrock's Primal Slam (18m throw + a wall that
persists 4s, ground-cast from 18m, ignores CC resistance, on a kit with Guard
Rune / Snare Charge / Defensive Slam) vs Iron-clad's whirlwind (12m, but the
caster must physically contact the diver while channeling). Every line of
that contrast is its own question.

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
   amplifier slot (Hallowfall + healing offhand); an off-hand carries no
   row (`gear/offhand.yaml`): its stats are its supply, through the
   build-stat channel (mechanics.yaml `build_stats`). The loadout model
   supplies the candidates.
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

The judging instruments are boards generated locally into `review/`
(gitignored, never committed): the stat chart
(`py -3 pipeline/build_stat_chart.py` — real numbers per capability,
spell-keyed, typed sub-groups, ranked on the vs-players number with a
different vs-mobs number shown as context, plus the per-spell fact line —
persistence, delivery, cast range, counter-immunity flags) and the
magnitude board (`py -3 pipeline/build_magnitude_review.py` —
score-vs-dumps-text audit boards over every composed row, `use:` variants
included). `py -3 pipeline/curate_helper.py <WEAPON>` prints one weapon's
evidence worksheet with the rows it scores today. Rebuild the boards after
sheet edits. Worked cases and every magnitude decision: the
`tests/VALIDATION.md` log.
