# data/ — the evidence layer

Versioned source-of-truth for everything the engine knows that is NOT the
game's own data (changeschapter2.md, chapter 2). Four concepts, kept strictly
apart — raw popularity, killboard sightings, or community submissions never
automatically become "ideal" recommendations:

| concept | where | what it is |
|---|---|---|
| game facts | `source_pins.yaml` + `pipeline/out/` | items/spells/ranges from ONE pinned ao-bin-dumps commit, manifest-verified |
| published builds | `published_comps/`, `published_builds/`, `armory_imports/` | what named sources actually published, verbatim + provenance |
| loadout observations | `pipeline/out/weapon_usage_v2.json`, companion imports | what players were SEEN wearing — prevalence, never advice |
| canonical builds | `canonical_builds/` + generated flags in `builds_index.json` | human-reviewed defaults that cleared the §F promotion gate |

Generated views: `pipeline/build_builds.py` normalizes everything here into
`pipeline/out/builds_index.json` (ordered by the §F selection criteria,
canonical defaults flagged with their basis) and writes the
`validation_result` record to `pipeline/out/builds_validation.json`.
Human-maintained files stay VERBATIM; every derived value is generated and
carries the basis it rests on; unknown stays unknown.

Statuses: `raw → normalized → (quarantined | candidate) → approved`, plus
`stale` and `rejected`. Imports are never born approved. A canonical default
requires Armory evidence + independent validation, OR two genuinely
independent source families, OR explicit current shotcaller approval — same
author never counts twice.

## Source policy (§D.4)

- **MetaBattle** — automated via their MediaWiki Action API
  (`pipeline/adapters/metabattle.py`), CC BY-SA attribution on every record.
  Adapter v2 (2026-08-26) captures every group-PvP category (ZvZ, Hellgate
  5v5/10v10, Crystal League/Arena, Ganking; solo/PvE modes stay out) into
  `published_builds/metabattle.yaml`, each record's `content` derived from
  the page's own mode category.
- **Official Armory** — manual imports only (`armory_imports/README.md`);
  no reverse-engineering of game traffic or private endpoints.
- **Albion Online Grind** (<https://albiononlinegrind.com/group-builds>) and
  **Albion Free Market** (<https://albionfreemarket.com/builds>) — NOT
  scraped or bulk-ingested without permission. Manual imports with a source
  link are welcome as `kind: manual_link` records; a sanctioned adapter can
  slot in beside the MetaBattle one later.
- **Albion Online Data Project** (<https://www.albion-online-data.com/api/>)
  — optional build-PRICE enrichment only. Price is never build quality.
- **MurderLedger and other 1v1 sources** — restricted to solo/1v1 contexts;
  the schema validator rejects any such record whose party-size range
  reaches past 2, and they have zero eligibility for 10-20-player
  recommendations.

Nothing in this directory feeds Forge scoring. Displayed equipment/spell
loadouts may come from canonical builds; gear stays non-scoring until a
separately validated gear-capability model exists.
