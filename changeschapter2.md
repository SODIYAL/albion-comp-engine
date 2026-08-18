You are working in my Albion Online composition-builder repository. Implement the next chapter: a trustworthy, reproducible system for real item stats and real weapon builds.

Do not stop at an audit or plan. Implement the scoped changes, add tests, rebuild the appropriate generated artifacts, and report exactly what changed.

PRE-FLIGHT SAFETY

1. Inspect `git status`, `git diff`, repository instructions, and recent commits before editing.
2. Preserve all existing/in-progress changes. Do not reset, checkout, revert, or overwrite unrelated work.
3. If `pipeline/templates/composition.yaml` exists, verify the template loader does not mistakenly treat it as a content template before running generators.
4. Record the test baseline before changing anything.
5. Do not commit or push unless I explicitly request it.

PRIMARY GOAL

Create a versioned evidence layer that keeps these concepts separate:

1. Game facts: items, spells, effects, ranges, cooldowns, tiers, etc.
2. Published builds: caller sheets, MetaBattle, manual Armory entries, approved community sources.
3. Observed loadouts: companion or battle/killboard sightings.
4. Canonical builds: human-reviewed defaults for a precise content, party-size range, style, role, and weapon.

Raw popularity, killboard sightings, or community submissions must never automatically become “ideal” recommendations.

A. MAKE GAME-DATA INGESTION REPRODUCIBLE

The current item pipeline follows moving `ao-bin-dumps/master`, caches indefinitely, and does not record enough provenance. Fix this.

- Pin all item, spell, localization, and Armory configuration inputs to one exact `ao-data/ao-bin-dumps` commit.
- Fetch every related input from that same commit. Do not mix a downloaded `items.json` with spell data from an unrelated local clone.
- Add a source manifest containing at least:
  - repository
  - commit SHA
  - commit timestamp
  - fetch timestamp
  - schema/adapter version
  - SHA-256 of every source file
  - environment/server where applicable
  - related Albion patch/version when known
- Cache by commit, not as an anonymous forever-cache.
- Release builds must fail closed if required inputs, hashes, schema versions, or curated-weapon coverage are missing or inconsistent.
- Offline tests must use checked-in fixtures and never require live network access.
- Generated outputs must be deterministic.
- Clearly label raw values as base values. Do not invent tier/IP/quality scaling when the dumps do not provide a verified formula.

Also fix existing normalization weaknesses:

- Preserve nested enchantment records.
- Store tier, enchantment, quality, and IP separately.
- Do not discard meaningful zero-to-nonzero transitions.
- Validate cross-tier slot/category consistency.
- Preserve stable raw item and spell IDs.
- Make tier parsing structurally correct rather than depending on a single-digit regex.
- Catalog inclusion must not depend on whether an icon downloaded successfully.
- Avoid embedding the complete item-stat payload twice in the dashboard.

B. REMOVE THE UNSOUND RANGE RULE

`pipeline/build_dataset.py` currently turns basic-attack `attackrange >= 9` into permanent `ranged_presence`, including in `loadout.always`.

Remove this behavior.

Basic-attack range is not evidence that a weapon’s selected Q/W/E delivers useful ranged AoE damage. It incorrectly benefits weapons such as one-hand Cursed Staff and Chillhowl.

Replace it with an explicit, auditable model based on the selected spell:

- spell UniqueName
- cast/projectile range
- radius or area geometry
- maximum targets where available
- delivery type
- cooldown
- whether the damage belongs to the selected Q, W, or E
- explicit curated evidence when structured game data is insufficient

If these facts are unavailable, mark the capability unknown. Do not infer it from autoattack range. Every derived scoring capability must have evidence and must participate in release validation.

C. CREATE A CANONICAL BUILD SCHEMA

Production build data must no longer live in `tests/meta_comps.yaml`.

Create normalized entities or equivalent structures for:

- `source_snapshot`
- `game_patch`
- `published_build`
- `published_comp`
- `loadout_observation`
- `canonical_build`
- `validation_result`

Each complete build must support:

- stable build ID
- exact weapon/item UniqueNames
- head, armor, shoes, cape, offhand, potion, food, and optional mount
- tier, enchantment, quality, and IP separately
- exact Q/W/E/passive spell UniqueNames
- armor active/passive spell UniqueNames
- offhand/consumable effects where applicable
- structured alternatives rather than slash-delimited text
- conditions explaining when an alternative is used
- role
- content
- style
- party-size minimum and maximum
- core, optional, or replacement status
- source kind, source URL, source record/revision, author
- published/updated/observed/ingested timestamps
- attributed patch and snapshot commit
- license/attribution status
- approval status
- freshness status
- confidence by dimension, not one unexplained average

Required confidence dimensions should include item mapping, spell mapping, patch, content context, party size, source independence, loadout completeness, and outcome where relevant.

Use stable UniqueNames as authoritative. Numeric selections such as `q3`, `w2`, or `p1` may be retained as raw source data or derived display values, but must not be the canonical identity.

Validate that every chosen spell is actually equippable on that exact item at the attributed snapshot. Fix or quarantine invalid references such as an Enigmatic Staff passive index that exceeds the current passive pool.

Unknown data must be stored explicitly as unknown. Never silently choose option 1 or fabricate a spell.

D. BUILD SOURCE ADAPTERS

1. MetaBattle

Implement the first automated published-build adapter using MetaBattle’s MediaWiki Action API, not brittle HTML scraping.

Source:
https://metabattle.com/albion/ZvZ_Builds

Capture:

- page ID/title
- revision ID and timestamp
- source URL
- categories
- raw build template data
- exact gear
- selected abilities/passives
- consumables
- alternatives
- claimed patch/freshness
- CC BY-SA attribution metadata

