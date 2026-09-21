# Escape-healer floor — design (2026-09-21)

Status: design approved, not implemented. Plan to follow in
`notes/plans/`. Origin: V3 round 2, Castle Outpost 7 (log
`notes/validation/2026-09b.md`, "V3 round 2, Castle Outpost 7").

## Problem

At every size the party's disengage and mobility rows are met by worn
kit alone. The content targets are medians of dressed comps, and in the
three comps that fitted Castle Outpost the weapon-only mobility supply is
0, 1 and 6 units against a dressed supply of 6, 7 and 15 (the dressed
audit records the gear flipping the target on two of three). Once a party
is dressed, no weapon's own escape is worth anything to the score, so the
healer seat is chosen on the heal rows alone and a stationary two-hander
outranks the mobile one-hander in every case where a healer is the pick.

The party-sum model cannot express what the caller is choosing: that one
healer should carry an escape on the weapon itself, beyond the baseline
every healer already gets from boots and a defensive chest. A row-level
fix was measured and rejected: with gear removed from the two rows and
the targets left as fitted, top-3 agreement on the reviewed form rises to
58%, but only because a target of 7 becomes unreachable by weapons; with
the targets re-fitted to weapon-only medians it falls to 33%. Neither is
the mechanism.

## Evidence

Fully known killer parties on the TRAINING split (`battle % 5 != 0`) that
field at least one healer, and the share fielding at least one healer
whose own sheet carries mobility or disengage at 2 points or more
(Hallowfall, Blight Staff):

| Size | n | At least one escape healer |
|---|---|---|
| 6-8 | 3,250 | 50% |
| 9 | 747 | 73% |
| 10-14 | 2,931 | 85% |
| 15-19 | 3,827 | 95% |
| 20+ | 978 | 97% |

Per labelled style at 10+ the share is uniform (brawl 90 / 97 / 99%,
clap 85 / 95 / 97%, kite 79 / 93 / 96%, clap_kite 84 / 95 / 97%), so the
floor is not style-conditioned. "Every healer carries an escape" is NOT
what winners field (46% at 10-14, 25% at 20+): the rule is one body, not
the seat.

Below 10 the typical winner does not field one (50% at 6-8), so the floor
cannot arm there (standing rules 3 and 17). The Castle Outpost 7 miss that
surfaced the mechanism stays open; it is logged as the prior-weight
question and waits on validation rounds (standing rule 16).

## Decisions

