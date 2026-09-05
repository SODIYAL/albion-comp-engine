"""Kit blind round: a weapon's real fielded builds, shown without labels.

The roster blind rounds test the identity labels; this one tests the
KIT-to-style link the owner reads by eye (2026-09-05: "give me different
builds for a weapon and I tell you what playstyle it might be part of").
For one weapon it lists the most-worn chest / helmet / boots combinations
from labelled killer-party rosters of 10+ (one line per distinct build,
ordered by DISTINCT PLAYERS), and keeps the answer — the styles of the
rosters each build was actually worn in — off the form.

Grading convention (owner, same day): "one build can be part of multiple
styles", so the answer is a distribution, not a label, and a call agrees
when it names the styles that carry the build's players.

Report-only, network-free; reads out/party_cache through the audit's
loader and labels with the engine's comp_identity (worn chests passed).

    py -3 pipeline/kit_blind_round.py "Realmbreaker"          # the form
    py -3 pipeline/kit_blind_round.py "Realmbreaker" --answers
    py -3 pipeline/kit_blind_round.py "Hallowfall" --top 10
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from engine.engine import Engine  # noqa: E402
import audit_style_rosters as audit  # noqa: E402

SIG_SLOTS = ("Armor", "Head", "Shoes")


def labelled_rosters(engine):
    """Every 10+ roster with its comp_identity style (chests passed)."""
    rosters = audit.load_rosters(set(engine.weapons), 10, 0.8)
    gk = engine.gear_key
    out = []
    for r in rosters:
        gears = []
        for m in r["members"]:
            kit = m["kit"] or {}
            chest = gk(kit["Armor"]) if kit.get("Armor") else None
            gears.append([chest] if chest and chest in engine.gear else None)
        engine.set_content("territory_defense", r["size"])
        ci = engine.comp_identity([m["weapon"] for m in r["members"]],
                                  None, gears)
        out.append((ci.get("style"), r["members"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weapon", help="display name, e.g. Realmbreaker")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--answers", action="store_true",
                    help="print the style distribution per build")
    args = ap.parse_args()
    e = Engine(content="territory_defense", size=20)
    byname = {wd["display_name"]: w for w, wd in e.weapons.items()}
    if args.weapon not in byname:
        sys.exit(f"unknown weapon '{args.weapon}'")
    W = byname[args.weapon]
    gk = e.gear_key
    name = lambda k: e.gear[k]["display_name"] if k in e.gear else str(k)
    sig_styles = collections.defaultdict(lambda: collections.defaultdict(set))
    for style, members in labelled_rosters(e):
        if not style:
            continue
        for m in members:
            if m["weapon"] != W or not m["kit"]:
                continue
            sig = tuple(gk(m["kit"].get(s)) if m["kit"].get(s) else None
                        for s in SIG_SLOTS)
            if None in sig:
                continue
            sig_styles[sig][style].add(m["name"])
    rows = sorted(((len(set().union(*st.values())), sig, st)
                   for sig, st in sig_styles.items()),
                  key=lambda t: (-t[0], t[1]))
    print(f"{args.weapon}: {len(rows)} distinct builds in labelled 10+ "
          f"rosters; top {args.top} by distinct players")
    for i, (n, sig, st) in enumerate(rows[:args.top], 1):
        line = f"{i}. " + " / ".join(name(k) for k in sig)
        if args.answers:
            dist = {k: len(v) for k, v in
                    sorted(st.items(), key=lambda kv: -len(kv[1]))}
            line += f"   [players {n}]   {dist}"
        print(line)


if __name__ == "__main__":
    main()