Use checked-in API-response fixtures for tests. Network fetching must be an explicit command and not part of normal builds or CI.

Map names to exact Albion UniqueNames. Ambiguous or unresolved records must enter a review/quarantine report rather than silently resolving to the first match.

Imported records begin as `candidate`, not `approved`.

2. Official in-game Armory

The official Armory is the strongest conceptual source because it uses real gameplay and exposes activity, group size, gear, abilities, consumables, popularity, and performance:

https://albiononline.com/update/radiant-wilds

There is no documented public export/API. Do not reverse-engineer game traffic or private endpoints.

Instead, implement a manual Armory import format and validator that records:

- activity
- official group-size tag
- complete build and alternatives
- performance/popularity fields if manually supplied
- recent versus established
- capture date
- patch
- source/citation or screenshot reference
- reviewer

3. Caller and companion data

- Move real caller builds into production build-data files.
- Import builds even when some skills are unknown; mark their completeness rather than silently skipping them.
- Normalize companion observations into the same item/spell schema.
- The companion’s exact roster, equipment, spell UniqueNames, IP, timestamp, and source are the strongest existing direct party observations.
- Keep personal identities hashed or excluded where not required.

4. Other public sources

Do not scrape or bulk ingest these without permission:

- Albion Online Grind group builds:
  https://albiononlinegrind.com/group-builds
- Albion Free Market:
  https://albionfreemarket.com/builds

Support source links and manual imports now. Structure adapters so sanctioned imports can be added later.

Use the Albion Online Data Project only for optional build-price enrichment:

https://www.albion-online-data.com/api/

Never treat price as build quality.

MurderLedger and other 1v1 sources must be restricted to solo/1v1 contexts and must have zero eligibility for 10–20-player recommendations.

E. FIX OBSERVATION AND PARTY-SIZE SEMANTICS

The current battle sampler treats whole-battle `totalPlayers` as party size. Correct this throughout the data model and UI.

Keep these dimensions distinct:

- actual party size
- observed/lower-bound roster size
- side size
- total fight size

For existing GameInfo/AlbionBB data:

- Label it as fight-size equipment prevalence.
- Do not call it party-size evidence.
- Do not infer selected abilities; store them as unknown.
- Retain raw observations, source IDs, server, event/battle ID, timestamps, complete available equipment, and sampling frame.
- Track loadout swaps rather than keeping whichever player sighting happens to appear first.
- Deduplicate events and battles.
- Aggregate confidence at battle/party/side level rather than pretending correlated player slots are independent samples.
- Keep prevalence separate from effectiveness.
- Do not wire these observations into Forge scoring in this chapter.

F. CANONICAL BUILD PROMOTION AND SELECTION

A published or observed build must not become a default merely because it is popular.

Implement explicit statuses such as:

- raw
- normalized
- quarantined
- candidate
- approved
- stale
- rejected

A canonical default should require either:

- sanctioned/current official Armory evidence plus independent validation, or
- agreement across at least two genuinely independent source families, or
- explicit current shotcaller approval

Copied builds from the same author must not count as independent agreement.

When selecting the displayed build for a weapon, use:

1. exact weapon UniqueName
2. exact content
3. matching party-size range
4. matching style and role
5. approval
6. patch freshness
7. confidence/source agreement

Do not use `variants[0]` as the default. If falling back to a broader context, show that fallback explicitly.

Imported canonical builds may drive the displayed equipment and spell loadout for a selected weapon. Gear must remain non-scoring until a separately validated gear-capability model exists.

Context attaches to the exact weapon, not merely its family. For large-group PvP, one-hand Cursed Staff, Chillhowl, Ironclad, and similar unsupported weapons should remain ineligible by default unless current exact large-group evidence clears the gate. Implement this through evidence eligibility, not permanent hardcoded bans.

G. DASHBOARD REQUIREMENTS

For every displayed recommended build, show:

- source
- source revision or date
- attributed patch
- content
- party-size range
- role/style
- approval and freshness
- confidence/source agreement
- default selections
- structured alternatives
- unresolved or unknown fields

Do not imply that community votes are win rate or that observed equipment is an ideal build.

H. TESTS AND ACCEPTANCE CRITERIA

Add tests covering at minimum:

1. Atomic pinned snapshot and hash verification.
2. Deterministic regeneration.
3. Release failure for missing/mixed/stale source inputs.
4. Full curated weapon/item coverage.
5. No `attackrange -> ranged_presence` shortcut.
6. Evidence required for every derived scoring capability.
7. Stable spell-ID and item-ID resolution.
8. Spell equippability and bounds validation.
9. Tier/enchantment/quality normalization.
10. Structured alternatives and unknown fields.
11. MetaBattle fixture parsing and CC BY-SA attribution.
12. Manual Armory/caller import validation.
13. Source deduplication and independence.
14. Party-size, side-size, and fight-size remaining distinct.
15. 1v1 evidence having zero large-group eligibility.
16. Unsupported exact weapons not receiving large-group defaults through family-level evidence.
17. Gear catalog independence from icon availability.
18. No imported popularity or observation data entering Forge scoring.
19. Existing dashboard codec/parity tests remaining green.
20. Generated output containing source and patch provenance.

Do not weaken existing tests to get green results. If an unrelated pre-existing test fails, document it clearly; do not hide it or tune this data layer to game the assertion.

FINAL HANDOFF

When complete, provide:

- concise architecture summary
- files changed
- migrations performed
- source adapters implemented
- exact commands run
- complete test results
- number of records imported/approved/quarantined/unresolved
- provenance manifest details
- remaining permission-dependent sources
- known limitations
- confirmation that no noisy external data was automatically wired into Forge scoring
- confirmation that existing unrelated changes were preserved