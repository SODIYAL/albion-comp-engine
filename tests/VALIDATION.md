# Validation Plan — Composition Engine

How we test the design *before* building it, what already ran (2026-08-12), and what remains. Principle: every risky claim in the design doc gets a cheap falsification test; build only after the cheap tests pass.

## Tier 1 — Model validity (ran today, no product code needed)

**V1. Golden-case recommendation tests** — `prototype_engine.py`, runnable anytime (`python3 prototype_engine.py`).
A ~250-line throwaway implementation of the scoring model (13 hand-scored weapons, 1 content template) against 9 assertions encoding what any experienced player knows to be true:

| # | Case | Result |
|---|---|---|
| T1 | Longbow+Witchwork+Permafrost → recommends a healer | PASS |
| T1b | Weakness list leads with healing | PASS |
| T2 | After healer joins → recommendation flips to frontline | PASS |
| T3 | Empty party → first pick isn't pure DPS | PASS |
| T4 | 2 healers in 4 → no third healer recommended | PASS |
| T5 | 6-DPS party, last slot → healer | PASS |
| T5b | Greedy-trap lookahead flags ≥3 uncovered capabilities | PASS |
| T6 | Known meta comp outscores troll comp by >25% (84.9 vs 19.3) | PASS |
| T7 | Auto-generated "why" leads with the right capability | PASS |

**9/9 after one design iteration — and the iteration itself is the headline finding:** the first run failed 4/9 because soft targets alone let breadth weapons (Heavy Mace covering five medium gaps) out-rank a healer fixing the single critical gap. The design doc's `hard_floor` mechanic (§3.1) — zero healing/frontline is catastrophic, not merely suboptimal — turned out to be **load-bearing, not a nice-to-have**. This is exactly the class of error that would otherwise have surfaced after weeks of building.

*Caveat: 9 assertions over 13 weapons is a smoke test of model shape, not proof of recommendation quality. Quality is tested in Tier 2.*

**Status 2026-08-12 (full-coverage pass):** the golden suite graduated to
`test_golden.py` running against the built dataset and stays **9/9 with all
137 combat weapons curated** (no illustrative placeholders left). Getting
there produced two more load-bearing findings of the V1 class:

- *Heal-floor strength*: with richer curated data, synergy + meta-prior
  leakage let a breadth pick out-rank every healer for a healer-less party by
  0.014 — `penalty_mult` raised 1.5 → 2.0 (PROVISIONAL). The structural fix
  worth testing after Tier-2 is step-function floors (no partial relief).
- *Pseudo-tankiness*: personal defensive cooldowns (Parry, Deflecting Spin,
  Counter…) scored as `tankiness 1` harvested tank-floor relief and put a
  purge lance above every tank. Resolved by the momentary-defensive ruling
  (they ground no tankiness); 41 scores removed in one pass.

**V2. Live data spikes** — real albionbb battle `1431808107` (22 players, 2-sided):

| Claim from design doc | Measured | Verdict |
|---|---|---|
| Weapon attribution >85% of players | 20/22 (91%) had weapon + role | PASS |
| Win/loss decidable for clean fights | 8–0 kills, 2.0M–0 fame → unambiguous | PASS |
| Full comps reconstructable | Winning side fully legible: 2× Avalon Holy healers, mace+quarterstaff frontline, dual-axe/dagger/frost core | PASS |
| Known noise sources | 2 players weaponless; several `damage: 0` despite kills (stats only captured from kill-event snapshots); battle list contains many-sided brawls where "winner" is meaningless → "inconclusive" label is necessary, as designed | CONFIRMED |

## Tier 2 — Recommendation quality (before/while building MVP, needs humans)

**V3. Expert blind test.** Give 10–15 partial parties to 3+ experienced shotcallers; collect their next-pick independently; compare with engine top-3. Target: expert pick appears in engine top-3 ≥70% of cases. This is the true accuracy metric — the curation prerequisite is now MET (all 137 weapons, 2026-08-12) and `tests/tier2_form.md` is regenerated against the full pool (seed 20260812). **V3 is the project's current critical path**; everything else is tuning noise until it runs.

**V4. Meta-comp reproduction.** Feed the engine each published meta comp (albioncompo, guild guides) minus one member; the engine should propose the missing member's role in top-3. Automatable version of V3. Case list: `data/published_comps/` (moved out of `tests/meta_comps.yaml` by chapter 2, 2026-08-19 — production build data now lives in the evidence layer with full provenance envelopes) — two real entries recorded 2026-08-12, both relayed by the project owner, all weapon cells mapped to catalog keys: (1) shotcaller "Deadlyhooker", large-content ZvZ, 3 parties × 20, battlemount slots flagged as outside the weapon model; (2) shotcaller "Timothy", blackzone-roam brawl comp "blap", 1 party × 20, **with per-slot skill loadouts (q/w/p), potions and food** — the first real default-kit data (V5 catch #1 established this has no public statistical source). 20-size templates now exist (`blackzone_roam`, `territory_defense`, 2026-08-12) so the runner is technically unblocked — but both took role-ratio calibration from these same two comps, so leave-one-out against them is weakened evidence (documented in the template headers). The clean V4 run needs comps from callers whose sheets did NOT inform the templates. The golden suite meanwhile anchors both templates to the real comps in weak form (T8/T9: fitness discrimination vs troll comps + healer-floor sanity; 13/13 as of 2026-08-12), and `tests/test_js_parity.py` holds the app's in-browser scoring identical to the Python engine (60/60 random parties, 1e-9).

