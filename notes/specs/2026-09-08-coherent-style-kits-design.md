# Coherent builds and style-conditioned kit doctrine — design (2026-09-08)

Status: APPROVED in chat 2026-09-08 (owner: "go ahead with your
recommendations"; balanced comps keep the band doctrine, style cells fire
on a DECLARED style only).

## Why

Owner, 2026-09-08: use the harvested comps "to increase the quality of the
engine such that we start seeing better quality of equipment for every
seat". Two of the seven levers proposed were approved for now:

1. **Coherent builds, not modal slots.** The doctrine miner already runs
   a conditional modal chain over all seven slots
   (`_modal_build_chain`, owner ruling 2026-09-01) but the chain stops
   after one or two slots for 92 of 118 weapons. Measured 2026-09-08 on
   the 2,042-battle harvest: the dominant stop (69 of 118 weapons) is the
   guard `n < 0.5 * uncond_top[slot]` — a conditional COUNT inside a
   shrinking pocket compared with the unconditional modal's COUNT over
   the whole population. Once the chest pocket is under half the
   population that guard fails by construction, and every later slot
   falls back to the per-slot mode — the Frankenstein the chain was
   built to prevent.
2. **Style-conditioned doctrine.** Kit blind rounds 1-2 (2026-09-05)
   proved chests split by style (Royal Jacket: 359 ranged rosters vs 6
   brawl; Hellion: 487 brawl vs 332 ranged). Doctrine is keyed by seat x
   weapon x size band and never by style, so a clap Realmbreaker and a
   brawl Realmbreaker are dressed the same.

Not in scope (proposed, not yet ruled): kill-vs-death contrast, item-power
gating, seat-level pooling of thin slots, carrier floors, harvest targeting.

## 1. The chain guard, rescaled

`_modal_build_chain` keeps its shape (armor -> head -> shoes -> cape ->
offhand -> potion -> food; one player one vote; a step needs >= 2 distinct
players and >= 25% of its pocket). Two guards change:

- **Pocket floor** (replaces the count-vs-count rule as the "rare pocket"
  defence): the chain continues only while the pocket holds at least
  `CHAIN_POCKET_SHARE` (0.20) of the weapon's population OR
  `CHAIN_POCKET_VOTES` (20) votes. The 2026-09-04 Greataxe case (a 7-of-8
  cape inside an 8-build pocket of a ~74-build population) still stops:
  8/74 = 11%.
- **Share-vs-share** (keeps the "don't front a rare item" intent): the
  pick's share of the pocket must be >= half the unconditional modal's
  share of the population. Counts are never compared across pools of
  different size again.

Measured before/after on the same harvest (weapons at 10+, group band):
depth 4+ goes 6 -> 37 weapons; mean depth 1.77 -> 2.62; the remaining
stops are thin pools (< 5 votes) and single-player picks.

Nothing downstream changes: `kit_build` / `kit_weapon_build` keep their
`{slot: [id, n, of]}` shape, the engine's `observed_build` annotation
keeps its meaning (n / of at that step).

## 2. Style cells

### Labels: `pipeline/derive_party_styles.py` -> `out/party_styles.json`

Reads the COMMITTED `out/party_rosters.json` (never the raw cache, so it
runs on any machine and is byte-reproducible), labels every party of
`KB_MIN_PARTY` (10)+ members with `Engine.comp_identity` on its weapons
alone (the audit's DRESSED labels need member kits the committed artifact
does not carry; naked matched dressed 19/20 in blind round 4), and writes:

```json
{"_source": {"party_rosters_sha256": "..."},
 "_engine": "comp_identity, weapons only, territory_defense at party size",
 "parties": [{"battle": 1439160917, "index": 0, "size": 20,
              "style": "clap", "strength": "strong"}, ...]}
```

`style` is null for split / forming / unlabelled parties. Deterministic
order (battle, index). LF, `newline="\n"`.

Rerun order after a harvest becomes: `sample_parties` ->
`audit_style_rosters` -> `derive_style_bands` -> `derive_party_styles` ->
`build_dataset` -> gates.

### Linkage: build -> party

`sample_parties.analyze` gains a `party` field on every build: the index
of the build's party inside the battle's deduplicated party list (the
same list `parties` in the artifact is written from). Exact, no
inference. Until the next harvest regenerates the artifact, builds carry
no `party`, and the miner falls back to **(battle, weapon) when exactly
one 10+ party in that battle fields that weapon** — measured 11,186 of
21,162 group-band builds link that way, 9,218 of them to a labelled
party. Ambiguous builds are simply not in any style cell (they stay in
the band pool). Nothing is guessed.

### Doctrine: `kit_styles` under the group band

