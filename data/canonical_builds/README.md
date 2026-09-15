# Manual canonical pins

Most canonical defaults are derived: `pipeline/build_builds.py` orders each
(weapon, content) group by the selection order and flags the top record
canonical when the promotion gate passes (`data/README.md` "Promotion gate
and selection order"; see `builds_validation.json` `promotions` for every
decision and its basis).

A file here (`kind: canonical_build`) pins a specific build as the default
for one exact context, overriding the derived ordering — for when a human
reviewer decides between two eligible records:

```yaml
kind: canonical_build
weapon: 2H_LONGBOW
content: blackzone_roam
build_id: "timothy_blap_blackzone_roam_2026_08:blap:3"
reviewer: "<reviewer handle>"
as_of: "2026-08-19"
reason: "why this record over the derived winner"
```

The pinned build must still clear the eligibility gate; a pin cannot
promote a record whose evidence does not qualify.
