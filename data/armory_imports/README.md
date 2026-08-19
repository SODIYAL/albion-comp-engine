# Manual Armory imports

The official in-game Armory (announced with the Radiant Wilds update,
<https://albiononline.com/update/radiant-wilds>) is conceptually the
strongest build source this project can have: real gameplay, official
activity and group-size tags, gear, abilities, consumables, popularity and
performance. **There is no documented public export or API**, and this
project does not reverse-engineer game traffic or private endpoints
(changeschapter2.md §D.2) — so Armory evidence enters by hand, through this
directory, and every record says exactly where it was read and by whom.

One YAML file per import session, `kind: armory_import`. Files with
`example: true` are format documentation and are never ingested.

Required per record (see `example.yaml`):

- `activity` — the Armory's own activity label, verbatim
- `group_size_tag` — the official group-size tag, verbatim
- `captured` — date the Armory was read (YYYY-MM-DD)
- `patch` — game patch the reading belongs to
- `recent_or_established` — which Armory view the build came from
- `source_citation` — screenshot reference or in-game path; enough for a
  second person to re-check the reading
- `reviewer` — who read and entered it
- the build itself: exact `weapon`/gear UniqueNames (normalize with the
  gear catalogue; keep the Armory's raw text in `*_raw` fields), spells,
  alternatives, and explicit `unknowns` for anything the Armory view did
  not show
- `performance` — popularity/performance figures ONLY if the Armory
  actually displayed them; never inferred

Imported records start as `candidate`. Promotion to a canonical default
follows the §F gate in `pipeline/builds_lib.py` — Armory evidence counts as
the strongest source family but still needs independent validation.

Run `py -3 pipeline/build_builds.py` after adding a file; it validates
equippability against the pinned game snapshot and quarantines anything
inconsistent.
