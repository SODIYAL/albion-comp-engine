# Albion Online Dynamic Composition Engine — Feasibility & Design

*Research date: 2026-08-12. All API claims below were verified by live requests on this date unless marked otherwise.*

---

## 1. Data Source Audit

### 1.1 Official gameinfo (killboard) API — VERIFIED LIVE

Undocumented but tolerated by Sandbox Interactive ("SBI tolerates the use of this API by 3rd parties but doesn't provide any documentation" — Tools4Albion API docs). No official ToS, no published rate limit; community convention is gentle polling (~30s intervals) with a proper User-Agent.

Base URLs (one per game server):

| Server | Base |
|---|---|
| Americas | `https://gameinfo.albiononline.com/api/gameinfo/` |
| Europe | `https://gameinfo-ams.albiononline.com/api/gameinfo/` |
| Asia | `https://gameinfo-sgp.albiononline.com/api/gameinfo/` |

Key endpoints (all verified returning JSON):

- `GET /battles?range=&limit=&offset=&sort=recent` — battle list. Each battle: id, start/end time, totalFame, totalKills, `players{}` (name, guild, alliance, kills, deaths, killFame), `guilds{}`, `alliances{}`. **No equipment at this level.** `clusterName` exists but was `null` in sampled battles.
- `GET /events?limit=51&offset=0` — rolling window of recent kill events (~last 1,000; limit ≤ 51, offset ≤ 1000). This is the firehose MurderLedger polls.
- `GET /events/battle/{battleId}?limit=51&offset=0` — all kill events inside one battle. This is how full compositions are reconstructed.
- `GET /matches/crystal` — Crystal League matches.
- Constraint: `offset + limit ≤ 10,000` on paged endpoints. Known reliability issues: intermittent 504s and occasional multi-day outages (has happened to MurderLedger).

**What a kill event contains (verified):** full killer + victim equipment — MainHand, OffHand, Head, Armor, Shoes, Cape, Bag, Mount, **Potion, Food** — each with item `Type` (e.g. `T8_MAIN_FIRESTAFF_KEEPER`, `T5_2H_SPEAR@1`), Quality, enchantment as `@N` suffix. Plus `AverageItemPower`, a `Participants[]` array where each assisting player carries **`DamageDone` and `SupportHealingDone`**, `GroupMembers[]`, `BattleId`, and `KillArea` (e.g. `OPEN_WORLD`).

**Critical limitation (verified at scale, 2026-08-12):** `ActiveSpells` and `PassiveSpells` arrays are **always empty** — 0 populated out of ~2,000 fields scanned across ~45 events on the Europe and Asia servers, identical on both the list and single-event endpoints, and no community record (wrappers, forums, code search) of the field ever carrying data. Caveats: Americas endpoint returned empty bodies the day of testing, and historical absence is an argument from silence. Practical conclusion stands: the killboard exposes *items only*; any capability that depends on ability choice is invisible in battle data and must come from default kits (§2.4).

**What this enables:**

| Question | Answer |
|---|---|
| Can complete team comps be reconstructed? | Mostly. Join `battles/{id}` roster with `events/battle/{id}` equipment. Players who never killed, died, or assisted on a kill have no equipment record (in practice a small minority in real fights). |
| Can content type be identified? | Partially, heuristically. `KillArea` distinguishes some contexts (open world, hellgate, corrupted dungeon); Crystal League has its own endpoint; the rest must be inferred from cluster names, party sizes, and time windows (e.g. castle/outpost fights occur at fixed spawn times in known clusters). No explicit "this was a castle fight" label exists. |
| Can win/loss be associated with comps? | Yes for 1v1/2v2 (clean kill outcomes — MurderLedger proves this). For group fights, "winning" must be derived heuristically (kill/death differential, fame differential, wipe detection). Noisy but usable at volume. |

### 1.2 albionbb.com — VERIFIED LIVE, highest-value third-party source

Undocumented JSON API that has **already done the composition-reconstruction work**:

- `GET https://api.albionbb.com/us/battles?minPlayers=10` (also `eu/`) — battle list.
- `GET https://api.albionbb.com/us/battles/{id}` — full battle with a `players[]` array; each player: name, guild, alliance, kills, deaths, ip, **`heal`, `damage`, `role` (pre-classified: "healer", "melee", …), and `weapon` {name, type, quality}**.