1. **A flag predicate `escape_heal`**, beside `primary_heal` and
   `standoff`. A member satisfies it when its primary seat class is
   `healer` (`Engine._primary_seat_class`, the one role read) and the RAW
   caps of its RESOLVED loadout (`_raw_member_caps(weapon, combo)`: sheet
   always-on plus the chosen bundle per slot) carry `mobility >= 2` or
   `disengage >= 2` in sheet points. Hallowfall qualifies on its E with
   every combo; Blight Staff qualifies only with its mobility spell
   equipped (one spell per slot: supply comes from resolved combos, never
   a kit's union). Worn gear never counts: the predicate reads the weapon
   and loadout basis only, so boots and chests, which give every healer a
   baseline escape, cannot satisfy it. Cached per (weapon, combo) like
   every predicate; both ports.
2. **A seat floor in every content template's `hard_floors`:**
   `escape_heal: {min_party_size: 10, min_members: 1, penalty_mult: 0.5,
   weight_of: heal_sustain}`. Armed when the party is at least
   `min_party_size` and fewer than `min_members` members satisfy the
   predicate. Penalty = `penalty_mult` x weight(`weight_of`) x
   (`min_members` - count) / `min_members`. At heal_sustain weight 10 an
   open floor costs 5 points: below the primary-heal floor's 20 at zero
   healing (a healer-less party still asks for healing first) and above
   the roughly one-point fit gap between healers (an escape healer wins
   the healer seat while the floor is open). Once met, healers rank on
   their heal rows as today. `penalty_mult` is PROVISIONAL and lives in the
   template row (the tune channel addresses requirement rows only);
   `min_party_size` is hand-set and cited to
   the table above, as every existing floor is. Roads never reaches 10
   in game and keeps the row for uniformity; Castle Outpost arms when the
   plan grows past 9.
3. **Where it scores.** The party term is added in `fitness()` beside the
   capability floor penalties. The candidate term is the exact delta of
   that penalty for adding the candidate with the combo under evaluation,
   computed inside the per-combo scoring (`_combo_score` and
   `_combo_score_dressed`), because the combo decides Blight's
   membership. `party_state` carries the current count. `_eval_pick` and
   `_forge_eval_pick` share the path, so the forge's pick and the page's
   pick keep the F1 equality. Dressed and naked candidates read the same
   weapon-only basis (Option C), so a kit can never buy floor relief.
4. **A generation minimum.** The constraint bands from `min_size: 10`
   upward gain `escape_heal: {min: 1}`, counted through the predicate
   machinery like `primary_heal`. The primary-heal minimum keeps priority
   in the fill logic; the seat skeleton's healer typical bounds the
   bodies, so the escape healer takes one of the typical healer seats and
   never adds a body.
5. **Provenance.** `audit_style_rosters.py` reports, per band, the share
   of winners fielding an escape healer (one report-only line beside the
   seat rows), so each fold shows drift against the cited arming size.
   Nothing generates the floor; a change to `min_party_size` is a logged
   decision citing the board.
6. **Display.** The engine exposes `escape_floor(party, combos)` returning
   `{armed, count, need}`; the page renders a roster note ("no healer
   carries its own escape") when armed and short. The UI computes
   nothing.

## Rule precedence

Minima and floors, in the order they bind: the capability hard floors
(heal_sustain, tankiness) and the primary-heal minimum; then the escape
floor and minimum; then the seat skeleton's typicals; then the scalar.
An escape healer never displaces the primary healer: a party of one
healer at 10+ that is Hallowfall satisfies both; a party whose only
healer is Great Holy pays the escape floor, not the primary-heal floor.

## Data shapes

Template row (every content yaml, `hard_floors`):

```yaml
escape_heal: {min_party_size: 10, min_members: 1, penalty_mult: 0.5, weight_of: heal_sustain}
```

Constraint band rows (`composition.yaml`, `min_size >= 10`): `escape_heal: {min: 1}`.

Engine constants: `ESCAPE_HEAL = "escape_heal"`; predicate thresholds
`ESCAPE_HEAL_MIN_PTS = 2` on `mobility` / `disengage` (sheet points, the
unit the other predicates are calibrated on).

Dataset: no new stamped field; the predicate derives at engine load from
the sheets and the role book, both ports identically.

## Engine changes (both ports)

- Predicate membership: `_pred_contrib` (Python) / the predicate contrib
  mirror (JS) add `ESCAPE_HEAL` under the seat-class and raw-caps test;
  `_pred_possible` and `pred_members` carry the flat could-qualify view.
- `set_content`: read the floor row; arm by size; resolve `weight_of`.
- `party_state`: `escape_count`.
- `fitness`: subtract the penalty at the party's count.
- `_combo_score`, `_combo_score_dressed`: add the exact penalty delta for
  the candidate's combo (count -> count + 1 when the combo satisfies).
- `explain`: one term `escape_heal` when the delta is positive, so the
  "why" text names it.
- `escape_floor(party, combos)` for display.
- Constraint bands: `escape_heal` counted like `primary_heal` in
  feasibility, eval, audit and the deadlock guard.

## Tests

- Golden: at Blackzone Roam 12 a healer-less roster ranks Hallowfall over
  Great Holy dressed and naked; the same roster at Castle Outpost 7 is
  unchanged from the shipped ranking (floor unarmed); every existing case
  holds.
- Forge: a forged 20 in each style fields at least one escape healer
  within the healer typical, and the forged healer count does not grow.
- Validation modes: Great Holy in Cleric Sandals on a 12-man does not
  satisfy the floor (gear never buys floor relief).
- Predicate: Hallowfall satisfies with every combo; Blight only with the
  mobility spell; no non-healer satisfies; no hand list exists.
- Parity: the 60 random parties already cover sizes at and above 10 with
  combos; add one directed case at 12 with Blight on and off its mobility
  spell.
- Tier-2 gate (`v4`) and `v4h` report-only, before and after.
- Tone on every touched file.

## Deferred, with reasons

- **A derived `healer_escape` capability row** (targets from the style
  board): the cleaner long-term shape, but its numbers regenerate only on
  the harvest machine and no fit exists below 10. Revisit once the floor
  has a round behind it.
- **The Castle Outpost 7 miss.** Not groundable as a floor (50% at 6-8);
  logged as the prior-weight question.
- **Self-immunity as an escape fact.** Would need a new dumps extraction;
  the sheet rule covers the two healers that carry one today.
