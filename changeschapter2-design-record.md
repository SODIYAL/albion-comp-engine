# Chapter 2 — Evidence layer: reproducible game data + real build provenance

Design record for implementing `changeschapter2.md` (2026-08-19). The prompt is
the requirements document; this file records the **adaptations** made to fit
the actual repo (static pipeline + single-file SPA, no database, no backend)
and the architecture decisions a future session needs.

## Verified pre-flight facts

- Working tree clean at `9924861`; baseline gates all green (golden 24/24,
  forge 11/11, parity 60/60 + embed, V4 role 20/26 = 77%, codec 24/24,
  patch-history 14/14, lint clean).
- `pipeline/templates/composition.yaml` is explicitly branch-handled by
  `load_templates()` — never mistaken for a content template.
- ao-bin-dumps master HEAD `5cf2e8e9b7021f98683181fa5b0e3c64575978e4`
  (2026-07-27 data update, game patch "update 20260721" / 2026-07-21) serves
  an `items.json` **byte-identical** (SHA-256
  `fc009a9f…f29c077`) to the local dumps cache — pinning to it introduces
  zero data drift. `spell_index.json`/`weapon_lines.json` (generated
  2026-08-12 from a clone) and `item_stats.json` (2026-08-18 master download)
  therefore already derive from this one commit's content; the pin makes that
  provable instead of lucky.
- MetaBattle runs Semantic MediaWiki. `Category:ZvZ builds` has 31 build
  pages; each carries `{{Build}}` + `{{Build equipment}}` templates with
  named fields (main hand weapon, ordered skills lists, head/cape/armor/shoes
  + skills, potion, food) — parseable without HTML scraping, via
  `action=parse&prop=wikitext|revid|categories`.
- The usage-derived meta prior is NOT wired into scoring (scoring.yaml
  carries hand-set values; `build_meta_prior.py` output is reviewable only).
  Chapter tests pin this rather than change it.

## Adaptations of the prompt to this repo

1. **"Normalized entities" = schema-validated YAML files + generated JSON
   indexes**, not database tables. The prompt allows "or equivalent
   structures". Entities map to: `source_snapshot` →
   `pipeline/out/source_manifest.json`; `game_patch` →
   `out/patch_history.json` (already exists); `published_build` /
   `published_comp` / `loadout_observation` / `canonical_build` → files under
   `data/`; `validation_result` → `out/builds_validation.json`.
2. **Pin choice**: `5cf2e8e9…` (see above). All five inputs (items.json,
   spells.json, localization.json, formatted/items.json,
   formatted/items.txt) fetched from that one commit by
   `pipeline/fetch_snapshot.py`; cache keyed by commit
   (`out/dumps_cache/<sha12>/`), manifest with SHA-256 per file.
3. **ranged_presence** (section B): derived per **slot bundle**, not
   `loadout.always`. A bundle gets `ranged_presence` iff its curated
   damage-AoE claim (`burst_aoe`, already evidence-linted to an equippable
   spell) cites a spell whose game-data `castrange >= 9`; radius/max-targets
   recorded when extractable from spells.json. `pipeline/ranged_overrides.yaml`
   grants/denies with citation where structured data is insufficient.
   Missing facts → capability absent + weapon listed in
   `out/ranged_presence_report.json` as unknown. Consequence: the capability
   participates in scoring only when the scored combo actually includes the
   AoE spell.
4. **MurderLedger/1v1**: no adapter yet; the eligibility rule is enforced
   structurally — the builds validator rejects any record whose source
   context is solo/1v1 with a party-size range reaching beyond 2.
5. **Armory**: manual import format under `data/armory_imports/` + validator;
   the checked-in example is `example: true` and excluded from promotion.
6. **Exact-weapon large-group eligibility (F)**: the existing
   `composition.yaml` exclusions stay the enforcement point, but each entry
   now carries an evidence record validated by the builds layer, and a test
   pins that family-level evidence cannot grant an exact weapon a default.
   Fully evidence-driven eligibility is a documented limitation until enough
   canonical builds exist.
7. **meta_comps.yaml migration**: caller comps move to
   `data/published_comps/*.yaml` with a provenance envelope, keeping the
   slots shape the V4 runner reads (weapons/role/skills/gear stay). The V4
   runner's default path and `build_dashboard.py` are rewired; a tombstone
   comment replaces `tests/meta_comps.yaml`.
8. **Dashboard**: LOADOUTS embed is regenerated from the builds layer with
   provenance fields (source, revision/date, patch, approval, freshness,
   confidence, structured alternatives, unknowns); explicit selection order
   replaces `variants[0]`; `ITEM_STATS` aliases `DATASET.item_stats` instead
   of a second embed; gear catalogue no longer filtered by icon manifest
   (placeholder/hotlink fallback instead).

## Phases

1. **Snapshot + normalization**: fetch_snapshot.py, manifest,
   rewire fetch_item_stats/parse_dumps/fetch_gear_lines to the pinned cache,
   fix normalization (nested enchantments, @tier attribute over regex,
   zero-transitions, cross-tier slot/category consistency, raw per-tier item
   IDs), dataset provenance + fail-closed release, fixtures + tests.
2. **ranged_presence rework** per adaptation 3; reconcile golden/forge/V4.
3. **Builds layer**: `pipeline/builds_lib.py` (schema/normalize/validate/
   promote), `pipeline/build_builds.py`, data/ migration, MetaBattle adapter
   (`pipeline/adapters/metabattle.py`) + fixtures, Armory format, companion
   observation schema, statuses raw→…→approved, selection ordering.
4. **Observation semantics**: sample_battles rework (fight-size framing,
   swaps, dedup, battle-level aggregation), UI copy relabel.
5. **Dashboard provenance UI**.
6. **Tests (H.1–20), docs, full gate run, handoff report.**

Statuses: `raw | normalized | quarantined | candidate | approved | stale |
rejected`. Canonical default requires: sanctioned Armory evidence +
independent validation, OR two genuinely independent source families (same
author never counts twice), OR explicit current shotcaller approval (the
caller-authored sheets carry this for their own comps).

Confidence dimensions: item_mapping, spell_mapping, patch, content_context,
party_size, source_independence, loadout_completeness, outcome.
