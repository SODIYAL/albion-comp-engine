# Validation Plan — Composition Engine

How we test the design *before* building it, what already ran (2026-08-12), and what remains. Principle: every risky claim in the design doc gets a cheap falsification test; build only after the cheap tests pass.

## Tier 1 — Model validity (ran today, no product code needed)

**V1. Golden-case recommendation tests** — `prototype_engine.py`, runnable anytime (`python3 prototype_engine.py`).
A ~250-line throwaway implementation of the scoring model (13 hand-scored weapons, 1 content template) against 9 assertions encoding what any experienced player knows to be true:

| # | Case | Result |
| --- | --- | --- |
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
| --- | --- | --- |
| Weapon attribution >85% of players | 20/22 (91%) had weapon + role | PASS |
| Win/loss decidable for clean fights | 8–0 kills, 2.0M–0 fame → unambiguous | PASS |
| Full comps reconstructable | Winning side fully legible: 2× Avalon Holy healers, mace+quarterstaff frontline, dual-axe/dagger/frost core | PASS |
| Known noise sources | 2 players weaponless; several `damage: 0` despite kills (stats only captured from kill-event snapshots); battle list contains many-sided brawls where "winner" is meaningless → "inconclusive" label is necessary, as designed | CONFIRMED |

## Tier 2 — Recommendation quality (before/while building MVP, needs humans)

**V3. Expert blind test.** Give 10–15 partial parties to 3+ experienced shotcallers; collect their next-pick independently; compare with engine top-3. Target: expert pick appears in engine top-3 ≥70% of cases. This is the true accuracy metric — the curation prerequisite is now MET (all 137 weapons, 2026-08-12) and `tests/tier2_form.md` is regenerated against the full pool (seed 20260812). **V3 is the project's current critical path**; everything else is tuning noise until it runs.

**FIRST V3 ROUND (2026-08-23, n=1: the owner-expert, in-chat blind protocol)** — all 12 seed-20260812 castle_outpost cases answered blind (engine output withheld until each batch of picks was in), reasoning captured per case:

- **Intent/role-level: 12/12 = 100% (gate 70%, PASS — provisional).** Most answers were role-shaped ("needs a healer", "melee/tank to hold the outpost"), scored the V4 role way; the engine's top-3 contained the asked-for role every time, and its printed weakness diagnosis matched the expert's stated *reasoning* in cases 1, 2, 7 (tankiness/engage; heal_sustain).
- **Named-weapon level: 2 clean hits, 2 misses (n=4).** Hits: Blight Staff called, engine #1 (case 2); Hand of Justice + Hallowfall called, engine #1 and #2 (case 7). Misses: Polehammer called, engine ranked it 10th (case 4); Longbow-or-Greataxe called, engine ranked them 74th/14th and led with Hellfire Hands (case 8).
- **F-V3-1 (clump vs lockdown, case 4): RESOLVED 2026-08-23 — owner ruled CLUMP-FIRST IS RIGHT.** On reflection, dragging enemies into the ranged core's AoE is the stronger play at outposts; case 4 counts as a full engine hit (round 1 role tally effectively 12/12 with the engine also vindicated on the one judged disagreement). No template change; the finding closes.
- **F-V3-2 (playstyle coherence, cases 6/8):** the expert repeatedly reasons about the comp's EMERGING IDENTITY ("battleaxe and weeping repeater clash", "longbow to keep in line with ranged siegebow") — the engine has no concept of a partial comp's identity at small scale and topped case 8 with a utility-damage hybrid (heal_reduction + clump terms) where the expert wanted coherent ranged damage. This independently confirms roadmap item 2 (composition identity detection) from real blind disagreement. **Descriptive v1 shipped same day (2026-08-23):** `comp_identity()` in both engine ports labels the party's playstyle lean from its capability fingerprint; golden T23/T23b/T23c pin the classifications (blap→brawl, fixtures→their styles, case 6→split with Battleaxe flagged) and that NOTHING in scoring reads it. Identity-aware recommendation — the actual fix for the case-8 miss — stays parked until this layer survives more expert rounds.
- Caveats: single expert (the owner, whose rulings already steer MASTERSHEET — weaker than 3 independents), single content, role-level answers are easier to hit than exact weapons. Next rounds: fresh seeds, other contents/sizes, and where possible exact-weapon answers.

**BLIND LABEL SPOT-CHECK (2026-08-23, in-chat, n=1 owner, 2 uncalibrated comps):** SOB BLAZE OS 7-man — owner "kite and clap... 1-shot comp, kill 1 or 2 then run and reset", engine "kite strong" (bomb share 45%, just under the clap line): AGREEMENT, and the comp's "lacking" kill-pressure lights match the owner's own kill-1-or-2-and-reset description. KroozLT19 6x-Wailing-Bow 8-man — engine "clap strong", owner: "it's a bomb squad... not part of main party but support main party by doing damage off timers... a different play style": a VOCABULARY GAP, not a misread — the owner taught a new archetype, shipped same day as the bomb-squad detachment label (near-monoculture ranged burst; golden T23e). Also ruled: the Harpoon review-queue entry resolved systemically (pierce/damage_debuff count as slot-carrying group utility; the review queue is now empty and only the Battleaxe override remains group-barred).

**BLIND LABELS 3/4 (2026-08-23, same protocol):** Deadlyhooker P1 — owner clap, engine clap: AGREEMENT. albioncompo 20v20 competitive — owner clap, engine "split identity": MISS, diagnosed to one weapon: melee share 35.5% (a hair over the 35% ranged-core line) with Spirithunter as the sole rigid minority carrier — but the owner's same-day Harpoon ruling says its damage is incidental to its pierce-bot job. Fix (E-first-consistent, shipped same day): UTILITY CARRIERS (single-scale damage + exemption-clearing utility kit) never anchor a damage-identity split. OWNER FOLLOW-UP REFINEMENT, same session: "clap kite could be its own playstyle — the two comps I marked as clap have both clap potential and kite potential." Shipped as the fifth playstyle: `clap_kite` in styles.yaml (PROVISIONAL clap/kite weight blend, mechanics 6/3 — the ranged twin of brawl-clap), per-weapon fit = best of the weapon's clap and kite verdicts, and identity detection = ranged core with real bomb share (>=0.40) AND real reset mobility (>=2 evade pts/member) — DH P1 and the 20v20 (aoe ~.53, evade 2.6/m) read clap-kite while pure clap10 (evade 1.8) and pure kite10 (aoe .26) stay pure (golden T23f). Label spot-check running tally: 3 agreements, 1 vocabulary gap (bomb squad, taught), 1 threshold miss that unfolded into a NEW PLAYSTYLE — every miss so far has converted into a ruling the same day.

**IDENTITY SYSTEM SHIPPED FROM THE ROUND'S FINDINGS (2026-08-23, phases A–D, all descriptive):** per-weapon style/size fit derived E-first with owner overrides (`style_overrides.yaml`, audit `out/style_fit_report.json`, H21 gates); `comp_identity()` v2 built up from member identities (T23 family); the style-selection-is-intent suggestion gate (F13/T24 — never scoring); and the kill-pressure three-light checklist (`kill_pressure()`, T25/T25b) whose bars are a lens over the comp-fitted targets this file's 2026-08-21 ruling established. VALIDATION NEEDED: the identity labels, fit verdicts, and kill-pressure lights are exactly the kind of claims the next V3-style blind rounds should spot-check — the owner reviewing `style_fit_report.json` (first review-queue entry: 2H_HARPOON_HELL) and disagreeing with labels in the planner is the tuning loop.

**FORGE-QUALITY BLIND ROUND (2026-08-23, in-chat, n=1 owner):** five fresh forges presented (castle_outpost 7 balanced/brawl, roads 7 kite, blackzone 10 clap, blackzone 20 brawl), owner graded slot-by-slot before any engine rationale. Every disagreement converted same-day into a ruling + mechanism + pin:

- **Economics is a real axis the model lacked.** Exalted Staff (slot in 4/5 forges) and Forgebark overruled on regear cost: "crystal artifact weapons are quite expensive ... I wouldn't run it unless there were 30+ people involved, but others might use it if they are rich rich." The committed killboard sample corroborates (Exalted 0/0/5, Forgebark 0/0/2 small/mid/large vs Mace 35, Permafrost 45 large) — used as evidence FOR the ruling, never as a scoring input. Shipped: `cost_tier` derived per weapon (suffix rule, `out/economics_report.json`), `viability.cost_gate` bars crystal from suggestions/generation below 30 exactly like an exclusion (manual/locked picks score, flagged `off_budget`). F14/T27. Tension accepted knowingly: Deadlyhooker's 20-mans DO field Exalted — the owner calls that a rich-group choice, not a forge default.
- **A hybrid healer can never be the sole healing foundation.** Forgebark as only healer overruled: "too expensive to be the only healer ... it's not which line but which weapon — the weapon needs to have high healing numbers on its e." Shipped: `full_healer` derived from the E bundle's summed heal points (>= 6; the E is combo-independent so the flag is static; audit in the economics report — the derived split lands all owner-named cases correctly), `primary_heal` band minima routed through the combo-aware predicate machinery. F15/T27b. Borderline for review: plain 1H Holy / Divine / Lifetouch fall OUT at threshold 6.
- **Role bands were brawl-calibrated and style-blind.** "5 healers in 20 feels like too much, especially clap and kite ... for kite you'd rather get teammates that facilitate movement like occult or bedrock"; 20-brawl's 6 frontline "too many tanks ... not enough damage"; 10-clap's third hammer overruled ("instead of a great hammer — occult, icicle, witchwork, permafrost"). Shipped: `constraint_overrides` per style in styles.yaml (owner-ruled: 20-man healers brawl 3-4 / clap 2-3 / kite 2, kite@7 = 1, brawl@20 frontline capped at blap's 5, clap@10-14 frontline 2; other rows flagged PROVISIONAL interpolation). F16, and F5 now validates forges against the effective style-merged band.
- **Great Holy is brawl-only.** "It has to stop moving and needs everyone to clump in place to heal with e — that's not good [for clap]" + "only useful in like brawl situations." Shipped as a cited `style_overrides.yaml` entry (unfit clap/kite/clap_kite at gang/group; the healers-are-style-flexible derivation rule stands otherwise). T27.
- **Watch items, deliberately NOT retuned:** Evensong ("maybe it's just undervalued ... I would run it with more damage" — killboard 1/0/1); Hand of Justice's monoculture as the engage slot (owner: Earthrune and 1H Mace are also good for brawl/clap — both now appear in forges after the band changes, no sheet change needed); Primal Staff (0/0/0 observed, still forged — no ruling asked yet). Next grading round owns these.

Post-round forges: no crystal below 30 anywhere, 20-brawl 5 frontline/4 healers/11 damage-support, 10-clap 2 frontline + full healers only, 7-kite single full healer. All 18 forge + 43 golden + 60/60 parity + exact JS forge parity on the five graded cases.

**ROUND 2 REFINEMENT (2026-08-23, same session) — heal scale is structural, no per-weapon rules.** Owner on the round-1 borderline: "1 hand holy IS full healer but it's not a good group healer for anything larger than 5 people. I would use it at 3 people and very rarely at 5 but never above that ... hallowfall is better, redemption is better, fallen staff etc, things that heal group are better. **I don't want to make rules on individual weapons — it should all be based on what the weapon does and its effect, [no] custom rules for individual weapons to influence author bias.**" Shipped accordingly:

- The foundation flag became MAGNITUDE (E heal >= 6) **AND SCALE** — the heal spell's own area facts (radius >= 3 or max_targets >= 5 -> group). The dumps' facts split 16 of 18 heal Es correctly on their own; the two whose area lives in a landing/impact sub-effect the dumps don't surface (Divine Jump, Celestial Sphere) are corrected in the new `pipeline/heal_overrides.yaml` — cited FACT corrections on the spell, the ranged_overrides pattern, not taste rules. Zero unknowns.
- Resulting foundation set (8): Blight, Fallen, Great Holy, Hallowfall, Nature, Rampant, Redemption, Wild. Druidic moved OUT **by structure alone** (single-target ultimate) — unprompted but consistent with the ruling. Single-scale dedicated healers (6): 1H Holy, Divine, Great Nature, Lifetouch, Ironroot, Druidic.
- `derive_style_fit` grew the healer half of the E-first ladder: a dedicated single-scale heal E grades gang situational / group unfit for every style — exactly how single-scale damage already degrades. Under declared styles these healers leave 10+ suggestion pools; balanced gates nothing (standing Phase C design).
- Also ruled this round: Primal Staff is fine ("an alright d-tank especially for zoning") — its killboard absence stays a curiosity, not a finding.
- Band granularity: the owner's 1H-Holy cutoff is 5, but the fit bands split at trio<=3 / gang 4-9 — "situational at gang" still lets a single-scale healer into a 6-9 forge (the 7-brawl sample fields Druidic as second healer). **RESOLVED same session — owner: "leave it, keep everything consistent."** A single-scale healer may take a NON-foundation healer slot at gang sizes; the primary_heal minimum already guarantees the foundation is a group healer. No 4-5 seam; the standard bands stand.

Golden T27c pins the structural split (1H Holy single/trio-fits/group-unfit, Hallowfall+Redemption group via cited override, Druidic out of the foundation set); 44/44 golden, 18/18 forge, 60/60 parity + forge parity all green after the rework.

**ROUND 3 (2026-08-23, same session) — six fresh forges graded blind (kite 10, clap 15, faction_war 15 balanced, castle 25 brawl, clap 7, territory clap_kite 20).** Verdicts: four passable ("maybe not ideal but okay"), two "just not good": the faction-war 15 ("it has dagger and boltcaster, both of which can only damage 1 person at a time with e and that's not good for anything higher than 3v3, heavy crossbow at least can do damage through people with e") and the castle 25 brawl (2x Permafrost, 2x Wailing Bow, Dagger, Whispering Bow, Light Crossbow, Glaive named). Diagnosis was one mechanism, not many: **every killed weapon derives SITUATIONAL for its context, every passed weapon derives FITS — and situational never gated generation.** Shipped as the **generation-fit gate** (both ports): a DEFAULT generated comp fields damage picks the derivation says FIT — declared style's verdict must be "fits" at the band; balanced requires fits for at least one style (so a fits-NOTHING weapon like Battleaxe now leaves balanced generation too — size fitness, not style intent; F13 revised accordingly); trio gates nothing; healers/frontline/support untouched (preserving the same-day Druidic ruling); situational stays a legitimate MANUAL pick — scores normally, never flagged. F17 + golden T28 pin the owner's exact cases; T15's fixture reads Dagger Pair through an explicit pool now that the default pool correctly omits it. V4 role gate unchanged 25/32 = 78% PASS (weapon-level 13/92 — one hit was a situational weapon the pool no longer offers). All ports parity-clean including forge parity.

**ROUND 4 (2026-08-24) — same-job redundancy, the last graded failure class.** Owner on round 3's fixes: 2x Earthrune beside Hand of Justice has no value ("a better secondary clump might be witchwork, and 1 earthrune could work too if we are lacking on clumps"); the castle curse pile gives diminishing returns ("the q spells … stack but don't do extra damage from more people"); Hellfire is "usually a brawl-clap weapon and not a clap option" (Realmbreaker earns clap through health cut + ranged E + engage follow-up); 1H Holy at 15 confirmed the healer gap ("no way above 5 and there is no chance above 9"). Shipped — ALL data-side except the healer gate; the engines' existing machinery (groups, dup allowances, verified non-stacking, style gate) did the rest:

- **Healer generation gate**: a healer unfit at group for every style (the single-ally-heal-E class) never generates at 10+, balanced included; gang stays open (the Druidic ruling). Engine+JS, golden T28b.
- **Duplicates earn their place**: generation default max copies 2 -> 1 at every size; a second copy comes only from a per-weapon allowance citing a real comp (Permafrost/Hallowfall/Bedrock/Great Arcane/Rift Glaive/Wailing unchanged). Kills 2x Earthrune and every future unlisted double. F18.
- **Derived clump_core group**: composition.yaml `derived_groups` -> build-time membership from the sheets (flat clump_create >= 4: HoJ, Camlann, Witchwork — structural, no hand list), max 2 generated per roster. F18.
- **First verified non-stacking scoring record**: CURSEDOT — its own description states the target-side pool ("stacks up to 4 times"), DEATHCURSE2's verified record reads the same pool, owner ruling quoted. Party supply now counts the curse Q's sustained_dps once across all cursed wielders. test_interactions revised (the "no verified nonstacking exists yet" pin became "CURSEDOT is the one, and count-once bites").
- **Hellfire cited override**: clap -> situational (generation-fit gate keeps it out of default clap comps; brawl_clap home intact; Realmbreaker untouched). T29.

Post-round: faction-war 15 fields ONE Earthrune + Heavy Crossbow and no single-target-E dps; clap 15 swaps Hellfire for Longbow/Realmbreaker/Spiked; castle 25's curse pile shrank with its shared Q priced honestly. 20/20 forge, 47/47 golden, 32/32 interactions, 60/60 + forge parity, tier2 78% PASS.

**ROUND 5 (2026-08-24) — curse budget + the first hybrid band.** Owner: "there are so many weapons which can dps, why stack so many curse. usually 2 curse is max in a 25 man party — like damnation and lifecurse and maybe rotcaller" and "clap kite at 20 doesn't need 5 healers, maybe 3 or 4 max." Shipped as pure data: `derived_groups.curse_pressure` — membership is the cursed LINE derived from the shared Q pool the CURSEDOT record prices (all 8 weapons, no hand list), max 2 generated (F18b; castle 25 now fields exactly Damnation + Cursed Skull); clap_kite's first constraint_override (healer 3-4 at 20-29, F16 extended — territory clap-kite dropped to 4 healers). Note Rotcaller turned out to be the CRYSTAL 1H cursed — the owner's "maybe rotcaller" is a 30+ pick by their own economics ruling, which the gates already compose correctly. 21/21 forge, 47/47 golden, 32/32 interactions, all parity + tier2 green.

**ROUND 6 RULING, RECORDED — NOT YET IMPLEMENTED (2026-08-24, session close):** "if a brawl comp has two curse weapons it had to be damnation and lifecurse. the e spell has to provide serious utility because it doesn't do that much damage anyway." E-first again: within the curse budget, a BRAWL curse slot is earned by the E's UTILITY (Damnation's aura, Lifecurse's heal cut), not its damage (the forge had picked Damnation + Cursed Skull). Next session: derive which cursed Es are utility-Es vs damage-Es from the sheets (the E bundles already split heal_reduction/resist_shred vs damage caps) and condition the brawl fit or the group's brawl membership on it — structurally, no hand list, per the standing no-author-bias rule.

**ROUND 6 SUPERSEDED (2026-08-24, round-7 session):** the owner withdrew the weapon-specific reading — "i wasnt giving a rule ... i dont want to give custom rules for different weapons. i want the engine to make comps based on the general understanding of why certain comps are the way they are. ... the rule should be something like in cases where having multiple weapons doesnt benefit — q stacking not doing extra damage — then probably the engine shouldnt stack weapons from same tree." The Damnation/Lifecurse pairing was an EXPLANATION of the principle, not a target. The general mechanism largely exists: the verified CURSEDOT count-once record prices the shared Q pool, and `derived_groups.curse_pressure` derives its membership from that same pool (round 5) — the standing question is whether the WITHIN-budget pick (utility-E curse over damage-E curse in brawl) emerges from the sheets' own capability scores, which is E-audit territory (below), not a new rule. Also same message: per-player weapon profiles and slot-lock tooling (roadmap items 4/5) are DEPRIORITIZED — "most people can bring anything ... a later on project not something i want to take on before i am satisfied with the comps and builds the engine makes." And the standing method directive: "you should be able to infer mostly from the e spell what the weapon does primarily and then what its used for and where. it would better for you to check first and then ask me for the weapons you are not sure of" — check the E's effect, magnitude, impact radius and the other spell signals; bring the owner only the unresolved cases.

**ROUND 7 CANDIDATES — OBSERVED-FAMILY RECONCILIATION (2026-08-24, PENDING; no rulings yet, nothing changed).** First systematic diff of forge output vs the mined cohort families (`out/cohort_families.json`): forge blackzone_roam @ 20 (large) and @ 10 (mid) across all six styles, then for every family weapon check suggestion-pool membership, the barring gate, and forge presence; reverse check for forged weapons unobserved in the bucket. Per the anti-circularity rule these are HYPOTHESES for the owner — the observed layer proposes, the engine's gates stand until ruled otherwise. **Sampling caveat on all of it:** cohorts come from KILL EVENTS, so weapons that secure kills are over-represented and supports under-represented; prominence is meaningful, absence is weak.

- **C7-A Battle Bracers** — 84% of F1's cohorts (16/19, 13 orgs; also 40% of the mid family), yet in NO suggestion pool at 10+: derived `damage_scale: single` → situational for every style at gang/group → the generation-fit gate (T28 class) bars it. But the derivation also flags it `utility_carrier: true` — structurally the Harpoon case. Question: does its observed ubiquity come from E/kit utility the situational verdict undervalues (cited override to fits, like Hallowfall's heal override), or is the meta fielding it for reasons outside the model and the gate is right to refuse?
- **C7-B Spirithunter** — 68% of F1's cohorts; the existing owner ruling grades it situational (T23e). The observed layer says "situational" is in practice near-default in the ZvZ family. Stand or promote (brawl/group)?
- **C7-C Bloodletter** — 42% of F1's cohorts, barred by the same single-E rule. Prime suspect for the kill-event bias (the chase/secure weapon appears in kill feeds by definition). Rule on the weapon or discount as sampling artifact?
- **C7-D Galatine Pair** — 52% of F1's cohorts, IN the balanced/brawl/brawl_clap pools (derives fits), but never chosen by any forge at 20 — a ranking contest it always loses, not a gate. If the owner would field it in the meta ball, this becomes a sheet/ranking case (golden-pin material).
- **C7-E engine darlings (weak-form, absence evidence only)** — forged at 20/10 yet observed in ≤1 cohort of the bucket: Evensong (already the round-1 watch item — this is evidence AGAINST "just undervalued"), Great Holy (balanced forge still fields it at 20; owner already ruled it brawl-only for suggestions), Hoarfrost/Glacial (clap staples unobserved), Incubus Mace / Clarent Blade / Grailseeker / Cursed Skull. No action proposed; watch-list corroboration only.

**ROUND 7 RULED (2026-08-24, same session) — the two-prong E rule.** Owner: the system should judge every weapon's E for group usefulness — bar "those that affect single targets OR dps weapons that have low damage AND add nothing to the group. the AND is important, like heavy mace has low damage on its e but it silences enemy group so is really useful"; and "any primarily solo target abilities, like dagger pair 1 hand fire etc are max affective in 3 man situations and then good/okay at 5 man and then start falling off hard." Owner gradings calibrated the constants: Energy Shaper stays ("super high damage ... great in large group fights"), Greataxe stays ("its e can hit everyone in its vicinity ... it's okay"), Twin Slayers left to the crystal cost gate, Primal Staff ranking commentary only. Shipped:

- **C7-A RESOLVED — curation gap, owner right, killboard corroborated.** Owner: "battle bracers is not single target, it damages all people it lands on doesn't it?" Verified from dumps: Falcon Smash "deals physical damage within a 4 radius upon impact" (264 vs players) — the sheet had never scored the E's damage, and the single-scale verdict cascaded from that gap. Sheet fix (burst_aoe 4, evidence DIVEPUNCH_RISE) → derives group-scale, brawl-fits, back in every group pool — exactly where the observed ZvZ family fields it. The reconciliation loop worked end to end: killboard proposed, dumps verified, owner ruled, sheet cited.
- **Prong-1 fact overrides** (style_overrides.yaml, all cited): Warbow ("terrible in a group setting ... single target damage and it can get easily blocked" — Magic Arrow's 3.0×2.5 line footprint), 1H Fire (the named DP-class case; Pyroblast detonates on the first enemy hit), Hellspawn ("primarily single target damage ... not good in above 5" — the Imp transformation). All three: gang situational / group unfit / trio fits.
- **Prong 2 derived** (`weak_group_e` in build_dataset): group-scale dps E with damage < 4 sheet points AND no single E tool at 4+ (UTILITY_EXEMPT set + interrupt; self-only mobility/disengage/self-sustain never rescue) → the trio-class ladder. Catches Phantom Twinblade and Icicle Staff (the scattered-2s class the owner's Double-Bladed-Staff standard describes — DBS itself is rescued by its engage tool); demotion is situational, never unfit, so manual picks stay legitimate. Constants PROVISIONAL in the audit report.
- Golden T31/T31b pin the whole contract (54/54); forge 21/21, parity 60/60, V4 role gate 78% PASS unchanged.
- **C7-B/C/D RULED (same session, follow-up message):**
  - **C7-B Spirithunter — PROMOTED for clap (and its clap_kite hybrid); owner correction: "not exactly bomb style, its clap style" — the pierce enabler is a CLAP piece, not the bomb-squad archetype.** Owner: "spirithunter is great in clap and clap kite, just read the e ability, it has a massive pierce that enables the whole dps line." Dump text agrees (Corrupting Steel pierces through ALL enemies, cuts damage resists of every enemy hit, trail cuts magic resist further). Cited override: clap + clap_kite gang/group → fits; brawl/kite keep the 2026-08-23 situational grade. T23e updated (the refinement supersedes its all-styles-situational pin), T31c pins pool membership.
  - **C7-C Bloodletter — RESOLVED, no gate change: killboard prominence is a MOUNT-CARRIER artifact.** Owner: "bloodletter isn't really used as fighting but as a mounted weapon for battlemounts. bloodletter has high mobility so people use it for that." The recorded kill-event sampling bias made concrete — battlemount pilots hold it, so it rides into cohort baskets without ever being a comp slot. Stays out of group generation; caveat added to KILLBOARD_AFFINITY.md.
  - **C7-D Galatine Pair — RESOLVED, no change.** Owner: "galatine pair is great for solo bombs" — a specialist play (the one-man dive bomb) the comp-fitted templates don't demand, so the forge passing on it is correct ranking, not a gate. Stays pooled for manual/specialist use.
- Ranking commentary logged, not gated: Double Bladed Staff ("doesn't have the same utility a mace will have"), Rift Glaive's kidnap fling ("very rare cases"), Great Cursed vs the utility-E curses (feeds the open round-6 derivation). C7-E watch items stand.

**FIRST FULL E-AUDIT (2026-08-24, per the owner's check-first directive).** Every weapon's E read against its sheet bundle and derived verdicts: description damage numbers vs scored damage caps, radius/area/pierce wording vs damage scale, effect-layer candidates vs curation. 17 structural flags of 137; 13 resolved on inspection (shield-absorb regex false positives; healers/frontline/support whose incidental E damage rightly goes unscored — 1H Mace's 203-damage stun leap, Hand of Justice, Bedrock, Tombhammer, Chillhowl the already-viability-excluded case; Battleaxe already owner-ruled; Bear Paws' cone damage already scored; crystal weapons cost-gated regardless). **Two Battle-Bracers-class gaps FIXED (sheet curation, dump-cited):**

- **Fists of Avalon** — Purifying Fist "deals 232 physical damage ... purges all buffs from all enemies hit": the E's area damage was never scored. burst_aoe 4 (the sibling Battle Bracers 264/r4 = 4 calibration). Now group-scale, brawl-fits, in group pools — the dive purge-bomb.
- **Trinity Spear** — "Roots all enemies in a 3.0 radius on impact ... deals 191.65 physical damage" + the ally attack-speed mist: impact damage unscored. burst_aoe 2 (modest beside the root). Now group-scale, in group pools — the engage/root bomb with an ally steroid.

Both promotions were AUDIT JUDGMENTS presented for owner review; **both open questions RULED same session:**

- **Fists of Avalon purge 3 → 4** — owner: "fist of ava purge can be a 4." Landed in MASTERSHEET tune:sheets (the expert control surface). The dive purge-bomb stands in group pools.
- **Trinity Spear OUT of large-scale generation** — owner: "seems like a group tool but no one is doing auto attack damage usually so its never used in large scale. only time its used is for a swap for hitting castle gates or terry walls ... never as the main weapon in party." Cited override: group unfit, every style; gang keeps the derived verdict (the ruling names large scale only). **General principle recorded for future curation: an AUTO-ATTACK steroid is not large-scale utility** — nobody auto-attacks in big fights; ally attack-speed buffs (Trinity's mist, and any future buff_allies grounded in attack-speed) should not carry group slots. The audit judgment was wrong precisely where derived facts can't see meta reality (what players actually do with auto-attacks) — exactly the case the owner review step exists for.

Golden T31d pins both. 56/56 golden after the round.

**ROUND 8 (2026-08-25) — the round-6 derivation lands: non-stacking slots are EARNED.** Owner facts, E-first as directed: Rotcaller's E "prevents healing for 2 seconds, which is great for a clap and clap kite comp since the objective is to hit quick and kill fast"; Damnation "adds an amazing pierce on a huge size"; Lifecurse "purges enemy buffs, a good all round weapon"; and the observed bound — "for curse the only weapon i see in any party bigger than 15 people is the lifecurse, damnation, or rotcaller. Don't see any other weapon on larger scale. Demonic staff is not a true brawl weapon at larger than 7 people party." Shipped structurally (no hand list):

- **The rule**: a member of a derived NON-STACKING group (membership from `evidence_spells` — the pool a verified count-once record prices; today only `curse_pressure`) earns a GROUP-band slot with an E enemy-DEBUFF tool at the standing tool bar (`E_DEBUFF_CAPS`: purge / resist_shred / heal_reduction / max_health_cut / damage_debuff, ≥ `E_UTILITY_TOOL_MIN`). Members that fail demote to **situational at group for every style** — never unfit, trio/gang untouched, `style_overrides.yaml` still wins. The derivation reproduces the owner's observed list exactly: Damnation (pierce 4) / Lifecurse (purge 4) / Rotcaller (heal-cut 4) earn; Great Cursed (HoT-purge 2), Cursed Skull, Shadowcaller, 1H Cursed, and Demonic fail — the fear is DISPLACEMENT, not a debuff, which is precisely the owner's Demonic verdict. Fields `e_debuff_max`/`nonstack_member` audit it in `out/style_fit_report.json`.
- **The gate** (both ports): the generation-fit gate now also checks non-stacking-group members at group band — declared style needs its "fits", balanced needs fits-somewhere; manual picks score normally, never flagged. Castle 25 brawl now fields Damnation + Lifecurse (was Damnation + Cursed Skull, the round-6 trigger). Rotcaller composes with the crystal cost gate (a 30+ pick, round-5 note).
- **Band seam, decided by precedent**: the owner said "bigger than 15"; verdict bands split at group 10+. Per the standing band-consistency ruling (round 2, "leave it, keep everything consistent") the demotion applies at the group band — stricter than literal at 10–15. Overrule with a cited override if damage-E curses should stay generable at 10–15.
- **Found and pinned honestly — irreducible saturation filler.** Barring the damage-E curses changed the beam path at two size-11 matrix cells (castle/brawl, faction_war/brawl_clap): the forge converges to an assembly whose last slot is slightly negative (−0.02/−0.07) with NO better legal candidate (measured: the fielded member IS the best remaining pick; even the barred curses would score negative there). The pre-ruling assemblies stay reachable manually. F5's contract was strengthened, not weakened: filler is legal ONLY when irreducible — any filler slot with a strictly better legal replacement still fails.
- **Magnitude-queue note, not acted on**: the owner's damage ordering within the earned trio is "damnation doesnt deal that much damage, lifecurse a little more and rotcaller the most" — the Damnation sheet's DoT-delivered `burst_aoe 6` (the line's highest) is in tension with that reading and joins the magnitude audit queue for adjudication.

F19 pins the whole contract (derivation split, pool membership at 20 balanced+brawl, gang and manual intact, castle-25 forge). 22/22 forge, 56/56 golden, 60/60 parity + embed, tier2 role 78% PASS, all side suites green.

**C7-E RULED, same session — the engine darlings stand; one number gap found and fixed.** Owner: "its fine if the engine likes those weapons, i dont think they are being overrated. maybe great holy is a bit overrated but if the engine has seen the numbers and thinks they add value then all ok from me. Just make sure you look at the actual damage, support, def whatever the relevant numbers are." The directed number check ran all seven against the dumps:

- **Evensong — FIXED (the round-1 watch item resolves as an OVERscore, not undervaluation).** The E deals 112 in r5 — below the owner-calibrated E-damage ladder's 2-anchor (Trinity Spear 191/r3 = 2; Bracers 264/Fists 232 = 4) — yet was scored burst_aoe 4. Trimmed to 2 with citation. The weapon's real identity checks out and stays: Dark Auras (−15% healing received / −15% damage dealt / 15% slow, 5r around 3 enemies, 5s) **stack up to 3 times** — overlapping auras reach −45% on a clump; heal_reduction 4 + damage_debuff 2 stand on that fact (comments now record the stacking). Killboard absence + this trim tell one story: the engine loved it partly for damage it doesn't have.
- **Incubus Mace — grounded, stands.** The E is a triple 40% debuff (max AND current Health cut, damage dealt, Healing CAST) for 8s in a cone: max_health_cut 4 / heal_reduction 4 / damage_debuff 4 all check. Kill-event support-undercount explains the absence.
- **Great Holy — numbers check** (channel 50 HP/0.5s to 10 allies ≈ 1000 HP/s of group healing, +16% ally resists, 10m CC-resist-ignoring shove): heal_sustain 6 / peel 4 / buff_allies 4 are honest. The owner's "a bit overrated" has no factual home in the sheet — recorded as ranking commentary only.
- **Hoarfrost** (every score already owner-adjudicated 2026-08-21, dump-matched), **Glacial** (15s storm = zone 6, low tick = burst 2), **Grailseeker** (3.5s recastable root wall = root/zone/peel/catch 4, 125 line = burst 2) — all consistent, stand.
- **Clarent Blade — magnitude-queue note**: the E's 170 damage pierces THROUGH all enemies (line delivery) but is bucketed burst_st 4, which the size physics taxes at scale — if anything the sheet undersells it at 20. No change; queued for the bucket question at the magnitude audit.

Post-fix: 56/56 golden, 22/22 forge, 60/60 parity + embed, tier2 78% PASS. The C7-E watch list is CLOSED.

**Q16 SIGNED OFF, same session.** The owner pasted the current wiki Resilience and AoE Escalation pages (both exact matches to the wired `mechanics.yaml` tables — now marked owner-confirmed), stated the physics reading themselves ("single target damage is punished in large groups and aoe damage is rewarded in larger groups"), and confirmed both shipped `size_physics` tables as presented — "ok that seems fair" on `st_value_mult` (25% ST value at 20-man, 20% at 30+) and `count_mult` (×1.6 clump at 20, ×2.0 at 40+). The tables lose their PROVISIONAL label; MECHANICS_TODO Q16 is closed. Remaining owner-only mechanics numbers: Q14 (per-style clump/focus counts).

**ROUND 9 (2026-08-25, "ask me questions for finish off the rest") — eleven questions, eleven rulings; the audit queue and the mechanics chapter close together.**

- **Q14 CLOSED, delegated with an ordering rule**: "i cant give you numbers for that you have to use logic to figure that out. for clap and kite and clap kite and brawl clap, the number will usually be higher than brawl." styles.yaml values already satisfy it (brawl 3 the floor); comment updated. Dive/assassination style: "sure but only if we have more than 20 people" — deferred, 20+-only if ever built.
- **Resilience Penetration WIRED (the owner's #3)**: "single target is just a non pick at 20+ usually because enemy will have too many defensives to protect that one person, you can wire it as partial rebate." The full 69-row wiki table (post-Realm-Divided, revision oldid=84609, retrieved same day) landed in `pipeline/resilience_penetration.yaml` (cited; melee-only stat, ranged/magic categorically 0); `build_dataset` stamps `resil_pen` (69/69 matched by display name); both ports rebate burst_st/execute SUPPLY by (1 − DR·(1−pen)) / (1 − DR) at the style's grown focus count — dagger-class 40% pen keeps ~35% more ST at 20-man physics, on top of (never instead of) the owner-confirmed st_value weight tax. F20 pins stamping, ordering (dagger > mace > pen-less), and scale-monotonicity; F1 exact-marginal invariant and 60/60 parity hold untouched.
- **RULE queue ADJUDICATED wholesale**: "the batch is fine, just test it internally" — all twelve specialist E-supplement upgrades stand (list in MECHANICS_TODO). Both three-level ladders confirmed (frost zones "6 is fine"). ONE reversal: **Rotcaller's 1H damage-budget discount REJECTED** — "1 handed does have smaller damage BUT damage comes from equipment and 1 hand allows for adding an offhand, which can INCREASE damage depending on the offhand" — sustained_dps/CURSEDOT 2 → 4 (line default). General principle recorded: no automatic 1H damage discounts; the offhand compensates.
- **Peel ranking commentary (logged, not gated)**: on Quarterstaff's Separating-Slam 6 the owner mused "best peeler might be grailseeker, or the one that throws a tornado to knock people up" (= Soulscythe, same line, peel 4 with Grailseeker). Hedged, no score change; revisit if it comes back firmer.
- **Damnation damage RESOLVED BY NUMBERS (the owner's own decision rule)**: "if the numbers say high damage then ok keep at 6 but its mostly for its capability of a massive aoe pierce i thought." Dumps: Cataclysm deals 24/tick × 6 = **144 total over ~6s** on a 13m radius — below the 191=2 ladder anchor. burst_aoe 6 → 2, cited; the r13 blanket + escalation stay in cap_delivery; the pierce (resist_shred 4, the weapon's identity and its earned-slot ticket) untouched.
- **Heal-cut ladder reviewed roster-wide** (the owner asked "what about dawnsong healcut... what other weapons have healcuts"): Dawnsong was already accounted (heal_reduction 4, −40% inside the fire — the −40/−50% one-shot class: Carrioncaller, Incubus, Staff of Balance, Dawnsong all hold 4 beside Rotcaller's 100%-negate 4); the bleed/HoT-purge class holds 2. One change from the ruling "evensong heal-cut should be weaker than rotcaller": **Evensong heal_reduction 4 → 3**.
- **Evensong structural consequence, surfaced**: with both trims (damage 4→2 from the C7-E number check, heal-cut 4→3 here) Evensong now derives `weak_group_e` (E damage 2 < 4 AND best E tool 3 < 4) — trio-class, situational at gang/group, out of default generation above 3. The round-7 prong-2 rule doing exactly what its ruling says, and the killboard (0–1 observed) corroborates. A cited override can rescue it if the owner ever wants it generable.
- **Clarent Blade REBUCKETED**: "clarent blade e is aoe damage" — burst_st 4 → burst_aoe 4 (the 170 wave pierces through all enemies; line-delivered area). It now escalates instead of being ST-taxed.
- **Curse band seam CONFIRMED**: "at 10+ i just said 15 as a general number" — the round-8 group-band cutoff stands as ruled, no seam.

All gates after the round: 23/23 forge (F20 new), 56/56 golden, 60/60 parity + embed, tier2 role 78% PASS, builds/interactions/provenance/patch/cohort/codec/display green. With Q1/Q3/Q4/Q6–Q10/Q12/Q14–Q16/Q19 closed, the remaining mechanics backlog is: per-spell burst_aoe escalation gating (needs a styled expert pass), Q11/Q13 (asymmetric numbers — parked by design), Q17 (meta prior — parked behind win-lift), and the PASV/TOP magnitude review boards.

**ROUND 10 (2026-08-25) — the ROLE LAYER: the kit bug becomes a design.** Owner observations, both verified before design: (1) the kit advisor gave the whole brawl-20 comp the same chest (Hellion class) regardless of job — measured: comp-pool marginal valuation makes item values wearer-independent (identical to four decimals across members) once the tank pool saturates; (2) Grailseeker sat in a dps slot (`role_hint: melee` → dps) despite 4 damage vs 18 utility points and a 125-damage E. Owner model (quotes in roles-design.md): a role is a property of the member-in-comp, weapons carry MENUS of roles selected by gear ("one realmbreaker can play different roles... roles shouldnt be locked 1:1"; Royal Armor = team energy / Royal Jacket = team cooldowns / Hellion = damage — all three wiki-verified); roles are the PRIMARY objects populated from evidence, not 137 hand menus; coarse classes stay as the band layer; cross-class assignment allowed and highlighted; advisory is a headline feature (the Longbow-in-the-wrong-jacket flag; "3 heavy maces in party and 0 engage tanks would be an obvious flag"); scoring stays capability-driven, roles never add points. Design approved ("ok go for it"), recorded in roles-design.md. Correction landed same round: Incubus doctrine kit is Sacred Ground + SNARE CHARGE, not Guard Rune (roles.yaml doctrine field).

**Increment 1 SHIPPED same session**: `pipeline/roles.yaml` — 18 roles (engage/stopper/off tank; main/kite/brawl healer; aura/shield/curse/zone support; ranged_aoe/sustained_brawler/bomb/pierce_enabler/dive_cleanup; meta battlemount/caller/scout, never forged), 69 weapons on menus, EVERY membership cited (own comps' slot labels — which already field Lifecurse as dps AND support, Camlann as support AND tank; the 2026-08-25 role-taxonomy research with the 18-slot "Realmbreaker Support" comp and the Earthrune-as-engage-tank case; owner rulings; derived signatures like clump_core). Build validates fail-closed and stamps `role_menu` (inverse index); `out/roles_report.json` is the owner's grading board. Both ports carry `detect_role` (played role from weapon × worn chest class) and `role_advisory` (off_role_kit per member; no_engage_tank at 10+ with 2+ frontliners and no clump maker) — DESCRIPTIVE only, R5 pins comp_score untouched; parity carries role_advisory per case (60/60). The status card renders the role tally + flags from the members' actual LOADOUT chests. tests/test_roles.py R1–R6 (6/6): R6 is the original bug pinned — Incubus + Grailseeker in Hellion Jacket both flag off-role kit. Pending increments (roles-design.md): kit-doctrine advisor (2), forge role assignment + owner-graded need profiles (3), uptime economics (4).

**Owner grading, first pass (same session) — the taxonomy corrected to FUNCTIONS.** "why is curse support its own role, shouldnt those weapons be in like the pierce, purge, healcut role/category ... also the aura support i feel should be broken down in individual type of auras/effects. for example there is also the demon armor aura, judicator armor aura, guardian armor aura." Restructured (roles-design.md taxonomy v2): `curse_support`/`pierce_enabler`/`aura_support` dissolved — SEAT roles (uniformed) vs FUNCTION roles (`pierce` = Damnation + Spirithunter; `purge` = Lifecurse + Fists of Avalon; `anti_heal` = the round-9 heal-cut roster: Rotcaller, Carrioncaller, Incubus, Dawnsong, Staff of Balance, Evensong) that ride along with any seat and claim no chest; plus a typed `gear_effects` catalog (energy font / cooldown banner / enemy-weaken aura / ally force shield / reflect area / lifesteal steroid — each cited to its catalog item or wiki, with evidenced carrier weapons). Detection reports seat + functions + carrying; kits are judged against SEATS only — the seat/function split is exactly what keeps R6 honest (the anti-heal function never excuses Incubus's damage jacket). R1–R7 7/7, 60/60 parity with functions + carrying carried per case, all other gates green.

**Second grading pass, same session — the E-FIRST TIERED SWEEP.** Owner: "Go through all the weapons and add them to the roles (I see carving sword isnt on pierce even though it has a pierce AOE effect on its e) ... certain weapons have these abilities on their q, or w like axes have heal cut and curses have pierce or snare w's but it would be a secondary level role for them. the primary roles for a weapon should come from its e spell." Verified first: Carving's E (dash) cuts damage resistances up to 20% through the line — sheet already scores resist_shred 4, the book had never swept it. Shipped as DERIVATION, not hand lists: function-role membership now sweeps ALL weapons from the sheets' own slot structure — E-slot cap ≥3 → PRIMARY; a Q/W ABILITY ≥2 → SECONDARY (passive procs and always-on stats deliberately excluded: the rule names abilities; Longbow's shred proc dropped out on that distinction). Results: pierce 5 primary (Damnation, Spirithunter, Carving, Crossbow, Dreadstorm) + 77 secondary — shred Q/Ws are near-universal in the game (Iron Breaker, Sunder Armor, Frazzle, Piercing Arrow, Frost Lance, the curse Armor Piercer the owner named); kept at the standard bar BECAUSE the owner's example lives at rung 2, with a per-role `secondary_min` knob recorded if that tier should ever discriminate harder. purge 5+10, anti_heal 6+17 (the axe-bleed class, exactly the owner's example). Weapons carry `role_menu` (primary) + `role_menu_secondary`; detection/advisory/parity carry the `secondary` list; the status card shows secondary-function chips dimmed. R8 pins the owner's own cases (Carving E-primary; axe bleed+smash secondary; curse Armor Piercer secondary with Damnation staying E-primary). 8/8 roles, all gates green.

**Offhand-pairing check (owner: "i think incubus is mostly paired with leering cane for its +cc duration can you check online").** Verified online, honest split: Leering Cane + Incubus IS documented (albionfreemarket "Incubus Tank"; grind duo-gank) and the broader mace-CC + Leering pattern is confirmed meta (metabattle's 1H Mace ZvZ lists Leering Cane as PRIMARY offhand; CC-duration stacking threads); the earlier-cited "Inncubus ZvZ Support" w/ Timelocked Grimoire also re-verified item-by-item (real page, 2026-02); Incubus-in-ZvZ evidence splits Astral Aegis / Timelocked / Leering. Usage-stat sites (murderledger) unreachable (403). Both pairings recorded in the gear sheet comments; the CC-stacks-with-CC pairing rule is queued as increment-2 kit-advisor logic.

**INCREMENT 2 SHIPPED (2026-08-25, next session) — the KIT-DOCTRINE ADVISOR.** Design presented, owner-approved with two rulings: "yes its the whole build. infact we might even need to include food, potion and capes and you are right about passive defaults" (doctrine covers every slot; cloth = damage passive, leather = CDR, plate = CC-duration on the frontline). Shipped as derivation end to end: (1) UNIFORM GATE — `kit_options` (both ports) resolves the weapon's primary seat (`role="auto"`; None = old ungated pool) and hard-gates the CHEST pool to the seat's uniform classes — R12 pins Incubus + Grailseeker to plate-only chests, the everyone-gets-Hellion bug dead at the pool level while manual builds still score anything; (2) DOCTRINE TIERS — every other slot (head/shoes/cape/offhand/food/potion) carries a doctrine tier MINED from the seat members' observed reference builds (builds_index, conservative id normalization, build-id citations; audit board = roles_report `kit_doctrine`, off-uniform sightings reported never admitted). Mined pools are real doctrine: stopper chests Demon/Judicator plate, brawler chests Hellion + ROYAL JACKET (the owner's Realmbreaker variant, surfacing cited with its `carries: cooldown_banner` chip — R16), Beef Stew on damage seats vs Omelette on tank/healer seats. Ordering ruling from T22: context-free kits rank the doctrine tier first; COMP-AWARE kits rank the exact marginal first (the engine's own physics outranks a sparse observation — the initially-shipped tier-first comp ordering handed the castle-24 tank an Assassin Hood and broke the T22 pin; doctrine demoted to annotation + tie-break in that mode); (3) PASSIVE DOCTRINE — roles.yaml names only the FAMILY per gear class; each piece's actual passive id resolves from its own dumps menu and the magnitude parses from the spell description (Aggression +8% damage & healing cast; Quick Thinker +5% CDR display-only — no invented channel; Authority +10% CC duration; Tenacity +20% CCR), stamped `doctrine_passives` per piece per seat class and fed into the build stat channels by `build_extra(role=)` — R14; (4) EMERGENT PAIRING — `bonusccdurationvsplayers` joined the dataset stat copy and the new `cc_mult_caps` channel (stun/root/slow/silence; knockbacks are instantaneous and stay out) multiplies the wearer's OWN CC — R13 pins Leering Cane worth something on Incubus and exactly nothing on Great Fire, the owner's pairing as physics with zero hand lists. Kit parity now rides the 60-case suite (comp-aware + context-free serialized per sampled case, values at 1e-9); the JS port's missing brawl-cloth-gate drift was found and closed in the same mirror. R12–R16 (16/16), 56/56 golden, 23/23 forge, 60/60 parity, full battery green.

**Seventh pass addendum — the FULL offhand roster.** Owner: "is that all the offhands, or missing some" — the catalog held 6 of the bank's 18. All 12 missing offhands added (empty capabilities BY DESIGN — no active; the stat profile is the identity): Tome of Spells (cast time), Celestial Censer (+heal, −defense), Muisak (+damage +heal, energy tax), Leering Cane (+CC duration), Cryptcandle (+spell damage, −defense), Eye of Secrets / Sacred Scepter / Taproot (the BOOK CLASS — near-no modifiers, identity = raw item-power progression, 725/800/775 vs 700 baseline at T4; affinity deliberately empty pending owner grading), Unbreakable Ward + Facebreaker (shields: defense+threat; Facebreaker adds damage), Timelocked Grimoire (cast+CDR — the guide-cited Incubus-support pairing), Torch (attack speed+CDR). One sign bug caught by the board itself: Censer/Cryptcandle carry defense PENALTIES and had landed in tank seats — the defense rule now requires a POSITIVE modifier (Censer → healer seats only, Cryptcandle → dps seats only). 11/11 roles, all gates green.

**Seventh pass, same session — OFFHANDS classified by their numbers.** Owner: "for offhands, they have no active ability, their usefullness comes from the stats. so to properly classify them, you have to get the stats for all offhands to get its role and logic for what builds they work with." Found: the stats bank (`out/item_stats.json`) held every offhand's identity profile all along — the gap was the dataset build's copy filter carrying only the eight chest-centric fields. Widened (defense bonus, threat, cooldown/cast-time reduction, energy, HP, heal modifier — engine scoring channels unchanged, they read only their documented keys) and offhand `role_affinity` now derives from the STAT PROFILE: defense/threat → tank seats (Shield/Caitiff/Sarcophagus), heal+damage output → healer+dps seats (Blueflame Torch the hybrid), cooldown/cast/energy utility → caster-support families (Mistcaller = pure CDR 0.96%/100IP → healer/support seats, matching its comp-cited seat beside the 1H Mace engage tank; Astral Aegis = defense + energy discount → the widest board, tank AND support seats — honestly what the item is). R11 pins Mistcaller + Sarcophagus; 11/11 roles, all gates green. Remaining gear-model work rides increment 2: tree-shared actives + the passive pick per role doctrine.

**Sixth pass, same session — Mistcaller/Lymhurst directionality fix.** Owner: "i dont think mistcaller and lymhurst capes are ally buffing effects, they are self buffing i believe." Dumps agree: Mistcaller has NO active (a self stat stick; the offhand stats-bank gap had left its identity to a curated proxy) and Lymhurst's ability is PASSIVE_CAPE_LYMHURST, a self proc — both `buff_allies 2` rows were GEAR_STATS-grounded direction errors (the V5 catch-#1 class). Rows removed with citations; both items drop off the gear-effect candidates list automatically (now: Druid Cowl, Knight Helmet, Guardian Helmet — all genuinely ally-targeted actives). 10/10 roles, all gates green.

**Fifth pass, same session — the law renamed, passives counted.** Owner: "dont call it E-first law, it should be something like unique ability first law because armor pieces arent on e, they might be on d,f,r etc" — recorded as the UNIQUE-ABILITY-FIRST law (roles-design.md), with E-first as its weapon case. And "the damage/heal bonus isnt taking into account the passives which are also unique to that tree ... most cloth users will take the damage passive on equipment to increase damage even higher" — the tree passive sets were already in the dumps extraction (gear_spells.json) and now stamp every worn item (`tree_passives`, on the items board): cloth = +8% damage/heal OR −10% cast time OR energy cost (the damage passive the owner names as the cloth default); leather = balance / AA speed / CD reduction; plate = MR-AR / CC duration / CCR / threat. The passive PICK per role doctrine (cloth dps takes the damage passive) is recorded as kit-doctrine work for increment 2. R10 extended; 10/10 roles, all gates green.

**Fourth pass, same session — the EQUIPMENT model lands.** Owner: gear mirrors weapons — three ability choices, "the tree shares the first two spells ... just like weapons, the identity of the equipment is derived from its unique spell"; and "damage and tankiness is based on which tree the equipment belongs to. you need to pull numbers to classify items into right role." Numbers pulled and verified: cloth chests 54–68 armor / +40–50% damage-heal, leather 92–100 / +25–30%, plate 152–161 / +0–5% — numbers-derived class agrees with the tree id on every statted chest. `classify_gear` stamps `gear_class` (numbers first) + `role_affinity` per worn item; the items board + gear-effect CANDIDATES (ally-buff actives not yet catalogued: Lymhurst Cape, Druid Cowl, Knight Helmet, Guardian Helmet, Mistcaller) ship in out/roles_report.json for grading. Recorded gaps: stats bank zeros for head/shoes/offhand (class falls back to tree id); gear records curate only the unique active — the tree-shared first two abilities await curation for full kit picks. R10 pins the board; 10/10 roles, all gates green.

**Third grading pass, same session — SHIELD BREAK split out of purge.** Owner: "the purge role is mixed in with shield break it looks like, hammers i think only break shield on q, it isnt really a purge. shield break is like the primary role of black monk i think." The sheets' own row comments already carried the distinction (the 2026-08-21 shield-break-below-true-purge ruling); shipped as the SPELL-CLASSIFIED split: a function role may claim specific evidence spells (`spells:` on the role record — Iron Breaker, Black Monk's E, Claws' E) which the sweep routes to IT and never to the unfiltered role on the same cap; `primary_min: 2` on shield_break because its ladder is deliberately held below the purge ladder. Result: purge = TRUE purges only (Lifecurse, Fists, Heavy Mace's Battle Howl, 1H Arcane, Daybreaker — zero secondary); shield_break = Black Monk + Claws E-primary, the eight hammers Q-secondary — exactly the owner's reading. R9 pins it; 9/9 roles, 60/60 parity, all gates green. NEXT (owner-directed): "once we have the weapons sorted, we could also start working on the roles each item(equipment) plays. so really get a complete picture" — the equipment-role pass folds into increment 2 (kit doctrine): classify all 41 catalog items (and the missing uniforms like Royal Armor) into role uniforms + gear effects, then rebuild the kit advisor on top.

**FULL-BOARD GRADING (2026-08-26) — 465 rows reviewed, 15 rulings, everything else accepted as shipped.** The complete roles_report (seat memberships, kit-doctrine pools, gear effects, 43-item equipment board) went to the owner as an interactive grading board (mark-what's-wrong artifact); the copy-back report is verbatim below the wiring. Eight MEMBERSHIP corrections (roles.yaml, each with the quote at the removal site): Iron-clad off stopper_tank (consistent with its standing ≥10 exclusion); Great Holy off main_healer ("brawl anchor" reading — brawl_healer seat stands); Witchwork off shield_support ("witchwork does not play for cleanse, its a clump and damage weapon" — engage_tank stands); Black Monk off shield_support ("does not shield team, it purges shields from enemy" — shield_break stays primary); Chillhowl ("not good for group content"), Glacial ("more DPS than a support") and Permafrost ("dps and engage dps") off zone_support — the frost dps pair keep their ranged_aoe seats, Chillhowl leaves every menu; Great Arcane off bomb_aoe ("role ... is to stop enemies ... can work with the one shot dps to set them up" — shield_support stands as the setup seat). Five KIT-DOCTRINE rulings, shipped as the new cited `kit_doctrine.overrides` layer (drop must name a mined item, add a cataloged uniform-legal one — anything stale blocks the release; audit trail in roles_report `overrides`): engage potion drops Resistance Potion; stopper cape drops Lymhurst; stopper offhand swaps Timelocked Grimoire → Leering Cane; brawl_healer offhand swaps Sarcophagus → Blueflame Torch ("if user is on judicator armor too" — conditionality recorded verbatim, conditional kit logic stays increment-3+ work). One EQUIPMENT ruling via the new `gear_affinity_overrides` layer: Leering Cane's derived caster-support affinity (its small CDR stat) replaced with [stopper_tank] ("not for brawl healer, its mostly for stop tanks that are one hand"). One VIABILITY ruling: Dagger Pair + Deathgivers excluded at ≥7 ("never in medium-large scale (7+)") — composition.yaml exclusion with the standard evidence-gate lift; trio stays open, the 4–6 band was already gated by the round-7 style rules, and their dive_cleanup seats stand at small scale. R17 pins the whole batch (17/17 roles); 56/56 golden, 23/23 forge, 60/60 parity, full battery green.

**INCREMENT 2.5 (2026-08-26, same session) — PER-WEAPON DOCTRINE + EFFECT QUOTAS.** Owner, on the graded board: "its not likely that hand of justice would be using demon armor and i dont know how we would fix that situation" — then, on the one observed counter-case, the diagnosis itself: "its fine if a weapon wears that armor once but in those special cases you have to find why its doing that. maybe its filling a role. maybe the composition didnt have enough demon armors so the engage tank has to take one. maybe 4 cases isnt a big enough sample pool." Hypothesis VERIFIED before wiring: the sighting is cb_clonepeek_zvz20 seat 19, and that roster fields 4 Demon + 4 Judicator + 1 Guardian — a reflect-heavy frontline allocating its quota. Shipped accordingly (both ports, R18-pinned): kit pools now also mine per weapon (`kit_weapon` / report `by_weapon`; Polehammer's own tier is Knight ×5 of 5) and the kit advisor ranks the weapon's own observed tier first with sample-size honesty (`doctrine_n`); effect-carrier chests (the typed gear_effects) are excluded from weapon tiers — they stay in the seat pool tagged `effect:` and are quota-mined per near-complete roster (`effect_quotas`: reflect shells in 7 of 8 rosters, typically 3 copies — DISPLAY-ONLY until the owner grades the pattern, now on the board with the per-weapon kits); overrides gained weapon scope and seat drops cascade so a seat-wide ruling can't resurface through a weapon tier. 18/18 roles, 56/56 golden, 60/60 parity + embed, full battery green.

**SAMPLE WIDENED (2026-08-26, owner: "increasing the sample even more so we get more accurate stats").** The MetaBattle adapter grew to v2: fetch now captures every group-PvP build category (ZvZ + Hellgate 5v5/10v10 + Crystal League/Arena + Ganking — solo/PvE modes deliberately out), `content` derives from each page's own mode category (MODE_CONTENT priority), and the batch ships as `data/published_builds/metabattle.yaml` (metabattle_zvz.yaml retired; the build's ZvZ style-fit cross-check now filters `content == "zvz"` so ganking builds can't vouch for group-scale fitness). Result: 46 pages captured (was 31), evidence corpus 222 → 237 records over 65 → 74 weapons, 914 kit-doctrine observations, new `ganking_smallscale` + wider `hellgate_5v5` buckets — dive_cleanup's daggers now carry their own observed kits from real ganking builds. Two records quarantined on an ambiguous 'Frost' spell name (fail closed, correctly). Full battery green (53/53 builds, 18/18 roles, 56/56 golden, 60/60 parity, provenance/patch/cohort/codec/display/tier2). The sample lever remains open-ended: more caller sheets in data/published_comps is still the highest-value growth per observation.

**INCREMENT 3 (2026-08-26) — NEED PROFILES: blind round, evidence pass, wiring.** Protocol honored end to end: the owner's mix calls were collected BLIND (20 brawl: "1 maybe 2 ways to clump and then give focus on 4 stop tanks ... 3 supports who slow or deny ... 3 or 4 heals ... remaining melee dps ... make sure i have things covered like heal cut and pierces"; clap-kite same skeleton ranged; terry "add more stop tanks"; 7-man shapes; then the directive: "it doesnt matter what i believe is important. what matters is what the data says"). Evidence pass: the forge's own current mixes at five matched cases, the 8 curated rosters, Wardergrip's guide ("4-5 tanks, 3-4 supports, 4 healers"), and a NEW killboard roster miner (`pipeline/sample_rosters.py`, sanctioned albionbb endpoint → `out/roster_mixes.json`): 139 near-complete fight rosters (24 party / 39 mid / 76 gang; wiped sides so the whole roster is attributed — the winner cohort is reported separately because healers under-attribute on winning sides). Findings: healers 3-4 mode 4 (every source agrees); ENGAGE > STOPPER everywhere (live 1.95/1.09, curated 2.6/1.8) — the data overruled the owner's 4-stopper blind call, which survives as the territory-defense override; pierce fielded by 100% and heal-cut 92% of live party rosters (the owner's kill-pressure doctrine confirmed in the wild); shield support 1.5 live vs 3.2 curated (flank-party skew confirmed); dive_cleanup lives at gang scale. Owner approved the v0 profiles ("yeah go for it"). Wired: roles.yaml `need_profiles` (engage 2-3 / stopper 1-2, terry stopper 2-4 engage 1-3, off <=1, shield 1-3, zone <=1, pierce >=1, anti_heal >=1; min_size 15, scaled by size/20 half-up), validated fail-closed in build_dataset, shipped in the dataset, enforced in BOTH ports as generation constraints riding the forge's predicate channel (seat maxima via ctx seat_max; locked members count; manual parties always score; below 15 nothing arms). Both ports produce identical profile-constrained 20-man forges (checked at three armed cases; the 60-case parity forge runs at size 8, below arming — recorded gap). F21 pins the contract; 24/24 forge, full battery green. The forge's clap_kite melee-heavy failure case is documented as the motivating defect; its full fix (delivery-mix bands per style) awaits a numeric owner ruling on the clap_kite ranged-core minimum.

**CONDITIONAL-PAYLOAD RULE (2026-08-26, the comp-status radar round).** The new status radar surfaced it: a forged 20-man clap read "split identity — melee and ranged damage pull apart", with every true-ranged staff flagged as pulling against a MELEE core — "why do we have a melle core in a clap comp to begin with?" Diagnosis: the forge satisfied the 7-strong ranged-AoE core largely with FLEX bruisers (fists/sword class — the predicate is honest, their Es land at range), and comp_identity counts flex damage on its home melee side, so the roster read 59% melee. The owner REJECTED a delivery-category fix ("I dont want to set a hard rule that a weapon needs to be range or melle") and ruled the job-difficulty doctrine instead: clap = giving up leather tankiness for "naturally high damage that can be delivered almost instantly" — "permafrost can instantly deliver an aoe stun ... similar with spiked gauntlet ... this job is a lot harder for clarent blade because it has to stack its q." Per-weapon rulings: Clarent/Ursine "nice melee brawl weapons but maybe dont fit so well in clap"; Carving "good brawl for resistance shred"; Longbow KEEPS clap ("nice clap over wall because the dps it does"); Earthrune ("very meta clump tank"), Malevolent Locus ("good support"), Enigmatic/Lifecurse/Blight ("fine supportive weapons") untouched; Energy Shaper keeps ("good damage"); Morning Star "no one uses, just check stats" — killboard: 1 large-fight appearance, none mid/small. Wired fully derived, zero hand lists: parse_dumps gains a structural `channel` fact (a `channelingspell` node anywhere in the spell tree — Gravitas hides its channel in a sub-spell, so the walk follows references); derive_style_fit demotes a GROUP damage carrier to situational at clap/clap_kite gang+group when every damage E is ramp-dependent (consumes charges/stacks — description-detected, the charge spend hides in a generic removeactivespell) or a non-ranged channel. The scoping needed no exceptions: every "keep" ruling falls out of existing derived facts (ranged channels exempt by delivery; support/tank seats exempt by damage_scale none). Catalog diff: exactly 4 weapons flipped — Clarent, Carving, Ursine, and Rift Glaive (a true positive: its E deals damage "based on the amount of Spirit Spear Charges", and crystal is cost-gated below 30 anyway). Result: the same clap forge now fields Damnation + Heavy Crossbow + Wailing Bow + 2× Permafrost instead of Ursine/Clarent, reads "Clap-Kite · leaning" with ZERO conflicts at 42% melee — the owner had predicted "it might instead have a witchwork and damnation" before the fix ran. Fitness moved 139.4 → 139.2: the sacrifice lives in the pool, not the score, exactly as the owner framed it ("the composition should have some natural things it lacks"). Kite deliberately untouched pending a ruling; the >100% radar readings were explained, not retuned (targets are comp-fitted floors at 0.9× the least a good comp fields — per the anti-circularity rule any target reshaping waits for its own evidence round). T32 pins the pool membership both ways; full battery green (57/57 golden, 24/24 forge, 60/60 parity + embed, 18/18 roles, provenance, tier2 78%).

**KITE EXTENSION (2026-08-26, same session — "how is this a kite comp:").** The owner ran the kite-20 forge next and challenged the result; the engine agreed (comp_identity: "split identity", 65% melee — five sustained melee brawlers fielded). Three gaps composed: the conditional-payload rule had deliberately parked kite, "flex fits everywhere" admits every bruiser, and kite carried NO ranged-core constraint (increment-3's ranged_aoe_core went to clap/clap_kite only). Evidence pass before proposing numbers: the one real kite 20-man in the corpus (ss_kite_20, albioncompo) fields 13 ranged / 4 melee / 3 flex — the melee bodies are all tanks/stoppers plus the pierce bot, ZERO ramp/channel bruisers, flex damage is instant-payload only — and counts 5 ranged-AoE-core predicate qualifiers (lower than clap's 7 because kite pressure legitimately includes curse/sustained ranged damage the burst-AoE predicate does not count). Owner approved ("ok"): conditional-payload extended to kite gang+group (same 4 weapons flip their kite cells: Clarent, Carving, Ursine, Rift Glaive), and kite constraint_overrides gain ranged_aoe_core min 5 at 20-29 / 4 at 15-19 (0.9x the observed 5, rounded to the owner's firmer side per the clap-7 precedent). Result: the kite forge drops from 5 sustained brawlers to 1, fields a real ranged core (Longbow, Permafrost, Glacial, Dawnsong, Bow of Badon, Damnation + the arcane support stack), melee share 65% -> 38%, zero conflicts. Honesty check recorded: Hellfire Hands generates in kite — its E (Boulder Toss) is genuinely unconditional, so the derived rule correctly passes it; its clap exclusion is the separate 2026-08-24 owner override, which is clap-scoped, and whether Hellfire belongs in kite generation is an open owner call. T33 pins pool membership + the armed core minimum; full battery green (58/58 golden, forge, 60/60 parity + embed, roles, provenance, builds, interactions, patch, cohort, codecs, tier2 78%).

**THE DISPLAY RULER (2026-08-27, owner: "we should never ever be above 100 for anything but this 0-100 has to be based on ground facts").** The radar and the capability board had been quoting supply as % of TARGET — and targets are comp-fitted floors (0.9x the least any good comp fields), so a competent comp read >100% everywhere and the playstyle tradeoffs the owner named ("clap comp gives up tankiness on dps and brawl comp gives up a bit damage ... these types of tradeoffs are what define the playstyle") were invisible. Re-ruled to the CEILING, no template retune needed: 100% = the comp-fitted soft cap (1.15x the MOST any good comp fields, from the same 2026-08-21 recalibration ruling — already ground facts, already style-neutral, so a real brawl ball now pushes ~100% Frontline while sitting low on ranged Damage and a clap reads the opposite). Per-cap supply counts up to its own soft cap, so nothing can read above 100; stacking beyond the ceiling shows as the purple overstack marker, never a bigger number. The target minimum stays visible as a brass TICK per radar spoke and per capability bar (target/soft position). Scoring untouched — targets, soft caps, headroom and floors are exactly what they were; only the measuring stick the DISPLAY quotes changed. Both surfaces (dl radar, renderGroups bars) re-ruled together; parity embed + display gates green.

**SIX CAPABILITIES PROMOTED (2026-08-27, owner: "is that all the effects? have we missed anything" -> "first let's add those missing items").** Audit of the taxonomy against the sheets found 31 capabilities supplied by weapons/gear but only 25 scored by any template. The six orphans were fully curated with cited evidence AND used by other layers (the kite chain's Slow stage reads slow+root; Peel reads anti_dive; mechanics.yaml scales all three geometric CC caps) — but no template carried a requirement row, so fitness weighted them ZERO: an AoE root earned a weapon nothing. Evidence per cap: slow 87 weapons/220 pts, root 74/190, knockback_displace 56/150, anti_dive 19/62, interrupt 19/40, max_health_cut 5/12. Fitted from the REAL comps by the standing 2026-08-21 convention (target = 0.9x the least any good comp fields, soft = 1.15x the most), measured in the same weapon+spell-pick unit as every existing row so the templates stay internally consistent — the unit re-base (weapons vs whole people) is a separate pending question and must move ALL rows at once. Weight 1 across the board: the documented low-and-flat start for a newly promoted capability (design doc; anti_zone/damage_debuff precedent), because an unvalidated number must never dominate a recommendation — raising them is an owner ruling once the effect on real picks is seen. scales: true for the three geometric CC caps (mechanics.yaml geometric_caps), false for the dedicated-slot tools. HONEST GAPS RECORDED, not invented: castle and faction_war get NO rows (zero comps in the corpus for either content); castle_outpost gets no max_health_cut row (no comp fields it); roads is fitted from ONE comp, so its target is 0.9x a single observation and its soft cap uses the median soft/target spread the multi-comp contents show (a 1.15x band around one point would flag overstack instantly) — re-fit when a second roads comp lands. Effect: blackzone scores 24 -> 30 items, total weight 121.5 -> 127.5; blap measures at or above target on five of the six (anti_dive 0.0/1.2 is a real, visible hole in a comp that fields zero anti-dive); the CC-utility weapons the model was blind to (Bedrock Mace 17 pts of newly scored supply, Incubus 13, Tombhammer 13, Frost Staff's root 6) now earn what they bring. Full battery green (golden, forge, parity + embed, roles, provenance, interactions, builds, tier2 role gate PASS). Still unpromoted and recorded as open: reveal/anti-stealth and enemy CC-resistance reduction (real dump effects, no taxonomy home); PvE-only effects (mob defense/threat/mob CC duration) deliberately stay out.

**THE LAST TWO EFFECTS INVESTIGATED (2026-08-27, owner: "ok add these effects too") — one added, one correctly refused, and my own earlier claim retracted.** I had told the owner two effects were "real in the dumps with no home in the taxonomy". Investigating both to the dump level found that half of that was wrong. (1) **"Reduce enemy CC resistance" DOES NOT EXIST** — retracted. The effect map already carried `crowdcontrolresistance-: enemy: []` with a reasoned non-promotion ("1 weapon line"), and what the dumps actually carry is the per-spell `@ignorecrowdcontrolresistance` FLAG on 54 equippable CC spells: a spell QUALITY (this CC bypasses their resistance), the same shape as resil_pen, not a supply a team fields. Recorded in the map: if ever modelled it belongs beside resilience penetration as a multiplier on the CC caps, never as a capability row. (2) **`reveal` stays unpromoted, now with evidence rather than a shrug** — every WEAPON source of remove:invisibility is a PURGE spell (Battle Howl, Arcane Orb, Cripple, Breakthrough, Iron Will, Devastating Strike, Enfeeble Blades: invisibility is a buff, so purging strips it), meaning a reveal row would double-count purge on seven lines; only TWO sources reveal WITHOUT purging (Guardian Armor's Enfeeble Aura, Stalker Hood's Mortal Agony) and both are GEAR, which the effect catalogue does not index (367 entries, weapon spells only) — the lint rejected both claims, correctly, and I backed them out rather than forcing them through the override channel. No comp fields anti-stealth either, so there is no demand to fit a row against. (3) **What the investigation DID find is a real curation gap, now fixed: Defensive Slam was never curated.** A Q on five maces (Oathkeepers, Morning Star, Heavy Mace, Camlann, 1H Mace) granting +0.15 damage resistances AND +0.15 Crowd Control Resistance to the caster and up to 10 allies in 8m for 4s — the effect map already routed both halves (`damageresistance+`/`crowdcontrolresistance+`, ally direction -> buff_allies, peel) and the spell HAS structured effects, but no sheet ever cited it, so five maces scored zero for a genuine group defensive buff. Curated buff_allies 3 (calibrated against Royal Armor's 10-ally energy buff) + peel 2 (kept below Guard Rune's outright CC immunity at 4 — a resistance is not an immunity); both marked owner-review. Effect: Oathkeepers buff_allies 4, Heavy Mace/Camlann/1H Mace 3. Recorded standing gap: the effect catalogue indexes weapon spells only, so every gear-sheet claim rests on prose + overrides rather than structured evidence — the reason the reveal claims could not be checked. Lint PASS, full battery green.

**THE EFFECT CATALOGUE NOW COVERS GEAR (2026-08-27, owner: "ok do extend the catalogue to gear") — and the first run caught six bad claims, one of them backwards.** The catalogue indexed WEAPON spells only (367), so every gear-sheet score rested on prose + overrides and the evidence lint could not check a single one — the wall the reveal investigation hit. `effect_catalogue.py` now indexes gear actives AND passives from gear_spells.json alongside weapon spells (367 weapon + 194 gear = 559 indexed), tracks `gear_lines`/`gear_line_count` per effect beside the weapon counts, and every gap report (unmapped / no-prose / needs-a-call) now spans both sources — an effect that only ever appears on armor was previously invisible to all three. Immediately, the lint went from silently skipping gear to FAILING with 6 grounded errors; each was adjudicated against the newly visible structured effects, not waved through the override channel: (1) Fiend Robe's Fear Aura `anti_dive` -> `knockback_displace` (its only enemy effect is forced_movement — and displacement is now a scored capability); (2) Fiend Sandals' Position Swap `mobility` DROPPED (its only effect is invincibility; one repositioning trick is not group mobility); (3) Hellion Shoes' Mark of Sacrifice `mobility` -> `catch` (the mark strips the target's movement buffs — it is a catch tool); (4) Specter Shoes' Spectral Run `mobility` DROPPED (invisibility plus self-penalties, no speed component at all); (5) Knight Helmet's Displacement Immunity `buff_allies` DROPPED (the map deliberately routes an ally IMMUNITY to peel, "protection AGAINST the effect", and peel already carried it). (6) **Demon Armor's `tankiness` was BACKWARDS** — Protection of the Fiends grants magicresistance+/physicalarmor+ to ALLIES while applying magicresistance-/physicalarmor- to the WEARER: the chest buys the group's durability with its own, and the model had it as the wearer's own tankiness. Re-cited to buff_allies 3. That error survived every review precisely because gear claims were unverifiable. Gear sheets: 6 errors + 34 unverifiable warnings -> 0 errors, 5 warnings. Lint PASS, dataset rebuilt, full battery green (golden, forge, parity + embed, roles, provenance, builds, interactions, patch, tier2).

**REFLECT + SELF-COSTS + THE FIRST SUPER-ADDITIVE DUPLICATE (2026-08-28, owner: "we should add reflect ... no team will bring just one user on demon armor, they always bring 2 or more to counteract the self tank loss").** The owner's play observation turned out to be measurable and mechanistic, and closing it needed three new pieces. EVIDENCE FIRST: the killboard quota miner had independently recorded reflect shells at 3,3,4,3,3 across the five near-complete 20-man rosters — never one — and the dumps explain why. Demon Armor's Protection of the Fiends is the ONLY team reflect in the game: it returns 50% for the wearer AND up to 9 allies while granting them +0.43 resistances, and it pays for that by cutting the WEARER's own resistances by 0.37. Every other reflect in the catalogue (Counter 150%, Parry 125%, Deflecting Spin 100%, Retaliate 85%, Inferno 38%, Frost 15%) says "increasing YOUR resistances" — self-only. So two wearers stand in each other's aura and the penalty is repaid; one wearer just eats it. SHIPPED: (1) **reflect is structural** — `reflectdamageactive` (@amountpercent, @target) added to the effect catalogue's node extraction and mapped self->[reflect], ally->[reflect, buff_allies]; 32 weapon lines and 25 gear pieces carry it, and the lint now grounds every claim. Curated on its real sources: Demon Armor 6 (team-wide), the personal stances 2, Frost Shield 1. (2) **SELF-COSTS** — a new `self_costs:` block on a sheet entry, compiled into the dataset and charged in `build_extra` on the WEARER's own vector (never the team pool), last so the stat channels cannot re-multiply a cost, floored at zero. This is the field whose absence let a backwards `tankiness` claim survive every review: the sheet could express the upside and nothing else. (3) **`self_cost_offset_min_copies`** — the mirror of the count-once rule and, by owner ruling, the ONLY super-additive duplicate in the model ("duplicate is worth more only in special cases like demon armor"): verified-confidence only, scoring_note required, an int >= 2, and it may CANCEL A COST but never add supply, so a duplicate still cannot out-earn two independent first copies. The interactions layer also gained gear equippability — REFLECTAREA is its first GEAR record, which its own comment had deferred "until gear records exist". RESULT, measured: a six-body party scores tankiness 12.00 naked, **11.72 with ONE Demon Armor (the team is worse off)** and 14.44 with two. NO TEMPLATE ROW for reflect, deliberately: it measures 0.0 in the weapon+spell-pick unit for all eight comp parties (the reflect Ws are never the default combo), and in the person unit three comps field 9-12 while five field none — a genuine disagreement, which the 2026-08-21 convention leaves untouched. It waits for the pending unit re-fit; the Demon Armor mechanism does not wait on it, because the self-cost lands on tankiness, which every template scores. Five new pins in test_interactions (37/37): the record's discipline, that it is the only offset in the corpus, that one copy costs the party, that two beat twice one, and that reflect supply itself stays strictly additive. Full battery green (13 suites incl. 60/60 parity + embed, golden, forge, tier2).

**THE STYLE LABELS + THREE EVIDENCE-QUALITY RULINGS (2026-08-28).** Per-style targets need style-labelled comps, and 8 of 13 records carried no `style:` at all — so the corpus was shown to the owner as rosters only (no engine reading, blind-round protocol) and came back labelled in one pass: hellgate5 **clap**; roads_oneshot **clap_kite**; sob_blaze_os **clap_kite**; sortasaucy_7man_ftb **clap** ("more clap than clapkite but does have some kite elements" — labelled clap, the kite lean recorded in-file and NOT fitted); clonepeek_zvz20 **brawl_clap**. Record-level styles went 5 -> 10. THREE of the answers were evidence-quality rulings rather than labels, and each is now enforced, not just noted: (1) **cb_kroozlt19_bomb_squad** gets NO style — "its a bomb squad which is a bit different than regular party, their objective is to do as much damage without much survivability (assassin jackets ability increases damage even though its leather)". It carries `archetype: bomb_squad` (the archetype comp_identity already models) plus `fit_exclude`, because folding a deliberately fragile comp into clap would drag clap's durability targets down. (2) **cb_shadowlagrange_tracking5** gets no style and `fit_exclude`: "this is a PVE comp to do tracking content" — it answers a different question than any PvP template. (3) **deadlyhooker party_2 and party_3** are excluded — "party 2 and 3 are kind of not built properly and would probably give wrong data for a comp i think" — while **party_1 is labelled clap_kite leaning clap** ("the most relevant"). That forced the schema to admit PER-PARTY style and exclusion: one record's parties are not always one comp shape, and the record-level value is now the fallback rather than the only answer. Both `style` and `fit_exclude` are validated per party (an exclusion without a stated reason is rejected — indistinguishable from lost data) and travel into builds_index so every consumer sees the ruling instead of re-deriving it; tier2 honors them and now prints the skip with its reason. STALE-LIST BUG FOUND BY THE LABELS: `builds_lib` rejected `clap_kite` as an unknown style — its whitelist predated the fifth playstyle (owner-identified 2026-08-23) and nothing had caught it because no comp was labelled clap_kite until now. Effect on the gate: V4 drops from 25/32 = 78% to 17/23 = 74% role-level — still PASS, and the drop is the point: it stopped grading itself against two parties their own author disowns. Full battery green.

**ONE COMP, SEVERAL CONTENTS (2026-08-28) — and the finding that reframes the template layer.** Half the corpus states a content that names a FORMAT, not a template (`zvz_20man`, `zvz_7man`, `zvz_20v20`, `large_scale_zvz`), so those comps skipped every fit. The audit layer had been guessing a single mapping (zvz_20man -> blackzone_roam etc., flagged audit-only, never a gate). Owner ruling: "zvz 20man can be blackzone roaming or castle outposts or castle defense, same with zvz 7man, it can also be avalonian roads" and "any comp doing outposts or castles or roaming in blackzone could do so in faction aswell". Shipped as `content_candidates: [...]` on the seven format-labelled records (20-man -> blackzone_roam/territory_defense/castle/faction_war; 7-man -> castle_outpost/roads/faction_war), validated against the real template list so a typo or renamed template surfaces instead of silently dropping a comp from every fit, and carried into builds_index. Applied ONLY where the stated content names no template — transferability for the explicitly-labelled comps is a separate call. THE FINDING: measuring how much the six templates actually differ (targets normalized per head, so size scaling is removed) first suggested 19 of 30 capabilities were "content-specific" — but that was an artifact. Only blackzone_roam and territory_defense were ever comp-fitted (2026-08-21); castle, castle_outpost, faction_war and roads still carry hand-set provisionals, and the spread was mostly fitted-vs-guessed. Comparing ONLY the two fitted templates: **21 of 30 targets agree within 25% (mean difference 20%)**, and just six genuinely diverge — cleanse (0.8 vs 7.2), engage (11.7 vs 4.2), mobility (19.8 vs 4.2), silence, anti_dive, anti_zone. Every one is about MOVEMENT vs HOLDING GROUND, which is exactly what the owner's ruling implies: the same 20-man ball roams, hits outposts and fights faction war; what changes is whether you chase or hold. CONSEQUENCES for the pending re-fit: (a) multi-content evidence is not a contamination risk but the fix — it is how the four never-fitted templates get real numbers instead of provisionals; (b) the convergence worry is mostly moot, since honestly-measured templates were already ~80% alike; (c) content difference may be better modelled as a small set of movement/holding modifiers over a shared base than as six independently-fitted 30-row tables, most of which cannot be filled. Full battery green.

**WIKI RESEARCH PASS + TWO CLOSING RULINGS (2026-08-28, owner: "why don't you look up these things in Albion wiki to build good understanding").** Four things came back from the wiki (fetched via Playwright — it 403s scripts). (1) **Disarray** is listed as a core ZvZ mechanic beside Focus Fire and AoE Escalation; already in mechanics.yaml with current data incl. the Radiant Wilds battle-mount rule, and deliberately unwired for a sound reason already recorded — it prices OUTNUMBERING, not composition (a no-op in a mirror fight). No gap. (2) **"Outpost" is two different objectives**: Faction Outposts (royal zones, towers with a capture ring, open terrain) vs Castle Outposts (Outlands, guards -> elite guards -> Outpost Lord -> claim circle, "a smaller castle" exactly as the owner said). That separates two axes that were being conflated: faction war is OPEN TERRAIN but still requires HOLDING a ring, so move-vs-hold and open-vs-enclosed are independent dimensions. (3) The armour classes read exactly as the owner described them — cloth "limited defense but excels at offense", leather "balanced", plate "high defense but low on offense" — so cloth-as-squishy-marker is the game's own framing; and "each armor piece has one active and one passive ability", which confirms the passive-as-a-slot design for the pending passive-scoring work. (4) **Resistance is directional**, which the engine flattens into one tankiness number. RULING, after measuring: **do not split.** The skew is real (leather exactly equal at 98.2/98.2; cloth 59.4/76.0 and plate 154.0/120.6, both 22%) — and it cancels. Classifying every weapon by SUBCATEGORY (the game's own rule: melee/ranged physical, magic weapons magical) and weighting by the damage each actually supplies, real comps field a 50/50 mix (268 vs 266 damage points), at which the two skews cancel EXACTLY — all three classes price identically whether averaged or weighted (0.0% error). SELF-CORRECTION, same day: the first pass classified by E-description text, got 62/38 and ~3% error, and was committed before the flaw was found — that sample was biased twice over (the regex missed shapeshifters, whose damage lives in the transformed form, and utility-E weapons, whose damage sits on their Q/W; and it counted BODIES rather than damage, so healers holding holy staffs voted "magical" while supplying none). The conclusion held but the evidence was wrong, so both records were corrected. Splitting would double every durability row for no correction at all, and nothing could act on it regardless, because of the second ruling: **the app models no enemy** — "no the app doesn't need a notion of what we expect to fight, out playstyle dictates how we fight regardless of who or where". Both recorded at the summation site in mechanics.yaml so neither is re-litigated. This also closes the open peel question's third branch (peel tracking enemy dive threat): with no enemy model, peel must be explained by comp or content alone.

**FOUR RULINGS, same session ("what do u need from me ask it now").** (1) **clap/clap_kite ranged core = 7 at 20** (owner picked 7 over the recommended 6) — wired into styles.yaml constraint_overrides (merged into the existing first-match rows; 15-19 carries the scaled interpolation 5), F21 extended; the forge's ranged styles now guarantee seven members whose SELECTED spells deliver ranged AoE (combo-aware, the F12 predicate — flex weapons like Realmbreaker count by their ranged E, so the seat labels still show melee bodies; capping melee SEATS under ranged styles would be a new style-dimension profile, noted as follow-up if the owner wants it). (2) **Icicle stays zone_support** — the blind round's "my d tanks would be things like bedrock and icicle" was loose usage, no membership change; ruling recorded so the question never reopens silently. (3) **Healers at 5-7 stay 1-2** — the owner declined the data-mode cap; the forge may field a second healer at 7. (4) **Effect quotas GRADUATE to advice** ("yes — advise quotas"): the dashboard's killboard-evidence strip gains "Observed effect quotas" — per typed gear effect, the roster's LOADOUT chests counted against the median carriers near-complete observed rosters field (scaled to PLAN, armed 15+; members without gear set are counted as unknown and never produce a shortfall claim; language + placement follow the killboard evidence rules — advice only, nothing scores). build.py computes the medians from roles_report effect_quotas at build time; display-math case 14 pins the counting, scaling, unknown-gear honesty and arming (14/14). Full battery green after all four.

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

**RULED + RECALIBRATED (2026-08-21, same day)** — the owner ruled that real comps set the numbers. 31 target/soft rows across blackzone_roam (16) and territory_defense (15) were re-fitted from the real comps measured in CURRENT engine units (target = 0.9× the least any good comp fields, soft = 1.15× the most; rows where comps disagree left untouched; blackzone ranged_presence deliberately NOT lowered — both evidence comps are brawl balls and that row carries the style signal; blackzone burst_st/execute NOT raised — golden T15's expert scale ruling outranks the fitting rule). Bist's comp admitted to the gate. **V4 role: 25/32 = 78% (PASS)** — up from 69% pre-recalibration and above the old 73% at n=26; weapon-level 17/92 = 18% (from 12%). All three healer misses resolved: the comp-fitted heal_burst target makes a dropped healer leave a visible hole. T15's fixture was re-pinned to assert the ruling directly (a pure-ST dagger's value must be utility, not kill damage — its total-score proxy stopped isolating the ruling once catch/mobility un-saturated); H20 now accepts explicitly-null patch per H10's unknown-handling rule.

**Circularity disclosure (owner adjudication wanted):** the 2026-08-18 reweights (anti_zone/damage_debuff 3→1-2, brawl burst_aoe 0.85→0.7) were motivated by defects VISIBLE IN these same gate comps; a counterfactual run with only those reweights reverted scores 18/26 = 69% — they are load-bearing for the gate. Each is argued from documented intent (the rows' own "can never dominate" rule; the brawl blurb's "blap fields zero ranged"), not from the misses alone, and each stays PROVISIONAL — but under this file's standing anti-circularity rule the 77% is weak-form evidence squared: treat the gate pass as provisional until the expert confirms the reweights or an independent comp reproduces it.

**FORGE REGRESSION SUITE (2026-08-18, `py -3 tests/test_forge.py`, 11 checks)** — the structural contracts of the rework: the pick-score invariant (reported marginal == exact comp-score delta, 1e-9, every content × style), template-gated + cross-member synergy, growing exact-duplicate costs with meta-proven allowances, the full size-11 large-content matrix (legal, deterministic, zero excluded weapons, no unheld negative slots), viability exclusions barring suggestions but never scoring (off-comp flags), floor clamping, size physics (no ST boost above small gangs; T16's inversion intact; roads' content restoration), headroom shape, spell-pick locks reaching scoring, and locked-member preservation. JS parity extends to forge rosters, locked loadouts, redundancy and provenance codecs (60/60 + a dashboard-embed check).

**V4 AFTER THE RANGED-PRESENCE REWORK (2026-08-19)** — role-level **19/26 = 73%** (gate 70%, still PASS); weapon-level 8/70. The chapter-2 rework replaced the always-on `attackrange >= 9` ranged_presence with per-spell-bundle evidence (curated burst_aoe + the spell's own delivery/cast range, cited overrides for gap-closers; audit in `pipeline/out/ranged_presence_report.json`). 42 weapons qualify (was 57); Great Arcane, Locus and the shapeshifter staffs lost their always-on flag because no selected spell of theirs delivers ranged AoE — the one lost role-level hit follows from that supply shift. This is the sounder rule pricing the same comps honestly, not a tuning regression; the gate holds.

**V5. Curation reliability.** Two people independently score 15 weapons; disagreement >1 point on >10% of cells means the capability definitions are too vague — tighten definitions before mass curation.

**V5b. Automated evidence lint** (promoted from V5 findings — now a mandatory CI gate, see design doc §6.3): every nonzero capability score must cite a spell UniqueName; the lint verifies the spell is actually equippable on that item (ao-bin-dumps `craftingspelllist`), that the spell's function tags/description support the claimed capability class, and that its target direction (enemy/ally/self) matches. Catches fabricated capabilities and direction errors without waiting for human review.

*V5-type reviews caught two bugs on day one (2026-08-12), which is why V5b exists:*

*Catch #2 — 1H Mace listed `purge 1`; the weapon has none. Wiki-verified the full mace ability list: no mace Q/W removes buffs, and 1H Mace's E (Deep Leap) is a mobility/stun leap. The purge actually lives on Heavy Mace's E (Battle Howl, "purges before the silence") — meaning the original Heavy Mace sheet was wrong in the opposite direction (filed purge as a W choice when it's inherent). Both sheets corrected with per-spell citations; the data model was reworked so capability sheets exist per item with a mandatory `evidence_spell` column, and archetype capabilities are computed by composition, never hand-entered.*

*Catch #1 (earlier): domain review flagged Longbow's `knockback_displace 2` — bow-line Frost Shot knocks the **user** back (repositioning), not enemies, and isn't in the standard group kit. Fixed in prototype + design doc; taxonomy gained a directionality rule (self- vs enemy-targeted effects) and a curation lint. This validates the review step as essential, and confirmed a hard data limit: no public source records which spells players run per content (killboard `ActiveSpells` is empty everywhere; all "build stats" sites show items only), so default kits must come from human curation per content type — the only statistical alternative is opt-in client-side capture, AODP-style (Phase 3+, optional).*

**GEAR COMBAT EXPANSION + T22 RE-PIN (2026-08-27)** — the owner directed the full combat gear catalog into the capability sheets ("add the combat pieces in"): 76 new pieces in `sheets/gear/combat_expansion.yaml` (19 heads, 16 chests, 21 shoes, 12 capes, 8 potions; gatherer/decorative/economy food skipped), every score citing the item's real ability or GEAR_STATS, with 23 `effect_overrides.yaml` additions for the known parser-artifact classes (teleports, immunity windows, self-cleanse, direction misreads — each dumps-cited). The expansion exposed a latent kit-advisor hole: comp-aware ranking was exact-marginal-first across the WHOLE catalog, and with 27 heads curated the castle-brawl control tank's "best head" became Mercenary Hood (scarce damage_debuff/interrupt), then Graveguard Helmet (scarce heal_burst) — golden T22 red. OWNER RULING (in-session): "search more comps to see what tanks are actually wearing — lots of tanks wear cleric cowl especially in brawl comps; no one is wearing graveguard helmet on tanks." Implemented evidence-first: (1) MetaBattle re-fetch widened the build sample 180→237 records — the observed engage_tank head tier now contains Cleric Cowl (confirming the owner's claim from evidence) and Graveguard Helmet appears in no tank tier; (2) comp-aware kit ranking went DOCTRINE-TIER-FIRST in both ports (marginal picks within the observed tier, never outside it — the increment-1 "member's job, not comp pool" rule closed for the full catalog); (3) T22 re-pinned to the mechanism: the tank head must come from the observed doctrine tier and never the off-tier marginal bait. Heavy Mace's comp-aware head resolves to its own observed tier (Assassin Hood / Judicator / Hellion Hood ×2 observed). Potion rows and the flagged judgment scores (marked "owner review" in the sheet) queue for the next blind round.

**DRESSED FORGE + T30c RE-PIN (2026-08-27)** — forge/recommend now evaluate DRESSED candidates (weapon + combo + doctrine kit, one divergent variant; spec `docs/superpowers/specs/2026-08-27-dressed-forge-design.md`), priced by the exact comp_score-with-gears the page displays (the page also started passing LOADOUT gear to scoring the same day — a discovered gap: the engine had scored full builds since 2026-08-20 but the UI never sent them). One golden flipped: T30c's "5th Longbow is negative" fixture was a NAKED four-stack, and the dressed candidate's kit (Knight Helmet/Cleric Robe/Royal Sandals/Martlock Cape/Muisak) closes ~28 units of genuinely missing supply → verdict "ok" +13.3. Against the same four-stack DRESSED in its own kits (the real-world case) the pick is negative −1.83 with caps_gain 0.0 — the 2026-08-24 ruling's exact shape. OWNER RULING (in-session): re-pin with the dressed fixture, and pin the naked-party behavior as the model's documented honesty. Search fixes landed with the change: 1-opt may re-pick the SAME weapon (the beam freezes combo+kit under an earlier partial state; re-resolution was unreachable — F5's faction_war case proved it), F5's reducibility checker prices dressed and legal-only, variant count capped at 2 by measurement (2.8× at 3 variants; 1.6×/0.9× at 2 — inside the 2× budget).

**DRESSED VALIDATION HARDENING (2026-08-27, full pass — plan `docs/superpowers/plans/2026-08-27-dressed-validation-calibration.md`, findings in `docs/superpowers/findings/2026-08-27-*.md`).** The audit that motivated it: since the dressed forge, `recommend(party, n)` with no gears prices NAKED incumbents against DRESSED candidates — so every historical V3/V4 number was an asymmetric hybrid (neither weapon-model benchmark nor production). All pre-2026-08-27 numbers are re-labeled "weapon-only-incumbent benchmark with dressed candidates." What shipped (no scoring change anywhere; full battery green and byte-stable on the legacy metrics):

- **`Engine.set_dressing(False)`** (both ports, parity case, contracts `tests/test_validation_modes.py`): candidates evaluate naked through the identity short-circuit — one formula, no second scoring path. Default ON; validation affordance only.
- **V3 modes**: `score --mode w` (V3-W, symmetric weapon-only) / `--mode d` (V3-D, production dressed: incumbents in recorded gear else doctrine v0 else honestly naked, source recorded; candidates dressed). **The 70% gate applies to V3-D.** Richer blind form (PRIMARY NEED / BEST PICK / OTHER GOOD PICKS / BAD PICK / CONFIDENCE / REASON, optional GEAR_KEYS; legacy YOUR PICK still parses; seed-20260812 parties byte-identical) + the full metric set (top-1/top-3/acceptable/ranks/need-agreement/bad-pick-rate/confidence-weighted — never one collapsed number).
- **V4 evidence classes**: `weapon_only` (legacy — STILL the exit-code gate pending an owner ruling) / `doctrine_inferred` (labeled inferred; doubly weak-form — the doctrine pools were mined from these same comps) / `actual_gear` (kits joined from builds_index — published comps carry gear on all 201 slots; 387/485 pieces resolve into the curated catalog, unresolved counted never guessed). **Result: 78% legacy role-level collapses to 34% (doctrine) / 41% (actual) dressed; 92/92 slots change top-3; 12/32 role hits lost, 11 of them tank drops.**
- **Root cause measured, not tuned** (`audit_dressed_templates` + `audit_frontline_floor` + `audit_validation_asymmetry`, all report-only): worn-armor stats add +419–622% of the tankiness target in every template; ordinary doctrine kits alone clear the castle-outpost tankiness floor for a 7-man with ZERO frontline weapons (0→15.88u vs floor 1.7, penalty 9.0→0, weakness erased) — the 2026-08-12 pseudo-tankiness ruling's failure mode recreated through the gear stat channel. Classification: representation problem (category 1). **Options A–D + recommendation (source-aware floors, Option C) await the owner's ruling** — tankiness/frontline finding.
- **Synergy-source finding**: gear-sourced caps forgo 0.14–0.45 score in minimal constructions and would move blap NEGATIVELY (−0.112) if gear counted (J rises under dressed vectors while target-capped sides don't). Recommendation: Model 2 — synergy stays weapon-only, documented as "weapon-interaction synergy"; Model 1 would be a J-rule redesign, calibration-gated.
- **Calibration layer scaffolded** (`calibration/` with train/validation/holdout discipline; 4 train cases transcribed from round 1 — nothing invented; validation/holdout EMPTY until fresh rounds): `pipeline/calibrate_scoring.py` sweeps the Phase-8 box with a scoring-path self-check and per-point golden counts against a patched dataset copy (BION_DATASET, real dataset untouched). Result: SENSITIVITY MAP ONLY — train curves flat (n=4), golden pins robust across the whole box except rho=0 (the duplicate-penalty pin, by design), synergy bonuses cannot flip a two-candidate contest even at 3.0. Every coefficient stays at its shipped value, PROVISIONAL.
- **Gear blind cards generated** (`tests/gear_blindtest.py` → 16 cards, engine answers in a hidden key file, relative-ranking scorer) — awaiting the expert round.
- **Adjacent gaps reported, not fixed**: `forge()` hard-codes locked members naked (F23 pins it; the dressed-forge spec's locked-kit language is not yet true for forge locks); standalone `refine()` is gear-blind.

**RULINGS NEEDED (2026-08-27, open):** (1) tankiness/frontline Options A–D — recommended C, source-aware floors; (2) V4 gate re-basing to a dressed class (recommended: after ruling 1); (3) synergy source Model 1 vs 2 — recommended 2; (4) the next V3-D round (fresh seed, richer form) to create uncontaminated validation/holdout; (5) forge locked-gears / refine() intended behavior.

**FIVE RULINGS DELIVERED AND IMPLEMENTED (2026-08-27, same day — owner approved all five with behavior defined; no coefficient/template/sheet/style/meta number changed anywhere):**

- **Ruling 1 — Option C SHIPPED (both ports, 60/60 parity at 1e-9).** STRUCTURAL hard floors read the WEAPON+LOADOUT supply: `fitness` takes a naked-basis floor read when gears are present; every marginal path splits the same way (`_combo_score` on dressed parties; `_combo_score_dressed` always — a candidate's KIT can never buy floor relief either; `_marg_fit_from`/`_marg_fit_pre` grew the floor-basis parameters; `pick_report` floor_lift rows and `explain` follow; `_floor_gain` caches the weapon-side floor gains for the hot path). Gear still counts toward coverage/headroom/overstack; floor magnitudes untouched per the ruling. Naked parties are bit-identical (V4 weapon_only 13/92 + 25/32 = 78% EXACT; V3-W byte-stable). Dashboard floor tags read the same basis (`supplyFloor` in `_app.js`/`_decision_layer.js` — the floor_armed display contract holds). Pins: `test_validation_modes.py` V5a–V5f (no-frontline 7-man pays the full 9.0 penalty in doctrine kits AND in all-plate; one real tank repairs it; dressed pick score == dressed comp_score delta at 1e-9). Measured after: adversarial A/C floors bite dressed (old rule: cleared); **V4 actual_gear role-level 41% → 47%** (two Deadlyhooker tank drops recovered; 0 newly lost); the remaining dressed shortfall vs 78% is the soft-cap/target SATURATION question — category 5, parked for the calibration rounds. **Found & fixed en route (structural, both ports): a pre-existing forge pruning blind spot** — a pick could exhaust a role band every remaining satisfier of an unmet predicate minimum needed (locked-Ironroot castle 7: the beam picked a second non-full healer, capping the band with primary_heal unmet, and DIED at 6/7 members, feasible=False). `_forge_ctx` now precomputes per-predicate (role, seat) capacity gates and `_forge_feasible` refuses band-stranding picks; F15 green again. Ordinal changes from Option C, fully enumerated (probe diff vs the committed artifact): 2 V4 role slots recovered; 2 of 12 V3 seed-case DRESSED top-3s changed (cases 1/4 — small floor-armed parties where candidate kits had bought floor relief; case 1 now leads Hand of Justice over the kit-boosted Witchwork); the deprecated legacy-hybrid ordinals moved on the same two cases (intended — kits no longer harvest floor lift against naked parties); ZERO golden changes (57/57, no re-pins).
- **Ruling 2 — gate re-basing DEFERRED as directed.** The exit code stays on weapon_only role-level (78% PASS, unchanged). Post-fix dressed numbers reported: doctrine_inferred 11/32 = 34%, actual_gear 15/32 = 47%. The which-dressed-metric-becomes-the-gate decision remains open, now with the floor bug out of the way.
- **Ruling 3 — Model 2 documented.** `scoring.yaml`'s synergy block now names the concept WEAPON-INTERACTION SYNERGY (engine rule 3, with the measured negative-participation citation); engine/README carries it; no J redesign; Phase-9 discrimination cases retained in `out/calibration_report.json`.
- **Ruling 4 — next round prepared.** `generate` gained `--content`/`--style` and forms now carry a machine-readable `FORM_CONTEXT` line that `score` reads (a round can no longer be scored under the wrong context silently). Fresh blind forms committed: `tests/tier2_form_r2_castle7.md` (seed 20260827) and `tests/tier2_form_r2_blackzone20.md` (seed 20260828, blackzone_roam 20) — richer fields, engine output hidden; the 16 gear cards regenerated against the post-ruling engine (answer key refreshed). Validation/holdout stay empty until real answers arrive; nothing synthetic is ever seeded.
- **Ruling 5 — both dressed-engine gaps FIXED (both ports, parity-carried).** `forge(..., locked_gears=)`: a locked member with supplied gear is scored in EXACTLY that kit and never re-dressed; without gear it stays naked (nothing invented); legacy calls byte-identical (F23 stands; F25 pins the contract + determinism + score == dressed comp_score). `refine(..., gears=)`: dressed local search optimizing the same comp_score-with-gears everything else uses — incumbent kits preserved, replacements tried per doctrine kit variant, returns `{party, gears}`; `gears=None` keeps the legacy list-returning weapon-only path bit-identical (F26/F26a pin dict shape, monotone dressed score, convergence — no improving dressed swap remains — fixed-slot gear preservation, determinism). Parity grew mirrored `refine_dressed` and forge `locked_gears` fixtures (60/60 + embed).

Full battery after the rulings: 57/57 golden (zero re-pins), 38/38 forge (F25/F26 new), 18/18 validation-modes (V5 new), 18/18 roles, 32/32 interactions, 60/60 parity + embed, builds/provenance/patch/codec/display/cohort/lint green, tier2 legacy 78% PASS. STILL OPEN: ruling 2's final gate choice; the saturation/template-unit-scale calibration (needs the expert rounds); the expert answers themselves (forms ready).

## Tier 3 — Data pipeline claims (before Phase 3 investment)

**V6. Content-labeling accuracy.** Sample 100 battles, hand-label content type from context, measure classifier agreement. Gate: ≥80% precision on castle/hellgate/roads labels, else Phase 3 stats stay content-agnostic.
**V7. Coverage at scale.** Rerun V2 across ~200 battles of varied size/server (script, not eyeball). Gate: ≥85% weapon attribution in 10–50-player battles. **Script exists (2026-08-13): `pipeline/sample_battles.py`** — samples the official gameinfo API with per-battle caching, buckets by fight size (small <12 / mid 12–30 / large >30), writes `out/weapon_usage_v2.json` with a coverage stat; the dashboard quotes it as display-only "field reports". Check the coverage number in that file against the 85% gate on each refresh.
**V8. Statistical sanity backtest.** Compute weapon win-lift on 3 months of data; check that community-consensus-strong weapons show positive lift. If stats contradict consensus everywhere, the confounds dominate and δ (MetaPrior weight) stays small.

## Standing regression suite

`prototype_engine.py` graduates into the real repo as the seed of the unit-test suite: every golden case stays green through every tuning change, every patch-driven data update, and every scoring refactor. Add a golden case whenever an expert disagrees with the engine and the expert is right.

## Gear-name resolution (2026-08-28)

**GEAR RESOLVER: ITEM IDS + CALLER SHORTHAND (2026-08-28).** Asked what stood
between us and accurate fitness numbers, the answer was measured rather than
guessed: the evidence layer was silently discarding most of the gear the comps
record. `match_gear` matched only DISPLAY NAMES, but 11 of 13 published comps
write gear as game item IDs (`ARMOR_CLOTH_AVALON`, `HEAD_LEATHER_SET3`,
`CAPEITEM_SMUGGLER`). Those cells resolved to nothing at all: 729 of 1124 gear
cells were ID-style and **zero** of them resolved. Only Deadlyhooker and blap
(display-name sources) carried gear into the index.

Three fixes in `pipeline/builds_lib.py`, all identity or spelling facts, none a
guess:

- **Item-ID matching** (`_match_gear_key`/`key_form`) — an ID *is* the catalogue
  key, so it is an identity match. Tier prefix and enchant suffix are normalized
  off both sides (sources write `MEAL_STEW`, the catalogue says `T8_MEAL_STEW`).
  Slot-checked, and returns None on a key collision rather than picking one. The
  ID shape (all-caps, underscore-joined) cannot capture a display name.
- **Caller shorthand** (`GEAR_ALIASES`, slot-scoped) — OWNER RULINGS, verbatim:
  *"GG might be graveguard boots if it's on boot slot"*, *"blink would be stalker
  shoes most likely for their double blink ability"*, *"cleanse might be any
  leather helm with second ability"* (→ Hellion Hood). Plus spelling facts:
  `RoP` → Robe of Purity, `Smugglar` → Smuggler Cape, and `helm` → `helmet`
  (`WORD_FIXES`), the caller's word for the catalogue's.
- **Notation** — a leading tier marker is stripped (`TIER_NUM_RX`: "7.1 omelette",
  "8.1 beef stew", "T8 Beef Stew"); no catalogue name begins with a digit.
  `split_alternatives` learned `" or "` alongside `/`, so "Caitiff or Aegis"
  becomes a primary plus a recorded alternative instead of an unresolvable cell.

One entry is INFERRED, not ruled, and is flagged for confirmation: a bare
`omelette` is ambiguous in the catalogue (Pork / Avalonian Pork, both T7), and is
listed as the plain line because callers name the Avalonian one explicitly
("ava pork omelette"). It sits in the alias table where it can be overruled,
rather than in a matcher tiebreak where it could not be seen.

**Result: all 13 comps now carry gear** (was 3). Corpus-wide, 0 of 1117 recorded
pieces are unresolved and **1086 = 97.2% reach a CURATED record** — the number
that matters, since only curated pieces carry capabilities. Prior recorded figure
was 387/485.

**Resolution is not supply — the two were being conflated.** 31 pieces resolve to
real game items that are not in the capability sheets and therefore contribute
ZERO supply: 20× `T5_POTION_REVIVE`, 6× `T8_MEAL_STEW_FISH`, 4×
`T7_MEAL_OMELETTE_FISH`, 1× `HEAD_GATHERER_HIDE`. `dusthole crab omelette`
resolves correctly to `T7_MEAL_OMELETTE_FISH` and still supplies nothing. These
are curation gaps, not resolver gaps, and they are the honest remainder.

**Two of my own earlier claims were wrong and are retracted here.** (1) I reported
that "only 4 comps have usable gear" was an extraction error on my side and that
"11 of 13 comps were already 100% resolvable" — that was wrong in the other
direction: those 11 comps resolved *no* gear, because the resolver could not read
item IDs. (2) I read a ripgrep rendering of `split_alternatives` as containing an
escape-sequence bug (`"n\a"` for `"n/a"`); the file was correct and ripgrep had
mangled the display. Verified against the source before changing anything.

Full battery green after the change, no re-pins: golden, forge, builds,
provenance, interactions, roles, patch-history, cohort-families, validation-modes,
js-parity, evidence-lint, codec, display-math, tier2 (78% weapon_only PASS,
unchanged — tier2 reads gear through its own reader and was already ID-aware,
which is exactly why it disagreed with the builds index and exposed this).

This unblocks Step 1 (the unit re-fit) on data completeness: the person-unit
measurement now has 14 sources and ~1086 curated pieces behind it instead of 3
sources and 629.

## Optional capabilities + the peel ruling (2026-08-28)

**THREE OWNER RULINGS, verbatim:** *"the anti zone is only on one weapon, the
crystal healing staff and it's brought [by] some zvz groups but usually when
party is like 30+ people. so it's fine to keep those targets just maybe make
some optional."* / *"as for execute keep that too but optional."* / *"peel is
about how you are fighting."*

**Verified before implementing.** `anti_zone` is supplied by exactly ONE item in
the whole catalogue -- Exalted Staff, `2H_HOLYSTAFF_CRYSTAL`, the crystal holy
staff, citing HOLY_DISPEL. `execute` is supplied by five single-target melee
weapons (Bloodletter, Prowling Staff, Kingmaker, Infernal Scythe, Broadsword).
The owner's description matched the data exactly.

**SHIPPED: `optional: true` on a template requirement row** (both ports, all six
templates that carry either row). Bringing the capability earns its coverage
exactly as before; not bringing it is not a hole.

This is a **DENOMINATOR-ONLY rule, and provably so**: every fitness term for a
capability at zero supply is already zero -- coverage is `min(1, 0/target)^gamma`,
`_headroom_bonus` returns 0 unless `have > target`, `_overstack` needs
`have > soft_cap`. An optional capability can therefore only leave
`max_fitness()`, never `fitness()`. The one term that IS charged at zero supply
is `_floor_penalty`, so optional + hard floor is contradictory by construction;
both ports raise on that combination rather than score inconsistently (neither
capability has a floor in any template -- floors exist only on heal_sustain and
tankiness). `max_fitness(party, combos, gears)` gained the party-aware form;
called with no party it returns the every-capability supremum, so legacy callers
are bit-identical. The dashboard passes the same loadout and gear the numerator
uses, and the radar drops an absent optional capability from its axis instead of
drawing it as a gap.

**Consequence: no score, ranking, pick value, or forge decision moves.** Full
battery green with ZERO re-pins (57/57 golden, 38/38 forge, 60/60 parity + embed,
builds/provenance/interactions/roles/validation-modes/patch/cohort/lint/codec/
display-math, tier2 78% weapon_only PASS). Parity gained a `max_fitness_party`
case covering the new path in both ports. Displayed fitness moves +0.2 to +3.3
points across the ten measured comps; the roads comps move most because roads
carried `execute` at weight 4, the heaviest row nobody fields.

**A FINDING OF MINE WAS WRONG AND IS CORRECTED HERE.** I reported that the corpus
showed peel to be content-shaped -- "the two roads comps field 5x what everyone
else does." That was a ratio misread as a measurement. Per person, peel is
**flat at 3.4-5.1 across every style, content and size**; the two roads comps sit
at 4.07 and 4.36, mid-pack. What actually differs is the TARGET: roads asks 0.37
peel per person where blackzone_roam asks 2.01, a 5.4x spread. The templates
disagree about peel far more than real comps do -- same shape in silence
(0.13-1.01 per person) and zone_control (0.19-0.45). Corrected in
`docs/superpowers/findings/2026-08-28-fielded-supply-per-person.md`.

**Standing hazard this exposes, for the re-fit:** every supply/target RATIO
carries two meanings -- "comps bring a lot" or "this template asks little" --
and only raw per-person supply separates them. The re-fit must be done on raw
per-person numbers, never on ratios.

The peel ruling itself stands on game knowledge, not the corpus: the data shows
no content effect and no style effect, so there is no fitted number to hang a
per-style peel modifier on yet. Recorded as an owner ruling to convert into
per-style target modifiers during the re-fit; NO number invented in the interim
(the "never invent a number to fill a hole" rule).

## Peel is CC, not protection (owner ruling 2026-08-28)

**The challenge.** Shown that Knight Boots and Cleric Cowl carried peel scores,
the owner pushed back: *"knight boots and cleric cowl are peel? I thought cleric
cowl is defensive stats not exactly peel. I thought things peel would be like
something that directly affects enemies in some way."*

**Checked before answering, and the challenge was half right.** Cleric Cowl's
ability is Force Field -- *"Send out a shockwave, knocking back all enemies
within a 6 radius around you by 9 (ignoring Crowd Control Resistance)"* -- a
point-blank enemy knockback, so its peel is correct and the owner's guess about
it was wrong. Knight Boots' ability is Shield Charge -- *"Charge towards the
target... applies a shield on you... if the target is an ally, the shield is
also applied to the target"* -- which never touches an enemy. That one was a
genuine miss, and it opened a whole class.

**The design doc already agreed with the owner** (albion-comp-engine-design.md
§2.2): `clump_create` and `peel` "sit in Control because they are the two
directional uses of CC (offensive stacking vs. defensive protection)". Peel was
DEFINED as crowd control. The effect layer had drifted from that definition.

**RULING (owner, from three offered options): peel = enemy CC, plus cancelling
enemy CC on a teammate. Plain damage protection is NOT peel** -- it is
buff_allies/tankiness. Immunities, CC-resistance and diminishing-returns grants
KEEP peel (they defeat the enemy's CC, the defensive half of the same axis);
resistance buffs, absorb shields, damage redirection and invincibility LOSE it.

**Implemented.** `effect_map.yaml`: `physicalarmor+`, `magicresistance+`,
`bonusdefensevsplayers+` and `invincibility` on an ALLY now map to
`[buff_allies, tankiness]` instead of peel -- which also removed a live internal
contradiction, since `hitpointsmaxbonus+` on an ally was ALREADY
`[buff_allies, tankiness]`. `effect_overrides.yaml`: four hand-written peel
overrides removed, each of which encoded the overruled assumption in its own
justification string -- FORCESHIELD ("ally-resist zone... functions as peel
(ally-armor rule)"), EMERGENCY_SHIELD ("group absorb shield"), CHARGE_SHIELD
("an absorb shield delivered onto a focused ally"), SOUL_LINK ("halving the
focus damage on a dived ally"). Every enemy-facing override was KEPT
(PBAOE_KNOCKBACK, WINDWALL, CASTBUBBLE, ENFEEBLEAURA).

**The lint then found every affected claim by itself** -- the fail-closed gate
working exactly as designed. Five claims went ungrounded and were removed from
the sheets, none replaced by an invented number:

- `ARMOR_PLATE_KEEPER` Judicator Armor, peel 4 -> removed. **This was the
  highest peel score on any gear in the game**, resting entirely on Force
  Shield granting allies +25% resistances.
- `HEAD_PLATE_SET3` Guardian Helmet, peel 2 -> removed (Emergency Shield).
- `SHOES_PLATE_SET2` Knight Boots, peel 2 -> removed (Shield Charge) -- the
  item the owner named.
- `2H_NATURESTAFF` Nature Staff, peel 2 -> removed (ally resistances).
- `MAIN_NATURESTAFF_AVALON` Ironroot Staff, peel 4 -> removed (Soul Link).

**CONSEQUENCE FLAGGED FOR THE OWNER:** Ironroot Staff loses peel entirely. Its
sheet comment literally called it "the soul-link peeler" and peel 4 was its
defining score; it now carries buff_allies + heal_sustain and no peel. Soul Link
redirects half the focus damage off an ally without doing anything to the enemy,
so the ruling is unambiguous, but if Ironroot should still read as a protector
the honest fix is a buff_allies/tankiness magnitude, NOT a restored peel row.
Nothing was invented to preserve the old identity.

**Measured effect.** Peel per person across the ten dressed comps falls from
3.43-5.11 to **2.14-3.86** -- roughly a third of what the model counted as peel
was damage protection. The blackzone comps now sit much closer to their own
2.01-per-person target (push_monkey lands at 2.14 against 2.01). The
measurement got more honest, not just smaller.

Full battery green, **zero re-pins** (golden/forge/parity/validation-modes/
roles/interactions/builds/provenance, evidence lint clean). The golden cases
turned out not to depend on any of the five claims.

**Still open, deliberately not decided:** `SHAPE_W_TETHERBEAM` keeps its peel
override ("pulling an endangered ally out of danger"). Ally-repositioning is
neither enemy CC nor CC-cancelling, but it is not damage protection either, so
it falls outside what was ruled. Flagged rather than silently resolved.

### Peel ruling, second pass — the flagged loose ends closed (2026-08-28)

Owner: *"ok fix it all up."* Both items left hanging by the first pass are
resolved, and one of them turned out to be a MIS-CITATION rather than a bad
claim — the capability was real, the evidence pointed at the wrong spell.

**1. Tether Shift — peel removed, consistent with the ruling.** Held back on
the first pass because ally-repositioning is neither enemy CC nor damage
protection. Reading the whole spell settles it: *"Applies a shield that absorbs
300 damage... if the ally is a guild, alliance or party member, pull them to
your position. Attaching to an enemy: dash towards the attached enemy."* It
shields the ally, repositions the ally, and its enemy half only moves YOU.
Nothing touches an enemy or cancels enemy CC, so it falls with the absorb-shield
class. Re-homed as `buff_allies` (the 300-absorb shield).

**2. The shapeshifter pool's peel was REAL but mis-cited — fixed, not deleted.**
Removing the Tether Shift override ungrounded `peel 2` across the whole
shapeshifter line (9 sheets, one shared pool row). The row's own comment named
the true source: *"W: tether-pull a party ally OUT; **Polymorph a diver**"*.
Polymorph *"transform[s] the first unmounted, not transformed player hit into a
helpless animal for 2.5"* — hard CC on an enemy, exactly peel under the ruling.
The parser had captured only the mob-case max-health debuff, so the
transformation is invisible to the structured vocabulary (which knows the
concept only in negative form: `immunity:transformationcc`, `dr:DRTransformationCC`).
Added `SHAPE_W_POLYMORPH.peel` to `effect_overrides.yaml` as a documented parser
misfire and re-cited the pool row to it at the SAME score. **A true capability
was nearly deleted because its citation was wrong; the fix was to correct the
citation.**

**3. Ironroot Staff's identity resolved on the honest axis.** peel 4 -> the
`buff_allies 4` it now carries, header comment corrected from "the soul-link
peeler" to "the soul-link protector". **The magnitude is ANCHORED, not
invented**: Brier of Life (2H_NATURESTAFF, same file) scores `buff_allies 4` for
+13% resistances on one ally; Soul Link halves incoming damage on one ally —
strictly stronger protection on the same single target — so 4 is a floor under
this sheet's own scale, not a number chosen to match the row it replaced.

**Swept for the same class of hole:** no peel row anywhere cites the
`GEAR_STATS`/`WEAPON_STATS` sentinel, which the lint skips by design — so all 83
surviving peel rows are map-verified, none unverifiable.

Peel per person is unchanged from the first pass (2.14-3.86 across the ten
dressed comps) — the shapeshifter re-citation restored exactly what the tether
removal took. Full battery green, ZERO re-pins: golden, forge, parity+embed,
builds, provenance, interactions, roles, validation-modes, patch-history,
cohort-families, codec, display-math, evidence lint, tier2 (78% weapon_only
PASS).

**Deliberately still uncurated, and not "fixed" by invention:** the 31 recorded
pieces that resolve to real items with no capability sheet. The resurrection
potion (20 uses, every blap member) has no home in the vocabulary at all — it
revives a dead ally, which is not heal, buff, or CC — so giving it a score would
mean inventing a capability. The fish meals and the gatherer hood are the same
story at smaller scale. Recorded as a curation gap, per the "say we do not know"
rule.

### Tier-agnostic gear lookup (owner ruling 2026-08-28)

**A correction first.** I reported the 31 uncurated pieces as items with "no
home in the capability vocabulary", singling out `T5_POTION_REVIVE` (20 uses,
every blap member) as a resurrection potion that revives a dead ally and
therefore cannot be scored. **That was wrong on both counts.** I read the item
ID instead of the item. The game data names `T5_POTION_REVIVE` the **Gigantify
Potion** — Albion reuses the legacy `REVIVE` id for it — and it is FULLY
CURATED at `tankiness 2`, under `T7_POTION_REVIVE` (Major Gigantify). The comps
run the plain tier, the sheets curated the Major tier, and an exact-key lookup
scored 20 real potions as zero. A bug, not a vocabulary gap.

**Root cause, and it is the day's recurring shape.** Consumables are curated at
ONE representative tier (one row per potion type: `T7_POTION_REVIVE`,
`T8_POTION_BERSERK`, `T6_POTION_ENERGY`...) while comps record whatever tier
they actually ran. `builds_lib.match_gear` deliberately prefers the PLAIN tier
when a name matches several ("Gig" -> the untiered Gigantify), which is correct
for recording what was worn — but the ENGINE then looked the key up exactly and
found nothing.

**RULING (owner, from three options): ignore tier everywhere.** Implemented as
`gear_key()` in both ports: exact key wins; otherwise fall back to the
tier-and-enchant-stripped form (`_key_form` / `keyForm`, mirroring
`builds_lib.key_form` added earlier the same day). The alias index is built
only for UNAMBIGUOUS forms — if two curated items share one, the form is
dropped and the lookup fails rather than guessing. Applied at every gear entry
point: `gear_extras`, `build_extra`'s stat channels and doctrine passives, and
the self-cost loop. Justification: tier is not part of an item's identity in
this model — a 1..7 sheet score is far coarser than the tier ladder, and the
sheets already curate one tier as the representative of a whole line.

Verified: `T3/T5/T7_POTION_REVIVE` all resolve to the curated Gigantify
(`tankiness 1.0` supply each); `T5_POTION_STONESKIN` -> Resistance Potion;
`T5_POTION_CLEANSE2` -> Cleansing Potion; exact keys such as
`ARMOR_CLOTH_AVALON` unchanged. blap's 20 members now carry the potion the
model already knew about — party tankiness 75.56. **Full battery green with
ZERO re-pins** (golden, forge, 60/60 parity + embed, builds, provenance,
interactions, roles, validation-modes, display-math, lint): no golden fixture
used a non-representative tier, so the change is additive to real comps only.

**The four items, named** (the answer to "what are they"): `T5_POTION_REVIVE` x20
= Gigantify Potion (blap) — FIXED by the above; `T8_MEAL_STEW_FISH` x6 =
Deadwater Eel Stew (metabattle); `T7_MEAL_OMELETTE_FISH` x4 = Dusthole Crab
Omelette (blap); `HEAD_GATHERER_HIDE` x1 = Adept's Skinner Cap (metabattle).

**STILL OPEN, deliberately not guessed — the two fish meals.** They have no
sheet at ANY tier, so tier-aliasing cannot reach them. Curating them needs to
know what the foods actually do, and THE PIPELINE DOES NOT CARRY IT: meals
appear in `gear_lines.json` with name and slot only, and the four curated foods
were scored by human judgement citing the `GEAR_STATS` sentinel, which
`evidence_lint` skips by design. So there is nothing in the repo to check a
guess against. Closing this properly needs the real food bonuses (wiki via the
Playwright MCP, or a dumps re-parse that captures meal nutrition) — 10 pieces,
~1 supply unit each. The Skinner Cap is gathering gear recorded in a combat
build and is correctly out of scope.

## Per-style target modifiers — the mechanism (2026-08-28)

The owner's standing case: *"clap comp would require more peel and disengage
than brawl comp."* Until now `styles.yaml` could not express that. Its
`multipliers` scale a capability's WEIGHT — what a style VALUES — while every
style in a content shared identical TARGETS, by explicit design ("targets, soft
caps and hard floors are untouched"). So the model could say a clap comp cares
more about disengage, never that it needs more of it before it counts as
covered.

**SHIPPED: `target_mults` on a style** (both ports, `test_validation_modes.py`
V6a-V6f). Semantics, pinned by the contracts:

- target and soft cap scale TOGETHER, so the headroom band keeps its shape
  (kite disengage 6.3 -> 12.6 and 9.2 -> 18.4 at a 2.0 multiplier);
- unlisted capabilities are untouched;
- **HARD FLOORS NEVER SCALE** — the same rule the weight overlay has always
  followed. A style may change what it emphasises and how much it needs, never
  what keeps the party alive (V6e pins tankiness/heal_sustain floors identical
  under a styled engine);
- balanced is the identity by definition and must stay empty.

**EVERY STYLE SHIPS EMPTY. The mechanism is the identity and changes nothing**
— full battery green with zero re-pins, and V6a is a standing guard that fails
if a value ever appears without a deliberate ruling. Both ports verified to
agree on an injected multiplier (identical targets, soft caps and floors);
js-parity will cover the path automatically the moment a real value ships,
since both read the same dataset key.

**WHY NO NUMBERS: the corpus cannot fit them, and this is the honest reason to
stop.** Of the eight published blackzone_roam comps, brawl has 3 and kite has
2, while **clap, brawl_clap and clap_kite have exactly ONE each**. Any
per-style number fitted today would be one comp's idiosyncrasy wearing a
style's name. Per-person means by style (blackzone_roam only, the content
confound removed — both roads comps are clap_kite):

```text
                     brawl  brawl_clap   clap  clap_kite   kite
(n comps)                3           1      1          1      2
disengage             0.77        1.25   1.50       0.65   1.64
peel                  2.92        3.08   2.29       3.42   3.60
tankiness             3.06        2.12   3.05       1.93   2.17
engage                1.54        0.85   0.93       1.55   0.75
mobility              2.34        1.50   1.00       1.77   1.61
stun                  0.89        0.48   1.62       1.36   1.77
```

**On the owner's specific claim, the corpus splits it.** DISENGAGE agrees:
brawl is lowest at 0.77 and clap (1.50) and kite (1.64) roughly double it,
and kite is the one non-brawl style with replication (n=2), so this is the
strongest candidate for the first ruled value. PEEL does not: clap fields the
LEAST peel of any style (2.29 vs brawl's 2.92). That contradiction is on n=1
for clap and should not be treated as a refutation — but it is exactly why the
number has to be ruled rather than fitted.

Recorded for the owner to rule; nothing invented in the interim, per the
"never invent a number to fill a hole" rule.

### Per-style targets: looked up, derived from prior rulings, two thirds rejected (2026-08-28)

Owner: *"you look it up."* Three routes were tried; the third worked.

**1. External sources — nothing usable.** Web search returns weapon tier lists,
not composition requirements. The one "ZvZ Clap and kite basic composition"
page (albiononlinegrind) is a user's 18-build scrapbook mixing Crystal Arena
and fame-farm builds, not a comp. MetaBattle's Albion wiki has no composition
pages at all (`list=search` for "ZvZ composition" -> totalhits 0) — it is a
build library, which is why the adapter only ever pulled builds. The
clap/kite/brawl vocabulary lives in voice comms and Discord, not in any
quantified public form.

**2. Killboard rosters — blocked by CIRCULARITY, and this is worth recording.**
The plan was to label the 139 near-complete observed rosters with the engine's
own `comp_identity` and measure supply per style, for a real sample instead of
n=1. Checked the classifier first: `comp_identity` computes
`evade += mobility + disengage` and uses it to decide the kite half
(engine.py, IDENTITY_HYBRID_EVADE). So labelling rosters that way and then
"discovering" that kite comps field more disengage would be reproducing the
definition. Abandoned. (`roster_mixes.json` is also stored as seat counts, not
weapons, so it cannot yield capability supply without re-deriving from the
118-battle cache.)

**3. THE OWNER'S OWN PRIOR RULINGS — this is where the numbers were.** The
model already contained style-varying requirements, in seat units, ruled by the
owner in the 2026-08-23/26 forge rounds: `constraint_overrides` in styles.yaml
(healer 3-4 brawl / 2-3 clap / 2 kite at 20; frontline bands; `ranged_aoe_core`
min 7 clap / 5 kite at 20) against composition.yaml's style-blind base bands.
**And the targets ignored all of it** — `heal_sustain` asked 7.50 of every
style alike. The forge was told a kite 20-man runs 2 healers while the scorer
still demanded brawl-level healing. That inconsistency IS the per-seat issue,
and it was already inside the repo.

Multipliers were derived as (ruled seat count) / (base band count) at each
ruled size, then TESTED against the published comps: does coverage
(supply/target) cluster tighter across styles, or scatter?

```text
capability      spread before -> after      verdict
burst_aoe            2.38 -> 1.58           KEPT
heal_sustain         1.93 -> 2.56           REJECTED
heal_burst           2.04 -> 3.34           REJECTED
tankiness            4.02 -> 4.93           REJECTED
```

**Two thirds of my own derivation failed its own test, and that is the finding.**
The seat-count mapping only holds where the ruled seat count IS the capability.
`ranged_aoe_core` counts members satisfying a burst-AoE predicate, so it maps
almost one-to-one onto burst_aoe supply. Healer count does NOT predict healing
supply — real kite comps already over-cover healing relative to brawl (1.74 and
1.13 vs blap's 1.91) because gear, off-heals and support weapons carry much of
it, so lowering their target made them over-cover harder. Frontline count does
not predict tankiness at all: that is the known unit defect, where worn armor
gives every member tankiness regardless of seat, and nothing about tankiness
can be fitted before the unit re-fit.

**SHIPPED — the one derivation that survived**, cited to the ruling it comes
from: `clap` and `clap_kite` `burst_aoe: 1.71` (ruled ranged_aoe_core 7-at-20
and 5-at-15-19 vs base 4 and 3 — ratios 1.75, 1.67), `kite` `burst_aoe: 1.29`
(ruled 5 and 4 vs base 4 and 3 — 1.25, 1.33). brawl and balanced stay the
reference at 1.0. Rationale: a clap comp is REQUIRED to field ~1.7x the base
burst-AoE core, so scoring it against the base target handed it free
over-coverage for doing the one thing its style demands.

**INDEPENDENT CORROBORATION — the blind test improved.** tier2 leave-one-out
against published comps, which had no part in the derivation:
weapon_only role-level **74% -> 78%** (17/23 -> 18/23), weapon-level 15% -> 18%;
actual_gear role-level **39% -> 43%** (9/23 -> 10/23). Full battery green, zero
re-pins. `test_validation_modes` V6a now PINS the shipped set, so an
undocumented multiplier fails the gate (it fired correctly the moment these
values landed, which is what it was written for).

**Still unruled and deliberately empty:** brawl and balanced (the reference),
brawl_clap (the owner has never ruled it — it carries no constraint override
either), and every capability other than burst_aoe. The owner's original case
— "clap needs more peel and disengage than brawl" — remains unfitted: there is
no ruled seat count that maps to peel or disengage, the corpus has n=1 for
clap, and the killboard route is circular for exactly those two capabilities.
That one still needs an owner ruling; nothing was invented in its place.

### Per-style targets, round 2: a second independent sample (2026-08-28)

Owner: *"I will say you go with your recommendation based on what you find
online."*

**Found the source the corpus already came from.** Eight of the thirteen comps
cite albioncompo.com. That site has **130 public comps** behind a clean JSON
API (`/api/compositions/<CODE>`, found by watching the page's own network
calls) carrying full item IDs per slot — weapon, helm, armor, boot, cape,
offhand, potion, food. Exactly the shape the corpus wants, and item IDs are
now readable since the resolver fix earlier today. Triage: 96 are ZvZ, and
**27 are usable** (ZvZ, n>=10, every weapon in the catalogue, every member
geared).

**A NON-CIRCULAR STYLE LABEL, which was the blocker.** Labelling rosters with
`comp_identity` is circular (it defines the kite half AS mobility+disengage).
But many authors NAME the style themselves: "Brawl Hit 20", "BRAWL BY LATTEX",
"Hard ZvZ Brawl 20ppl", "ss kite", "kite deff", "HDCP BOMB", "RANGED BOMB",
"SIEGEBOW BOMB", "BUS BOMB", "Brawl Clap", "BUILDS FOR BRAWL BOMB". That label
comes from the author, not from the engine, so measuring capabilities against
it is not circular. ("Bomb" reads as clap — styles.yaml's own clap blurb is
"stack them and delete them - one engage, one bomb".) 13 comps carry a
declared style: clap 5, brawl 3, kite 2, brawl_clap 2, clap_kite 1. **Clap went
from n=1 to n=5.**

**INDEPENDENT CONFIRMATION OF THE SHIPPED burst_aoe VALUES.** Those were
derived purely from the owner's ruled `ranged_aoe_core` seat counts. The
author-labelled sample shares no input with that derivation:

```text
style        shipped   observed/brawl    gap
clap            1.71             1.73   +0.02
clap_kite       1.71             1.62   -0.09
kite            1.29             1.51   +0.22
brawl_clap         -             1.22   (unruled, stays 1.0)
```

Two derivations with nothing in common agreeing to 0.02 on clap is the
strongest validation any number in this model has.

**THE OWNER'S ORIGINAL CASE, ANSWERED — half right.** *"Clap comp would
require more peel and disengage than brawl comp."* Testing each claim across
BOTH samples (published corpus, author-labelled), as a ratio to that sample's
own brawl:

```text
peel        published  declared   agree?
brawl_clap       1.05      1.01   yes
clap             0.78      1.07   NO - flips
clap_kite        1.17      1.29   yes
kite             1.23      1.27   yes

disengage   published  declared   agree?
brawl_clap       1.62      0.94   NO - flips
clap             1.95      0.64   NO - flips
clap_kite        0.84      1.10   NO - flips
kite             2.13      1.17   yes
```

**CLAP is the half that fails.** Both of its claims flip sign between samples —
peel 0.78x then 1.07x, disengage 1.95x then 0.64x. No clap row was written; two
independent samples disagreeing is not evidence, it is noise, and inventing a
number there is exactly what the standing rule forbids.

**KITE is the half that holds**, and it replicated on both:
- `peel 1.25` — 1.23x brawl published, 1.27x declared. Kite genuinely peels
  more. `clap_kite` gets the same 1.25 (1.17x, 1.29x).
- `disengage 1.20` — direction replicated (kite above brawl in both) but the
  magnitude is unstable (2.13x, 1.17x), so this takes the CONSERVATIVE end
  rather than the mean. kite only; clap_kite flips and gets no row.

**tier2 improved again, twice in a row.** weapon_only role-level 74% (before
any target_mults) -> 78% (burst_aoe) -> **83%** (peel/disengage), weapon-level
15% -> 18% -> **24%**. The blind test had no part in any derivation. Full
battery green, zero re-pins.

Test note: V6b/V6c inject a multiplier and compare against a baseline, and
used to do it on `kite`. Once kite gained shipped values its baseline stopped
being 1.0 and those cases FAILED — correctly. They now inject into `brawl`,
which ships nothing and is a true identity reference.

**Still unruled:** `brawl_clap` (no ruled seat override, and only n=2
declared), and every clap row beyond burst_aoe. The 27 usable comps are NOT
yet ingested into `data/published_comps` — that is the durable next step, and
it would take clap from n=5 measured to n=5 CITED, with provenance.

### Corpus ingestion: 13 -> 36 published comps (2026-08-29)

Owner: *"do what needs to be done."* The 27 usable albioncompo comps found the
previous day were measured but not cited; they are now ingested as evidence.

**23 new records** in `data/published_comps/`, same format as the existing
albioncompo entries: slot rows VERBATIM (game item ids as the site serves
them), spells `null` because the source has no spell fields, full provenance
(share url, author family from the account id, retrieval date, view count,
`is_public` licence note). Four excluded on quality: three where a weapon is
not in the catalogue, three where not every member is fully geared, and one
the AUTHOR marked unfinished ("Kite clap 7 man+ (Not finished)") — a comp its
own author says is unfinished is not evidence of a real one.

**Style labels are AUTHOR-DECLARED, taken from each comp's own name**
("Brawl Hit 20", "kite deff", "HDCP BOMB", "Brawl Clap"), never from the
engine's classifier — that would be circular. Comps whose names declare
nothing carry `style: null` rather than a guess.

**Corpus after: 36 comps (was 13).** By style: brawl 6 (was 3), clap 6
(was 1), clap_kite 3, brawl_clap 3 (was 1), kite 3 (was 2), unlabelled 15.
**Every thin style now has n>=3, and clap went from 1 to 6** — the sample-size
problem that blocked every per-style question is gone. Build records
237 -> 625; canonical defaults 55 -> 112; no new quarantines.

**THREE GATES FIRED, ALL CORRECTLY — none was a false alarm:**

1. **`build_dataset` refused the build (exit 2, provenance FAIL).** A
   MASTERSHEET/roles kit override adds `OFF_TORCH_CRYSTAL` to
   `brawl_healer/offhand`; with the new comps that item is now in the seat's
   OBSERVED doctrine tier on its own, so the hand-ruling became redundant and
   the gate refused to ship a ruling that no longer does anything. **The
   owner's 2026-08-26 ruling was VINDICATED, not reversed** — the evidence
   caught up with it. Override removed, reasoning kept in a comment, resulting
   tier unchanged.
2. **`test_roles` R18** pinned Polehammer's armor doctrine at `[5, 5]`; it is
   `[9, 12]` now. The MECHANISM it guards is intact — the weapon's own
   observed kit still outranks the seat aggregate and still resolves to Knight
   by a clear majority. Count re-pinned with a note that `doctrine_n` tracks
   corpus size, so the next such change reads as expected rather than as a
   regression.
3. **`test_builds` H16** asserted excluded weapons have "no build records AT
   ALL". A new comp ("AvA Raid", 10 players) genuinely fields
   `MAIN_FROSTSTAFF_AVALON`, which is on the >=10 exclusion list. **That is
   not a family leak — it is a real record, and it contradicts the exclusion's
   own stated reason** ("no caller sheet, published build or observation
   fields them at party size >= 10"). The assertion was stricter than the
   design it guards: composition.yaml's documented exit says an excluded
   weapon is lifted when it gains an APPROVED CANONICAL build, via the
   evidence gate and an owner ruling. Split into two checks — approved/
   canonical records still fail hard (that is silent re-admission), while
   known candidate evidence is recorded explicitly so a NEW one is still
   visible. The exclusion STANDS (the record is candidate; `exclusion_gate` is
   correctly empty). **OWNER RULING NEEDED: the premise for excluding
   `MAIN_FROSTSTAFF_AVALON` at 10+ is now weaker than when it was written.**

**tier2 improved for the third time today**, and it had no part in any of this:
weapon_only role-level **74% -> 78% -> 83% -> 87%** across the day;
weapon-level 15% -> 24%; **actual_gear role-level 39% -> 57%** (the biggest
single jump, from the gear evidence). Full battery green.

Not yet done: the per-style multipliers were fitted when clap had n=1. They
should be re-derived now that clap has n=6 — the measurement, not the
mechanism, is what is stale.

### Re-derivation on the 36-comp corpus — NOTHING CHANGED, deliberately (2026-08-29)

The per-style multipliers were fitted when clap had n=1. With the corpus at 36
comps (clap n=4-6 labelled at n>=10) they were re-derived from the CORPUS
itself rather than a scratch dump. Every shipped value held, and every one
turned out to be the CONSERVATIVE end:

```text
style       cap          shipped   re-derived    gap    n
clap        burst_aoe       1.71         1.93   +0.22   4
kite        burst_aoe       1.29         1.75   +0.46   3
kite        peel            1.25         1.22   -0.03   3
kite        disengage       1.20         1.36   +0.16   3
clap_kite   burst_aoe       1.71         1.92   +0.21   1
clap_kite   peel            1.25         1.23   -0.02   1
```

`peel` re-measures to within 0.03 of what shipped, on an independent basis
(the ruled/observed blend vs the full corpus). The rest sit below the newly
measured effect, so the model currently UNDER-states every style difference it
models — never over-states one.

**The larger sample also revived a derivation I had rejected.** On the small
sample the healer-count -> healing-target mapping widened coverage spread and
was dropped. At n=3-5 it now matches observation closely: clap heal_sustain
observed 0.73 against the 0.82 the ruled healer counts predicted, kite 0.64
against 0.61. The earlier rejection was a small-sample artifact, not a fact
about the model. New signals appeared too — `slow` runs clap 1.73 / clap_kite
2.33 / kite 1.51 against brawl, consistently.

**FOUR CANDIDATE SETS WERE TESTED AND NONE SHIPPED.** tier2 leave-one-out is
the arbiter (it holds a published comp out and asks the engine to rebuild it,
so it is not the thing being fitted):

```text
A  shipped (baseline)                       weapon_only 15/62 role 20/23 | actual_gear 13/23
B  kite burst_aoe 1.29 -> 1.50              weapon_only 15/62 role 20/23 | actual_gear 13/23
C  + healing (the revived derivation)       weapon_only 15/62 role 20/23 | actual_gear 13/23
D  + slow (clap 1.73 / kite 1.51)           weapon_only 15/62 role 20/23 | actual_gear 13/23
```

Identical, to the case. Golden clean in all four. **The gate cannot tell these
apart, so there is no evidential basis to prefer any of them over what ships**
— and adding multipliers the gate cannot validate is fitting numbers to taste.
Nothing was changed.

**That flatness is itself the finding: tier2 has saturated as a discriminator
for per-style targets at this corpus size.** It moved four times today
(74 -> 78 -> 83 -> 87% role-level) and now does not respond to further
per-style tuning at all. Sharpening these numbers needs a different
instrument, not more of this one — more held-out labelled comps, or the expert
blind rounds the harness was built for. Recorded so the next attempt does not
re-run the same sweep expecting a signal.

## THE UNIT RE-FIT — shipped (2026-08-29)

Owner: *"go ahead."* The long-standing defect (HANDOFF.md, "KNOWN UNIT DEFECT,
ruling pending"): every target and soft cap was fitted counting WEAPONS while
the engine measures whole dressed PEOPLE, so the two sides of every comparison
were in different units. tankiness read 4.2-6.6x target in every published comp.

**SHIPPED: 152 rows across all six templates, moved together** (the "one unit,
everywhere" rule — a partial move would leave the templates in mixed
currencies). `weight`, `scales` and `optional` untouched. **Hard floors
untouched**: Option C (owner 2026-08-27) makes floors read the WEAPON+LOADOUT
supply only, so they are already in weapon units by design and must stay there.

### Result

```text
                       before    after
tankiness coverage    4.2-6.6  1.19-2.12     <- the defect, fixed
median coverage           n/a       1.82     (still conservative)
tier2 weapon_only         87%        70%     (naked; the retired unit)
tier2 doctrine_inferred   26%        87%
tier2 actual_gear         57%        87%     (real recorded kits)
```

Full battery green: golden, forge, parity, validation-modes, roles,
interactions, builds, provenance, patch, cohort, display-math, codec, lint.

### Three failed attempts, and why each failed — the method was the hard part

1. **Re-derive every row from scratch** (0.9x least / 1.15x most, over all 28
   dressed comps). REJECTED: the convention says "the least any GOOD comp
   fields", and across a mixed-quality corpus the WEAKEST comp sets the target
   — heal_burst collapsed to 0.11x because one comp fields almost none.
2. **Scale by the median per-comp dressed/naked ratio.** REJECTED: the ratio
   varies 1x-27x across comps, so the median overshoots for high-variance
   capabilities. It pushed blap — a melee ball that deliberately carries little
   escape — from 1.11 disengage coverage down to 0.37.
3. **Scale by min(dressed)/min(naked) and max/max.** REJECTED as the whole
   answer: min-based ratios are outlier-driven where the minimum naked supply
   is near zero (engage x3.50, mobility x4.55 off single comps), and 3 of 4
   reference comps ended up BELOW the tankiness target.

### What shipped, and the two principles that fixed it

Fit on the **OWNER-VETTED comps only** (the 11 the owner labelled by hand and
ruled on, minus the two Deadlyhooker parties they excluded from fitting) —
9 fully-dressed comp-parties — measured DRESSED, style-normalised, with the
owner's own formula. Then:

- **A UNIT CONVERSION CAN ONLY ADD.** Gear never removes supply, so a factor
  below 1.0 is not a unit correction — it is a separate claim that the old
  target was miscalibrated. Twelve came out below 1 and were CLAMPED to 1.0
  (left exactly as they were). Without this clamp, burst_st's target fell 47%
  and forge F3 broke: the cross-member `resist_shred x burst_st` synergy
  saturated on a single member, so a real interaction silently priced at zero.
  The clamp is what makes this a unit fix rather than a retune wearing its
  clothes.
- **Only 13 of 29 capabilities move at all**, and they are exactly the
  gear-fed ones: buff_allies x4.63, tankiness x3.88, cleanse x3.00,
  sustained_dps x2.59, anti_zone x2.25, anti_dive x2.14, stun x2.11,
  damage_debuff x1.50, resist_shred x1.35, knockback_displace x1.23,
  root x1.11, clump_create x1.03, heal_sustain x1.02. **The other 16 keep
  their targets exactly** — peel, disengage, mobility, engage, catch,
  burst_aoe and the rest were already right in person terms. So the original
  calibration was never uniformly in weapon units; only the capabilities worn
  armor supplies were wrong. That is a more precise statement of the defect
  than the one in HANDOFF.md.

### Two golden re-pins, both intended consequences

- **T26 fight chain** graded blap NAKED and expected all-strong. Against
  person-unit targets a naked party correctly reads weak — that is the same
  unit error the re-fit removes. Re-pinned to grade blap DRESSED in its own
  doctrine kits (what the page does): **all five stages strong**. The chain
  lens was itself in the wrong unit; this fixed it.
- **T30d** heal band moved overstacked -> headroom as the soft cap rose. The
  load-bearing judgements this case is actually about are unchanged: neither
  of two healers redundant, a third still redundant, tank clean, fitness
  untouched.

### OPEN — the gate now needs the owner's ruling

`tier2`'s exit gate is still legacy `weapon_only` role-level (naked
incumbents), which the re-fit necessarily degrades 87% -> 70%: it measures in
the unit the model just left. It PASSES, but sits exactly on its 70%
threshold, while both dressed classes jumped to 87%. **Ruling 2 (2026-08-27,
"gate re-basing DEFERRED as directed") is now the blocking question** — the
honest gate is `actual_gear`, which scores real recorded kits and is at its
best-ever 87%. Recommend re-basing; not done unilaterally because the owner
deferred it once already.

Median coverage 1.82 says the targets remain CONSERVATIVE (good comps
over-cover). That is the safe direction and the residual is a calibration
question, no longer a unit question.

### Gate re-based to actual_gear, and it now ENFORCES (owner ruling 2026-08-29)

Ruling 2 (2026-08-27) deferred re-basing the tier2 exit gate off the legacy
naked metric. The unit re-fit forced the question: `weapon_only` scores NAKED
incumbents, so after targets moved to person units it measures in the unit the
model has left — it fell 87% -> 70% for that reason alone, while both dressed
classes rose to 87%. Owner: *"ok do that."*

**Two changes, and the second matters more than the re-basing:**

1. The gate now reads `actual_gear` role-level (70% threshold unchanged).
   That class scores incumbents in the gear their published source actually
   records — what the page does — and it is the only class whose incumbents
   are not mined from the same doctrine the engine itself uses
   (`doctrine_inferred` is doubly weak-form by construction).
2. **THE GATE NOW ACTUALLY ENFORCES.** The v4 path ended in a bare
   `return 0`, so the PASS/FAIL verdict had only ever been *printed* — the
   command could not fail. That is why it exited 0 at 57% during the re-fit
   trials without anyone noticing. It returns 1 on failure now, verified both
   ways: PASS/exit 0 at the shipped 70% threshold, FAIL/exit 1 when the
   threshold is temporarily raised to 95%.

Current standing: **GATE PASS at 87% (20/23)**. `weapon_only` stays printed
beside it, reported not gated, labelled as the pre-re-fit unit. Docstring,
CLAUDE.md and HANDOFF.md updated; HANDOFF's "#1 THE UNIT RE-FIT (blocked)"
entry is closed and the historical statement kept for the record.

Full battery green with the gate live: golden, forge, parity, validation-modes,
roles, interactions, builds, provenance, patch-history, cohort-families,
display-math, codec, evidence-lint, tier2.

## Real party rosters from the killboard (2026-08-29)

Owner asked how to see what was in a killer's party. It turns out the data
exists and this project was not using it.

**The finding that unlocked it: `GroupMembers`.** Every official gameinfo kill
event carries the KILLER'S PARTY at kill time, each member with equipment,
plus `Participants` (who damaged the victim). albionbb strips both fields;
the official API keeps them. That is a real party roster — the exact unit the
engine models — available at killboard scale, against a comp corpus of 36
published compositions.

**A standing note in CLAUDE.md is now WRONG and was corrected:** "the official
gameinfo events endpoint 504s constantly" (verified 2026-08-13). Re-tested
2026-08-29 — events LIST, battles LIST and single-event detail all returned
200 in under a second, first try, and a 25-event probe succeeded 25/25 with
retry. Either it was a transient outage or it has been fixed. albionbb is
still preferred for DISCOVERY because it is the only source with a
`minPlayers` filter.

**THE THREE-STEP PIPELINE** (`pipeline/sample_parties.py`, network step, never
part of a normal build), each step present because the previous one cannot
answer the question:

  1. DISCOVERY  albionbb `/battles?minPlayers=N` — the size filter. Fight size
                comes from the battle LIST (`totalPlayers`); kill events carry
                no size at all.
  2. ROSTER     official `/battles/{id}` — EVERY player in the fight. No
                equipment, but it is the honest DENOMINATOR: coverage becomes
                measured instead of assumed.
  3. PARTIES    official `/events/{id}` per kill — `GroupMembers` with gear.

**FIRST HARVEST: 39 battles -> 193 distinct parties, 116 of size 5+, 184 with
every member's weapon known, median per-battle coverage 0.815.** Size
distribution reaches the top: 7 full 20-mans, 9 nineteens, 9 eighteens.
**109 parties of 5+ carry a complete weapon list** — three times the published
corpus, from fights that actually happened.

**TWO BUGS FOUND IN MY OWN OUTPUT, both caught by numbers that could not be
true.** Recording them because both are properties of the data, not slips:

1. **Coverage came out at 1.061 — above 100%.** `GroupMembers` reports the
   killer's WHOLE party including members who were NOT at that battle (a
   20-man party with 8 people present still lists 20). Dividing by
   `totalPlayers` therefore counted people the denominator never had.
   Coverage now intersects the seen set with the official battle roster, and
   the remainder is reported separately as
   `party_members_not_in_this_battle` rather than silently inflating it.
2. **One squad was counted five times.** Keying dedupe on the exact member-set
   is not enough: a party loses members as they die, so a single 19-man
   emitted 19/18/15/14/13-member arrays and read as five parties — which
   would have multiplied that squad's weapons by its kill count and wrecked
   every size statistic. Parties are now clustered by member OVERLAP (>50% of
   the smaller set) and the LARGEST observation wins. On the validation batch
   this collapsed 14 "parties" to 9 real squads.

**Standing caveats, carried in the artifact's own `semantics` field:**
WINNER-BIASED BY CONSTRUCTION — only parties that got a kill appear, so a
party wiped without killing anyone is invisible. A party is NOT a comp: a
300-player battle is a coalition of parties, and the party is the useful unit.
DISPLAY/EVIDENCE ONLY, never a scoring input — it may inform owner rulings
like every other observed layer, and nothing more.

Also measured while proving the design (302-player battle): albionbb
killer+victim sees 76% of the roster; official battle detail sees 100% but
carries no equipment; the per-event union reached 54% WITH equipment from only
36 of 182 events, adding 42 players the killer+victim route cannot see at all.

Full battery green. `party_cache/` gitignored beside the other caches;
`out/party_rosters.json` committed (83 KB, LF, no BOM).

### The party sample's bias, MEASURED — and the ZvZ meta it shows (2026-08-29)

**OWNER RULING:** *"it's okay if the losing party couldn't get a single kill
it's not worth having their party information."* Accepted, and then checked,
because "winner-biased by construction" turned out to OVERSTATE the problem.

The filter is not "won the fight" — `GroupMembers` is emitted on ANY kill, so
a party that traded a few and then got wiped is captured. Measured across 354
captured parties (5+ members present):

```text
   dominant   (2x+ K/D)                216   61%
   traded     (1-2x)                    68   19%
   wiped-ish  (more deaths than kills)  70   20%
   totals: 3785 kills / 1570 deaths, K/D 2.41
```

**Losing parties are well represented.** What actually drops out is the 10% of
players in no captured party at all: **474 players holding 34 kills against
475 deaths between them — K/D 0.07**, roughly one death each and almost no
kills. That is not a composition being tested; the owner's ruling is right on
the evidence. Coverage is **90% of all players** across the sampled battles.
The artifact's `semantics` field and the module docstring were rewritten from
"WINNER-BIASED" to the measured statement.

**THE ZvZ META, from 38 fully-geared 15-20 man parties (677 members).** This
supersedes the kill-event reading, which could only see players who killed or
died:

```text
 #  weapon              slots  per party  in % of parties  seat
 1  Hallowfall             74      1.95         97%       main_healer
 2  Realmbreaker           35      0.92         68%       sustained_brawler
 3  Permafrost Prism       35      0.92         76%       ranged_aoe
 4  Dawnsong               34      0.89         66%       anti_heal
 5  Spirithunter           26      0.68         63%       pierce
 6  Polehammer             25      0.66         55%       engage_tank
 7  Bedrock Mace           23      0.61         39%       stopper_tank
 8  Blight Staff           22      0.58         50%       main_healer
 9  Spiked Gauntlets       21      0.55         55%       sustained_brawler
10  Lifecurse Staff        21      0.55         47%       purge
```

**Hallowfall is in 37 of 38 ZvZ parties (97%) at ~2 per party** — the
strongest single signal in any evidence layer this project has.

**How much the attribution bias was distorting things:** Longbow ranked 3rd by
kill events, 12th here (29% presence — a few squads stack several, most bring
none). Battle Bracers 4th -> 15th. And **Bedrock Mace, Oathkeepers, Blight
Staff, Fallen Staff and Great Arcane Staff appear in the party top-20 while
being absent from the kill-event top-20 entirely** — support and tank weapons
whose users survive, so kill attribution never saw them. That is the
healers-under-attribute problem quantified.

Note the two columns answer different questions and should not be collapsed:
`slots` counts bodies (Longbow 20 slots but 29% presence — stacked when
taken), `in parties` counts how many teams chose it (Earthrune 19 slots at 45%
presence — one per party, taken more often).

Small/mid parties (5-14) are a different game: Wailing Bow, Frost Staff, Bear
Paws and Claws appear there and never in the ZvZ list — confirming the
fight-size split the bucket data suggested, now with party structure behind it.

### Party harvest scaled 39 -> 212 battles, and what ZvZ support actually is (2026-08-29)

**HOW MUCH ZvZ THERE IS, measured.** A discovery-only crawl of the albionbb
battle list (220 pages, no per-event fetches) found **4,400 battles of 20+
players in 8 days** — 550/day at 20+, **260/day at 30+**, 108/day at 50+,
34/day at 100+. Projected over a month that is ~7,800 fights of 30+. The first
harvest of 39 battles was therefore about **half of one percent of a single
day's** ZvZ. Scaled to 212 battles: **955 distinct parties, 656 of size 5+,
912 with every member's weapon known, median coverage 0.851.** ZvZ parties
(15-20, fully geared) went 38 -> **290**.

**THE FEED ONLY REACHES BACK 8 DAYS** even at 220 pages (oldest 2026-08-22).
A month-long picture cannot be backfilled from this endpoint — it has to be
accumulated going forward. Worth knowing before anyone plans a monthly census.

**THE SEAT STRUCTURE HELD ACROSS A 7.6x SAMPLE INCREASE**, which is the
strongest evidence yet that this layer is measuring something real:

```text
                    38 parties   290 parties
   pierce              2.76         3.16
   main_healer         3.29         3.16
   engage_tank         2.11         1.89
   shield_support      1.34         1.76
   stopper_tank        1.24         1.21
```

**OWNER QUESTION — "what kind of support is important":**

```text
   pierce          3.16/party   50% of the support block   in 97% of parties
      Spirithunter, Battle Bracers, Occult Staff, Damnation Staff
   shield_support  1.76         28%                            84%
      Great Arcane, Rootbound, Enigmatic, Arcane Staff
   anti_heal       0.85         13%                            58%
      Dawnsong, Rotcaller
   purge           0.43          7%                            39%
      Lifecurse Staff
   zone_support    0.12          2%                            12%
```

**Pierce is half of what "support" means in practice**, and only two seats sit
at ~97-100% of parties: main_healer and pierce. Resist-shred is as
non-negotiable as healing — a stronger statement than any template currently
makes.

**ZvZ weapon meta (290 parties, 5,164 members):** Hallowfall 2.12/party in 94%
of parties (held from 97% at n=38 — real), Realmbreaker 0.89/74%, Battle
Bracers 0.73/29%, Permafrost 0.73/60%, Spiked Gauntlets 0.70/70%,
Spirithunter 0.59/57%, Bedrock Mace 0.58/37%, Dawnsong 0.56/45%, Oathkeepers
0.53/50%.

What the bigger sample CHANGED: Battle Bracers is 3rd by bodies but only 29%
presence — a few squads run four or five, most run none, so slots and presence
must not be collapsed. Spiked Gauntlets 9th -> 5th. **Oathkeepers 9th and
off_tank in 51% of parties** — a real seat the 38-party read dismissed.

**Still true and worth repeating:** 212 battles is ~0.4% of a week's 30+
fights. Signals at 90%+ presence will hold; anything separated by a few points
will not. Display/evidence only.

## Observed BUILDS, and the role book tested against them (2026-08-29)

Owner: *"can we use that to get what real equipment is being used and from
there under what roles are played by what weapon."* Yes to both — after
correcting a claim of mine.

**CORRECTION FIRST.** I said the party harvest gave "real parties with full
gear". It did not. Measured per event role:

```text
   Killer        7/8 equipment slots filled, item power ~1300
   Victim        7/8
   Participants  7/8
   GroupMembers  1/8  — MainHand only, AverageItemPower 0
```

`GroupMembers` carries WEAPONS ONLY. The 955 parties were weapon rosters, not
builds. Full kits live on Killer / Victim / Participants, so the sampler now
takes party STRUCTURE from GroupMembers and BUILDS from the combat roles. A
member who never killed, died or dealt damage yields a weapon and nothing
more, and is recorded that way rather than guessed. Cache gained a `schema`
field; schema-1 records (weapons only) re-fetch automatically.

**HARVEST: 270 battles -> 1,283 parties (865 of size 5+) and 9,569 OBSERVED
BUILDS**, 9,261 of them with 6+ equipment slots, armour evidence on 132
weapons. Slot fill: MainHand/Head/Armor/Shoes 99%, Cape 98%, Potion 93%,
Food 60% (food is eaten and not renewed), OffHand 29% (two-handers occupy
both hands — a real fact, not a parse failure). Builds carry tier AND enchant
(`T6_ARMOR_CLOTH_AVALON@2`), which the published corpus mostly does not.

For scale: the curated evidence base was 625 gear pieces across 36 comps.

**THE ROLE BOOK VALIDATES — independently.** `roles.yaml` seats were curated by
hand; armour class is the owner's own role tell ("cloth wearing is a very good
indicator"). Across 8,752 builds whose weapon has an assigned seat:

```text
   class         n     cloth  leather  plate
   frontline   1247      6%      9%     85%
   healer      2068     72%      9%     19%
   dps         2848     46%     46%      9%
   support     2589     23%     42%     35%
```

**Frontline 85% plate, healers 72% cloth** — the curation matches how people
actually gear, from a source that had no part in making it. DPS splitting
evenly cloth/leather matches the owner's own account (cloth for long-channel
burst, leather for brawl DPS). **Support at 35% plate is the odd one**: a
third of the "support" class is armoured like frontline, which suggests that
class is holding two different jobs and may want splitting.

**ONE CONTRADICTION, n=93:** **Nature Staff is seated `main_healer` but 53% of
its users wear PLATE** (49 plate / 35 cloth / 9 leather). Every other healer
weapon is cloth-dominant. Either it is played as a plate frontline healer or
the seat is wrong for how it is actually used. Owner ruling wanted.

**ROLE-BOOK GAPS — real usage, no seat assigned:**

```text
   Brimstone Staff      n=75   cloth 100%    IP 1457
   Dual Swords          n=72   leather 86%   IP 1218
   Kingmaker            n=55   leather 64%   IP 1395
   Heron Spear          n=54   leather 44%   IP 1316
   Great Nature Staff   n=43   cloth 63%     IP 1182
   Holy Staff           n=36   cloth 86%     IP 1146
```

**Brimstone at 100% cloth over 75 builds** is exactly the profile the owner
described (2026-08-27): "a user wearing scholar robe assassin hood has
relatively no defensive but one would wear that if the role they have to play
is burst damage on a spell with long channel time like brimstone". That is a
burst-damage seat the role book does not have, now with evidence behind it.

**ARTIFACT SIZE, flagged for a decision:** `party_rosters.json` is now 4.44 MB
(it was 83 KB), essentially all of it the per-build gear. `pipeline/out/*.json`
is committed on purpose as parsed game data, but this is a growing
OBSERVATIONAL file — every future harvest enlarges it. If that becomes
unwelcome, the split is obvious: commit the aggregates (`weapon_armour`,
`parties`, `summary`) and gitignore the raw `builds` array beside the other
caches. Not done unilaterally because the raw builds ARE the evidence and
discarding them silently would be the wrong default.

Display/evidence only, unchanged: nothing here feeds scoring.

## Fail-closed kit generation (owner ruling 2026-09-01)

**The case:** the owner asked why Light Crossbow wore a mixed leather/plate
kit at faction_war/15/brawl and why Hellion Hood was suggested "on so many
seats and not just tank". Diagnosis: `kit_options` documented and served a
fallback — a weapon with no role-book seat "keeps the pre-doctrine kit
behavior", i.e. the WHOLE catalog marginal-ranked. 75 of 137 weapons resolve
no seat, and in any full comp the marginal ranking has a predictable winner:
almost every capability is saturated, silence almost never is, so Hellion
Hood's silence +3 topped the head slot for practically every seatless member
of every full comp. The 2026-08-26 "everyone-gets-Hellion fix" had gated only
the CHEST; the head slot's doctrine bound silently evaporates at seat=None.
(On real tanks Hellion is legitimate — weapon-tier observed doctrine.)

**The ruling** (owner, rejecting per-item patches: "that's the problem with
individual item rules, i want to fix the underlying issue which allows these
items and builds and kits to slide in to the team comp"): **the kit
suggestion channel only speaks evidence, end to end.**

- No seat -> `kit_options` returns empty kit and options (`seat: None` so
  the UI can say why). No fallback.
- A seated slot with no doctrine tier stays UNSET — never catalog-filled.
- `role=None` remains the explicit DIAGNOSTIC escape (audits/tests
  comparing against the ungated catalog); it is never the default channel.
- Manual builds still score anything — the gate is suggestion-layer only,
  exactly like the weapon-side style/cost/generation-fit gates.

Shipped in BOTH ports (engine.py + app_scoring.js, parity 60/60), pinned by
test_roles R19. The loadout panel now says "no role-book seat for this
weapon — the engine suggests no kit" instead of silently proposing nothing.
`kit_variants`/the dressed forge were already doctrine-filtered and are
byte-identical (forge 38/38, golden 59/59, validation-modes 25/25).

**Follow-up this ruling makes urgent:** the 75 seatless weapons now get no
generated kit at all until the role book covers them — seat curation
(evidence-cited memberships, per roles-design.md) is the real fix and needs
its own pass.

## THE SEAT-ALL PASS (owner ruling 2026-09-01, same session)

Owner: **"ok well lets fix seat for all weapons."** 73 of the 75 seatless
weapons received seats in `pipeline/roles.yaml`; the role book now covers
**135 of 137** (was 62).

**Evidence discipline per entry:** the killboard build harvest
(`pipeline/out/party_rosters.json` `weapon_armour` — observed armor-class
distribution per weapon, 2026-08 harvest) picks the uniform; the derived
E identity (delivery / damage scale / heal profile) picks the seat class;
family precedent and standing rulings break ties. Every membership cites
its build count and armor split (`killboard:party_rosters (N builds, X%
class)`); entries with fewer than ~10 observed builds carry an explicit
"thin" marker and lean on the owner's seat-all mandate. Notable baskets:
Battle Bracers 350 builds 68% leather, Spirithunter 193 builds 75%
leather, Lifecurse 133 builds 76% PLATE.

**One new seat:** `curse_support` (class support, uniform cloth+plate —
the killboard fields the front-rank curses in plate and the artillery
ones in cloth). Members: Lifecurse, Damnation, Shadowcaller, 1H Cursed,
Great Cursed, Demonic, Cursed Skull. Their purge/pierce FUNCTION roles
stand; the derived curse_pressure job group is unchanged.

**Two standing rulings respected, NOT overridden** (surfaced for the
owner): 2H_SHAPESHIFTER_CRYSTAL and 2H_IRONCLADEDSTAFF stay off every
menu — the 2026-08-26 grading board ruled them off ("not good for group
content"; the Iron-clad stopper removal + ≥10 viability exclusion). A
word from the owner seats them.

**Ruling-preserving test re-pins:** R17's Black Monk menu pin extends to
`[off_tank, shield_break]` (the 2026-08-26 ruling's substance — function,
never shield_support — holds; the seat is new). R19's seatless fixture is
now SYNTHESIZED (menu stripped in-memory) since no natural seatless
weapon remains. T30/T30b/T30d re-pinned under `set_dressing(False)`: with
1H Holy seated, a generation candidate evaluates DRESSED and its kit
honestly closes real gear gaps in a naked fixture (T30c's documented
honesty rider) — the weapon-level redundancy lens these cases pin runs in
the V3-W symmetric mode instead.

**Gates after the pass:** dataset release_clean (137/137 on menus incl.
2 sweep-only), roles 19/19, golden 59/59, forge 38/38, parity 60/60,
validation-modes 25/25, builds 54/54, interactions 37/37, provenance
25/25. **tier2 v4 actual_gear role-level rose 70% → 87% (20/23), gate
PASS.** (`test_cohort_families` 6/7 fails identically on clean HEAD —
pre-existing, unrelated: the committed sample now yields 21 small-bucket
families where the contract pins 0; needs its own look.)

**Effect:** with fail-closed generation + full seat coverage, every
weapon's kit suggestions are doctrine-bounded — e.g. Light Crossbow now
draws the ranged_aoe observed tier (Mistwalker Jacket, Cleric Cowl)
instead of the old catalog-marginal Hellion bait, and Lifecurse dresses
in its killboard-majority Knight Armor.

## KILLBOARD KIT DOCTRINE (owner ruling 2026-09-01, same session)

Owner: **"now shall we add seats for different gear too and base it on
seen evidence from the data we harvested from all the battles?"**

The kit-doctrine mining (`derive_kit_doctrine`, build_dataset.py) now
takes the KILLBOARD HARVEST as a second evidence stream beside the
curated builds_index: `out/party_rosters.json` carries 9,569 real
fielded builds (weapon + gear at kill time, ids pre-normalized to the
catalog key space; ~54k gear observations resolve, ~95% per slot except
food 84%). Same pools, same uniform gate, same effect-carrier
exclusion; suggestion-layer only, scoring untouched.

**Discipline:**

- **Noise floor** — a killboard-only item needs `KB_MIN_SEAT = 3`
  observations to enter a seat pool and `KB_MIN_WEAPON = 2` for a
  weapon tier; an item the curated corpus already cites merges its
  killboard count regardless.
- **Provenance stays separate** — audit rows carry a `kb` count and a
  `killboard:Nx` source token beside the build-id citations;
  off-uniform chest sightings aggregate into the same off_uniform
  report (never admitted). Winner bias is the harvest's documented
  property and rides the citation.
- **A hand ruling superseded by observation retires loudly**: the build
  fail-closed BLOCKED on the 2026-08-26 Leering Cane `add` (stopper
  offhand) the moment the killboard OBSERVED the cane there — the
  owner's "incubus is mostly paired with leering cane" confirmed by
  data; the add is retired with a comment, the affinity override and
  every drop ruling stand.

**Effect:** tiers went from a handful of curated items to observation-
led pools (ranged_aoe head tier 25 items, engage_tank shoes 22, the new
curse_support fully stocked), and per-weapon doctrine now exists for
the whole catalog — Light Crossbow wears its OWN observed kit
(Mercenary Jacket 3/7, Hunter Hood 5/5, Mistcaller 5/5, Guardian Boots
5/5), Polehammer's Knight majority holds at 63/95.

**Re-pins:** R18 doctrine_n [9,12]→[63,95] (corpus-size pin, mechanism
unchanged); T30c caps_gain tolerance 0.05→0.6 (Longbow's v0 changed;
substance — negative verdict, dup priced — holds).

**Gates:** dataset release_clean, roles 19/19, golden 59/59, forge
38/38, parity 60/60, validation-modes 25/25, builds 54/54, provenance
25/25, interactions 37/37. **tier2 v4 actual_gear role-level: 78%
(18/23), gate PASS** — down from the seat-all pass's 87%, still above
the 70% gate and the 70% pre-session baseline. OBSERVATION FOR THE
OWNER (not tuned, per anti-circularity): the killboard-widened
candidate kits cost 2 role-level slots on this n=23 corpus — either
noise or a hint that observation-led tiers dilute the curated signal
when DRESSING CANDIDATES; the incumbents' actual gear is unaffected.
A future blind round can separate the two.

## THE OBSERVED-BUILD OVERLAY (owner ruling 2026-09-01, same session)

Owner: **"i want gear that each seat is wearing to actually be based
on what real people wear. the engine keeps making up some random
builds."**

The diagnosis: even with observation-bounded tiers, the KIT was still
assembled slot-by-slot — comp-aware ranking picked each slot's
marginal-value winner independently, producing combinations no player
ever fielded, and a thin per-weapon tier could outrank a heavily
observed seat norm.

**The mechanism:** `_modal_build_chain` (build_dataset) mines a
CONDITIONAL MODAL build per weapon (>= 3 observed builds; seat-level
fallback over all member builds) from the killboard harvest — the
most-observed chest first (uniform-gated, effect carriers excluded),
then the most-observed head AMONG BUILDS WEARING THAT CHEST, and so on
down the slots, each step needing >= 2 observations. The result is a
coherent kit real players field together, cited with the step counts
([54/136] = 54 of the 136 builds at that step). Ships as
`kit_build`/`kit_weapon_build` on each seat; audit rows in
roles_report (`archetype`/`weapon_archetypes`).

**Both engine ports** overlay it in `kit_options`: the archetype item
moves to the FRONT of its slot's options (annotated
`observed_build: [n, of]`) so the kit pick and the dressed forge's v0
ARE the fielded combination; every other option keeps its tier/
marginal order for browsing; a gate that excludes the archetype item
(uniform, brawl cloth) leaves the slot to normal ranking; `role=None`
diagnostic mode gets no overlay. R20 pins all of it.

**Results:** Heavy Mace now dresses as the real stopper meta (Knight
Armor 42/142 + Hellion Hood 17/42 + Royal Shoes + Gigantify),
Hallowfall as Robe of Purity 672/1169 + Guardian Helmet 171/672 +
Mistcaller. Every gate stayed green WITHOUT re-pins (the killboard
reality matched F24's pinned tank v0 exactly), and **tier2 v4
actual_gear role-level rose 78% → 83% (19/23), gate PASS** — dressing
candidates in what real people wear validates better than marginal
assembly.

## The two exceptions ruled + a name mix-up resolved (owner 2026-09-02)

Owner: **"chillhowl - single target e, no good for group content
mostly a corrupted dungeon weapon, stillgaze is a d tank, iron clad is
just some random rat weapon that no one uses in zvz."**

Resolving the seat-all pass's two open exceptions surfaced a NAME
MIX-UP in the book: the 2026-08-26 grading removal labeled
`2H_SHAPESHIFTER_CRYSTAL` as "Chillhowl", but that id is **Stillgaze
Staff**; Chillhowl is `MAIN_FROSTSTAFF_AVALON` — which had kept a
zone_support seat all along.

- **Chillhowl (MAIN_FROSTSTAFF_AVALON)** — zone_support membership
  removed; off every menu, matching its standing ≥10 viability
  exclusion (composition.yaml, owner 2026-08-18).
- **Stillgaze (2H_SHAPESHIFTER_CRYSTAL)** — seated `stopper_tank`
  (killboard: 6/6 builds plate — thin but unanimous, and consistent
  with the d-tank ruling).
- **Iron-clad (2H_IRONCLADEDSTAFF)** — stays off every menu,
  confirmed; killboard's 17 builds are a small-scale population.

Role book: 135 → 135 of 137 (one in, one out — Chillhowl and
Iron-clad are the two deliberate menu-less weapons, both also
viability-excluded ≥10). R17 re-pinned with the corrected names. All
gates green; tier2 v4 holds 83% (19/23) PASS.

## Owner bug round 2026-09-03 — five defects behind "the engine is not functioning properly"

Owner report (verbatim fragments): "overstacked in certain areas and
understacked in others ... capability supply vs target is all wonky",
"reforge all buttons not working on certain comps", "big need -
frontline and then recommend we add some different type of weapon",
"adds an offhand to two handed weapons", "support weapon like occult
into dps column", "grailseeker has red color but its in tank column".
Reproduced on a forged clap / territory_defense / 20 before touching
anything; each finding below names the mechanism, not the symptom.

1. **Biggest need was measured NAKED while everything else was
   dressed.** `weaknesses()` in `_app.js` passed combos but not
   `GEARS_CUR`, so the need ranking read the bare roster (tankiness
   10 / 38.75 -> "Frontline") while the pick, the "have" number beside
   it and the radar read the worn kits (tankiness 76 / 38.75). The
   pick then correctly answered a different question, and the board
   read over/understacked against a need it did not share. Fixed in
   the display layer: `weaknesses` and `afterPickGaps` now take the
   same gear basis as the pick (candidate joins in the kit the engine
   valued it with). Zero scoring change.
2. **Every two-hander was dressed with an off-hand.** The seat doctrine
   pool is mined from the seat's one-handers too, and nothing in the
   engine knew which weapons have a free hand — the dumps' `twohanded`
   fact stopped at `weapon_lines.json`. Now `two_handed` rides the
   dataset (116 true / 21 false, dumps-sourced) and `kit_options` drops
   the slot for a two-hander in both ports, so `kit_variants`, the
   dressed forge and the page prefill inherit it. T22 re-pinned (its old
   pin DEMANDED an off-hand for Heavy Mace); R21 pins the gate.
3. **Three role classifications disagreed.** The comp board's column
   read the role-book SEAT, the tile colour and roster order read the
   sheet's `role_hint`, and the forge's bands read `role_class` (hint +
   composition overrides). Grailseeker: seat stopper_tank / hint melee /
   class dps — a red tile in the tank column that the frontline band did
   not count. Structural fix, no hand list: `role_class` now derives from
   the primary SEAT's class (first uniformed menu role, the same
   resolution `detect_role` uses; composition overrides still win; a
   seatless weapon keeps its hint), both ports; the page's tile colour
   and sort read the same seat. 11 weapons moved class (Grailseeker,
   Stillgaze, Primal, Soulscythe, Black Monk, Witchwork -> frontline;
   Icicle, Hoarfrost -> support; Forge Hammers, Rotcaller -> dps; Occult
   -> support via 4). R22 pins the derivation. Generation-only effect:
   the clap-20 forge now fills five frontline (Grailseeker counted) and
   spends the freed dps slot on ranged AoE — Realmbreaker leaves it.
4. **Occult Staff seated dive_cleanup (dps).** The 2026-09-01 seat-all
   pass read the killboard's 85% leather as a dive identity; the E is
   Time Corridor (ally move+attack speed, enemy slow) and the cited
   metabattle build is literally "ZvZ Support". Owner 2026-09-03:
   "support weapon like occult". Re-seated zone_support, leather
   admitted to that seat's uniform on the Occult evidence; off
   dive_cleanup. R23 pins it.
5. **"Reforge all" is a deterministic search.** With no manual slots,
   or the same manual slots, content, style and size, it returns the
   identical roster and the page re-rendered it silently. Verified in
   the browser: no exception, no change. The page now reports
   "Unchanged" with the reason and what to change; a URL-loaded comp
   (every slot manual) never shows the button at all, by design.

NOT changed, for the owner: Spiked Gauntlets and Realmbreaker generating
into clap dps are covered by the 2026-08-26 conditional-payload ruling
(the owner named spiked gauntlet as an instant-delivery clap weapon and
rejected a melee/ranged category rule), so the "bomb builds in clap"
complaint has no derived rule left to apply without a new ruling.

Gates after the fixes: golden 59/59, forge 38/38, roles 23/23,
validation modes 25/25, parity 60/60 + embed, dashboard layout all,
display math 28/28, codec 24/24, provenance 25/25, builds 54/54,
interactions 37/37, patch history 14/14, evidence lint clean, tier2 v4
actual_gear role-level 83% (19/23) PASS. `test_cohort_families.py` is
6/7 on main BEFORE this round: its canary pin ("small == 0") dates from
the 2026-08-25 artifact and the sample it mines was refreshed
2026-08-29 — a sample-refresh re-pin the owner has to bless, not a
regression from this work.

## THE KIT AUDIT (owner 2026-09-03) — "judge 10 random weapons ... build fixes until the engine agrees with the real data of people who win fights"

Owner examples: a 15-man clap Mace in Graveguard Armor ("why would it be
better than Judicator, Guardian, even Knight"), Leering Cane on its
off-hand, Hunter Hood on Oathkeepers ("people are most likely to use
assassin hood or cleric cowl").

**The harness** (`scratchpad kit_audit.py`, now pinned as R24): per slot,
the killboard's modal item over a weapon's harvested builds (official
kill-event party rosters, 9,569 builds, tier-agnostic ids) against the
kit the forge dresses the weapon in (`kit_variants` v0). Ten weapons
drawn with seed 20260903 from the 67 with >= 30 builds; then all 67.

| | exact-modal agreement | slots where the pick is worn < half as often as the modal |
|---|---|---|
| ten weapons, before | 43/61 = 70% | 9 |
| ten weapons, after | 54/61 = 89% | 0 |
| all 67 weapons, after | 370/420 = 88% | 4, all catalogue gaps (a plain Cape, a fish) |

**What people actually wear** (the numbers the engine was ignoring):
Oathkeepers Demon Armor 105/126 small, 37/47 at 20-59, 68/79 at 60+, and
Assassin Hood 112/40/72 of the same; 1H Mace Judicator 43 + Guardian 36
of 137 at 20-59 with Graveguard fourth; Galatine Pair Soldier Armor
(plate) 81% of 145 under a cloth/leather bomb seat; Witchwork cloth 33% /
leather 25% under a plate engage seat.

**Root causes, each fixed as a derivation, no hand lists:**

1. **Effect-carrier chests were banned from weapon evidence** (the
   2026-08-26 "comp-level allocation" rule; the allocator it promised,
   increment 3b, was never built). Demon/Judicator/Guardian/Royal
   Jacket/Hellion left every weapon tier and the archetype chain, so the
   modal chest could never be suggested and the leftovers (Graveguard,
   Duskweaver, Knight) were. Carriers now count like any piece; the
   comp-level rule became the **carrier quota** below.
2. **The seat uniform overrode the harvest.** Galatine's plate was
   "off-uniform" and thrown away; the archetype chain then conditioned
   on a 13-build cloth pocket and produced Royal Hood + Cleric Robe +
   Mage Sandals + Keeper Cape. Now a class worn by >= 25% of >= 50
   harvested builds is admitted for THAT weapon (dataset
   `kit_weapon_uniform`, reported as `uniform_extended`); the seat
   aggregate keeps the book uniform; thin samples (Grailseeker, 32
   builds) overturn nothing (R6/R12 hold).
3. **The archetype chain fronted rare pockets** (Hunter Hood 5/14 over
   Assassin Hood 131/149). The chain now stops when its conditional pool
   drops under 5 builds or the pick holds < 25% of it, and the overlay
   may only front an item inside the evidence band (worn >= half as
   often as the slot's modal item).
4. **Comp-aware ranking was value-first within a tier** (a mace got
   Cleric Cowl 32/216 over Judicator Helmet 81/216 because the comp
   lacked cleanse). Count leads in both modes; the comp marginal reorders
   only the evidence band; the seat tier keeps its count order.
5. **Carrier quota (increment 3b, derived).** Killboard share of builds
   wearing each carrier chest per fight-size bucket (dataset
   `carrier_quotas`: 20-59 players and 60+, the harvest's own floor)
   becomes a per-roster cap of share x size, half-up, min 1 — at 20:
   Hellion 2, Judicator 1, Guardian 1, Demon 1, Royal Jacket 1. A
   GENERATION constraint inside the search: `party_state` counts the
   carriers a roster wears and every dressed candidate skips a kit
   variant past the cap, a carrier-modal weapon carrying its best
   non-carrier chest as the alternative (Mace: Judicator -> Knight). A
   first version as a post-forge re-dress pass broke F5 (a refined
   roster re-priced negative); the constraint form keeps every forge and
   golden contract. Manual kits always score (R25).

**Where the data disagrees with the owner:** Leering Cane IS the modal
1H-Mace off-hand at 20-59 (64/137; Astral Aegis leads at 60+). The
context-free kit keeps it; the comp-aware kit now prefers Astral Aegis
inside the evidence band when the comp values it. The harvest has no
fights under 20 players (discovery floor) and no style split — the
next evidence round should lower the albionbb discovery floor and label
rosters with comp_identity.

Re-pins: T22 (two-hander has no off-hand slot), R18 (carriers are
weapon evidence; Polehammer Knight 63/144), R20 (fallback shown on a
chain-stopped weapon). New: R24 audit agreement, R25 carrier quota,
R26 observed chest class. Gates: golden 59/59, forge 38/38, roles 26/26,
validation modes 25/25, parity 60/60 + embed, layout, display math,
codec, provenance, builds, interactions, patch history, lint, tier2 v4
actual_gear role-level 87% (20/23) PASS. Browser: the JS forge dresses
the clap-15 identically (Witchwork Robe of Purity, Occult Royal Jacket,
one carrier, no off-hand on any two-hander, zero console errors).

**Addendum (owner, same day): "lifecurse support on kite in 20 man terry
defense went to cleric robe ... most lifecurse would be on demon armor".**
Confirmed and fixed. Harvest: Lifecurse wears Demon Armor 46/68 at 20-59
and 40/65 at 60+ (plate 76%, cloth 9%); the engine's own evidence ranked
Demon first. The Cleric Robe came from the new quota: one Demon per 20,
and Bedrock Mace (72% Demon itself) had taken it first in that forge.
Rule refined: a chest at least HALF a weapon's builds wear is that
weapon's IDENTITY chest and is exempt from the quota (both ports,
`_identity_chest`); the quota rations DISCRETIONARY carriers only — the
tank that "has to take one". The same kite-20 now dresses Bedrock Mace
AND Lifecurse in Demon Armor (R25 pins it). On the cloth question: cloth
Lifecurse is 9% of winning builds and pairs with Assassin Hood / Soldier
Helmet — a dps-style kit — but the book gives Lifecurse no dps seat
(menu: purge function + curse_support, uniform cloth+plate because
Damnation is a cloth curse support). Whether a cloth Lifecurse should
detect as dps is an open owner ruling on the role book (add a dps seat
for the 1H curse line, or narrow curse_support's uniform per weapon by
observed class), not something the data alone can settle.
Second half of the same case: with the exemption in place Lifecurse STILL
took Cleric Robe, because the alternative kit variant (a 7%-worn robe)
was free to beat the 79%-worn Demon on the exact score — the kite comp
lacked cleanse. The variant builder now applies the evidence band too: a
divergent alternative must be worn at least half as often as the slot's
modal piece, and the non-carrier chest a carrier weapon carries is a CAP
FALLBACK that the evaluators offer only when v0 is actually capped. The
forge no longer gets to out-think a weapon's standard kit with a rarity;
it may only choose among kits people wear. Both ports, parity 60/60.

**Addendum 2 (owner): "this grailseeker build is a ganking build not a
zvz build. also the heavy crossbow has soldier boots".** Both traced to
the harvest's evidence UNIT. The sampler keys on BATTLE size (20+
players), which admits 2-8 man gank parties fighting inside a big
battle; Grailseeker's 32 builds were mostly those (Hunter Shoes 20,
Demon Cape 21, Poison Potion 13, fish food 14), and Heavy Crossbow's 12
builds likewise. Fixed at the source: `sample_parties.py` now stamps
each build with `party_size` (the largest deduped killer party carrying
that player name in the battle; victims have no party record and stay
unknown), re-derived OFFLINE from the cached kill events (`--pages 0`,
no network). Coverage: 5,162 builds from killer parties of 10+, 1,557
from smaller parties, 2,850 unknown (victims). Doctrine mining, the
uniform extension, the carrier quotas, the audit harness and R24 all
read the 10+ population only (`KB_MIN_PARTY = 10`, the engine's group
band floor). Result: Grailseeker dresses from its 15 ZvZ-party builds
(Assassin Hood, Knight Armor, Hunter Shoes 7/15, Smuggler Cape,
Gigantify); Heavy Crossbow has 2 such builds and falls back to the
ranged-AoE seat kit — fail-closed, as designed. Audit on the ZvZ
population: ten seeded weapons 58/63 = 92% exact, 0 bad; all 39 weapons
with >= 30 ZvZ builds 225/245 = 92%, 1 miss (an uncurated plain beef
sandwich). R18 re-pinned to the smaller corpus (Polehammer Knight
35/82). The "Novice's Soldier Boots" label was a display defect:
`gear_lines.json` names a line by its lowest-tier example item, so a
T2-first line read "Novice's" beside "Adept's" elsewhere; the page now
uses the curated catalog's tier-free display name and strips the tier
adjective otherwise. Evidence still open: the harvest has no fights
under 20 players, so a party under 10 has NO kit evidence at all; a
gang-band doctrine needs a lower discovery floor.

## Harvest refresh (2026-09-04) — "lets do the data collection"

Two explicit network runs of `pipeline/sample_parties.py` (official
gameinfo kill events for detail, albionbb for discovery; the cache is
per battle and idempotent): 120 new ZvZ battles at the 25-player floor,
then 150 small-scale battles at an 8-player floor — the first fights
under 25 players in the corpus. Cache 270 -> 523 battles (8 to 400
players; 133 under 25), builds 9,569 -> 14,706.

| | before | after |
|---|---|---|
| builds from killer parties of 10+ (the doctrine population) | 5,162 | 7,085 |
| builds from parties under 10 (future gang doctrine; unused today) | 1,557 | 2,990 |
| victims, no party record (excluded) | 2,850 | 4,631 |
| weapons with 30+ ZvZ builds | 39 | 50 |
| weapons with 10-29 | 36 | 36 |
| weapons with 1-9 | 47 | 40 |
| weapons with none | 15 | 11 |

Still without ZvZ evidence: Arctic Staff, Black Hands, Crystal Reaper,
Divine Staff, Forcepulse Bracers, Great Cursed Staff, Ironroot Staff,
Pike, Skystrider Bow, Trinity Spear, Twin Slayers — they dress from the
seat aggregate, fail-closed. Carrioncaller gained evidence (it was at
zero and the forge fields it).

Audit on the refreshed population: ten seeded weapons 55/61 = 90%
exact, 0 bad; all 50 weapons with >= 30 ZvZ builds 283/313 = 90%, one
miss (an uncurated plain sandwich). One rule tightened en route: the
SEAT-level archetype (the fallback for slots a weapon's own chain
lacks) fronted Greataxe's cape with the brawler seat's Smuggler Cape
(101/156) over the weapon's own Lymhurst (19/41); a seat archetype now
fronts only slots where the weapon has no counts of its own. Spot
checks: Mace 136 ZvZ builds, Judicator 61 / Guardian 32, v0 Judicator
Helmet + Judicator Armor + Mistcaller (the larger population moves the
off-hand off Leering Cane); Lifecurse 95, Demon 69; Oathkeepers 98,
Demon 77; Grailseeker 23 in ZvZ parties, Knight 8 / Assassin Jacket 6,
still Hunter Shoes by count.

Re-pins for corpus size: R18 (Polehammer Knight 45/103), R25 (identity
Demon wearers unlimited; DISCRETIONARY Demon wearers within cap — the
kite-20 now fields Incubus in Demon as the one discretionary wearer
beside Lifecurse's identity Demon). Gates: golden 59/59, forge 38/38,
roles 26/26, validation modes 25/25, parity 60/60 + embed, layout, node,
provenance, builds, interactions, patch history, lint. **tier2 v4
actual_gear role-level 74% (17/23), PASS at the 70% gate but down from
87%** — the candidate's doctrine kit changed under the larger harvest
and three role-level hits moved; under the anti-circularity rule this is
a finding for the owner, not a retune (the blind-test comps must never
drive doctrine or scoring against their own gate results).

## Deep harvest + the overnight task (2026-09-04, evening)

Owner: "lets see if you can just get more battle data in general", then
"lets stop there for now and make this an overnight task". The deep pass
walked the full discovery list at the 25-player floor (up to 40 pages x
20 battles, cached ones skipped) and was stopped by the owner at 469 new
battles before the 8-player pass began; the cache was folded in offline
(`--pages 0`, no network). Cache 523 -> 994 battles (8 to 1,315
players), builds 14,706 -> 32,001.

| | morning | evening |
|---|---|---|
| builds from killer parties of 10+ | 7,085 | 15,165 |
| builds from parties under 10 | 2,990 | 6,652 |
| victims, no party record | 4,631 | 10,184 |
| weapons with 30+ ZvZ builds | 50 | 72 |
| weapons with 10-29 | 36 | 33 |
| weapons with 1-9 | 40 | 28 |
| weapons with none | 11 | 4 (Black Hands, Crystal Reaper, Ironroot, Trinity Spear) |

The audit on the larger population surfaced one more archetype-chain
defect: a conditional pool of 5-8 builds let a 7-of-8 cape (Greataxe:
Smuggler inside the Mistwalker pocket) outrank the slot's 36-of-74 modal
(Lymhurst), and a 4-of-5 shoe on Great Hammer beat Hunter Shoes 9-of-26.
The chain now also stops unless its pick is at least half the slot's
UNCONDITIONAL modal count over the whole population. Result: ten seeded
weapons 58/63 = 92%; all 72 weapons with >= 30 ZvZ builds 429/450 = 95%,
the single miss an uncurated plain cape.

R18 re-pinned as a MECHANISM (Knight from the weapon tier, >= 40% of the
slot over >= 35 builds): with the harvest now nightly, exact doctrine
counts are never pinned again. Gates: golden 59/59, forge 38/38, roles
26/26, validation modes 25/25, parity 60/60 + embed, layout, node,
provenance, builds, interactions, patch history, lint; tier2 v4 stays
at 74% (17/23), PASS — still an owner finding, not retuned.

OVERNIGHT TASK: `pipeline/harvest_overnight.ps1` runs both passes (25
then 8 player floor, 800 battles each, cache-skipping) and is registered
as the Windows scheduled task "CompForge overnight harvest", daily at
03:00 as the current user, 6-hour limit, runs late if the machine was
asleep. It harvests only — the dataset rebuild, the gate list and the
audit remain a reviewed, in-session step, so a bad night can never ship.
Logs land in `pipeline/out/fetch_logs/` (gitignored). Remove with
`Unregister-ScheduledTask -TaskName "CompForge overnight harvest"`.
The machine has to be on (or wake) at 03:00 for it to run.

## Style x size roster evidence pass (2026-09-04, owner: "ok lets do this now")

`pipeline/audit_style_rosters.py` (report-only): 1,690 killer-party
rosters of 10+ from the harvest, deduped by member overlap as the sampler
does, labelled by `comp_identity` (brawl 487 / clap_kite 305 / kite 211 /
brawl_clap 150 / clap 109 / split 428), kits joined by player name
(doctrine v0 where absent: 30-50% of members, counted), measured DRESSED
per style x band as distinct rosters. Board:
`docs/superpowers/findings/2026-09-04-style-roster-evidence.md`; numbers
and the blind-round answers: `out/style_roster_evidence.json`.

What it says, before any ruling: full 20-stacks are scarce per style
(5-54 distinct; most rosters are 10-19); at 20 the harvested medians run
1.5-2x the current targets on tankiness, sustained dps, healing and
burst AoE, and 3-10x on mobility, engage, peel, disengage and silence
against the contents fitted on a handful of comps (castle, roads,
faction war); ranged_presence sits at 0.6x for brawl (expected) and
1.4x for clap_kite; anti_zone and execute are ~0 everywhere (nobody
fields them). Structure at 20: 5 frontline / 3-5 support / 8-9 dps /
3-4 healers across styles, 2 engage + 1-2 stoppers, a 5-6 ranged-AoE
core for clap/clap_kite/kite against 1-1.5 for brawl, 10-12 pierce
carriers.

STANDING: nothing in the build reads this; the identity labels get a
blind round (ten rosters in the board) before any number is proposed for
a ruling; the evidence is content-agnostic and winner-biased and the
board says so.

### Blind round 1 on the harvested rosters (2026-09-04; owner: "dont take my word as final, its just what i think their comp is leaning towards")

Ten killer-party rosters of 15+ from the style x size evidence board,
weapons only, owner's call collected BEFORE the engine's label was read.

| # | size | owner | engine (strength) | melee share | bomb share |
|---|---|---|---|---|---|
| 1 | 17 | clap_kite | clap_kite (leaning) | 48% | 50% |
| 2 | 20 | brawl_clap | brawl (leaning) | 76% | 40% |
| 3 | 17 | brawl | brawl (strong) | 100% | 46% |
| 4 | 19 | kite | brawl_clap (leaning) | 50% | 53% |
| 5 | 18 | brawl | brawl (strong) | 88% | 55% |
| 6 | 18 | clap | clap_kite (leaning) | 42% | 41% |
| 7 | 20 | clap_kite | brawl_clap (leaning) | 47% | 46% |
| 8 | 17 | clap_kite | clap (strong) | 12% | 51% |
| 9 | 15 | clap | clap (leaning) | 21% | 52% |
| 10 | 15 | clap | clap_kite (leaning) | 24% | 40% |

Exact agreement 4/10; 9/10 within one step on the brawl-clap-kite axis
(the one far miss is #4). The three strong labels all agreed. Every
miss is a HYBRID-HALF call, and they point two ways: the engine's kite
half (evade points per member) fired where the owner saw pure clap (#6,
#10) and stayed silent where the owner saw clap-kite (#8); the clap half
did not fire on a 76%-melee roster whose bombs are Galatine pairs (#2);
and in the mid band the commit-posture tiebreak chose brawl_clap where
the owner read clap-kite (#7). Hypotheses for the owner, NOT rules: (a)
melee AoE bomb lines (Galatine) count toward the clap half; (b) the kite
half is a RANGED-COMPOSITION property (bows, ranged sustained pressure)
rather than an evade-points property. No threshold moved. Next: the
owner's definitions on (a) and (b), then a second round of twenty
rosters before the identity thresholds are touched and before any
number on the board is proposed for a ruling.


### Rulings from blind round 1 (owner, 2026-09-04) and what they became

Owner, on the clap half: "i have seen galatine pair be used as a solo
bomb in a big fight but realmbreaker is usually used with the rest of
the team hitting together so realmbreaker would be part of clap but
galatine is not, it needs to charge its q stacks before it hits."
Owner, on the kite half: "what makes a comp kite is basically them
having tanks which can throw enemies away, bedrock mace, hoarfrost staff
without having to commit their body into a fight. it also needs to have
range dps so team can hit the enemy from range and keep moving ... it
would also most likely have an occult staff to increase team movement
... icicle staff to slow enemy in large spaces ... purity robe for that
extra knockback."

Both landed as DERIVATIONS, no weapon lists:

- **Clap half.** A conditional-payload carrier (the 2026-08-26 ramp
  fact, now stamped into `style_fit`) has its burst AoE counted as
  SUSTAINED in comp_identity. Galatine, Clarent, Carving, Ursine, Rift
  Glaive, Kingmaker, Greataxe, Ravenstrike, Infinity Blade stop being
  bombs; Realmbreaker (instant leap-slam) stays one.
- **Kite half = STANDOFF TOOLS.** New derived fact `style_fit.standoff_e`:
  an E, damage-bearing or not, delivered at range (ground/enemy target,
  cast range >= 9) that displaces (knockback_displace >= 2) and commits
  nothing (no engage / clump / pull-catch, no self-move, no heal). Six
  weapons carry it: Bedrock Mace, Hoarfrost Staff, Demonic Staff,
  Brimstone, Infernal, Phantom Twinblade. (Bedrock's E is a utility E, so
  the damage-only delivery read had it as MELEE — the fact is read from
  every E bundle.) The hybrid needs standoff tools at scale: max(2, n/10
  half-up) — two at 20, two at 10 (clap10 with its one Bedrock stays the
  owner's pure clap); a pure kite needs at least one; a ranged core with
  none must commit to its bomb and is a clap whatever its bomb share
  (rosters 6 and 10). In the mid band the kite half outranks the
  commit-posture tiebreak (roster 7). The old evade-points read
  (IDENTITY_HYBRID_EVADE) is retired.
- Occult's team speed, Icicle's slow and Purity's knockback are in the
  owner's picture but not in the derivation yet: no capability separates
  team-speed from self-mobility, and gear is not passed to
  comp_identity. Recorded for the next round.

Re-score with the rulings in: fixtures blap / clap10 / kite10 / DH P1 /
20v20 all hold; the round moves 4/10 -> 7/10 exact. The three misses are
explained and recorded: 2 (brawl_clap called, brawl read) follows the
owner's own Galatine ruling; 4 (kite called, clap_kite read) is the
mid-band hybrid with three Bedrocks; 8 (clap_kite called, clap read) has
one Bedrock where a 17-stack needs two. T34 pins the facts, the five
fixtures and the seven agreed rosters. Label distribution on the 1,690
harvested rosters after the rulings: brawl 487, clap 320, clap_kite
216, kite 185, brawl_clap 43, split 439 — brawl_clap collapsed from 150
because Galatine-style bombs no longer make a clap half and the kite
half now takes mid-band hybrids first. Board regenerated. Gates all
green; tier2 v4 74% (17/23) unchanged.


### Rulings batch 2 (owner, 2026-09-04) — Glaive, Carving, and "look at what it is played with"

Owner: "glaive can be clap because you can stack it easily without
hitting anything using q and the e has a large range"; "carving wouldn't
be a DPS on clap but might be a tanky support which pierces with e and
has royal armor to provide team mana but you can check the actual builds
and teams its played with"; "brawl is basically dps using leather
jackets while clap and kite are dps usually if not always on cloth
armor".

- **Free ramp (derived).** The dumps carry the difference exactly: Rift
  Glaive's Q Spirit Spear (target self) "applies one Spirit Spear Charge
  on you" with no condition; the sword line's Heroic Strike targets an
  enemy and Cleave grants charges "based on the amount of enemies hit".
  A Q that applies its charge to the caster unconditionally now makes the
  E's ramp FREE (`ramp_free` in the style-fit report), so the E is not a
  conditional payload. The whole spear line reads ramp-free; the sword
  line and the fist lines stay conditional. Rift Glaive is back to
  "fits" for clap at group; T32/T33 hold (they never pinned Glaive).
- **Carving Sword, checked against the harvest** as the owner asked: 180
  appearances in brawl-labelled rosters, 29 in clap, 13 kite, 8
  clap-kite, 5 brawl-clap; Royal Armor is its modal chest in every
  style (62/180 brawl, 7/29 clap), then Hellion and Judicator. So it is
  a Royal-Armor energy carrier that lives in brawl and is rare in clap —
  consistent with the ruling. Royal Armor was listed as a named-only
  item in the energy_font effect; it is now linked to the catalog item
  and Carving is a cited carrier, so the role advisory reads "brawler
  carrying energy aura". Its clap generation stays situational (the
  harvest does not contradict that); whether a plate Carving should
  DETECT as a pierce support rather than a brawler is an open book
  question (the sustained_brawler seat admits plate, so it reads dps).
- **The kits decide a split (derived, descriptive).** Measured on the
  1,690 labelled rosters: dps-class members wear leather 60% in brawl,
  cloth 52% in clap, 73% in clap-kite, 60% in kite — and the 439
  "split" rosters read 55% leather, i.e. mostly brawls the delivery axis
  could not settle. comp_identity now takes the worn kits (page passes
  GEARS_CUR; the audit passes the harvested chests): when at least half
  the dps have a known chest, a leather majority leans a SPLIT roster to
  brawl and a cloth majority to the ranged read (clap / clap-kite / kite
  by bomb share and standoff tools); plate or no majority leaves it
  split; without gears the read is unchanged. Splits on the board fall
  439 -> 190 (brawl 644, clap 366, clap_kite 259, kite 153, brawl_clap
  78). T35 pins all three. Gates green; tier2 v4 74% unchanged.

### Blind round 2 (owner, 2026-09-04) — twenty harvested rosters of 15-20

Form: the twenty rosters at the bottom of the style-roster board (sampled
label-independently from every harvested killer party of 15+, round 1's
ten excluded). Owner's calls collected before the engine's were opened:
1 kite-clap, 2 brawl (not sure), 3 clap-kite, 4 kite-clap, 5 clap, 6 brawl,
7 brawlish (not sure), 8 kite, 9 gank, 10 kite, 11 brawl-clap, 12 not sure,
13 kite-clap, 14 not sure (daggers), 15 clap, 16 clap, 17 clap-brawl,
18 brawl-clap, 19 clap-kite, 20 brawl. "Dont take my word as final."

**Before:** engine agreed on 8 of the 16 called rosters (1, 2, 4, 6, 8,
13, 15, 20). The eight disagreements came from two mechanisms, not eight:

- **Flex bombs formed a melee core.** Rosters 3, 5, 16, 17 and 19 read
  brawl because Realmbreaker / Spiked Gauntlets / Rift Glaive (flex: melee
  stat line, E landed at range) counted their damage on the melee side
  and outweighed the ranged core they were in fact part of ("realmbreaker
  would be part of clap"). The docstring had always said a flex weapon
  "never pulls against a core" — but nothing stopped three of them from
  BEING the core. The first fix (flex bombs always ranged) broke round 1
  roster 3, the owner's brawl of five Realmbreakers behind two
  Oathkeepers. Ruling as derived: a flex carrier with an UNCONDITIONAL
  GROUP payload joins whichever rigid core the roster has (ranged when the
  rigid ranged damage is at least the rigid melee damage); a flex carrier
  with a single-target or ramp-dependent payload (Bloodletter, Ursine
  Maulers, Carving Sword) commits its body and is melee.
- **The kite half saw only displacement.** Rosters 10 and 19 needed
  Icicle/Occult as standoff bodies ("occult staff to increase team
  movement ... icicle staff to slow"). Ruling as derived: a SLOW FIELD laid
  at range (slow >= 4, cast range >= 9, ground/enemy/all target) whose E
  is not itself a bomb (burst_aoe < 4 — Longbow's rain and Spiked
  Gauntlets slow but are bombs) and commits nothing is a standoff tool:
  Icicle, Arctic, Glacial, Chillhowl. Occult's corridor is claimed as
  ENGAGE and stays out — the owner's own clap10 fixture fields it beside a
  Bedrock as a pure clap, and counting it made clap10 a clap-kite.
  Standoff tools now scale one per ten members for the PURE kite as well
  (never below one; the hybrid never below two): one Icicle among
  seventeen commit bodies is a clap (roster 15).
- Two threshold corrections fell out of the same rosters, both read off
  the owner's calls rather than tuned: the hybrid bomb-share threshold
  moves 0.40 -> 0.45 (the owner's kites with tools at scale sat at
  0.39-0.44, the clap-kites at 0.46-0.51; roster 10), and the brawl-clap
  read replaces the commit-posture half (three Hallowfalls' evade sank it
  on roster 11, five Battle Bracers) with THE BALL CARRIES THE BOMB:
  melee-delivered unconditional bombs hold at least half the bomb
  points, checked from a melee core as well as the mid band.

**After:** 12 of 16 exact (1, 2, 4, 5, 6, 8, 10, 11, 13, 15, 19, 20); round
1's seven agreed rosters and the five fixtures still hold (T34); the label
distribution moves brawl 644 -> 503, clap 366 -> 665, clap_kite 259 ->
213, kite 153 -> 191, brawl_clap 78 -> 29, split 190 -> 89. The four
misses are recorded, not tuned:

- 3 (clap-kite / clap): one Bedrock in a 16-stack, bomb share exactly
  0.40. Same shape as round 1 roster 8; the per-ten rule stands.
- 5 (called clap, RE-RULED brawl): Demonfang, Dagger Pair, Carving and
  Ursine (34 melee points) against Longbow, Great Frost, Blazing, Evensong
  and Rotcaller (32), Realmbreaker and Spiked Gauntlets joining the melee
  majority by two points — a split on weapons alone. The harvest has
  every dps in leather (Hellion, Stalker, Specter) and the engine reads
  brawl by the kits. Owner, shown the chests: "I just said clap based on
  weapon alone, I didn't see the equipment, so if it's leather dps mostly
  then it's most likely brawl." Counted as an agreement; T36 pins both
  reads (split naked, brawl dressed).
- 16 (clap / brawl) and 17 (clap-brawl / brawl): Demonfang x2 + Battle
  Bracers, Battle Bracers x3, each with Realmbreaker + Spiked; the rigid
  melee core outweighs the ranged casters, so the flex bombs join it.
- 18 (brawl-clap / brawl): Demonfang x3 + Galatine x2 + Ursine; the
  Galatines are ramp bombs and the owner's own ruling keeps them out of
  the bomb count. Compare roster 6 (Galatine x4 + Great Frost x2), which
  the owner called brawl — the two calls cannot both be derived from the
  Galatine count, so the engine keeps the ruling.
- 9 was called "gank" — a 17-body killer party of Grailseeker, Claws,
  Deathgivers, Bear Paws and Infinity Blade is not a ZvZ comp at all. The
  engine has no gank label; it reads brawl. A gank read (leather +
  single-target Es + no healer core) would be a derivation of its own —
  open, not started.

T36 pins the three rules, the facts (Icicle standoff, Occult/Longbow/
Spiked/Permafrost not) and the eleven agreed rosters; round 2's twenty
battles join GRADED_BATTLES so no later form re-samples them. Gates:
golden 62/62, forge 38/38, roles 26/26, validation modes 25/25, parity
60/60 + embed, provenance 25/25, builds 54/54, interactions 37/37, patch
history 14/14, lint, display math 28/28, codec 24/24.

### Style x band rows (owner ruling 2026-09-04, "ok do it") — THE STYLE x SIZE RE-KEY, part 1

The ruling, four parts, all accepted: (1) a style x size layer BESIDE the
content templates, never a replacement — a comp declared clap at 20 is
judged against what winning claps at 20 field, the content row stays the
fallback and the only source of hard floors (weapon units); (2) only cells
with >= 40 distinct harvested rosters carry their own numbers (brawl and
clap at every band, clap-kite at 15-19 and 20, kite at 10-14 and 15-19);
the thin cells (brawl-clap everywhere, clap-kite 10-14, kite 20) borrow
their nearest filled cell and say so in the file; (3) the standing
convention (target 0.9 x p10, soft cap 1.15 x p90, dressed person units)
with engage / mobility / knockback_displace / disengage EXCLUDED until
their worn-kit claims are measured (they run 5-11x the content targets
because every boot and cape carries a claim); (4) golden re-pins and a
tier2 re-run, and the blind-round loop keeps validating the labels the
rows are keyed on.

Implementation: `pipeline/derive_style_bands.py` (explicit step, like the
samplers) writes `pipeline/templates/style_bands.yaml` from the evidence
board; `build_dataset.py` validates and ships it as `style_bands`;
`set_content` in both ports reads the band for a declared style at 10+
AFTER the content row, scaling target and soft cap linearly from the
cell's ref size (12 / 17 / 20). Two rules that fell out of building it:

- **A zero p10 is not a target.** Fitness divides by the target, and a
  tenth of winning rosters field none of anti_dive, execute, silence and
  the like. Such a capability writes a SOFT-CAP-ONLY row: the content
  target stands and the harvest soft cap applies where it clears it.
- **The rows are measured per style, so `target_mults` do not stack.**
  The first cut multiplied the band row by clap's 1.71 burst_aoe target
  modifier and read a 34.6 target where the harvest says 20.3; the
  modifier was a proxy for exactly what the harvest now states. Below 10
  and for `balanced`, the content row with its target_mults stands.

What it does to the five graded fixtures (naked, under their declared
style; the rows are dressed, so the fixtures sit low by construction):

| fixture | n | style | balanced | before | after |
|---|---|---|---|---|---|
| blap | 20 | brawl | 84.0% | 82.9% | 81.4% |
| DH P1 | 20 | clap_kite | 83.5% | 84.9% | 85.0% |
| 20v20 | 20 | clap_kite | 83.2% | 84.6% | 84.9% |
| clap10 | 10 | clap | 72.1% | 73.2% | 74.6% |
| kite10 | 10 | kite | 64.5% | 66.4% | 71.2% |

Recorded, not tuned: blap reads a point lower under brawl than under clap
or kite after the layer, because winning brawls at 20 field more
tankiness (target 58 vs the content row's 39) and sustained damage than a
naked blap supplies. Whether that is the rows or the naked measurement is
the next thing the loop should test, with a dressed blap. T37 pins the
CONTRACT (band read, no target_mults stacking, soft-only rows keep the
content target, balanced / under-10 / floors / weights untouched), never
the numbers — they move with every harvest refresh. No golden case moved:
62 -> 63/63; parity 60/60 + embed. One contract moved: validation modes V6
(the target_mults mechanism) now runs its base and synthetic engines with
the band rows stripped, because at a declared style of 10+ the rows
supersede the multiplier by design. Forge 38/38, roles 26/26, validation
modes 25/25, provenance, builds, interactions, patch history, lint,
display math, codec; tier2 v4 74% (17/23) PASS unchanged.

### The movement four, measured (owner 2026-09-04, "go ahead with your recommendation")

The style x band ruling excluded engage, mobility, knockback_displace and
disengage on my claim that "every boot and cape carries a claim" inflated
them 5-11x. Measured on 300 winning rosters of 15+, normalised to 20
bodies (medians, person units):

| capability | weapons only | dressed | of which boots | content target -> soft |
|---|---|---|---|---|
| engage | 12.8 | 17.8 | 4.0 | 4.0 -> 25.2 |
| mobility | 16.8 | 29.1 | 10.6 | 4.0 -> 34.0 |
| knockback_displace | 11.3 | 17.6 | 0.0 | 3.3 -> 40.5 |
| disengage | 8.8 | 15.6 | 6.0 | 6.3 -> 43.1 |

The claim was wrong. The WEAPON-ONLY supply already runs 3-4x the content
targets and boots add about a third; the published comps that fitted the
targets carry boots on 509 of 579 slots, so the old fit was not missing
gear. The content targets are outlier minimums off single comps (the
2026-08-29 re-fit's own note: "engage x3.50, mobility x4.55 off single
comps"); a mobility target of 4 at 20 is one member who can reposition.
The harvest p10 is the first minimum with enough comps behind it.

Ruling: the four are admitted under the same convention as the other 26
(`EXCLUDED = ()` in derive_style_bands.py; the mechanism stays). Rows at
20, clap: engage 15.3 -> 31.7, mobility 29.4 -> 52.7, knockback 9.0 ->
27.5, disengage 11.3 -> 30.8.

**The fixtures are judged dressed from here on.** The rows are measured on
dressed winners; the five graded fixtures had been read naked:

| fixture | naked | dressed (before the four) | dressed (with the four) |
|---|---|---|---|
| blap | 81.4% | 93.4% | 91.9% |
| DH P1 | 85.0% | 93.6% | 93.8% |
| 20v20 | 84.9% | 95.4% | 94.8% |
| clap10 | 74.6% | 86.2% | 86.4% |
| kite10 | 71.2% | 81.5% | 81.7% |

Every dressed fixture clears the new engage and mobility targets with room
(blap engage 33 / 17.6, mobility 52 / 35.5). The one honest miss is blap on
disengage (7 vs the brawl target 16) and knockback (5.8 vs 10.3): winning
brawls at 20 carry more escape in their bottom decile than blap does. The
re-fit notes call blap "a melee ball that deliberately carries little
escape"; it costs a point and a half and is RECORDED, not tuned — the next
blind round on brawls should ask whether the escape is real. T37 now
asserts the four have rows above twice the content minimums; T38 pins the
dressed contract (recorded kits via `pipeline/gear_join.py`, doctrine kits
for the synthetic ten-mans, dressed > naked on all five, every one clearing
engage and mobility) and never the numbers.

### One player, one vote (2026-09-04) — distinct-player floors

A harvested build is one player in one battle. Measured on the 15,165
builds from 10+ killer parties: 9,131 distinct player-weapon pairs, a
median of 0.67 voters per build, and on thin weapons one person can be
most of the sample (Heavy Crossbow: one player in 7 of 20 builds; Demonic
Staff 5 of 15; Demon Hammer 5 of 14). Doctrine floors counted sightings,
so two battles by one player cleared the weapon-tier floor of 2 and seven
battles by one player fronted Fey Shoes on Heavy Crossbow over Morgana
Shoes worn by four different people.

Change, all derivation, no ruling: `sample_parties.py` stamps every build
with a stable non-reversible player key (sha1 prefix; the name never
leaves the cache); `derive_kit_doctrine` weighs each build 1/k where k is
that player's builds on the weapon (one player, one vote per weapon),
ranks by votes, applies every floor to DISTINCT PLAYERS (KB_MIN_SEAT 3,
KB_MIN_WEAPON 2 voters; a chain step needs two different people), ships
counts as rounded votes with `players` beside them and cites
`killboard:<votes>x/<players>p`; the uniform extension floor moves from
50 builds to 35 voters — the same strictness in the new unit (61 weapons
clear it vs 60; Grailseeker's 32 builds are 23 voters and still extend
nothing, R6/R12).

Effect on the shipped doctrine: 818 weapon-slot tiers, modal item changed
in 72 (thin weapons almost entirely), 337 single-voter items dropped out
of tiers, 15 uniform extensions (was 16: Rampant's plate at 23 voters and
Hellfire Hands' cloth at 21% of votes fall away, Bow of Badon's leather/
plate at 58 voters comes in). Bloodletter's head goes from Morgana
(45 sightings, 30 people) to Soldier Helmet (48 sightings, 43 people).
Polehammer keeps Knight, 72 votes of 145. The kit audit (R24) holds at
56/61 slots agreeing with the modal, none bad. R27 pins the mechanism.
Gates green; tier2 74% unchanged.

### Kit doctrine per size band (2026-09-04)

The party-size floor of 2026-09-03 kept only 10+ killer parties in the
doctrine, which fixed the Grailseeker gank kit in ZvZ but threw the 4,798
small-party builds (3,505 voters, 69 weapons with 20+ builds) away — and a
7-man planner was being dressed in ZvZ kits scaled down. Now two DOCTRINE
BANDS: the GROUP band (10+ parties, every curated content) stays the
seat's top-level kit; the GANG band (4-9 man killer parties plus the
small-scale curated contents — ganking, hellgate 5v5, tracking 5, roads,
7-man) ships under `kit_bands.gang`, mined by the same miner with the same
one-player-one-vote floors and NO grading overrides (those were ruled on
ZvZ kits). Both engine ports read every doctrine key through `_seat_kit`,
which returns the gang band at <= 9 members (trios included) and the
group band otherwise; the chest gate, kit_options, the archetype and
observed_share all follow it. 20+ was not split from 10-19 (2,597 builds,
14 weapons with 50+ — too thin to stand alone).

Audit at size 7, every weapon with >= 30 gang builds (47 weapons, 286
slots): the kit matches the small-party modal item in 286 of 286, no bad
picks — the band is the gang modal by construction. Gang and group kits
differ where the evidence does (Hallowfall's Guardian vs Assassin Hood at
7 vs 20; Longbow's Lymhurst vs Smuggler cape). R28 pins it. No golden or
forge pin moved (they dress at 7 through the same channel, and the gang
modal happened to agree with the old scaled-down pick on the pinned
cases). Gates green; tier2 74% unchanged.

### Blind round 3 (owner, 2026-09-05) — the 10-14 band

Form: twenty rosters of 10-14 from the harvest, every graded battle
excluded (`audit_style_rosters.py --blind-sizes 10 14 --blind-round 3`).
Owner's calls, given first: 1 not sure, 2 clap, 3 clap-brawl, 4 clap-brawl,
5 clap, 6 clap, 7 clap-brawl, 8 clap, 9 clap, 10 kite-clap, 11 kite-clap;
rosters 12-20 were left uncalled ("do the rest") and stay ungraded.

**Before:** 4/10 exact (2, 5, 6, 9), 3 and 7 half-right (clap for
clap-brawl), four misses: 4 (kite: one Icicle in a 13-stack made a kite of
a 0.48 bomb share), 8 (split: Battle Bracers x2 + Demonfang against
Dawnsong and two cursed staffs, with Spiked Gauntlets and Realmbreaker
joining the melee side by a two-point edge), 10 (clap: no standoff tool),
11 (split: three Bloodletters outweighed a ranged core behind two
Bedrocks).

Every candidate rule was scored against ALL earlier pins (round 1's seven,
round 2's eleven plus the dressed roster 5, the five fixtures) before
landing — `score_rules.py` in the session scratchpad, eight combinations:

- **A lone standoff body only makes a kite of a comp that is not bombing**
  (`IDENTITY_LONE_TOOL_AOE` 0.45): below the hybrid floor of two tools, a
  single Bedrock/Icicle turns a ranged core into a kite only when the bomb
  share is under 0.45. Roster 4 -> clap; kite10 (one Bedrock, 0.26) stays
  the owner's kite; nothing pinned moves.
- **The bomb's delivery names the mid band**: a mixed roster with a real
  bomb share (>= 0.45) that is neither a hybrid (tools at scale) nor a ball
  carrying half the bomb reads clap — the mirror of "the ball carries the
  bomb". Roster 8 -> clap; round 2 roster 16 (a recorded miss) turns to
  the owner's clap too. Formerly split.
- **Flex bombs go home only to a clearly melee core** (`IDENTITY_FLEX_HOME`
  2.0): the rigid melee damage must be twice the rigid ranged damage
  before Realmbreaker / Spiked Gauntlets count melee; a two-point edge no
  longer drags a bomb comp to brawl. No pinned roster moves; the
  five-Realmbreaker ball (no rigid ranged damage) stays brawl.
- **REJECTED — utility carriers out of the numbers.** Excluding
  Bloodletter / Spirithunter damage from the axis and the mode fixed
  roster 11 but lifted round 2's rosters 8 and 10 (the owner's kites)
  over the hybrid line and lost the dressed roster 5. Not landed; the
  2026-08-23 rule (utility carriers anchor no split) stands as it was.

**After:** 8/10 exact (2, 4, 5, 6, 8, 9 pinned as agreed; 3 and 7 read clap
where the owner said clap-brawl and are not pinned). Two recorded misses:

- 10 (kite-clap / clap): Camlann Mace x2, Polehammer, Mace x2, Grailseeker,
  Hellfire Hands, Bloodletter, Spear, Energy Shaper, Fire Staff. No E the
  derivation admits as a standoff tool: Camlann's Vacuum Slash is a pull
  (clump 6), Grailseeker's Soulshaker is a ROOT FIELD at 20 m (root 4,
  catch 4) that the catch >= 4 clause excludes. **Open question for the
  owner:** is a root field laid at range — Grailseeker — a kite tool in
  the Bedrock sense (hold them there and leave)? Admitting root >= 4 at
  range with no self-move would make roster 10 a kite (one tool, bomb
  share 0.30).
- 11 (kite-clap / split): three Bloodletters at 10 damage points each
  outweigh Longbow, Permafrost, Rotcaller and Energy Shaper; two Bedrocks
  give the kite half but the bomb share reads 0.24. The rejected rule
  above is the only derivation that fixed it, and it broke two kites.

Labels on the board after the rules: brawl 415, clap 773, clap_kite 213,
kite 151, brawl_clap 29, split 109 (was 503 / 665 / 213 / 191 / 29 / 89);
`style_bands.yaml` re-derived on the new labels (every cell moved a
little; the contract pins hold). T39 pins the rules and the six agreed
rosters; the eleven battles join GRADED_BATTLES. Gates green; parity
60/60.

### Harvest refresh, first overnight run (2026-09-05) — 994 -> 2,042 battles

The scheduled task fired at 03:00 and finished both passes by 06:46 (exit
0): cache 994 -> 2,042 battles, 32,001 -> 51,125 builds, 3,590 -> 6,795
distinct parties. Everything built for blind round 3 predates it (00:33-
00:37), so the refresh is its own step and its own diff: audit ->
derive_style_bands -> build_dataset -> dashboard -> gates.

What doubled data moved:

- Labelled rosters of 10+: 1,690 -> 2,351 (brawl 568, clap 1,073,
  clap_kite 305, kite 210, brawl_clap 43, split 152). Every style x band
  cell gained; kite at 20 still borrows from 15-19; brawl at 20 sits at
  41 distinct rosters and now owns its numbers.
- Style rows: 325 targets compared, median move 2%, p90 32% (the thin
  cells). Contract pins hold (T37 pins the mechanism, never the numbers).
- Doctrine: 822 weapon-slot tiers (12 new), modal item changed in 54;
  carrier quotas within a point of before; 15 uniform extensions — Bow of
  Badon's leather/plate falls away, GRAILSEEKER'S LEATHER COMES IN (below).
- Round-3 form re-sampled as a round-4 draw from 10-14 (every graded
  battle excluded); rosters 12-20 of the round-3 form are gone with it.

Two audit pins moved with the unit, both test fixes not retunes: R24
(the ten-weapon kit audit) now counts votes, not sightings — Fists of
Avalon's Assassin Hood was 12 sightings from 6 voters and a sightings
audit called the 4-vote Soldier Helmet a bad pick; R27's "single-voter
tops" floor drops from 5 to 1 because doubled data leaves fewer of them
(good).

**OPEN — owner ruling needed (R6 / R12 / R26 red until it lands).**
Grailseeker in 10+ killer parties now reads 52 builds from 35 voters —
exactly the extension floor — with class votes plate 63% / leather 34% /
cloth 3%; Assassin Jacket is its single most-worn chest (10.7 votes) in
BOTH bands (10-14: leather 43%; 15+: leather 39%). The derived rule
(>= 25% of >= 35 voters) admits leather to Grailseeker's weapon tier, so
a Grailseeker in Hellion Jacket now reads on-uniform (`kit_match` True)
— the exact case the 2026-08-25 role-layer bug report pinned as
off-role, on the owner's plate d-tank ruling. Anti-circularity: the gate
result is a hypothesis, not a fix. Options for the owner:
(A) accept the harvest — a third of winning Grailseekers at 10+ wear
Assassin Jacket, leather is a real Grailseeker kit; re-pin R6/R12/R26 on
Incubus alone (which stays plate-only at 0% leather) and record
Grailseeker as the extension example; or
(B) hold the plate ruling — add a cited class-extension override to the
kit doctrine (roles.yaml) dropping leather from Grailseeker's tier, a
new override kind, since today's overrides address items not classes.

**RULED (owner, 2026-09-05): "yeah grailseeker can be kite or d tank.
accept."** Two rulings in one line:

- **Accept:** leather is a real Grailseeker kit at 10+. R6 is re-pinned
  on Incubus alone (0% leather, still off-role in Hellion Jacket) with
  Grailseeker's Hellion reading on-uniform; R12 expects Grailseeker's
  chest classes to be plate + leather; R26 and R27 record Grailseeker as
  the extension example at the 35-voter floor (R27 had also been reading
  the wrong id — Deathgivers — for "grail"; fixed).
- **A root field laid at range is a kite tool** (the round-3 roster-10
  question): `standoff_e` now admits an E with root >= 4 at cast range
  >= 9 (ground/enemy/all), not itself a bomb, with no engage / self-move /
  clump / heal — and a root's own catch claim does not disqualify it,
  because a root catches by holding, not by pulling (the catch clause
  still keeps Soulscythe's tornado out of the displace/slow paths).
  Admits Grailseeker's Soulshaker and Frost Staff's Freezing Wind; Morning
  Star and Trinity Spear stay out on engage/mobility. Round 3 roster 10
  now reads kite on its one Grailseeker (owner: kite-clap — half-right,
  no longer a miss); kite10 keeps its kite with two tools instead of one.
  Board after: brawl 568, clap 1,020, clap_kite 319, kite 250, brawl_clap
  42, split 152; rows re-derived. Gates green; parity 60/60.

### Kit blind rounds 1-2 (owner, 2026-09-05) — builds without labels

A new round shape, the owner's idea mid-way through the round-4 roster
form ("give me different builds for a weapon and I tell you what
playstyle it might be part of"; the roster form's calls 1-10 stand as
read — 1 support, 3 gank, 5-7 and 9 clap, 8 brawl, 10 kite-clap — and
the form is otherwise abandoned). `pipeline/kit_blind_round.py`: a
weapon's most-worn chest / helmet / boots builds from labelled 10+
rosters, one line per distinct build ordered by distinct players, the
answer being the styles of the rosters each build was worn in. Owner's
grading convention: "one build can be part of multiple styles".

**Realmbreaker (7/8).** Royal Jacket builds are ranged-style without
exception (1 brawl in 189 players); Hellion Jacket builds are brawl OR
clap (110 / 100), which the owner first read as brawl and then agreed
with ("I agree with the harvest actually. it can be brawl or clap");
Royal Armor (the energy carrier) is style-blind, 12 / 12. Two leather
chests, opposite signals: the chest ITEM separates styles where the
class cannot.

**Hallowfall (6/8).** Robe of Purity builds are ranged (brawl 0-27%, and
every brawl sighting sits under a Guardian Helmet; the Druid Cowl builds
carry one brawl in 105 players). Judicator builds read brawl to the
owner ("judicator armor has to be brawl") but the harvest had them 51%
and 38% brawl — half in claps.

**The disagreement was the label.** Owner: "very unlikely that clap
comps that use cloth armor for dps will use plate for healer unless
there are other healers not on plate". Tested: in the 190 clap-labelled
rosters with a Judicator Hallowfall the dps wore leather 56%, 95 of 190
rosters leather-majority, 48 cloth-majority. Across every label:

| label | rosters | cloth dps | leather dps | plate dps | no majority |
|---|---|---|---|---|---|
| brawl | 568 | 6 | 358 | 66 | 32 |
| clap | 1,020 | 360 | 248 | 17 | 131 |
| clap_kite | 319 | 203 | 13 | 0 | 24 |
| kite | 250 | 101 | 38 | 1 | 39 |

A quarter of "clap" was leather-dps rosters the weapons had decided on
their own (ranged-delivered bombs), so the round-2 kit rule — which fires
only on splits — never saw them.

**Ruling (owner): "I do not think clap dps will wear leather mostly. it
would mostly be cloth. it could be that there are secondary parties
which are wearing assassin jackets to be a bomb squad which is getting
marked at clap mistakenly. for leather dps it would mostly be melee and
it would be brawl. point of clap is mostly high dps which is not possible
if majority of party is wearing leather."** Landed as derived: a clap
read decided by the weapons is overruled to brawl by leather-majority
dps kits; the bomb-squad archetype (one weapon holding half the carriers
— the owner's "secondary party of assassin jackets") keeps its read.
Cloth on a brawl read is NOT ruled and stays as it was. Both ports; T40
pins it on the owner's own clap10 dressed three ways plus a four-
Permafrost squad in leather.

After: brawl 800, clap 788, clap_kite 319, kite 250 (232 rosters moved;
the 16 leather-dps "claps" left are bomb squads). The clap cell now reads
cloth 360 / leather 16; the style rows re-derived on it. Gates green.

### Per-item chest lean (2026-09-05, "let's do the per item chest")

The kit rounds showed two leather chests with opposite signals (Royal
Jacket ranged without exception, Hellion brawl or clap), so the kit
tie-break now reads the chest ITEM first and the owner's class rule
where an item has none. Derived without a loop: `audit_style_rosters.py`
labels every roster WEAPONS-ONLY (no kits), keeps only clean cores (melee
share >= 0.65 votes brawl, <= 0.35 votes ranged; the mid band and every
kit-decided read stay out), and counts distinct dps wearers per chest; a
chest with >= 20 wearers and >= 75% on one side carries that lean. Written
to `out/chest_lean.json`, shipped as `chest_lean`, read by `_chest_side`
in both ports. The table (dps wearers in clean cores):

| chest | class | wearers | brawl | ranged | lean |
|---|---|---|---|---|---|
| Hellion Jacket | leather | 785 | 487 | 332 | class (brawl) |
| Robe of Purity | cloth | 645 | 15 | 633 | ranged |
| Scholar Robe | cloth | 520 | 16 | 506 | ranged |
| Cleric Robe | cloth | 370 | 56 | 320 | ranged |
| Royal Jacket | leather | 365 | 6 | 359 | ranged |
| Assassin Jacket | leather | 307 | 134 | 181 | class (brawl) |
| Jacket of Tenacity | leather | 283 | 68 | 223 | ranged |
| Soldier Armor | plate | 240 | 168 | 79 | class (none) |
| Hunter Jacket | leather | 177 | 24 | 156 | ranged |
| Guardian Armor | plate | 154 | 106 | 50 | class (none) |
| Royal Armor | plate | 100 | 59 | 43 | class (none) |
| Judicator Armor | plate | 80 | 23 | 58 | class (none) |
| Knight Armor | plate | 39 | 10 | 30 | ranged |
| Demon Armor | plate | 28 | 3 | 25 | ranged |

Eleven chests lean ranged, none reaches a brawl lean (Hellion 62%,
Soldier 70%, Guardian 69% sit under the 75% line and keep the class
rule), sixteen are class-default. The three leather chests that lean
ranged — Royal Jacket, Jacket of Tenacity, Hunter Jacket — are the
correction: under the class rule alone they voted brawl. Board after:
brawl 628, clap 941, clap_kite 319, kite 251 (172 rosters whose dps wore
those three chests move back to clap); rows re-derived. T41 pins the
mechanism on clap10 dressed in Royal Jackets (stays clap) and Hellions
(turns brawl); T35/T40 speak `kit_lean` = brawl / ranged now. Rerun
order after a harvest: audit (writes chest_lean.json) -> derive rows ->
build_dataset -> gates. Gates green; parity 60/60.
