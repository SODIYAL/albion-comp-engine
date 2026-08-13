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


# The Deadlyhooker comp is tagged with the content it was written for, which
# is broader than any single template; map to the closest fitted one.
V4_CONTENT_MAP = {"large_scale_zvz": "territory_defense"}


def v4(args):
    """Meta-comp reproduction (leave-one-out) against tests/meta_comps.yaml.

    For every weapon slot in every real comp party: remove it, ask the engine
    for its top-N at that party's size, and score two ways —
      weapon-level: any of the slot's listed weapons (alternatives count) is
                    in the top-N;
      role-level:   for healer/tank slots, ANY weapon of that role is in the
                    top-N ("propose the missing member's ROLE", VALIDATION V4).
    Battlemount slots are outside the weapon model and are skipped.

    CIRCULARITY CAVEAT (printed in the report): the 20-size templates took
    role-ratio calibration from these same comps, so treat results as a
    weak-form check until comps from uninvolved callers exist.
    """
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    if not os.path.exists(args.comps):
        sys.exit(f"{args.comps} not found — see tests/meta_comps.yaml schema; "
                 "comps must be REAL, never invented.")
    with open(args.comps, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    comps = doc["comps"] if isinstance(doc, dict) else doc

    probe = Engine()
    role_sets = probe.scoring.get("role_sets", {})
    ROLE_POOLS = {"healer": set(role_sets.get("healers", [])),
                  "tank": set(role_sets.get("frontline", [])),
                  "main_tank": set(role_sets.get("frontline", []))}

    w_hits = w_total = r_hits = r_total = 0
    misses = []
    for comp in comps:
        content = V4_CONTENT_MAP.get(comp.get("content"), comp.get("content"))
        if content not in probe.data["templates"]:
            print(f"  skip {comp.get('id','?')}: no template for content "
                  f"{comp.get('content')!r}")
            continue
        for party in comp.get("parties", []):
            slots = [s for s in party.get("slots", [])
                     if s.get("weapons") and s.get("role") != "battlemount"]
            members = [s["weapons"][0] for s in slots]
            e = Engine(content=content, size=len(members))
            for i, slot in enumerate(slots):
                rest = members[:i] + members[i+1:]
                top = [r["weapon"] for r in e.recommend(rest, TOP_N)]
                hit = any(alt in top for alt in slot["weapons"])
                w_hits += hit
                w_total += 1
                pool = ROLE_POOLS.get(slot.get("role"))
                if pool:
                    r_hits += any(w in pool for w in top)
                    r_total += 1
                if not hit:
                    misses.append(
                        f"{comp.get('id','?')}/{party.get('name','?')} "
                        f"dropped {slot.get('raw','?')} ({slot.get('role','?')}) -> "
                        f"{', '.join(e.weapons[w]['display_name'] for w in top)}")

    if not w_total:
        sys.exit("no scoreable slots")
    print(f"V4 leave-one-out over {w_total} slots "
          f"(top-{TOP_N}, battlemounts excluded):")
    print(f"  weapon-level: {w_hits}/{w_total} = {w_hits/w_total:.0%}  "
          "(strict — the exact weapon back in top-3)")
    if r_total:
        print(f"  role-level  : {r_hits}/{r_total} = {r_hits/r_total:.0%}  "
              f"(healer/tank slots only, n={r_total}; the designed V4 metric)")
    print(f"  gate {GATE:.0%} applies to the ROLE metric -> "
          f"{'PASS' if r_total and r_hits/r_total >= GATE else 'FAIL/insufficient'}")
    print("  caveat: 20-size templates were role-ratio calibrated on these "
          "same comps — weak-form evidence until independent comps exist.")
    if args.verbose and misses:
        print("\nweapon-level misses:")
        for m in misses:
            print(f"  {m}")
    return 0


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
    v.add_argument("--verbose", action="store_true", help="list weapon-level misses")

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