This is essentially the historical dataset this project needs, per battle, already aggregated. No published ToS or docs; the polite path is to ask in their Discord before depending on it, and to keep the raw-gameinfo pipeline as the fallback/independent path.

### 1.3 MurderLedger (now merged into AlbionOnline2D) — partially verified

- Lives at `murderledger.albiononline2d.com` (+ `-europe`, `-asia` variants).
- Polls the gameinfo `/events` firehose; stores loadouts as **hashes** (a modeling trick worth copying); computes **1v1 build usage & win-rate stats** (trailing 7-day, nightly), a **weapon-vs-weapon matchup matrix**, and 1v1/2v2 Elo leaderboards.
- Real JSON API with an OpenAPI spec (`/api/openapi.json`); author explicitly invites third-party use; API source is MIT on GitLab (`gitlab.com/albion-murder-ledger/api`). Site is behind bot protection — direct fetches from this environment returned empty; treat endpoints as documented-but-unverified here.
- **Scope limitation:** its statistics are 1v1/2v2 only. Useful as a *meta-usage and matchup prior*, not as group-comp data.

### 1.4 Static game data — ao-bin-dumps (github.com/ao-data/ao-bin-dumps) — VERIFIED

Actively maintained per patch (last push 2026-06-30). No license (dumped game data; community use tolerated under SBI's long-standing "look and analyze is OK" stance).

- `formatted/items.json` / `items.txt` — canonical `UniqueName ↔ localized name` mapping, including `@N` enchantment variants. Killboard `Type` strings join to these exactly (strip `@N` to get the base item; enchantments don't change abilities).
- `items.json` — each weapon carries `@activespellslots` and a `craftingspelllist` of `craftspell` entries: **the full set of Q/W/E abilities equippable on that weapon**. This is the weapon→abilities linkage every community tool uses.
- `spells.json` (13.8 MB) — machine-readable ability data: cooldowns, cast times, and effect trees with numeric buffs (e.g. `bonusccdurationvsplayers: 0.1`, `crowdcontrolresistance: 0.2`). Effect semantics are nested spell-graphs — extracting "2.4s stun" requires real parsing.
- **Auto-classification shortcut:** spell descriptions in `localization.json` embed the game's own markup tags — `[dmg]`, `[heal]`, `[cc]`, `[debuff]`, `[buff]`, `[mobility]`, `[other]` — so every ability can be coarsely auto-tagged by function without interpreting effect trees.

### 1.5 Supporting sources

| Source | Verdict |
|---|---|
| **Albion Data Project** (albion-online-data.com) | Market/gold prices only — nothing combat-related. Verified live. Rate limits 180 req/min. Only relevant later for a "cost of this build" feature. |
| **OpenAlbion** (api.openalbion.com) | Structured weapon→spells API (`/api/v3/spells/weapon/{id}`, grouped Q/W/E/passive with cooldown/range/description). Docs verified; live calls returned empty from this environment — retest or self-host (open source, Laravel). Wiki-derived data. |
| **Official wiki** (wiki.albiononline.com) | One page per weapon line documenting all Q/W options + each weapon's unique E with numbers ("reduces healing received by 20% for 5s"). Consistent MediaWiki HTML, scrapeable. No explicit reuse license — fine as internal reference, don't republish verbatim. |
| **render.albiononline.com** | Item/spell icons: `/v1/item/{UNIQUE_NAME}.png` (supports `@N`), `/v1/spell/{name}.png`. Verified. Use for all UI icons. |
| **albionbattles.com** | Battle-report frontend over gameinfo; multi-battle merge; no API found. UX reference only. |

### 1.6 Competitive landscape — the gap is real

- **albioncompo.com** — closest competitor: manual comp builder with sharing/ratings for ZvZ/HG/Ava/mists. **No analytics, no recommendations.** Small (~1.2K comps created).
- metabattle, roguesnest, albionfreemarket/builds, ezalbion — editorial build guides or single-loadout planners.
- MurderLedger — statistics, but 1v1/2v2 only.

**Nothing combines battle data + capability modeling into dynamic team-composition recommendations. The proposed tool occupies empty space.**

### 1.7 What must be maintained by hand

Battle data tells us *what* people wear and *whether* they won — it cannot tell us what a weapon *does*. No structured dataset classifying weapons by function exists anywhere. Therefore the core knowledge asset of this project is a **hand-curated capability table**: ~35 weapon lines / ~120 weapons / ~25 capabilities, seeded automatically (item taxonomy + `[cc]/[heal]/[mobility]` ability tags + wiki numbers) and then human-corrected. This is very manageable (a few thousand cells, most zero) and is the defensible IP of the tool. ao-bin-dumps patch diffs signal when to re-review a weapon.

---

## 2. Capability Taxonomy

### 2.1 Design principles

1. **Capabilities, not roles.** A weapon is a vector of functional scores, not a "tank/healer/DPS" label. Roles fall out of the vector (a "tank" is anything scoring high on Frontline + Engage/Peel).
2. **Provenance on every score.** Each nonzero score is tagged with *where it comes from*: `E` (inherent to the weapon's unique E), `QW` (available via a common Q/W choice), `GEAR` (typically supplied by standard armor pairing), `PASSIVE`. Since killboard data can't see ability choices, provenance encodes confidence: `E` scores are certain; `QW`/`GEAR` scores are "available if built for."
3. **Scores are 0–3**, not booleans: 0 = none, 1 = minor/situational, 2 = solid, 3 = defining strength. Coarse on purpose — finer granularity is false precision and makes curation contentious.
4. **Evidence rule (added after review caught two fabricated scores).** Every nonzero score must cite the specific ability that provides it — the spell's UniqueName from ao-bin-dumps (or the gear item, see below). A *weapon's* sheet may only contain capabilities delivered by the weapon's own Q/W/E/passives (its `craftingspelllist`). Capabilities provided by helmets, armor, boots, capes, potions or food live on *those items'* sheets — never smuggled onto a weapon. The two error classes this kills, both found in review: attributing a gear capability to a weapon (1H Mace "purge" — no mace Q/W/E removes buffs), and misattributing effect direction (Longbow "knockback" — bow Frost Shot displaces the *user*, not enemies). An uncited score is invalid by definition; the pipeline enforces this mechanically (§6.3).

### 2.2 The capability set (v1: 27 capabilities, 6 groups)

*Added 2026-08-12: `anti_zone`. The Crystal Holy Staff's E (`HOLY_DISPEL`,
"Sanctify") removes enemy-placed ground areas. That is neither `purge` (which
strips buffs off enemy **units**) nor `cleanse` (which strips CC and debuffs off
**allies**) — three different mechanics that happen to share the verb "remove".
It is the counter to `zone_control`, not an instance of it, and folding it into
`purge` would let a comp look purge-covered when it has no answer to a Frost
comp's zones.*

| Group | Capabilities |
|---|---|
| **Sustain** | `heal_burst`, `heal_sustain`, `cleanse` (remove CC/debuffs from allies), `self_sustain` |
| **Frontline** | `tankiness` (survive focus), `engage` (initiate/dive), `disengage` (get the group out), `anti_dive` (punish divers), `zone_control` (deny/hold space) |
| **Control** | `stun`, `root`, `silence`, `knockback_displace`, `slow`, `clump_create` (stack enemies for AoE), `peel` (protect own backline) |
| **Denial** | `purge` (strip enemy buffs), `anti_zone` (remove enemy ground areas), `heal_reduction`, `resist_shred` (pierce/armor reduction), `energy_drain` |
| **Damage** | `burst_st` (single-target burst), `burst_aoe`, `sustained_dps`, `execute` |
| **Tempo** | `mobility`, `catch` (run enemies down), `buff_allies` |

**Directionality rule (added after review):** every effect capability must be tagged by *target direction*. `knockback_displace` means displacing **enemies**; an ability that knocks the **user** back (e.g. bow-line Frost Shot) is `self_reposition` — it contributes to mobility/disengage for that player, never to enemy displacement. The same rule disambiguates other pairs the killboard can't distinguish: heals on self vs. allies, damage-reduction on self vs. group. Curation lint: any score justified by a self-targeted ability may only feed self-directed capabilities.

Notes: "CC" is deliberately split (stun/root/silence/displace/slow) because content templates need them separately — a comp with only roots still loses to a comp it can't interrupt. `clump_create` and `peel` sit in Control because they are the two directional uses of CC (offensive stacking vs. defensive protection); a weapon's raw CC often feeds both but not equally (Great Hammer clumps, Heavy Mace peels).

### 2.3 Example capability sheets

Scores shown as `value(provenance)`; omitted = 0.

**Heavy Mace** — tankiness 3, peel 3(E: Battle Howl + W: Guard Rune), silence 3(E: Battle Howl), purge 3(E: Battle Howl — purges before the silence), engage 2(W: Snare Charge), zone_control 2, slow 1(Q: Sacred Ground), sustained_dps 1. *(Corrected: purge is inherent to the E, not a W choice as first drafted.)*
**1H Mace** — tankiness 2, engage 2(E: Deep Leap), stun 2(E: Deep Leap), mobility 2(E: Deep Leap), peel 2(W: Guard Rune), root 1(W: Snare Charge), sustained_dps 1. *(Corrected: earlier draft listed purge — no mace Q/W nor Deep Leap removes buffs. Wiki-verified against the mace line's full ability list.)*
**Permafrost Prism** — burst_aoe 3(E), zone_control 3(E), slow 2(QW), clump_create 2(E), root 1(QW), mobility 1(QW), tankiness 1.
**Hallowfall** — heal_burst 3(E), heal_sustain 2(QW), mobility 2(E), cleanse 2(QW|GEAR), self_sustain 2, buff_allies 1.
**Longbow** — burst_aoe 2(E: Rain of Arrows), zone_control 2(E), slow 2(E), sustained_dps 2, root 1(W: Ray of Light), resist_shred 1(PASSIVE: Piercing Arrows — auto-attacks stack a Defense debuff). *(Twice corrected against game data: knockback_displace removed — Frost Shot pushes the user, not enemies; and resist_shred was wrongly filed as a W ability — no bow Q/W shreds; it exists only as an auto-attack passive, hence downgraded to 1. See `pipeline/sheets/longbow.yaml` for the lint-verified sheet.)*
**Witchwork Staff** — burst_aoe 2(E), clump_create 2(E), energy_drain 2(QW), sustained_dps 2, heal_reduction 1(GEAR), zone_control 1.
**Great Holy** — heal_burst 3(E), heal_sustain 3, cleanse 2(QW), buff_allies 1, mobility 0 — contrast with Hallowfall: same "healer" role, opposite mobility profile, which is exactly why roles alone are insufficient.

*(Illustrative, not final — final numbers come from the curation pass in Phase 1.)*

### 2.4 Handling ability- and gear-dependent capabilities

Sheets exist at the **item** level — weapons *and* gear pieces each carry their own evidence-backed capability sheet. An **archetype** composes them: weapon sheet ⊕ chosen-spell subset ⊕ gear sheets for its default kit. So "purge" in a 1H Mace archetype can only appear if a *gear item in that kit* provides it, and the UI attributes it to that item, never to the weapon.

Each weapon gets a **default kit** per content type: assumed Q/W choices + canonical armor pairing. The capability vector used in scoring = weapon E/passives + the kit's selected Q/W spells + the kit's gear items' sheets.

**Where default kits come from (researched 2026-08-12).** Battle data can never supply them (§1.1), but two editorial/community sources publish exact per-slot spell choices tagged by content type, and both are harvestable:

- **Metabattle** (metabattle.com/albion) — ~120 curated builds via an *open MediaWiki API*; each page's `{{Build equipment}}` template lists Q/W/E + armor actives/passives per slot with game-mode tags. CC BY-SA licensed. Fully automatable (one API call per build).
- **Albion Free Market** (albionfreemarket.com/builds) — 4,478 community builds using *game-native spell IDs* that join directly onto our ao-bin-dumps parser output; six tag axes incl. content and group size; upvotes as quality filter. Server-side-rendered pages, scrapeable via filter URLs; ask their Discord before bulk harvest.

Harvest strategy: kits where **Metabattle and top-voted AFM builds agree** become high-confidence defaults; disagreements or gaps go to human curation. This converts default kits from pure hand-curation into harvest + reconcile + review — and the evidence rule still applies: harvested kits list concrete spell IDs, so the lint validates every one against the weapon's real spell list. The UI shows conditional capabilities distinctly ("cleanse — if running Cowl of Purity") and lets an advanced user toggle kit assumptions. This is how the system stays honest despite the killboard's empty `ActiveSpells`.

---

## 3. Content Requirement Model

### 3.1 Structure

A content template is **not** a list of required roles. It is:

```yaml
content: castle_outpost
party_sizes: [5..10]           # template interpolates across sizes
requirements:                   # target supply per capability, per player count
  heal_sustain:   { target: 0.45/player, weight: 10, hard_floor: 1 unit at n>=4 }
  tankiness:      { target: 0.35/player, weight: 9 }
  peel:           { target: 0.30/player, weight: 8 }
  burst_aoe:      { target: 0.55/player, weight: 8 }
  clump_create:   { target: 2 units flat, weight: 7 }
  engage:         { target: 2 units flat, weight: 7 }
  purge:          { target: 2 units flat, weight: 6 }     # castle fights are purge-heavy
  heal_reduction: { target: 2 units flat, weight: 6 }
  resist_shred:   { target: 2 units flat, weight: 5 }
  cleanse:        { target: 1 unit flat,  weight: 5 }
  disengage:      { target: 1 unit flat,  weight: 4 }
  mobility:       { target: 0.25/player, weight: 3 }
caps:                           # diminishing/negative returns
  heal_sustain:   { soft_cap: 0.6/player }   # 3rd healer in 7 hurts
  clump_create:   { soft_cap: 4 units }
antisynergies:
  - [engage-heavy, disengage-zero]           # all-in comps flagged, not forbidden
```

"Units" are summed capability scores across the party (a 3 counts as 3 units). Some needs scale with party size (healing, frontline, damage); others are threshold capabilities where one copy is enough (cleanse, disengage) — flat targets express that.

### 3.2 Utility curves, not checklists

For each capability `c`, satisfaction is a concave function of supply:

```
U_c(s) = weight_c × min(1, s / target_c)^γ,  γ ≈ 0.6–0.8
       − overcap penalty if s > soft_cap_c (linear beyond cap)
```

Concavity gives the correct behavior automatically: the first unit of healing in a heal-less comp is worth far more than the third healer's marginal unit. Composition fitness = `Σ_c U_c(supply_c)`. "Biggest weaknesses" = capabilities ranked by `weight_c − U_c` (weighted unmet need) — exactly what the dashboard bars display.

### 3.3 Initial content templates (v1)

Castle Outposts, Castle fights, Open-world skirmish (5–10), Roads of Avalon (7/10/20), Hellgate 2v2, Hellgate 5v5, Small-scale ganking, Anti-gank/escort, ZvZ (20+, simplified in v1), Crystal Arena 5v5, Static dungeon PvE (adds PvE-specific needs: sustained_dps, heal_sustain, low purge weight). Templates are data (YAML), not code — tunable per patch without redeploys, and per-size interpolation means 7-man Roads and 10-man Roads are one template.

Templates are seeded from community knowledge (guild shotcaller conventions, meta guides) and later tuned against battle statistics (§8).

---

## 4. Recommendation Engine

### 4.1 Core algorithm: explainable marginal gain

Recommending "the next player" is a greedy step in a set-function optimization:

```
For each candidate weapon w (with its default kit for this content):
  Δ(w) = Fitness(party ∪ {w}) − Fitness(party)          # marginal capability gain
  Score(w) = α·Δ(w) + β·Synergy(w, party) + δ·MetaPrior(w, content) − ρ·Redundancy(w, party)
```

Suggested v1 weights: α = 0.55, β = 0.20, δ = 0.15, ρ = 0.10. (The user's proposed 35/25/20/10/10 split is directionally right; "historical performance" and "meta usage" are merged into MetaPrior until we have enough of our own battle data to separate them — see §8.)

- **Δ(w)** is inherently explainable: it decomposes into per-capability contributions ("+ heals a comp with 0 healing: +9.2; + cleanse: +2.1"). These per-capability terms *are* the "why" text, generated, not templated.
- **Synergy(w, party)** — pairwise bonus matrix (§4.2).
- **MetaPrior(w, content)** — usage/win-rate prior from battle statistics; starts as a small hand-set list (guards against recommending technically-fitting but practically-dead weapons), later data-driven.
- **Redundancy(w, party)** — penalty for duplicating a capability already past soft-cap, and for exact-weapon duplicates where that matters (three Permafrosts each add zone control on paper, but their E's share the same cooldown window and space).

Output: top recommendation = argmax Score, plus 2–4 alternatives with their own reason strings, grouped by the dominant capability they add ("Healer options: Hallowfall, Blight, Great Holy").

### 4.2 Synergies and overlap

Two mechanisms, kept separate:

1. **Capability-level synergy (automatic).** Some capability *pairs across players* are worth more than their sum: `clump_create × burst_aoe` (stack → nuke), `engage × catch`, `resist_shred × burst_st`, `heal_reduction × sustained_dps`. Encoded as a small pair-bonus table at the capability level (~10 entries), so it applies to any weapons providing those capabilities — no per-weapon-pair maintenance.
2. **Weapon-level synergy/antisynergy (curated + learned).** Specific famous combos (e.g. a defined E-chain wombo) and known non-stacking cases. Starts as a short curated list; §8 shows how battle co-occurrence lift extends it.

Overlapping roles are handled by the math, not special cases: a Nature Staff in a comp that already has a Great Holy contributes its healing into a near-capped `heal_sustain` (small Δ) but its `sustained_dps`/utility still counts — so it naturally ranks as a *second-support flex*, not a "healer".

### 4.3 Worked example (user's scenario)

Party: Longbow, Witchwork, Permafrost. Content: Castle Outpost, size 7. Using §2.3 sheets and §3.1 template:

Supply so far: burst_aoe 7, zone_control 5, clump_create 4, slow/CC moderate, resist_shred 2, energy_drain 2 — vs. heal 0, tankiness ~1, peel 0, cleanse 0, purge 0, engage 0, disengage 0.

Weighted unmet need ranks: `heal_sustain` (10 × fully unmet) > `tankiness` > `peel` > `engage` > `purge`. Candidate deltas: Hallowfall Δ ≈ heal(large) + cleanse + mobility; Great Holy Δ ≈ heal(large) + cleanse, no mobility; Heavy Mace Δ ≈ tankiness + peel + silence + purge, no heal. Healing's weight and total absence make any healer dominate → **recommend Healer; options Hallowfall / Great Holy / Blight**, reason auto-generated from the Δ terms ("your comp has strong AoE damage and zone control but zero sustain…"). After adding Hallowfall, `heal_sustain` is near target; the next argmax flips to Heavy Mace-class weapons (tankiness+peel+purge in one slot beats splitting them). This reproduces the user's intended UX exactly — from the model, not from scripted rules.

### 4.4 Edge cases where naive recommendation fails (and mitigations)

1. **Greedy trap / last-slot problem.** Greedy per-slot picks can strand the final slot needing three capabilities no single weapon provides. Mitigation: at each step, also run 2-step lookahead ("beam" of top-5 candidates) and warn: "If you take a 4th DPS now, no single weapon can cover peel+cleanse+disengage later."
2. **Ambiguous weapons.** Nature/Holy hybrids, Ironroot, 1H Arcane run as damage or support depending on kit. Mitigation: such weapons have *multiple archetypes* (weapon × kit), each with its own vector; the engine recommends an archetype, displayed as "Nature Staff (support kit)".
3. **Capability visible in data, absent in fight.** Killboard shows a Hallowfall but not whether it took cleanse. Mitigation: provenance tags + default kits (§2.4); never claim certainty for QW/GEAR capabilities.
4. **Party-size discontinuities.** 2nd healer is wrong at 5, mandatory at 10. Handled by per-size targets, not fixed ratios — but templates must be validated at each size, not interpolated blindly across breakpoints.
5. **Enemy-dependent needs.** Purge is worthless against comps with no buffs; anti-clump matters only vs. clump comps. V1 scores against the content's *expected meta*, encoded in template weights; a later "expected enemy comp" input can re-weight Denial capabilities dynamically.
6. **Meta-dead but on-paper-perfect weapons.** Pure capability math will recommend statistically terrible weapons. MetaPrior term guards this; conversely a *pure* stats engine only ever recommends the meta — the α/δ balance is the point of the hybrid.
7. **IP/economy and player skill.** A recommendation the player can't afford or can't pilot (e.g. Great Arcane requires shotcalling coordination) is useless. V1: show difficulty/cost tags on recommendations; don't model it in scoring yet.
8. **Mirror-match blindness.** Optimizing your comp in isolation ignores that the same content hosts rock-paper-scissors comps. Out of scope for scoring v1; surfaced honestly in UI copy ("strong general-purpose comp" not "winning comp").
9. **Patch drift.** Every balance patch invalidates curated numbers slightly. Mitigation: ao-bin-dumps diff triggers a review checklist of changed spells → affected weapons.

---

## 5. MVP Decision

**Option C — weapons first, structured so equipment comes later — with one refinement: the internal unit is the *archetype* (weapon + default kit per content), not the bare weapon.** Bare weapons underdetermine capabilities (edge case 2); full builds explode the curation and UI surface (~120 weapons × helmets × armors × boots). Archetypes keep the UI weapon-simple while making kit assumptions explicit and extensible: adding equipment analysis later = letting users override the default kit, same data model.

**MVP cut line:**

- IN: 3–4 content types (Castle Outpost, Hellgate 5v5, Roads 7, open-world 5–10), party sizes 2–10, full capability engine + recommendations + explanations, ~60 most-played weapons (covers >90% of actual usage — verify against albionbb frequency data), curated synergy/meta lists, static client-side app.
- OUT (later phases): ZvZ-scale templates, equipment/ability customization, live battle-data ingestion, enemy-comp counter-picking, accounts/sharing.

**Notably: the MVP needs no backend at all** (§6) — the entire dataset (~120 weapon vectors + templates + synergy tables) is a few hundred KB of static JSON, and scoring is trivial computation. This makes the MVP a static React SPA, free to host, with the statistics pipeline added as Phase 3 without rearchitecting.

---

## 6. Architecture

### 6.1 Phases

```
Phase 1 (MVP)        Phase 2                     Phase 3
─────────────        ─────────────               ─────────────
Static SPA           + Data pipeline (offline)   + Stats service
React/TS             ao-bin-dumps parser         Ingest gameinfo/albionbb
capability JSON  ←   wiki/OpenAlbion enricher    battle labeling + outcomes
scoring in client    curation UI (internal)      win-rate lift → MetaPrior JSON
                     versioned data releases     nightly rebuild of static JSON
```

The stats service never serves user traffic — it *compiles* statistics into the same static JSON the SPA consumes. User-facing latency stays zero; API fragility (gameinfo 504s/outages) never touches users.

### 6.2 Data model (works as SQLite/Postgres in the pipeline, exported to JSON for the client)

```sql
weapons(id, unique_name, localized_name, line, tier_agnostic_key)
capabilities(id, key, grp, description)
items(id, unique_name, slot ENUM(mainhand,offhand,head,armor,shoes,cape,potion,food))
item_capabilities(item_id, capability_id, score SMALLINT,
                  evidence_spell VARCHAR NOT NULL,      -- spell UniqueName or item self-ref
                  provenance ENUM(E,QW,GEAR,PASSIVE),
                  direction ENUM(enemy,ally,self),       -- directionality rule, §2.2
                  note)
archetypes(id, weapon_id, content_class, kit_json, is_default)
  -- kit_json lists concrete spell IDs + gear item IDs; archetype capabilities are
  -- COMPUTED by composing item_capabilities of its members, never stored by hand
content_types(id, key, name)
content_requirements(content_id, capability_id, target_per_player REAL, target_flat REAL, weight, soft_cap, hard_floor)
capability_synergies(cap_a, cap_b, bonus)
weapon_synergies(weapon_a, weapon_b, bonus, source ENUM(curated,learned), evidence)
-- Phase 3:
battles(id, server, started_at, content_label, label_confidence, size_a, size_b, outcome_json)
battle_players(battle_id, player_hash, side, weapon_id, ip, damage, healing, kills, deaths)
weapon_content_stats(weapon_id, content_id, window, usage_rate, win_lift, sample_n)
```

### 6.3 Static-data pipeline (Phase 2, mostly automatable)

1. Pull ao-bin-dumps → parse `items.json` (weapon catalog, `craftingspelllist`) + `localization.json` (`[cc]/[heal]/[dmg]/[mobility]` tags per spell) → auto-seed capability suggestions per weapon.
2. Enrich numbers from wiki scrape or self-hosted OpenAlbion.
3. Curation pass in a simple internal editor (or just YAML in git — reviewable, diffable, community-PR-able).
4. **Evidence lint (mandatory CI gate).** For every nonzero capability score, verify mechanically: (a) the cited `evidence_spell` exists in that item's `craftingspelllist` in ao-bin-dumps — kills gear-capability-on-weapon errors like "1H Mace purge"; (b) the spell's `[cc]/[heal]/[dmg]/[buff]/[debuff]/[mobility]` localization tags and description keywords are consistent with the claimed capability class (a `purge` claim requires buff-removal language; a `knockback_displace` claim requires an enemy-targeted effect) — kills direction errors like "Longbow knockback"; (c) every archetype's kit references only spells its weapon can equip and items that exist. Lint failures block the data release.
5. Release as versioned JSON (`data-v2026.08.1.json`); the SPA pins a version.

---

## 7. Dashboard

Single-page flow matching the user's sketch, with these behaviors specified:

1. **Setup:** content type + target size. 2. **Party builder:** add weapons via search (icons from render.albiononline.com); each row shows the weapon's top-2 capability contributions as its "primary function". 3. **Analysis panel:** capability bars = `supply/target` per capability, grouped by the 6 groups; bars past soft-cap render in a warning color (over-stacking is a real failure mode, show it). 4. **Weaknesses:** top-3 by weighted unmet need, in plain language. 5. **Recommendation card:** top archetype + reason bullets generated from Δ terms, 2–3 alternatives, conditional capabilities marked ("cleanse if running X"), one-click add → instant recalculation (all client-side, no latency). 6. **Lookahead warning** when the greedy trap (§4.4.1) is detected. 7. Shareable URL encoding content+party (compare comps by sharing links; later, save/vote à la albioncompo).

---

## 8. Learning From Battle Data Over Time (Phase 3)

1. **Ingest.** Poll gameinfo `/battles` + `/events/battle/{id}` per server (gently, resumable, outage-tolerant) — or bootstrap from api.albionbb.com (with maintainer blessing) since it already merges rosters + weapons + damage/heal/role.
2. **Label content.** Heuristic classifier per battle: party sizes, `KillArea`, cluster name (castle/outpost clusters, Roads clusters, hellgate flag), time-of-day (outpost spawn windows), + Crystal endpoint. Each label carries a confidence; low-confidence battles are excluded from stats rather than polluting them.
3. **Label outcome.** Kill/fame differential + wipe detection → win/loss/inconclusive per side. Inconclusive is a first-class label (many open-world battles have no clean winner).
4. **Compute, with shrinkage.** Per content type and rolling window: weapon usage rate; weapon win-lift vs. baseline; capability-mix win curves (does realized `heal supply/target ≈ 1.0` actually win more? — this *validates the templates themselves*); weapon-pair co-occurrence lift → promote to `weapon_synergies(source=learned)`. All rates get Bayesian shrinkage toward the prior (small-sample weapons must not produce confident garbage), and minimum-n gates before anything surfaces.
5. **Feed back.** Nightly job recompiles `MetaPrior(w, content)` and template-tuning suggestions into the static JSON. Template changes stay human-approved (statistics propose, curator disposes) — this keeps the explainability contract: every recommendation reason remains a capability statement, optionally reinforced by "and it's winning: +6% win lift in Castle fights this month (n=1,240)".
6. **Honest ceiling.** Battle data can never reveal ability choices, discipline, or shotcalling — statistical signals will always be confounded by *who* plays meta weapons (good players pick good weapons). Treat win-lift as a prior-adjuster (δ ≈ 0.15), never the primary term. That is why the hybrid design, with the capability model as the backbone, is the correct architecture rather than a stopgap.

---

## 9. Feasibility Verdict & Next Steps

**Feasible.** Every data dependency verified: equipment-level battle data exists (gameinfo, verified live), an already-aggregated composition dataset exists (albionbb, verified live), weapon→ability metadata is automatable (ao-bin-dumps + wiki), and no existing tool does this. The one hard limitation — ability choices are invisible in battle data — is designable-around via archetypes/default kits, and the one hard dependency — the curated capability table — is small (~thousands of cells) and mostly auto-seedable.

Suggested order of work:

1. Build the ao-bin-dumps parser → weapon catalog + auto-seeded capability suggestions.
2. Curate capability sheets for the top ~60 weapons (validate the top-60 list against albionbb usage frequencies) + 3 content templates.
3. Implement scoring + the worked-example test cases as unit tests (§4.3 is test #1). *Update 2026-08-12: a throwaway prototype of the scoring model now exists and passes 9/9 golden cases — see `tests/VALIDATION.md` and `tests/prototype_engine.py`. Note: hard floors (§3.1) proved load-bearing; without them, breadth weapons out-rank critical healers.*
4. Ship the static SPA MVP.
5. Then, and only then, the stats pipeline.

