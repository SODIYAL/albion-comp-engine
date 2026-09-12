"""Party style labels from the COMMITTED harvest artifact.

Spec: notes/specs/2026-09-08-coherent-style-kits-design.md, section 2.
Every killer party of MIN_SIZE+ members in out/party_rosters.json.gz gets the
engine's WEAPONS-ONLY identity (Engine.comp_identity — the same label the
blind rounds grade; naked matched the audit's dressed read 19/20 in round
4). The dressed label would need member kits the committed artifact does
not carry, so this runs on any machine and is byte-reproducible (only the
`_generated` date moves across days).

Reads committed files only; never the raw cache. Explicit step, never part
of a normal build. Rerun order after a harvest: sample_parties ->
audit_style_rosters -> derive_style_bands -> derive_party_styles ->
build_dataset -> gates. build_dataset.py refuses a party_styles.json whose
recorded artifact hash does not match the artifact on disk.

    py -3 pipeline/derive_party_styles.py
"""
import datetime
import hashlib

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rosters_io  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARTIFACT = rosters_io.path(OUT)
TARGET = os.path.join(OUT, "party_styles.json")
CONTENT = "territory_defense"   # identity is content-blind; the audit's choice
MIN_SIZE = 10                   # the group band's party floor (KB_MIN_PARTY)
MIN_KNOWN = 3                   # comp_identity's IDENTITY_MIN_MEMBERS

sys.path.insert(0, HERE)
import party_link  # noqa: E402


def sha256_of(path):
    return rosters_io.sha256(path)   # the stored (compressed) bytes


def derive(doc, engine_factory):
    """Label every MIN_SIZE+ party. `engine_factory(size)` returns an
    Engine already set to CONTENT at that size."""
    by_battle = party_link.parties_by_battle(doc)
    rows = []
    engines = {}
    for battle in sorted(by_battle):
        for p in by_battle[battle]:
            size = p.get("size") or 0
            if size < MIN_SIZE:
                continue
            row = {"battle": battle, "index": p["index"], "size": size,
                   "style": None, "strength": None}
            e = engines.get(size)
            if e is None:
                e = engines[size] = engine_factory(size)
            ws = [w for w in (p.get("weapons") or []) if w in e.weapons]
            if len(ws) >= MIN_KNOWN:
                ci = e.comp_identity(ws)
                row["style"] = ci.get("style")
                row["strength"] = (ci.get("strength") if ci.get("style")
                                   else None)
            rows.append(row)
    rows.sort(key=lambda r: (r["battle"], r["index"]))
    return {"_source": {"party_rosters_sha256": None},
            "_engine": f"comp_identity, weapons only, {CONTENT} at party size",
            "_min_size": MIN_SIZE, "parties": rows}


def main():
    if not os.path.exists(ARTIFACT):
        sys.exit("no out/party_rosters.json.gz — run sample_parties.py first")
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
    from engine import Engine  # noqa: E402
    doc = rosters_io.load(ARTIFACT)
    out = derive(doc, lambda size: Engine(content=CONTENT, size=size))
    out["_generated"] = datetime.date.today().isoformat()
    out["_source"]["party_rosters_sha256"] = sha256_of(ARTIFACT)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    labelled = sum(1 for r in out["parties"] if r["style"])
    print(f"party_styles: {len(out['parties'])} parties of {MIN_SIZE}+, "
          f"{labelled} labelled -> {os.path.relpath(TARGET, HERE)}")


if __name__ == "__main__":
    main()
