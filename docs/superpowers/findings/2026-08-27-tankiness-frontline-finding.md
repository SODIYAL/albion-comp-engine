# Finding: ordinary worn armor satisfies the structural frontline requirement

**Date:** 2026-08-27 · **Status: RULED AND IMPLEMENTED — Option C approved by the owner (same day) and shipped in both ports.**

> **Implementation record (Ruling 1):** structural hard floors now read the
> WEAPON+LOADOUT supply in `fitness`, every marginal path
> (`_combo_score` / `_combo_score_dressed` / `_marg_fit_from` /
> `_marg_fit_pre`), `pick_report`'s floor_lift rows and `explain` — in both
> engine ports, parity 60/60 at 1e-9; the dashboard's floor tags read the
> same basis (`supplyFloor`). Gear keeps counting toward coverage, headroom
> and overstack. Contracts: `tests/test_validation_modes.py` V5a–V5f
> (adversarial no-frontline party pays the full penalty dressed; one real
> tank repairs it; all-plate never clears it; pick score == dressed
> comp_score delta). Floor magnitudes untouched per the ruling. Measured
> after: adversarial cases A/C keep penalty 9.0 dressed (old rule: 0.0);
> V4 actual-gear role-level 41% → 47% (two Deadlyhooker tank drops
> recovered); the REMAINING dressed-V4 shortfall vs the 78% naked metric
> is the soft-cap/target saturation question (§3 rider 1) — a calibration
> item for the expert rounds, not a floor issue. Implementation exposed a
> pre-existing forge pruning blind spot (a pick could exhaust the healer
> band while primary_heal was unmet, beam dying at 6/7) — fixed
> structurally with per-predicate capacity gates in `_forge_feasible`,
> both ports.

The original finding follows, unchanged, as the decision record.

Evidence artifacts: `pipeline/out/frontline_floor_audit.json` (adversarial cases), `pipeline/out/dressed_template_audit.json` (real-comp saturation), `pipeline/out/validation_asymmetry_probe.json` (V4 role-demand collapse). All report-only; nothing was tuned.

## 1. What was measured

**Adversarial cases** (castle_outpost, size 7; tankiness floor 1.7u armed at 5+, target 3.5, weight 9):

| Case | tankiness naked → dressed | floor penalty | tankiness in top-3 weaknesses |
|---|---|---|---|
| A — 7 players, **zero frontline weapons**, ordinary doctrine kits | 0.00 → **15.88** | 9.00 → **0.00** | yes → **no** |
| B — same party, one real Heavy Mace | 3.00 → 17.38 | 0 → 0 | no → no |
| C — same no-tank party, **every member in full plate** | 0.00 → **23.09** | 9.00 → **0.00** | yes → **no** |

The domain expectation ("a party with no real frontline is still diagnosed as lacking one") is **violated in cases A and C** at the capability/floor level. Ordinary worn armor — not even adversarial plate, just doctrine kits — fully clears the hard floor and erases the diagnosis.

**Real-comp saturation** (dressed template audit over 16 published-comp parties): gear adds **+419% to +622% of the tankiness target** in every template and pushes past the soft cap in nearly every real comp (blap: 13.0 naked → 54.6 dressed vs target 9.2 / soft 13.4 — hand-verified; a plate-chested mage gains 3.22u, more than a Heavy Mace's own 2.0u weapon supply).

**Production consequence** (V4 leave-one-out, dressed incumbents): 12 of 32 role-level reproductions flip HIT→miss when incumbents wear their recorded gear — **11 of the 12 are tank/main_tank drops**. With the party dressed, dropping a tank leaves no visible tankiness hole and the engine's top-3 becomes pierce/burst utility (Spirithunter, Black Monk, Fists of Avalon) instead of a frontline weapon. This is the direct mechanism behind the dressed V4 role metric collapsing 78% → 41%.

Two mitigating observations, honestly recorded:

- At size 7 the dressed engine still *recommends* frontline weapons for case A/C through their other capabilities (engage, clump_create, peel, stun) — the failure is total at the tankiness/floor level but partial at the recommendation level at small sizes. At 15–20 dressed (the V4 evidence) the recommendation failure is real.
- The descriptive role advisory ("no engage tank") arms only at 10+ and stays silent at 7 by design; in case C it does flag `off_role_kit` members. Descriptive layers never score (R5), so they cannot compensate.

## 2. Why this happened (classification: **representation problem**, category 1)

`build_extra` converts worn armor+MR (0.004/point) and CCR (0.003/point) into the **same `tankiness` currency** that templates target, soft-cap, and hard-floor (`mechanics.yaml build_stats`; engine.py ~1007). The per-piece calibration is sane (plate chest ≈ 1.15u, cloth ≈ 0.5u), but a full kit across N members sums to ~2–3u × N — an order of magnitude above target scales that were comp-fitted in weapon-loadout units (2026-08-21 recalibration, 53-item catalog era; the 2026-08-27 expansion tripled the catalog). The capability now conflates two distinct game concepts:

- **personal durability** — how hard each body is to kill (what worn armor actually gives);
- **frontline structure** — bodies that engage, hold space, and absorb the enemy's opener (what the hard floor was designed to demand — the V1 2026-08-12 finding that made floors load-bearing, and the same session's *pseudo-tankiness* ruling that stripped `tankiness` from personal defensive cooldowns for exactly this reason).

