"""Build -> party linkage over the committed harvest artifact
(out/party_rosters.json). Spec: notes/specs/2026-09-08-coherent-style-
kits-design.md, section 2 "Linkage".

Two link paths, exact first, never a guess:
  1. the analyzer's `party` index on the build (sample_parties.analyze
     stamps it since 2026-09-08) matched to the party's `index`;
  2. for artifacts harvested before the index existed: (battle, weapon)
     when EXACTLY ONE party of >= min_size members in that battle fields
     that weapon. Zero or several -> None (the build joins no style cell;
     it stays in the band pool).
Party records without an `index` get their ordinal among the battle's
parties in artifact order, so both readers (derive_party_styles.py and
build_dataset.py) key the same party the same way.
"""


def parties_by_battle(doc):
    """{battle: [party, ...]} with every party carrying an `index`."""
    out = {}
    for p in doc.get("parties") or []:
        out.setdefault(p.get("battle"), []).append(p)
    for battle, ps in out.items():
        for i, p in enumerate(ps):
            if p.get("index") is None:
                p["index"] = i
    return out


def link_build(build, by_battle, min_size=10):
    """The index of the build's party in its battle, or None."""
    if build.get("party") is not None:
        return build["party"]
    cands = [p for p in by_battle.get(build.get("battle")) or []
             if (p.get("size") or 0) >= min_size
             and build.get("weapon") in (p.get("weapons") or [])]
    return cands[0]["index"] if len(cands) == 1 else None