`derive_kit_doctrine` mines, per seat, one cell per style in
`IDENTITY_STYLES` (brawl, clap, kite, brawl_clap, clap_kite) from the
killboard builds linked to a party of that style, with the SAME miner and
floors as the band (seat 3 voters, weapon 2, chain step 2, uniform
extension 35) plus a **cell floor**: a weapon's style cell exists only
with >= `STYLE_CELL_MIN_VOTERS` (5) distinct players. Below that the cell
is absent — never filled from the band, never from another style. The
cell carries the same keys the band carries where it has evidence:
`kit_weapon_build`, `kit_weapon`, `kit_weapon_uniform`, `kit_build`,
`kit`. Curated reference builds (builds_index) carry no style and stay
band-only. Gang band (<= 9) gets no style cells: labels exist for 10+
parties only.

Shape on the seat record:

```json
"kit_styles": {"clap": {"kit_weapon_build": {...}, "kit_weapon": {...},
                        "kit_weapon_uniform": {...}, "kit_build": {...},
                        "kit": {...}},
               "brawl": {...}}
```

`roles_report.json` gains the per-style detail beside `kit_doctrine`.

### Engine, both ports

`_seat_kit(rec)` is the ONLY reader (CLAUDE.md invariant). New rule:

- size <= gang max: gang band, unchanged;
- else if `self.style` is a declared style (not `balanced`) and
  `rec.kit_styles[self.style]` exists: return the style cell MERGED over
  the band record — for each doctrine key, the cell's per-weapon entries
  override the band's, the band fills every weapon and slot the cell
  lacks;
- else: the band record, unchanged.

**Balanced never reads a style cell** (owner, 2026-09-08). The detected
identity (`comp_identity`) is descriptive and stays out of generation.

`kit_options` annotates `observed_build` entries that came from a style
cell with `style: "<style>"` so the page can say "clap build, 41 of 60".
The carrier quota, the uniform gate, doctrine passives and every other
rule apply to the merged record exactly as before.

### Provenance

`build_dataset` reads `out/party_styles.json` if present: a
`party_rosters_sha256` that does not match the artifact on disk is a
release-blocking problem (fail closed, loudly). A missing file prints a
warning and ships no `kit_styles` (the file is generated after a
harvest). `test_provenance` keeps its byte-identical rebuild check; the
new artifact is LF.

## Tests

- `test_roles` R29 — chain mechanism: a synthetic population where the
  chest pocket holds 30% continues to the helmet; one where the pocket
  holds 11% of 74 (the Greataxe shape) stops at the chest; a pick under
  half the unconditional modal's SHARE stops.
- `test_roles` R30 — style layer: with a declared clap the forge dresses
  a weapon in its clap cell's chest where the cell meets the floor, brawl
  in its brawl cell, band under `balanced`, band when the cell is absent;
  the annotation carries the style. Pinned on MECHANISM (the corpus grows
  nightly) — the fixture picks a weapon whose cells exist and asserts
  chest == that cell's modal, not a hard-coded item.
- R24 (kit audit) becomes style-aware: with a declared style the modal
  it compares against is the style cell's where one exists.
- `test_js_parity` gains a `kit_options` case under a declared style.
- `test_provenance`: hash mismatch blocks.

## Out of scope / deferred

Dressed labels for the party file (needs member kits in the artifact);
style cells in the gang band; using detected identity for balanced comps;
all other levers from the 2026-09-08 list.

## 3. Seat pooling for thin slots (approved 2026-09-08, "i leave it up 2 you to get the best results")

Measured before designing (135 seated weapons, 844 forged tiles at 20,
balanced): 627 tiles rest on a weapon item worn by 5+ players, 160 on a
weapon item worn by 2-4 players, 57 on the seat fallback. Bootstrap on
well-evidenced weapons (15+ voters, 20 draws each): the modal of 3 random
players' builds matches the weapon's true modal for the helmet 58%, boots
48%, cape 68%, potion 86%, food 80%. The seat's modal among builds wearing
the SAME CHEST matches it 80% / 72% / 81% (helmet / boots / cape); the
plain seat modal 66% / 62% / 75%, and 95% / 82% for potion / food.
Conditioning on chest CLASS does not help (65% / 64% / 79%).

Rule (both ports, inside the one kit reader):

- A weapon slot is THIN when its weapon-tier modal carries fewer than
  POOL_MIN_VOTES (5) votes (votes are player-weighted, so 5 votes means
  at least 5 players).
- Thin helmet / boots / cape: front the seat's modal among builds wearing
  the chest THIS kit is dressed in (`kit_by_chest[chest][slot]`) when that
  item has 5+ players; else the plain seat modal (`kit_pool[slot]`) at
  5+; else keep the weapon's thin item — something observed beats nothing.
- Thin potion / food: the plain seat modal at 5+, else the thin item.
- Chest and off-hand are never pooled (identity and uniform; stat physics).
- The pooled option carries `pooled: "seat|chest" | "seat"` and
  `pooled_n: players`; the kit editor's engine-kit line names it.
- The miner ships `kit_pool` and `kit_by_chest` per seat and per band
  (group top level, gang under `kit_bands.gang`), player-counted, items
  with 2+ players, from the same killboard builds the tiers use; style
  cells ship none — the merged record keeps the band's pools.
- R24 skips slots whose killboard modal has fewer than 5 players (the
  pooling floor, mirrored like R24b); R34 pins the mechanism.

