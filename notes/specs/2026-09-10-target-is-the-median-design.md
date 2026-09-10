# Target is the median — design

Date: 2026-09-10. Status: SHIPPED 2026-09-10 (branch `target-median`).
Deviations from the draft, each recorded in `notes/validation/2026-09b.md`
"Target is the median": (1) the owner added a FOUR-STAGE board mid-build
("red below the bare minimum for winning, orange above it but not yet
ideal, green at ideal, purple too much"), so every row also carries `min`
= p10 / least fitted comp, exposed as `target_min()`; (2) the content
re-fit also RAISES a soft cap to 1.15 x the most any comp fielded where a
comp exceeded the old cap (several medians sat above their caps) and never
lowers one; (3) the descriptive lenses moved onto the two lines — kill
lights bar on the minimum, chain stages grade weak < min <= ok < typical
<= strong, `redundant_gain_max` 0.05 -> 1.0; (4) the pooled `balanced`
cell is coded but the committed board predates it (BACKLOG: regenerate on
the harvest checkout). Open: T25b pierce (BACKLOG, owner ruling). Owner ruling this
implements: "the data should come from the harvest median" (2026-09-10,
after the p10/p50/p90 explainer; the "3 healers at 15 is standard to try
to reach" case).

## Problem (owner's words)

> these numbers are meant to be like targets to hit for the style of comp
> and all of them are overshooting what is set as targets

> if someone sees they have heal burst / heal sustain at 12/4 they will
> think they have too many healers in party but in reality 3 healers in a
> party of 15 people is totally normal and standard to try to reach

Every `target` in the model is the **left edge** of what winning parties
field: the harvest convention is `target = 0.9 × p10` (90% of winners field
at least this much), and the hand-fitted content rows follow the same
"0.9× the least any good comp fields" rule. The score gives full credit
at that number (`w × min(1, have/target)^γ`) and pays at most 10% more
across the whole target..soft-cap band. Consequences:

- The board reads `heal_burst 12 / 4.6` for a normal 15-man kite with
  three healers. Every row overshoots; the label carries no signal.
- The forge agrees with the label: one healer "covers" 15 people and a
  second/third healer is worth ~0.3 points. The pick card contradicts
  itself ("already covers sustained healing … Hallowfall closes that").
- The measured **median** (p50) — where winners actually cluster — is
  computed in the evidence board, written into the YAML comments, and
  used by nothing.

This is one semantic error inherited by all 23 capability rows, every
style, every size, both layers (harvest bands and content templates).

## Ruling

1. **Target = the harvest median.** The point of full credit and the
   board's second number is what the typical winning party of that style
   at that size fields (p50), not the least any winner got away with.
2. **The over-stack line stays at 1.15 × p90.** Heavier than nearly any
   winner still means wasted seats.
3. **Below the target is one smooth curve.** No second cliff at p10.
   The structural hard floors (heal_sustain / tankiness minimums, weapon
   units) keep carrying the "nobody at all" disaster case, unchanged.
4. **Every row moves at once** (standing rule "any re-fit moves every row
   at once"): harvest bands and content rows in the same change, one
   commit, gates re-run on the result.
5. **No invented numbers.** Where no median exists (a content with no
   fitted comps, a cell where most winners field none) the row is left as
   it is and the board says so.

## Design

### 1. Harvest layer — `pipeline/derive_style_bands.py`

- Convention becomes `target = TARGET_OF_P50 × p50` with `TARGET_OF_P50 =
  1.0`, `soft_cap = 1.15 × p90` unchanged. The YAML `convention:` line and
  the header comment state the new rule; the per-row comment keeps
  `p10/p50/p90` so the old floor is still readable.
- **Zero-share rule retired for the target.** It existed because p10 sits
  on the edge of the zero mass and thrashes between folds. The median does
  not: kite|10-14 heal_burst has 10% zeros and a p50 of 5.8 that will not
  move when a few zero rosters enter. New rule: a row gets a target when
  `p50 > 0`; when `p50 == 0` (most winners field none) it carries the soft
  cap only and the content target stands, with the comment "most winners
  field none". `ZERO_SHARE_MAX` is deleted from the script and the YAML
  convention line (its reason no longer exists; keeping a dead knob invites
  a future reader to re-apply it).
- **A `balanced` band, pooled.** Today `balanced` never reads a band
  (2026-09-04 ruling, made when the bands were floors and the content rows
  were the safer default). With medians the harvest is the better source
  at every size it can see. `audit_style_rosters.py` writes one extra
  cell per band, `balanced|<band>`, aggregated over EVERY roster in the
  band regardless of style label (labelled and unlabelled alike — the pool
  is "winners at this size", not "winners we could name"). Same
  `MIN_DISTINCT`, same distinct-roster dedupe. `derive_style_bands.py`
  emits it under `bands: balanced:` like any style; it has no parent and
  borrows only across its own bands.
- Soft cap ≤ target rows are still skipped (as today).

The expected shape of the change, from the current board (kite, ref 17,
per-person scaled to 15): heal_burst 4.6 → 9.1, heal_sustain 4.9 → 10.0,
cleanse 1.6 → 5.3, tankiness 34.9 → ~42.

### 2. Engine — `engine/engine.py` and `engine/app_scoring.js`

- **Scoring formula unchanged.** Coverage, headroom, over-stack, floors,
  synergy saturation all keep their shape; only the `target` they read
  moves. This is deliberate: one moved number, no new mechanism, parity
  stays a re-run rather than a port.
- **`balanced` reads its band** at `min_size`+ like the declared styles
  (`set_content` drops the `style in bands` restriction; `band_row` /
  `band_key` are set for balanced too). `target_mults` still do not stack
  on band rows. Below `min_size` nothing changes.
- **Target provenance exposed for display, never scored.** `set_content`
  records per capability where the effective target came from:
  `harvest` (band row target), `content` (content row, median-fitted),
  `content_min` (content row still on the old minimum — thin or no comps),
  and whether the harvest cell was borrowed. Exposed as
  `target_source(cap)` on both engines; carried by parity like every other
  descriptive read. The dashboard uses it to label rows honestly.
- The floor clamp ("a hard floor never exceeds the target it guards")
  keeps working; with higher targets it binds less often.

### 3. Content rows — the six templates

The hand-fitted rows were measured from the published comps in
`data/published_comps/` by `audit_dressed_templates.py` (per-comp supply
in person units) and written by hand under "0.9× the least". The re-fit
uses the same audit, the same comps, and writes the **median** of the
fitted comps per capability, per content:

Comp counts per content follow `audit_dressed_templates.py` `CONTENT_MAP`
(`zvz_20man` → blackzone_roam, `zvz_7man` → castle_outpost,
`large_scale_zvz` / `zvz_20v20` → territory_defense), counted from
`data/published_comps/` on 2026-09-10:

| content | fitted comps | rule |
|---|---|---|
| blackzone_roam | 18 (2 stated + 16 `zvz_20man`) | median |
| castle_outpost | 3 (`zvz_7man`) | median (the middle comp) |
| territory_defense | 2 | n ≤ 2: keep current rows, mark `fit: minimum` |
| roads | 1 | keep, mark `fit: minimum` |
| castle | 0 | keep, mark `fit: none` |
| faction_war | 0 | keep, mark `fit: none` |

The 10/14/15/19-man `zvz_*` comps are unmapped to any content today and
stay so (they feed the blind-test gate, not the fit). Whether to map them
is a separate owner call and is not needed here: at 10+ the harvest
medians carry the targets.

Each template gains a header block `fit: {comps: N, stat: median|minimum|none}`
that `build_dataset.py` copies into the dataset so the engine can derive
`content` vs `content_min` above. `scales`, `weight`, `ramp`, `optional`,
hard floors: untouched. Rows a template has no comps for (`max_health_cut`
in castle_outpost) stay absent.

At 10+ the content rows matter only for capabilities the harvest cell
lacks and for hard floors / weights; below 10 (castle_outpost, roads,
small roams) they are the whole target, which is why they move too.

### 4. Dashboard — `dashboard/_app.js`, `_decision_layer.js`

- The capability board label reads `have / typical` (heading "CAPABILITY
  SUPPLY VS. TYPICAL WINNER" or similar; the exact copy is a build-time
  string). The ring keeps its tick at the target and its end at the soft
  cap — that IS the band "winners field target..cap".
- Rows whose `target_source` is `content_min` or `content` with
  `fit: none` carry a small chip ("min" / "no data") so a thin number is
  never read as a typical one. Borrowed harvest cells carry the existing
  `borrowed_from` note in the tooltip.
- `whySentence` excludes the lead gap capability from the "already
  covers" list, so the card can no longer say a capability is covered and
  then close it.
- **SIZE stepper follows the roster.** `PLANNED = max(PLANNED,
  party.length)` on every roster growth path, not only the companion path
  (the central `data-add` handler and the forge fill). Judgement was
  already at roster size; this only stops the header contradicting it.
- The "extrapolated size" notice text says what it means: validated at
  size N only; targets at this size come from the harvest median / linear
  scale of the content row.

### 5. Gates, validation, records

Run in this order and read the output, not the counts:
`derive_style_bands` → `build_dataset` → `dashboard/build.py` → every
gate in CLAUDE.md, including `tier2_blindtest.py v4` (70%) and the
report-only `v4h`.

- Golden cases that flip are **hypotheses for the owner**, one ruling
  each (blind: collect the owner's call first). Expected flips: parties
  where the forge previously stopped at one healer / one tank because the
  floor was "covered".
- New pins: (a) kite 15 with two healers — the third healer scores
  positively for heal_burst (2 × ~4 < 9.1); (b) `balanced` at 15 reads a
  band row; (c) `target_source` parity on 60 random parties; (d) a
  dashboard-layout contract that the board label and chip come from the
  engine's `target_source`, never a page-side rule.
- `tests/VALIDATION.md`: one index row "Target is the median (2026-09-10)"
  pointing at the dated log in `notes/validation/2026-09b.md` with the
  owner's words above and the before/after table. Anti-circularity note:
  the harvest that fitted the bands is not re-tuned against gate results;
  gate findings go to the owner.
- `MASTERSHEET.md`: the convention line ("targets are harvest medians;
  soft caps 1.15 × p90") beside the existing `tune:` knobs, so "what is
  the engine actually using" stays answerable there.
- `HANDOFF.md` "The engine today" and `pipeline/README.md` (style bands
  paragraph, content rows paragraph), `derive_style_bands.py` docstring,
  `BACKLOG.md` (close the item; open a follow-up for the roads /
  castle / faction_war comp gaps).

## Out of scope

- Great Nature Staff (and any single weapon's) behaviour at 14+ — that is
  the `style_fit` / suggestion-gate layer, checked separately after this
  lands; nothing here touches it.
- Re-fitting `styles.yaml` `target_mults` (they already do not stack on
  band rows; with a balanced band they matter only below 10).
- Any change to the scoring curve's shape, headroom, or over-stack
  economics. If the median targets make the headroom band feel too thin
  or the forge over-eager, that is a separate ruling with its own
  evidence.

## Testing

- `tests/test_forge.py`: the three new pins above; existing pick-score
  invariants must hold unchanged.
- `tests/test_golden.py`: re-run; every flip logged and ruled before the
  pin moves.
- `tests/test_js_parity.py`: `target_source` added to the parity payload.
- `tests/test_dashboard_layout.py`: board label / chip contract.
- A derive test (new, script-style like the rest): on a fixture evidence
  board, `derive_style_bands` writes `target == p50`, writes soft-cap-only
  when `p50 == 0`, emits a `balanced` cell, and no longer reads
  `zero_share`.
- `pipeline/evidence_lint.py`, `test_provenance.py` (byte-identical
  rebuild after the YAML changes), `test_validation_modes.py`.
