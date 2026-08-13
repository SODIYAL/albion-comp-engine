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

**V4. Meta-comp reproduction.** Feed the engine each published meta comp (albioncompo, guild guides) minus one member; the engine should propose the missing member's role in top-3. Automatable version of V3. Case list: `tests/meta_comps.yaml` — first real entry recorded 2026-08-12 (shotcaller "Deadlyhooker", large-scale ZvZ, 3 parties × 20, relayed by the project owner; all weapon cells mapped to catalog keys, battlemount slots flagged as outside the weapon model). The runner is blocked on a `large_scale_zvz` content template (only `castle_outpost` at size 7 exists) — and that template's weights must NOT be fitted to this same comp, or the test is circular.

**V5. Curation reliability.** Two people independently score 15 weapons; disagreement >1 point on >10% of cells means the capability definitions are too vague — tighten definitions before mass curation.

**V5b. Automated evidence lint** (promoted from V5 findings — now a mandatory CI gate, see design doc §6.3): every nonzero capability score must cite a spell UniqueName; the lint verifies the spell is actually equippable on that item (ao-bin-dumps `craftingspelllist`), that the spell's function tags/description support the claimed capability class, and that its target direction (enemy/ally/self) matches. Catches fabricated capabilities and direction errors without waiting for human review.

*V5-type reviews caught two bugs on day one (2026-08-12), which is why V5b exists:*

*Catch #2 — 1H Mace listed `purge 1`; the weapon has none. Wiki-verified the full mace ability list: no mace Q/W removes buffs, and 1H Mace's E (Deep Leap) is a mobility/stun leap. The purge actually lives on Heavy Mace's E (Battle Howl, "purges before the silence") — meaning the original Heavy Mace sheet was wrong in the opposite direction (filed purge as a W choice when it's inherent). Both sheets corrected with per-spell citations; the data model was reworked so capability sheets exist per item with a mandatory `evidence_spell` column, and archetype capabilities are computed by composition, never hand-entered.*

*Catch #1 (earlier): domain review flagged Longbow's `knockback_displace 2` — bow-line Frost Shot knocks the **user** back (repositioning), not enemies, and isn't in the standard group kit. Fixed in prototype + design doc; taxonomy gained a directionality rule (self- vs enemy-targeted effects) and a curation lint. This validates the review step as essential, and confirmed a hard data limit: no public source records which spells players run per content (killboard `ActiveSpells` is empty everywhere; all "build stats" sites show items only), so default kits must come from human curation per content type — the only statistical alternative is opt-in client-side capture, AODP-style (Phase 3+, optional).*

## Tier 3 — Data pipeline claims (before Phase 3 investment)

**V6. Content-labeling accuracy.** Sample 100 battles, hand-label content type from context, measure classifier agreement. Gate: ≥80% precision on castle/hellgate/roads labels, else Phase 3 stats stay content-agnostic.
**V7. Coverage at scale.** Rerun V2 across ~200 battles of varied size/server (script, not eyeball). Gate: ≥85% weapon attribution in 10–50-player battles.
**V8. Statistical sanity backtest.** Compute weapon win-lift on 3 months of data; check that community-consensus-strong weapons show positive lift. If stats contradict consensus everywhere, the confounds dominate and δ (MetaPrior weight) stays small.

## Standing regression suite

`prototype_engine.py` graduates into the real repo as the seed of the unit-test suite: every golden case stays green through every tuning change, every patch-driven data update, and every scoring refactor. Add a golden case whenever an expert disagrees with the engine and the expert is right.