**FIRST V4 RUN (2026-08-13, `py -3 tests/tier2_blindtest.py v4 --verbose`)** — 70 leave-one-out slots over both comps, battlemounts excluded:

- **Role-level (the designed metric): 18/26 = 69%** on healer/tank slots — one hit short of the 70% gate, on templates no expert has ever touched. Weak-form evidence (circularity above), but the project's first real recommendation-quality baseline.
- **Weapon-level (strict): 6/70 = 9%.** The misses are more informative than the rate:
  1. *Saturation degeneracy*: at 19-of-20 members every target is met, marginal gains collapse toward zero, and the top-3 becomes the same breadth fillers (Incubus Mace / Staff of Balance / Camlann Mace) regardless of what was dropped. Leave-one-out at a full party tests "best generic 20th body", not "replace what was lost" — a limitation of the METRIC at saturation, distinct from engine error. A future V4b should reconstruct the last ~5 slots instead, where targets still bind.
  2. *Breadth-over-depth at the margin*: bruiser-utility weapons win marginal-sum contests once nothing is critical — the Heavy-Mace-class V1 finding, now visible at scale. Concavity + floors govern the critical range; the saturated range may need a redundancy/diversity term (post-Tier-2 question).
  3. *Dedicated support never reproduces*: dropping Locus / 1h Arcane / Great Arcane always yields bruisers. The taxonomy captures their effects (cleanse, buffs, peel) but the templates' flat thresholds for those caps saturate early — support is structurally undervalued at the margin. Flag for the expert pass.

Per the standing rule, NOTHING was retuned off this run — these comps calibrated the templates, so tuning against them would be circular. The findings are hypotheses for the expert and Tier-2, not fixes.