The 2026-08-12 precedent is directly on point: personal defensive abilities were ruled to ground **no** tankiness because they harvested tank-floor relief. Worn armor has recreated that failure through the stat channel.

## 3. Options (Task 4B)

**A — keep one `tankiness` capability (status quo).** Rejected by the measurements above: the hard floor stops being structural the moment parties dress, which is now the production default.

**B — split `personal_durability` / `frontline_tankiness`.** The cleanest model, and the most expensive: a new capability, template targets/weights/floors re-fitted for it, both engine ports, parity, and a curation question (weapon tankiness sheet scores are already frontline-shaped; gear stat tankiness would move wholesale to the new cap). Re-opens template calibration the owner just ruled on. Not the smallest correct fix.

**C — keep one capability; make HARD FLOORS source-aware.** Floors (and only floors) read **weapon+combo tankiness** — supply computed without gear — while coverage/soft-cap/headroom keep pricing the full dressed supply. Rationale: the floor is the structural rule ("a real frontline body exists"); coverage is the fitness rule ("the party is durable"), where gear legitimately belongs and the existing overstack asymptote already bounds it. Implementation surface: floor evaluation in `fitness` + the marginal floor rows (`_cover_terms` / `_marg_fit_pre` floor tuple) in both ports — contained, no new capability, no sheet or template changes. The precedent is exact: momentary defensives were barred from floor relief in 2026-08-12; this extends the same ruling to worn-stat tankiness. **Recommended.**

**D — move the structural requirement entirely to the role/need-profile layer.** Need profiles already guarantee engage/stopper seats — but generation-only, armed at 15+, and manual parties always score (F21). Making them a scoring input would breach the descriptive-layers-never-score invariant and still leave sub-15 sizes uncovered. Works as a *complement* (it is why forged 20-mans stay sane), not as the fix.

**Recommendation: Option C**, with two riders —

1. The **soft-cap saturation** (+400–600% across all templates, and similar mobility/peel/purge injections) is a separate, wider calibration question: the templates' unit scale predates dressed supply. That is category 5 (genuine calibration) territory and must wait for the expert rounds — the overstack asymptote (`overstack_max 0.5`) bounds the damage meanwhile. Do not fold it into the floor fix.
2. Whether the healer-side equivalent (`heal_sustain` floor; gear supplies only ~2 heal items today, +40–77% of target) needs the same source-awareness should ride the same ruling — the measured effect is far smaller, and the one healer-drop flip in V4 (blap/Redemption) came through burst/pierce gear shifting the ranking, not heal gear.

## 4. Phase-11 note (floors as structural rules)

The work order asks whether load-bearing floors should become lexicographic/critical requirements instead of large negative scores. The measured failure here is **source-blindness, not magnitude** — in case A the naked penalty (9.0) is plenty; it simply vanishes once gear fills the bucket. Fix the source first (Option C); revisit lexicographic floors only if expert rounds then show penalty-magnitude failures (e.g. a party trading the entire floor penalty for enough damage supply). `primary_heal` already has its structural rule on the generation side (foundation minima, F15); no change proposed there.

## 5. Ruling needed from the owner

1. Adopt Option C (floors read weapon+combo supply; gear keeps counting toward coverage/soft-cap)? If yes it lands with tests in both ports + parity, and the dressed V4 sections re-measure.
2. Should `heal_sustain`'s floor ride the same rule?
3. Template unit-scale recalibration for dressed supply: park until calibration rounds (recommended), or schedule a comp-fitted re-measure now under the anti-circularity discipline?
