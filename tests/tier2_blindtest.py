#!/usr/bin/env python3
"""
Tier-2 validation harness — V3 (expert blind test) and V4 (meta-comp
reproduction). See tests/VALIDATION.md.

V3 is the project's TRUE accuracy metric: give experienced shotcallers partial
parties, collect their next pick independently, and measure how often that pick
appears in the engine's top-3. Gate: >=70%.

This script does the three mechanical parts. It cannot do the human part.

    generate  build N partial parties and write a blind form (the form shows NO
              engine output — that is what makes it blind)
    score     read the filled form + compare against engine top-3
    v4        reproduce published meta comps minus one member

Usage:
    py -3 tests/tier2_blindtest.py generate --n 12 --out tier2_form.md
    py -3 tests/tier2_blindtest.py score tier2_form_filled.md
    py -3 tests/tier2_blindtest.py v4 tests/meta_comps.yaml

Party generation is seeded and deterministic, so every expert sees the same
parties and a re-run reproduces the same set.
"""
import os, sys, argparse, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

TOP_N = 3          # "expert pick appears in engine top-3"
GATE = 0.70        # VALIDATION.md V3 gate


def generate(args):
    e = Engine(size=args.size)
    pool = sorted(e.weapons)
    rng = random.Random(args.seed)

    parties = []
    while len(parties) < args.n:
        # partial parties of 2..size-1, sampled without replacement
        k = rng.randint(2, max(2, args.size - 1))
        p = rng.sample(pool, k)
        if p not in parties:
            parties.append(p)

    lines = [
        f"# Tier-2 V3 — expert blind test  ({e.template['name']}, size {args.size})",
        "",
        "Fill in **one weapon name** per case: the next player you would add.",
        "Answer from your own judgement — the engine's answer is deliberately not shown.",
        "Write the weapon's common name (e.g. `Heavy Mace`, `Hallowfall`). One pick per case.",
        "",
        f"Generated with seed {args.seed} — every expert must receive this same file.",
        "",
    ]
    for i, p in enumerate(parties, 1):
        names = ", ".join(e.weapons[w]["display_name"] for w in p)
        lines += [f"### Case {i}",
                  f"- Party ({len(p)}/{args.size}): {names}",
                  f"- PARTY_KEYS: {' '.join(p)}",
                  "- YOUR PICK: ",
                  ""]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote {args.out}: {len(parties)} cases, size {args.size}, seed {args.seed}")
    print("Send the SAME file to 3+ shotcallers. Do not show them engine output.")


def _resolve(e, text):
    """Map a human-typed weapon name to a dataset key, tolerantly."""
    t = text.strip().lower()
    if not t:
        return None
    for key, w in e.weapons.items():
        if t == key.lower() or t == w["display_name"].lower():
            return key
    hits = [k for k, w in e.weapons.items() if t in w["display_name"].lower()]
    return hits[0] if len(hits) == 1 else None


def score(args):
    e = Engine(size=args.size)
    with open(args.form, encoding="utf-8") as f:
        text = f.read()

    # [ \t]* not \s* — \s* would swallow the newline after an unfilled
    # "YOUR PICK:" and capture the following line as if it were the answer.
    cases = re.findall(r"PARTY_KEYS:[ \t]*(.+?)[ \t]*\n-[ \t]*YOUR PICK:[ \t]*(.*)", text)
    if not cases:
        sys.exit("no cases found — is this a filled form from `generate`?")

    hits, scored, unresolved = 0, 0, []
    print(f"{'#':<4}{'expert pick':<22}{'in top-3':<10}engine top-3")
    print("-" * 96)
    for i, (keys, pick) in enumerate(cases, 1):
        party = keys.split()
        want = _resolve(e, pick)
        if want is None:
            if pick.strip():
                unresolved.append((i, pick.strip()))
            continue
        top = [r["weapon"] for r in e.recommend(party, TOP_N)]
        ok = want in top
        hits += ok
        scored += 1
        print(f"{i:<4}{e.weapons[want]['display_name']:<22}{'YES' if ok else 'no':<10}"
              f"{', '.join(e.weapons[w]['display_name'] for w in top)}")

    print("-" * 96)
    if not scored:
        sys.exit("no answers filled in yet")
    rate = hits / scored
    print(f"top-{TOP_N} agreement: {hits}/{scored} = {rate:.0%}   "
          f"gate {GATE:.0%} -> {'PASS' if rate >= GATE else 'FAIL'}")
    if unresolved:
        print(f"\nunresolved answers (fix spelling or use PARTY_KEYS names):")
        for i, p in unresolved:
            print(f"  case {i}: {p!r}")
    if rate < GATE:
        print("\nPer VALIDATION.md: a miss where the expert is right becomes a new "
              "golden case in tests/test_golden.py. Review misses before retuning.")
    return 0 if rate >= GATE else 1


def v4(args):
    """Meta-comp reproduction: drop one member, check the engine proposes it."""
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    if not os.path.exists(args.comps):
        sys.exit(f"{args.comps} not found.\n"
                 "Create it as a list of published comps, e.g.:\n"
                 "  - source: albioncompo.com/xyz\n"
                 "    content: castle_outpost\n"
                 "    members: [2H_MACE, 2H_HAMMER, MAIN_HOLYSTAFF_AVALON, ...]\n"
                 "These must be REAL published comps — do not invent them.")
    comps = yaml.safe_load(open(args.comps, encoding="utf-8"))
    total = hits = 0
    for comp in comps:
        members = comp["members"]
        e = Engine(content=comp.get("content", "castle_outpost"), size=len(members))
        for i, missing in enumerate(members):
            if missing not in e.weapons:
                continue
            rest = members[:i] + members[i+1:]
            top = [r["weapon"] for r in e.recommend(rest, TOP_N)]
            ok = missing in top
            hits += ok
            total += 1
            if not ok:
                print(f"  miss: {comp.get('source','?')} dropped "
                      f"{e.weapons[missing]['display_name']} -> engine said "
                      f"{', '.join(e.weapons[w]['display_name'] for w in top)}")
    if not total:
        sys.exit("no scoreable members (are the weapon keys curated yet?)")
    print(f"\nV4 meta-comp reproduction: {hits}/{total} = {hits/total:.0%} "
          f"(gate {GATE:.0%} -> {'PASS' if hits/total >= GATE else 'FAIL'})")
    return 0 if hits / total >= GATE else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate"); g.set_defaults(fn=generate)
    g.add_argument("--n", type=int, default=12)
    g.add_argument("--size", type=int, default=7)
    g.add_argument("--seed", type=int, default=20260812)
    g.add_argument("--out", default="tier2_form.md")

    s = sub.add_parser("score"); s.set_defaults(fn=score)
    s.add_argument("form")
    s.add_argument("--size", type=int, default=7)

    v = sub.add_parser("v4"); v.set_defaults(fn=v4)
    v.add_argument("comps", nargs="?", default=os.path.join(HERE, "meta_comps.yaml"))

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