**V4 AFTER THE FORGE REWORK (2026-08-18)** — role-level **20/26 = 77%, first pass of the 70% gate**; weapon-level 9/70 = 13%. What moved it, in order of honesty: the runner now scores each comp under its own declared style (blap's source line says "(brawl comp)"; `style:` recorded in `meta_comps.yaml` — evaluating a deliberate melee ball under `balanced` misread its missing ranged core as a deficiency); the anti_zone/damage_debuff from-zero windfall was trimmed to honor those rows' own "can never dominate" rule (finding 2's constant Incubus/Black Monk top-3 was exactly this); and the redundancy + viability terms separate proven large-group weapons from generic breadth fillers. The remaining 6 misses are healer drops in parties whose heal supply stays covered by support-class holies (P2/P3 field their frontline on battlemounts, so the engine correctly asks for tanks) — the saturation-degeneracy limitation of the metric, unchanged.

**FIRST INDEPENDENT COMP MEASURED (2026-08-21)** — the long-requested comp from a source that did not calibrate the templates arrived: "Roam 15" by Bist (albioncompo.com, 15-man blackzone brawl ball, fully role-labeled; `data/published_comps/albioncompo_bist_roam15_2026_01.yaml`). Mapping it to `blackzone_roam` moves the role gate **19/26 = 73% → 22/32 = 69% (FAIL)**. The misses are one story: all three healer leave-one-out slots fail identically — with 2 of its 3 healers remaining, the scaled heal target (~5.6 units at 15) is already met, so the engine's top-3 is Camlann/Witchwork/HoJ instead of a healer (Camlann appears in the top-3 for 14 of 15 slots — the saturated-margin favorite). This is finding 3 ("dedicated support never reproduces") now confirmed on independent evidence, and it corroborates the 2026-08-21 template audit's F6: both real roam comps field **1 healer per 5 players** (Bist 3@15, blap 4@20) while the template targets ~2.5-at-20. STANDING OWNER RULING: the comp is parked unmapped (`zvz_roam15`) so the gate stays green; admitting it (one-line content change) means either accepting a red gate or first raising the heal targets/softs toward the two-comp consensus — which would be the first evidence-driven retune of a template number. Nothing was retuned; per the standing rule the finding awaits the ruling.

**Circularity disclosure (owner adjudication wanted):** the 2026-08-18 reweights (anti_zone/damage_debuff 3→1-2, brawl burst_aoe 0.85→0.7) were motivated by defects VISIBLE IN these same gate comps; a counterfactual run with only those reweights reverted scores 18/26 = 69% — they are load-bearing for the gate. Each is argued from documented intent (the rows' own "can never dominate" rule; the brawl blurb's "blap fields zero ranged"), not from the misses alone, and each stays PROVISIONAL — but under this file's standing anti-circularity rule the 77% is weak-form evidence squared: treat the gate pass as provisional until the expert confirms the reweights or an independent comp reproduces it.

**FORGE REGRESSION SUITE (2026-08-18, `py -3 tests/test_forge.py`, 11 checks)** — the structural contracts of the rework: the pick-score invariant (reported marginal == exact comp-score delta, 1e-9, every content × style), template-gated + cross-member synergy, growing exact-duplicate costs with meta-proven allowances, the full size-11 large-content matrix (legal, deterministic, zero excluded weapons, no unheld negative slots), viability exclusions barring suggestions but never scoring (off-comp flags), floor clamping, size physics (no ST boost above small gangs; T16's inversion intact; roads' content restoration), headroom shape, spell-pick locks reaching scoring, and locked-member preservation. JS parity extends to forge rosters, locked loadouts, redundancy and provenance codecs (60/60 + a dashboard-embed check).

**V4 AFTER THE RANGED-PRESENCE REWORK (2026-08-19)** — role-level **19/26 = 73%** (gate 70%, still PASS); weapon-level 8/70. The chapter-2 rework replaced the always-on `attackrange >= 9` ranged_presence with per-spell-bundle evidence (curated burst_aoe + the spell's own delivery/cast range, cited overrides for gap-closers; audit in `pipeline/out/ranged_presence_report.json`). 42 weapons qualify (was 57); Great Arcane, Locus and the shapeshifter staffs lost their always-on flag because no selected spell of theirs delivers ranged AoE — the one lost role-level hit follows from that supply shift. This is the sounder rule pricing the same comps honestly, not a tuning regression; the gate holds.

**V5. Curation reliability.** Two people independently score 15 weapons; disagreement >1 point on >10% of cells means the capability definitions are too vague — tighten definitions before mass curation.

**V5b. Automated evidence lint** (promoted from V5 findings — now a mandatory CI gate, see design doc §6.3): every nonzero capability score must cite a spell UniqueName; the lint verifies the spell is actually equippable on that item (ao-bin-dumps `craftingspelllist`), that the spell's function tags/description support the claimed capability class, and that its target direction (enemy/ally/self) matches. Catches fabricated capabilities and direction errors without waiting for human review.

*V5-type reviews caught two bugs on day one (2026-08-12), which is why V5b exists:*

*Catch #2 — 1H Mace listed `purge 1`; the weapon has none. Wiki-verified the full mace ability list: no mace Q/W removes buffs, and 1H Mace's E (Deep Leap) is a mobility/stun leap. The purge actually lives on Heavy Mace's E (Battle Howl, "purges before the silence") — meaning the original Heavy Mace sheet was wrong in the opposite direction (filed purge as a W choice when it's inherent). Both sheets corrected with per-spell citations; the data model was reworked so capability sheets exist per item with a mandatory `evidence_spell` column, and archetype capabilities are computed by composition, never hand-entered.*

*Catch #1 (earlier): domain review flagged Longbow's `knockback_displace 2` — bow-line Frost Shot knocks the **user** back (repositioning), not enemies, and isn't in the standard group kit. Fixed in prototype + design doc; taxonomy gained a directionality rule (self- vs enemy-targeted effects) and a curation lint. This validates the review step as essential, and confirmed a hard data limit: no public source records which spells players run per content (killboard `ActiveSpells` is empty everywhere; all "build stats" sites show items only), so default kits must come from human curation per content type — the only statistical alternative is opt-in client-side capture, AODP-style (Phase 3+, optional).*

## Tier 3 — Data pipeline claims (before Phase 3 investment)

**V6. Content-labeling accuracy.** Sample 100 battles, hand-label content type from context, measure classifier agreement. Gate: ≥80% precision on castle/hellgate/roads labels, else Phase 3 stats stay content-agnostic.
**V7. Coverage at scale.** Rerun V2 across ~200 battles of varied size/server (script, not eyeball). Gate: ≥85% weapon attribution in 10–50-player battles. **Script exists (2026-08-13): `pipeline/sample_battles.py`** — samples the official gameinfo API with per-battle caching, buckets by fight size (small <12 / mid 12–30 / large >30), writes `out/weapon_usage_v2.json` with a coverage stat; the dashboard quotes it as display-only "field reports". Check the coverage number in that file against the 85% gate on each refresh.
**V8. Statistical sanity backtest.** Compute weapon win-lift on 3 months of data; check that community-consensus-strong weapons show positive lift. If stats contradict consensus everywhere, the confounds dominate and δ (MetaPrior weight) stays small.

## Standing regression suite

`prototype_engine.py` graduates into the real repo as the seed of the unit-test suite: every golden case stays green through every tuning change, every patch-driven data update, and every scoring refactor. Add a golden case whenever an expert disagrees with the engine and the expert is right.
