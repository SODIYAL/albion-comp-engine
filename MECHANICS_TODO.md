# Game-Mechanics Modeling — Open Questions & TODO

Goal: teach the engine real fight mechanics (Focus Fire / Resilience, AoE
escalation, Disarray, …) via direct numbers supplied by the expert. These will
modify **capability supply vs target** in `engine/engine.py` +
`pipeline/app_scoring.js` (change one, change both, rerun parity).

Status: **All three ZvZ mechanics received (2026-08-13, wiki): Focus Fire /
Resilience, AoE Escalation, Disarray. Canonical data home:
[pipeline/templates/mechanics.yaml](pipeline/templates/mechanics.yaml) — not
yet consumed by the build/engine. Remaining number gaps: resil-pen per weapon
(Q7), CC-escalation durations (Q8), escalation eligibility per spell (Q9),
current Disarray level table (Q12). Playstyle research pass done 2026-08-13:
attackers-per-target is a STYLE property — provisional per-style mechanics
table awaits expert sign-off (Q14).**

## Where the gap lives (context)

- [engine.py:73-78](engine/engine.py#L73-L78) — supply is a flat linear sum;
  no interaction with fight size, clump size, or targets actually hit.
- [engine.py:61-63](engine/engine.py#L61-L63) — targets scale linearly with
  party size; currently `burst_st` and `burst_aoe` scale identically.
- [scoring.yaml:12-16](pipeline/templates/scoring.yaml#L12-L16) — focus fire
  exists only as crude pair synergies; no concept of Resilience saturation.

## Received numbers — Focus Fire / Resilience (wiki, post-Realm-Divided 30.000.1)

Built-in protection: damage taken is reduced by a % that grows with the number
of players attacking the target. Lookback window 10s, buff lasts 5s.
**Resilience Penetration** (a per-weapon/ability stat, melee-heavy) lets an
attacker ignore a % of this reduction.

Melee and ranged currently share the same unmounted values; mounted targets
have their own (harsher) column.

| Attackers | Unmounted DR | Mounted DR | | Attackers | Unmounted DR | Mounted DR |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0% | 0% | | 14 | 63.3% | 75.2% |
| 2 | 14.3% | 14.3% | | 15 | 64.6% | 76.8% |
| 3 | 25.9% | 25.9% | | 16 | 65.9% | 78.2% |
| 4 | 35.3% | 35.3% | | 17 | 67.1% | 79.5% |
| 5 | 42.0% | 43.0% | | 18 | 68.2% | 80.0% |
| 6 | 46.6% | 49.4% | | 19 | 69.2% | 80.0% (cap) |
| 7 | 50.0% | 54.7% | | 20 | 70.2% | 80.0% |
| 8 | 52.4% | 59.2% | | 22 | 72.0% | 80.0% |
| 9 | 54.6% | 63.0% | | 24 | 73.6% | 80.0% |
| 10 | 56.6% | 66.2% | | 25 | 74.3% | 80.0% |
| 11 | 58.5% | 69.0% | | 26+ | 75.0% (cap) | 80.0% |
| 12 | 60.2% | 71.3% | | | | |
| 13 | 61.8% | 73.4% | | | | |

**Derived: effective attacker-equivalents** E(N) = N × (1 − DR(N)) — the real
throughput of N players focusing one unmounted target:

| N | E(N) | marginal |
| --- | --- | --- |
| 1 | 1.00 | — |
| 2 | 1.71 | +0.71 |
| 3 | 2.22 | +0.51 |
| 4 | 2.59 | +0.37 |
| 5 | 2.90 | +0.31 |
| 7 | 3.50 | +0.30 |
| 8 | 3.81 | +0.31 |
| 10 | 4.34 | +0.27 |
| 15 | 5.31 | ~+0.19 |
| 20 | 5.96 | ~+0.13 |
| 26+ | N/4 | +0.25 flat |

The 3rd attacker is worth half the 1st; by ~7 attackers each additional one
adds ~0.3 attacker-equivalents. Stacked single-target damage saturates HARD.

**Realm Divided (30.000.1) balance notes** (context for weapon-class skew):
melee dominance in ZvZ came from high Resilience Penetration; the patch cut
resil-pen generally and softened Resilience at 5+ attackers. Net: at
7-attacker Resilience ranged deals +6.4%, melee −4.6% avg; at 12-attacker,
ranged +18.8%, melee −2.8% avg. Unmounted cap moved 80%@25+ → 75%@26+.

**Mob HP bonus** (+10% max HP per player over threshold, up to +100%): PvE
mechanic — OUT OF SCOPE for the PvP comp engine; recorded for completeness.

## Received numbers — AoE Escalation (wiki + Wild Blood 23.000.1)

Built-in bonus damage for AoE spells "designed to attack three or more
players"; explicitly **in addition to Disarray**. The magnitude curve is
GLOBAL (not per-spell); which spells escalate is a per-spell eligibility flag.

| Targets hit | Damage bonus |
| --- | --- |
| 1 | 0% |
| 2 | +8% |
| 3 | +16% |
| 4 | +24% |
| 5 | +32% |
| 6 | +40% |
| 7 | +48% |
| 8+ | +56% (cap) |

Formula: `bonus = 8% × (targets − 1)`, capped at 8 targets. Applied **after
all other buffs** and NOT reduced by the ~150% damage soft cap. The same
mechanic gives AoE root/stun/silence spells increased CC duration ("CC
Escalation") — that duration curve was NOT in the wiki table (Q8).

Eligibility lists from Wild Blood 23.000.1 (fixed/improved, not exhaustive):
~40 damage spells (Spinning Blades, Heroic Cleave, Tornado, Avalonian Beam,
Firebreath, …) + 9 CC spells (Avalanche, Freezing Wind, Earth Shatter, …).
Full lists preserved in this repo's chat history and mechanics.yaml comments;
authoritative extraction should come from ao-bin-dumps (Q9).

**Derived: the AoE-vs-ST throughput gap at scale.** One player's AoE hitting
8 clumped enemies delivers ×1.56 (escalation, near-zero Resilience since each
enemy has few attackers-on-them). One player among 8 focusing a single target
delivers ×0.476 (52.4% Resilience). Per-player throughput ratio ≈ **3.3 : 1**
in AoE's favor — the mechanical root of AoE dominance in large fights, now
reproducible from data instead of hand-tuned template weights.

## What this means for the engine (design reading, to confirm)

1. **Focus fire is a protection, not a capability.** Resilience DEVALUES
   stacked single-target damage: `burst_st`/ST-family supply should pass
   through a saturation transform shaped like E(N), not a linear sum.
2. **AoE gets a double advantage in large fights**: spread damage mostly
   dodges Resilience (each enemy hit has few attackers-on-them) AND escalates
   per target hit. This is the mechanical explanation for AoE dominance at
   scale — the engine should reproduce it from the numbers, not hand-tuning.
3. **Resilience Penetration is a per-weapon stat** worth surfacing (possible
   new capability or sheet attribute) — it's why melee stayed viable as ZvZ
   damage. Post-patch values needed from dumps.
4. **Mounted column (80% cap at 18+) touches `catch`**: dismount-bombing a
   mounted target needs burst past an even harsher curve — but for 21+
   groups the forced-dismount CC/cleanse immunity is gone (29.040.1), so
   landing the dismount pays off more.
5. **Disarray is relative, not absolute**: it debuffs the attacker's damage
   and CC by 1%/level-difference only when OUTNUMBERING (level 0 ≤20
   players). Under the mirror-fight assumption it cancels exactly — it
   prices bringing more bodies, not comp choices. See Q11 for whether it
   enters scoring at all.

## Playstyle → mechanics parameters (research pass, 2026-08-13)

The Q2b question ("how many attackers focus one target?") has no single
answer — **it is a property of the playstyle, not the content**. Community
descriptions of the archetypes, confirmed across sources:

- **Clap** (aka bomb squad / blap): tanks CREATE the clump (Hand of Justice
  Onslaught pull, chained CC), then all DPS sync AoE bursts on the clump on
  one call. Damage delivery = synced AoE on 6–8 stacked targets → AoE
  escalation near its 56% cap, Resilience largely bypassed (each enemy in
  the clump has few attackers-on-*them* individually). Metabattle's Hand of
  Justice guide: dive deep, pull into your zerg, CC-chain — "a great choice
  for a shotcaller." Longbow guide: root the clump (Ray of Light), burst AoE
  (Rain of Arrows), "hit as many targets as possible."
- **Brawl**: sustained melee ball that grinds into the enemy; players fight
  semi-independently, damage spread across whoever is in reach. Cleaves hit
  ~2–4 targets; attackers-per-enemy stays low (~2–4). Sustain gear
  (Mistwalker Jacket named as "the single most important piece"). Forum
  meta thread: melee brawl DPS dominant in ZvZ, partly via high Resilience
  Penetration (pre-Realm-Divided).
- **Kite**: ranged poke at max range, disengage on commit, never brawl.
  Damage = AoE poke on the advancing clump (3–5 targets); focus fire only on
  overextended divers (3–5 attackers).
- **(Not yet a style in our styles.yaml) Assassination/dive**: small squads
  focusing ONE backline target — the only archetype that runs deep into the
  Resilience curve (5–10 attackers → 42–57% damage lost).

**Proposed system** — extend `templates/styles.yaml`: each style gains a
`mechanics` block, e.g. `expected_aoe_targets` (feeds the escalation curve
for AoE-family supply) and `focus_attackers` (feeds the Resilience curve for
ST-family supply). Content templates may add a clump modifier later (castle
chokes clump harder than open field), but the style is the primary driver.
Weapon-side playstyle affinity needs NO new per-weapon data: it already
emerges from the capability sheets (burst_aoe-heavy = clap-suited;
sustained_dps + self_sustain = brawl-suited; range + mobility + disengage =
kite-suited) — which is exactly what style weight-multipliers already
express on the demand side. Metabattle's ZvZ role tags (31 tagged builds:
healer/tank/support/melee DPS/range DPS) can serve as external validation
of our capability-derived classifications, and design doc §2.4 already
plans harvesting them.

PROVISIONAL numbers for the expert to confirm/correct (research-derived,
NOT wiki data — do not put in mechanics.yaml until confirmed):

| Style | expected_aoe_targets | focus_attackers |
| --- | --- | --- |
| clap | 6–8 | 3 |
| brawl | 3 | 3 |
| kite | 4 | 4 |
| balanced | 4 | 4 |
| brawl_clap | 4–5 | 3 |

Research sources: [Metabattle ZvZ builds](https://metabattle.com/albion/ZvZ_Builds),
[Metabattle Longbow ZvZ](https://metabattle.com/albion/Longbow_ZvZ_PvP_Build),
[Metabattle Hand of Justice ZvZ](https://metabattle.com/albion/Hand_of_Justice_ZvZ_Build),
[AO forum: "Clap and Brawl DPS in the ZvZ environment"](https://forum.albiononline.com/index.php/Thread/216096-%E2%80%9CClap-and-Brawl-DPS-in-the-ZvZ-environment%E2%80%9D/),
[albiononlinegrind group builds](https://albiononlinegrind.com/group-builds).
Note: albiononlinegrind + the official forum 403 direct fetches (search
snippets only); albionfreemarket unreachable from this network today.

## Questions — answered

- [x] **Q3 — Focus fire: which mechanic exactly?** ANSWERED: overkill
  saturation via the Resilience DR table above — a supply-side diminishing
  transform on ST damage, keyed to attackers-per-target. Not a synergy term.
- [x] **Q1 — form of numbers**: ANSWERED. Resilience = global table. AoE
  escalation = global curve + per-spell eligibility flag. Resilience
  Penetration = per-weapon stat. Global numbers live in
  `pipeline/templates/mechanics.yaml`; per-spell parts go through the
  sheets/overrides layer with dumps citations when they arrive.
- [x] **Q6 — AoE escalation magnitudes**: ANSWERED — global 8%/target from 2
  targets, cap 56% at 8 targets, applied after buffs, bypasses the ~150%
  damage soft cap. What remains per-spell is only eligibility (→ Q9).

## Questions — still open

- [ ] **Q2 — Enemy model.** Resilience needs "how many of OUR players focus
  one target" and AoE escalation needs "how many enemies does our AoE hit."
  Default proposal: mirror fight (enemy count = party size) + per-content
  clumping factor. Confirm or supply numbers.
- [ ] **Q2b — Supply-units → attackers mapping.** PARTIALLY RESOLVED by the
  playstyle research: attackers-per-target is a STYLE property (see the
  "Playstyle → mechanics parameters" section) — clap syncs everyone on a
  clump via AoE, brawl spreads 2–4 per target, dive squads stack 5–10 on
  one. Remaining: the unit-scale question (≈ how many supply units is one
  dedicated attacker) and expert sign-off on the provisional table.
- [ ] **Q14 (new) — Expert confirmation of per-style mechanics numbers.**
  The provisional `expected_aoe_targets` / `focus_attackers` table is
  research-derived; confirm or replace with your numbers before it enters
  `styles.yaml`. Also: should an `assassination/dive` style be added (the
  one archetype living deep in the Resilience curve), or is it out of scope
  for group comp forging?
- [ ] **Q15 (new) — Weapon playstyle affinity: derive or curate?** Proposal:
  DERIVE from existing capability sheets (no new per-weapon judgment data),
  validate against Metabattle's 31 ZvZ role tags; only curate exceptions
  where the derivation and the community tags disagree. Decide after the
  mechanics wiring makes the derived affinity visible.
- [x] **Q4 — Disarray numbers**: ANSWERED, and it corrects the earlier guess
  (it does NOT inflate heal/tank needs). Disarray reduces the ATTACKER's
  damage and CC duration by 1% per level of Disarray difference vs the
  target, and only when the attacker's level is HIGHER. Level 0 at ≤20
  players; level 1 at 21; level 5 at 25; ~level 26 at 60. Full tables +
  battle-mount points, Homesick, and the forced-dismount immunity removal in
  `mechanics.yaml`. Consequences → Q11, Q12.
- [ ] **Q5 — Threshold or continuous?** Resilience answers itself (continuous
  from 2 attackers, so even `castle_outpost` at 7 is affected). Still open
  for AoE escalation: expected-targets-hit per content size (ties into Q2 —
  escalation caps at 8 targets, so clump-size assumptions matter most in the
  2–8 range).
- [ ] **Q7 — Resilience Penetration values.** Post-Realm-Divided per-weapon
  values (dumps). Model as new capability, sheet attribute, or fold into
  ST-damage effectiveness?
- [ ] **Q8 (new) — CC Escalation duration curve.** AoE root/stun/silence get
  increased duration per target hit — same 8%/target shape or different?
  Numbers not in the wiki table. Matters for `stun`/`zone_control`/
  `clump_create` value at scale, not just damage.
- [ ] **Q9 (new) — Per-spell escalation eligibility.** Which of our curated
  spells escalate? Wild Blood lists ~40 damage + 9 CC spells (fixed/improved,
  possibly not exhaustive). Extraction pass over ao-bin-dumps needed to map
  spell names → our weapon sheets/lines; results go through
  `effect_overrides.yaml`-style evidence discipline.
- [ ] **Q10 (new) — Does `burst_aoe` supply become escalation-weighted?**
  If most meaningful ZvZ AoE spells escalate, a global multiplier on AoE
  supply may suffice; if eligibility is patchy across our 137 weapons,
  per-weapon escalation flags change relative weapon rankings within the
  AoE class — this decides whether Q9 blocks implementation or refines it.
- [ ] **Q11 (new) — Is asymmetric-numbers modeling in scope?** Disarray is
  RELATIVE: under the mirror-fight assumption (Q2 default) it is exactly a
  no-op, because both sides sit at the same level. It prices OUTNUMBERING,
  not composition. Options: (a) record it, wire nothing (mirror assumption
  stands); (b) add a per-content "expected numbers asymmetry" parameter —
  then Disarray devalues damage AND CC supply at sizes 21+ when outnumbering
  (a CC-reliant clump comp is doubly taxed), and slightly favors the
  outnumbered side's effective tankiness; (c) surface it only as UI advice
  ("at size 25 you fight at −5% vs smaller groups"), no scoring change.
  Recommendation: (a) or (c) now, (b) only if content templates gain an
  enemy-size field. Note our templates: only `castle` (25) crosses the
  21-player threshold at base size, but free-form sizes go to 60 (~−26%).
- [ ] **Q12 (new) — Disarray level table staleness.** The wiki group-size
  table is labeled Version 22.090.1 and tops out at level 67 (445 players);
  Radiant Wilds (31.000.1, 2026-04) extended max level to 99 and added
  battle-mount contributions. Verify the current level-vs-size mapping from
  dumps/forum before wiring anything that reads it.
- [ ] **Q13 (new) — CC value at 21+ sizes.** Two received mechanics touch CC
  in opposite directions: CC Escalation (duration UP per target hit, Q8) vs
  Disarray (duration DOWN when outnumbering, Q11). Also forced-dismount
  immunity is REMOVED for 21+ groups (29.040.1) — dismount-bombing a blob is
  more lethal, which raises `catch`/`clump_create` value at castle sizes.
  These need to be netted coherently, not wired independently.

## Implementation checklist — DONE 2026-08-13 (first wiring)

- [x] Mechanics data home: `pipeline/templates/mechanics.yaml`, shipped into
  the dataset by `build_dataset.py` under a top-level `mechanics` key.
- [x] Placement decided: SUPPLY-side effectiveness multipliers, per style,
  NORMALIZED to balanced (balanced ≡ identity — template calibration and
  the V4 baseline untouched by construction). Escalation → `burst_aoe`;
  Resilience → `burst_st` + `execute`. `sustained_dps` deliberately in
  neither family (spread damage fits neither curve cleanly).
- [x] Double-counting: gamma concavity is per-capability diminishing returns
  on COVERAGE; the mechanics multipliers are style-RELATIVE physics — they
  compose rather than double-count. The `resist_shred×burst_st` synergy
  kept as-is for now (resist shred ≈ resilience-pen analog — revisit with
  Q7 data).
- [x] Implemented in `engine/engine.py` AND `pipeline/app_scoring.js`;
  parity 60/60 at 1e-9 across all templates × styles.
- [x] Golden: all previous cases pass unchanged (T10 clap-direction margin
  WIDENED — mechanics reinforce the style axis); new T11/T11b/T11c pin
  escalation direction, Resilience direction, and the supply transform.
  Suite is now 18/18.
- [x] V4 rerun: identical to baseline (role 69%, weapon 9%) — EXPECTED,
  since V4 evaluates at balanced and balanced is the identity. Mechanics
  quality is untested until styled expert comps exist (ties into Q14).
- [x] Design doc amendment (2026-08-13, "later") + HANDOFF updates written.

## Reliability roadmap (2026-08-13) — from "scores well" to "actually ideal"

Motivating failure, measured: **Dagger Pair ranks #2/137** recommending into
a half-built 20-man blackzone party — pure breadth-over-depth (a pile of 1–2
point utility caps), the exact V4 finding. Real usage (149 battles): **2
players out of ~470 in the >30 bucket (~0.4%)** vs Spiked Gauntlets 47,
Deathgivers 28, Hallowfall 27. The mechanism layer says "plausible"; the
battlefield says "nobody does this." The fix is layering, not more tuning:

1. **Mechanism (built)** — sheets + evidence lint: no score without a cited
   spell. Anti-hallucination for WHAT a weapon does.
2. **Physics (built, style-relative only)** — mechanics layer. GAP: at
   balanced it is the identity, so ST weapons aren't taxed by fight size.
   Fix: per-CONTENT mechanics params (expected clump / attackers scaled by
   template+size) applied absolutely — needs one recalibration pass of
   burst_st/burst_aoe targets, golden must stay green. → Q16
3. **Empirics (data exists, unwired)** — promote `weapon_usage_v2.json`
   into a per-size-bucket MetaPrior with Bayesian shrinkage + minimum-n
   (design §8 came early). δ=0.15 slot already exists in the score; today
   it covers 7 hand-set weapons. Usage prior is INDEPENDENT of template
   calibration → V4 with prior on/off is a legitimate A/B, unlike template
   tuning. Guardrails: shrinkage (149 battles must not overfit), large
   bucket thin (6 battles — top up first), prior stays a nudge (δ moderate)
   so novel-but-sound comps aren't crushed. → Q17
4. **Expert loop (running)** — Tier-2 blind tests; every correction becomes
   a golden case. Long-term: content labeling (V6) + win-lift (V8) turn
   "who plays it" into "who WINS with it."

Weapon tagging reliability = cross-source agreement, not authorship:
capability-derived role (sheets) × albionbb's pre-classified per-player
`role` field (real battles) × Metabattle tags (community). 3/3 agree →
trusted; disagreement → expert queue, never silently overridden.

- [~] **Q16 — content-absolute mechanics physics. BUILT + MEASURED
  2026-08-14; UNCOMMITTED, pending sign-off.** The physics is now ABSOLUTE by
  size, anchored to (balanced style, base_size): at base size nothing changes
  (calibration untouched, golden 20/20 + parity 60/60 green), but ABOVE base
  size single-target damage is taxed harder (more Focus Fire) and AoE boosted
  (more Escalation). Growth is sub-linear + capped: `grow(p) = min(8, p*(1 +
  0.5*(scale-1)))`, `scale = size/base_size` (the "capped/realistic" curve the
  user chose). Verified: `burst_st` mult drops x1.000@20 → x0.896@30 →
  x0.825@40 → x0.736@60; `burst_aoe` rises to x1.258@60.
  **KEY FINDING — Q16 is correct physics but is NOT the Dagger-Pair fix.**
  It taxes DAMAGE caps only (`burst_st`/`execute`, boosts `burst_aoe`), but DP
  ranks high on UTILITY BREADTH (catch/mobility/peel/stun/…), which Q16 doesn't
  touch — so DP stays #3 through size 40, dropping to #5 only at 60. Bridled
  Fury (also a single-target dagger) drops too; Q16 taxes ST broadly and does
  not distinguish the two. Magnitudes (0.5 damp, cap 8) are my choices, not
  expert-validated, and V4 can't validate Q16 (V4 runs at base size where
  scale==1). Ship-or-hold is a validation call; it stands on grounded-physics
  merit (Resilience/escalation tables are wiki-sourced) independent of DP.

- [x] **Q18 — breadth/redundancy penalty. INVESTIGATED + REJECTED 2026-08-14.**
  Hypothesis (VALIDATION.md V4 finding #2): DP over-ranks because fitness SUMS
  its per-cap marginal gains across all 12 caps, as if one player delivers
  every capability at once (an action-economy fiction). Fix tried: a geometric
  discount on a candidate's sorted per-cap benefits (`rho^rank`; best counts
  full, 2nd × rho, …; costs undiscounted; rho=1.0 = provable identity, verified
  to 3.6e-14). **Swept rho 1.0→0.35 and it does NOT earn its place:**
  - DP barely moves at base size (its TOP contributions are genuine gaps); it
    only drops meaningfully once rho is aggressive enough to distort everything.
  - V4 role stays 69% then REGRESSES to 65% at rho≤0.45 — the 8 role-misses are
    the saturation-metric artifact (drop 1 of several healers → healing still
    covered → a bruiser wins the 20th-body contest), not breadth cases.
  - It can BACKFIRE: rho=0.55 nudged DP from #8 UP to #5 in a diver-present
    party, because the discount also hits DP's breadth-bruiser competitors.
  **Decisive counter-evidence — the engine ALREADY de-ranks DP by context:**
  dive-less party DP #3 (a real gap, correct) → add 1 diver #8 → add more #39.
  Concavity + supply already collapse DP's marginal once its niche is filled.
  So the "DP over-ranks" premise is largely FALSE for realistic parties; the
  original #2/#3 alarm was a dive-LESS party where DP filling that gap is right.
  Reverted; engine.py left Q16-only. REVISIT only with V4b (reconstruct the
  last ~5 binding slots) if a genuine saturated-regime breadth failure appears.
- [x] **Q19 — loadout model (one-spell-per-slot) + single-target recalibration.
  SHIPPED 2026-08-14.** Expert insight: a weapon's sheet lists caps across ALL
  its Q/W/E/passive spell options, but a player equips ONE per slot — Dagger
  Pair can't run Shadow Edge (catch/stun/peel) AND Dash (disengage) AND
  Forbidden Stab at once. The flat `caps[cap]=max(...)` union in build_dataset
  summed the whole menu. FIX (two coupled parts, both required):
  1. **Loadout model.** `build_dataset.build_loadout()` auto-derives each cap's
     ability SLOT from its evidence spell (via weapon_lines spells-by-slot;
     measured clean — 1278/1319 caps resolve to one slot, 0 span multiple, 41
     are the WEAPON_STATS always-on sentinel) and emits `loadout:{always, slots}`
     per weapon. The engine (`best_loadout`) + JS score a CANDIDATE as its best
     single loadout: one bundle per slot, NO empty option (a player always has
     each slot filled — the empty option let weapons dodge over-stack penalties
     and cost 11pts of V4). Base-party supply stays flat-union so fitness()/
     golden are untouched; only the evaluated candidate is loadout-limited.
  2. **Single-target recalibration** (expert ruling: single-target damage is
     weak in 20-man group content — heals + Resilience overpower focused
     damage). blackzone_roam + territory_defense `burst_st` weight 4/3→1,
     target 4/3→2; `execute` weight 4/3→1. Kept a token weight (kill-secure
     still happens), not zeroed like castle_outpost.
  **COUPLING (measured):** the loadout model ALONE regresses V4 to 50% (fixing
  the double-count changes every marginal, so the flat-calibrated templates no
  longer fit); WITH the recalibration it reaches **V4 role 73% — first pass of
  the 70% gate**, up from the 69% flat baseline. Golden **22/22** (added T14
  one-spell-per-slot, T15 AoE-dagger-beats-ST-dagger), parity **60/60**. Dagger
  Pair in a rounded 20-man: **#3 → #33**, and Demonfang (AoE dagger) now
  out-scores it — the expert's principle. FOLLOW-UPS: (a) other template
  targets were calibrated on the flat supply model too and may want a full
  recalibration pass now that supply is loadout-aware (V4 is weak-form here —
  circularity); (b) base-party members still use flat-union supply, not a joint
  best-loadout — a future refinement; (c) `explain()`/dashboard now report the
  chosen loadout's caps, but the dashboard artifact under docs/ must be rebuilt
  (`build_dashboard.py`) + deployed for the live site to reflect this.
- [~] **Q17 — usage-derived MetaPrior. BUILT + MEASURED 2026-08-14; NOT
  wired (deliberately).** `pipeline/build_meta_prior.py` produces a
  size-bucketed prior from `weapon_usage_v2.json` (share × n/(n+8) shrinkage,
  per-bucket normalize to 1.0, positive-only) → `out/meta_prior_usage.json`.
  The engine + JS now DETECT a bucketed prior and pick the bucket by size
  (small <12 / mid 12-30 / large >30); flat maps behave exactly as before
  (golden 20/20, parity 60/60). The prior is data-honest and size-correct —
  it captures the case study cleanly: Dagger Pair 0.43 mid / 0.00 large,
  Bridled Fury 0.00 mid / 0.20 large.
  **KEY FINDING — the prior does NOT fix the Dagger-Pair-at-scale
  over-ranking.** A/B (flat vs usage) and a δ sweep (0.15→0.8, i.e. up to 5×)
  both leave V4 at 69% and Dagger Pair at #3. The meta term (δ·prior) is far
  weaker than the fitness term; DP ranks high on shallow-broad COVERAGE, and
  no prior weight overcomes that. The real fix is fitness-side: **Q16**
  (content-absolute Resilience taxing single-target damage at scale) or a
  breadth/redundancy penalty. Also note: at mid (20-man) the usage data
  actually SUPPORTS Dagger Pair (0.43) — people do run daggers there; the
  genuine bug is only at large (30+), where DP is absent yet still ranks #3.
  CONFOUND still stands: usage conflates viability with price/accessibility;
  the prior shrinks toward NEUTRAL at low n (never negative), and only
  win-lift (V8) may demote a weapon the mechanism layer likes. TO ADMIT:
  paste `meta_prior_usage.json`'s `meta_prior` into scoring.yaml, rebuild,
  re-run the A/B — but per project rule it stays display-only until it
  demonstrably improves a metric, which at δ=0.15 it does not.

**Case study (2026-08-13): Dagger Pair vs Bridled Fury** — line-mates,
identical Q/W, only the E differs (EXECUTEDAGGER burst_st:3+execute vs
CRYSTAL_DAGGER_BLADE_RING burst_aoe:2+mobility). The sheets encode the
user's game-sense EXACTLY right (layer 1 sound). Yet at blackzone 20
balanced the engine ranks DP #2 vs BF #32 — BACKWARDS — because (a) the
template demands burst_st 4 + execute 2 units that nobody in the test party
supplies, so DP's deep ST scores land huge marginal deltas (3.27 + 2.46),
and (b) no absolute Resilience tax exists at balanced to shrink them (the
mechanics layer is style-relative). BF's burst_aoe lands in partially
saturated AoE supply → small delta. Q16 is the structural fix; the ST
targets/weights in the 20-size templates are also suspect (expert: how many
dedicated ST units does a real 20-man want? plausibly ~0 — ST arrives
incidentally on utility kits).

## Overnight session (2026-08-14) — done + upgrade menu

SHIPPED overnight (committed, tested where possible without a live game):
- **Shape-based auto-calibration** (`4e1e779`): the companion dispatches events
  by parameter SHAPE, not hardcoded code numbers, so a patch that renumbers
  events self-heals. `/status` shows the detected role→code bindings.
- **Connect-companion button** (`afa0f62`): Comp Forge rail control that polls
  the companion and loads the live party into a comp. Verified vs a mock.

BLOCKED on one live run (needs the game + you): confirm spells resolve,
auto-calibration binds, and the connect button pulls the live party. See
`companion/README.md` "Status — pick up here".

OPEN REQUIREMENT (2026-08-14, from live testing): **keep the roster live
through mid-fight joins/leaves.** Today only the bulk roster event (231)
updates membership; if a party join/leave arrives as a separate INCREMENTAL
event, the roster goes stale until the next zone. Must determine (by watching
a live join/leave): does 231 re-fire on membership change (then already
handled), or is there an incremental "player joined/left" event to add a
handler for? Identify by correlating the /schema + --debug timestamp with the
actual join/leave; do NOT guess the shape (a party-join looks like NewCharacter
— a name + guid + flag — so a blind handler would pollute the party with
visible guildmates). Also: the roster event only fires on zone/party-change,
so the companion must be running before you zone into content (or trigger one
zone) to capture the initial party.

Upgrade menu, roughly highest-value first — pick when you resume:
1. **The one live verification run** (finishes the whole companion arc).
2. **Q17 usage-derived MetaPrior** — kills the Dagger Pair over-ranking using
   the 149-battle data already in hand; has a clean V4 on/off A/B. Biggest
   engine-quality win that needs no new data.
3. **Spell picks into scoring** — now that the companion resolves each player's
   real Q/W/E to sheet evidence IDs, feed them into the (QW)-conditional layer
   so a comp is scored on actual loadouts, not line defaults.
4. **Magnitude audit queue** (below) — 16 RULE groups need your adjudication;
   each is a quick call that improves data quality.
5. **Q16 content-level physics** — absolute Resilience/escalation by content so
   single-target damage is taxed at 20-man even under balanced (flips the
   Dagger Pair vs Bridled Fury case). Needs a template recalibration.
6. **Gear sheets** — the biggest remaining build item (design doc §2.4);
   unblocks archetype composition + the cleanse-if-running-X conditional UI.
7. **Companion polish** — show spell names in the connect box / weapon drawer;
   version-check cache refresh instead of the 7-day timer; item-power display.

## Magnitude audit — dataset-wide (opened 2026-08-13)

Standing rule: every capability score encodes MAGNITUDE, not existence.
Tooling: `py -3 pipeline/build_magnitude_review.py` → `review/magnitude.html`
(1,319 rows / 28 capabilities; every score beside its dumps numbers).

- [x] `knockback_displace` — DONE (the founding pass): holy W Sacred Pulse
  removed line-wide, AA-passive removed, all air-throws/knock-ups → 1 (no
  travel), Tackle → 1 (dumps: 2m), Backhand + Launcher line-unified. Golden
  T13 pins the ladder.
- [ ] **RULE queue — 16 same-spell-different-score groups (89 rows).** Each
  is either a real line-rule violation or a legitimate E-supplement missing
  its mandatory comment. Expert adjudication needed per group:
  anti_dive/QS_WHIRLWIND2 [1,2] · buff_allies/EMPOWERBEAM [1,2] ·
  buff_allies/HOLYHOT [1,2] · burst_aoe/BOLTSHOT [1,2] ·
  burst_st/KNUCKLECOMBO [1,2] · catch/LEGBREAKER [1,2] ·
  catch/SKILLSHOT_TELEPORT [1,2] · disengage/GROUNDDASH [1,2] ·
  engage/CHARGESLOWAE [1,3] · engage/CHARGE_ROOT [1,2] ·
  peel/SEPARATING_SLAM [1,2,3] · peel/SHIELDFRIENDLY [1,2] ·
  sustained_dps/CURSEDOT [1,2] · sustained_dps/PASSIVE_AASPEEDCHANCE_DAGGER
  [1,2] · zone_control/FROSTBOMB_CASTSLOW [1,2,3] ·
  zone_control/SACRED_GROUND [1,2]
- [ ] **PASV queue — 39 rows** where PASSIVE_*/WEAPON_STATS evidence grounds
  a score ≥2; each needs an explicit justification or a downgrade.
- [ ] **TOP review — 44 score-3 rows**, the top of every ladder, reviewed
  capability by capability against the dumps numbers on the board.
- [ ] After each adjudicated capability: corrections through sheets, golden
  case when a ruling changes, rebuild, gates.

## Game/party integration roadmap (researched 2026-08-13)

Goal: automate "who is in the party and what do they play" per person.
Verified live today: gameinfo `search?q=name` → player Id; `players/{id}/kills`
(and `/deaths`) carry FULL equipment per event with timestamps — a per-player
recent-loadout history. CAVEAT: no `access-control-allow-origin` header
(verified) — the public page cannot call it directly; needs a tiny proxy
(Cloudflare Worker) or a local helper script producing a paste/drag JSON.

- [ ] **Stage 1 — killboard roster import (ToS-clean, build next).** Paste
  names or a guild name (guild members endpoint) → per player: recent
  MainHand distribution by fight-size bucket → auto-fill slots with
  most-likely weapon + confidence + click-to-override. Enables CONSTRAINED
  FORGING: best comp where each member plays only weapons they demonstrably
  play (assignment problem over engine scores × player weapon pools).
  Decide CORS route: Worker proxy vs local helper JSON.
- [~] **Stage 2 — live companion. WORKING (live-verified 2026-08-14) —
  `companion/`**. Roster + weapon + full gear confirmed against a real
  5-person party; spell-name resolution built (needs a live test); the Comp
  Forge "connect companion" button is the remaining piece. Authoritative
  resume notes: `companion/README.md` "Status — pick up here" + HANDOFF.
  (Older detail below kept for context.)
  Standalone MIT-stack C# console app: raw-socket capture → PhotonPackageParser
  → party/equipment/spell handlers → `localhost:53321/party` JSON. Compiles
  clean; item DB + HTTP + JSON verified without a live game. REMAINING: one
  live-game run as Administrator to confirm the event-code indices parse
  (party join, NewCharacter, EquipmentChanged) — codes may need a sync vs
  SAT per the README patch ritual. Then the Comp Forge "connect companion"
  button (poll /party, map weapon→slots). Scope: `COMPANION_SCOPE.md`.
- [ ] **(superseded detail) Stage 2 — live companion (legitimate under the visibility rule).**
  No official live API, but the client SHOWS party roster and, via inspect/
  proximity, the gear of players in your zone — so a read-only local Photon
  reader extracting party + equipment surfaces nothing beyond your screen.
  That is the same tolerated category as Statistics Analysis Tool (which
  already decodes party members + weapons, open source, years of open use);
  the banned category is specifically info you CANNOT see (radar, other
  zones). Build route: SAT fork/plugin (C#, already has Photon decoding +
  item-ID mapping) writing party.json to a localhost HTTP endpoint with
  CORS; Comp Forge "connect companion" button polls it (loopback is exempt
  from mixed-content blocking in modern browsers). Only the caller needs to
  run it. CORRECTED 2026-08-13 (owner screenshot): the in-game INSPECT
  window shows the target's full ability loadout — selected Q/W/E, head D,
  chest R, shoes F, passives — plus equipment, average IP and market value.
  So the inspect response carries spell picks even though the web
  killboard's ActiveSpells is empty, and a companion can capture them
  visibility-rule-clean. That unlocks the (QW)-conditional layer: sheets
  mark QW-conditional capability scores precisely because line-mates share
  spell pools — with real picks per player, the engine can score the
  ACTUAL loadout (Sacred Pulse vs Holy Beam changes peel/heal supply),
  not the pool assumption. Average IP is also visible → future gear-
  quality input. Caveats: read-only, no gameplay automation, SBI policy
  can change; per-member inspects may be needed once per session.
- [ ] **Stage 3 — close the loop.** Post-fight battle ingestion labels the
  fielded comp + outcome → V6 content labels, V8 win-lift.

## Not wired (deliberate)

- Disarray: recorded in mechanics.yaml only — cancels in a mirror fight
  (Q11); revisit if templates gain an expected-enemy-size field.
- CC Escalation: no duration numbers yet (Q8) — `stun`/`clump_create`
  untouched by mechanics for now.
- Resilience Penetration: no per-weapon values yet (Q7).
- Per-spell escalation eligibility: global multiplier assumes the AoE class
  escalates uniformly until Q9's dumps extraction says otherwise.
