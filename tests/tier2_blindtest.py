#!/usr/bin/env python3
"""
Tier-2 validation harness — V3 (expert blind test) and V4 (meta-comp
reproduction). See tests/VALIDATION.md.

V3 is the project's TRUE accuracy metric: give experienced shotcallers partial
parties, collect their next pick independently, and measure how often that pick
appears in the engine's top-3. Gate: >=70%.

DRESSED VALIDATION (2026-08-27): the production engine evaluates DRESSED
candidates (weapon + combo + doctrine kit) against the party's actual
loadout gear, while this harness historically scored naked incumbent
parties — an asymmetric comparison (a dressed candidate collects gap
credit a dressed party would never concede; golden T30c's honesty rider
pins the effect). Scoring now runs explicit modes:

  V3-W  weapon-only, SYMMETRIC: incumbents naked AND candidates naked
        (Engine.set_dressing(False)) — tests the weapon/capability model
        by itself, through the authoritative scoring machinery (the
        identity short-circuit; no second formula).
  V3-D  production, dressed: incumbents wear the case's recorded gear
        (GEAR_KEYS) where present, else their doctrine kit (kit_variants
        v0), else stay honestly naked; candidates take the normal dressed
        path. This measures the recommendation behavior users receive.
        THE 70% GATE APPLIES TO V3-D; V3-W prints beside it as the
        weapon-model benchmark. Per-case gear sources are recorded.

V4 leave-one-out likewise reports three incumbent-gear classes:
  weapon_only        the legacy naked-incumbent metric — STILL the
                     exit-code gate until an owner ruling re-bases it
  doctrine_inferred  incumbents in kit_variants v0 (inferred, and labeled
                     so — the doctrine pools were mined from these same
                     comps, so this class is doubly weak-form)
  actual_gear        incumbents in the gear their published source
                     actually records (builds_index join; published
                     comps carry gear on every slot). Unresolved pieces
                     stay off the member and are counted, never guessed.
Candidates always take the normal dressed path. Weapon-only reproduction
is NOT production recommendation accuracy; the dressed sections are the
production-faithful measurements.

This script does the three mechanical parts. It cannot do the human part.

    generate  build N partial parties and write a blind form (the form shows NO
              engine output — that is what makes it blind)
    score     read the filled form + compare against engine top-3 per mode
    v4        reproduce published meta comps minus one member

Usage:
    py -3 tests/tier2_blindtest.py generate --n 12 --out tier2_form.md
    py -3 tests/tier2_blindtest.py score tier2_form_filled.md [--mode both|w|d]
    py -3 tests/tier2_blindtest.py v4 [--verbose] [--json out.json]

Party generation is seeded and deterministic, so every expert sees the same
parties and a re-run reproduces the same set (seed 20260812 still emits the
round-1 parties' PARTY_KEYS unchanged).
"""
import glob, json, os, statistics, sys, argparse, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402

TOP_N = 3          # "expert pick appears in engine top-3"
GATE = 0.70        # VALIDATION.md V3 gate
FULL_RANK = 10 ** 6  # top_n large enough to return the whole ranked pool

# Expert PRIMARY NEED vocabulary -> engine capability. PROVISIONAL alias
# table; a need word that fails to map is reported, never guessed.
NEED_CAPS = {
    "pierce": "resist_shred", "resistance reduction": "resist_shred",
    "resist shred": "resist_shred", "shred": "resist_shred",
    "heal": "heal_sustain", "healing": "heal_sustain",
    "healer": "heal_sustain", "sustain": "heal_sustain",
    "burst heal": "heal_burst",
    "tank": "tankiness", "frontline": "tankiness", "tankiness": "tankiness",
    "anti-heal": "heal_reduction", "anti heal": "heal_reduction",
    "heal cut": "heal_reduction", "healcut": "heal_reduction",
    "clump": "clump_create", "engage": "engage", "catch": "catch",
    "damage": "burst_aoe", "aoe damage": "burst_aoe", "aoe": "burst_aoe",
    "bomb": "burst_aoe", "single target": "burst_st",
    "sustained damage": "sustained_dps", "dps": "sustained_dps",
    "peel": "peel", "purge": "purge", "cleanse": "cleanse",
    "mobility": "mobility", "kite": "mobility", "disengage": "disengage",
    "zone": "zone_control", "stun": "stun", "silence": "silence",
    "cc": "stun",
}

# Confidence weights for the confidence-weighted agreement metric.
# PROVISIONAL constants; unstated confidence counts as medium (0.6).
CONF_W = {"high": 1.0, "medium": 0.6, "low": 0.3}


def generate(args):
    e = Engine(content=args.content, size=args.size, style=args.style)
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
        "For each case fill in **BEST PICK** — the next player you would add.",
        "The other fields are optional; each one you fill makes the round",
        "count for more:",
        "",
        "- PRIMARY NEED — what the party lacks most, in your own words",
        "- OTHER GOOD PICKS — acceptable alternatives, comma-separated",
        "- BAD PICK — a pick you would veto if the engine suggested it",
        "- CONFIDENCE — High / Medium / Low",
        "- REASON — one line on why",
        "",
        "Answer from your own judgement — the engine's answer is deliberately",
        "not shown. Use weapons' common names (e.g. `Heavy Mace`, `Hallowfall`).",
        "",
        f"Generated with seed {args.seed} — every expert must receive this same file.",
        "",
        f"- FORM_CONTEXT: {args.content} {args.size} {args.style} {args.seed}",
        "",
    ]
    for i, p in enumerate(parties, 1):
        names = ", ".join(e.weapons[w]["display_name"] for w in p)
        lines += [f"### Case {i}",
                  f"- Party ({len(p)}/{args.size}): {names}",
                  f"- PARTY_KEYS: {' '.join(p)}",
                  "- PRIMARY NEED: ",
                  "- BEST PICK: ",
                  "- OTHER GOOD PICKS: ",
                  "- BAD PICK: ",
                  "- CONFIDENCE: ",
                  "- REASON: ",
                  ""]
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {args.out}: {len(parties)} cases, size {args.size}, seed {args.seed}")
    print("Send the SAME file to 3+ shotcallers. Do not show them engine output.")


def _resolve(e, text):
    """Map a human-typed weapon name to a dataset key, tolerantly."""
    t = (text or "").strip().lower()
    if not t:
        return None
    for key, w in e.weapons.items():
        if t == key.lower() or t == w["display_name"].lower():
            return key
    hits = [k for k, w in e.weapons.items() if t in w["display_name"].lower()]
    return hits[0] if len(hits) == 1 else None


# Field values live on their OWN line — the legacy regex lesson (an
# unfilled field must never swallow the next line as its answer; [ \t],
# never \s) holds structurally in a line parser. Unknown "- Foo:" lines
# (e.g. the display "Party (3/7)") fail the uppercase pattern and are
# ignored; YOUR PICK is the legacy alias of BEST PICK.
_FIELD_RE = re.compile(r"^-[ \t]*([A-Z][A-Z_ ]*?)[ \t]*:[ \t]*(.*?)[ \t]*$")


def _parse_cases(text):
    """Parse a (possibly filled) blind form into case dicts.

    Every field except PARTY_KEYS is optional: {party, gears, need, best,
    good[], bad, confidence, reason}. GEAR_KEYS (optional, for cases
    derived from real comps rather than generated ones) records one kit
    per member, ';'-separated, each kit comma-separated catalog ids,
    '-' = naked."""
    blocks = re.split(r"(?m)^###[ \t]*Case[ \t]*\d+.*$", text)[1:]
    cases = []
    for block in blocks:
        f = {}
        for line in block.splitlines():
            m = _FIELD_RE.match(line)
            if m:
                f[m.group(1).upper()] = m.group(2)
        if "PARTY_KEYS" not in f:
            continue

        def val(k):
            v = (f.get(k) or "").strip()
            return v or None

        gears = None
        if val("GEAR_KEYS"):
            gears = []
            for part in f["GEAR_KEYS"].split(";"):
                part = part.strip()
                gears.append(None if part in ("", "-") else
                             [g.strip() for g in part.split(",") if g.strip()])
        good = [g.strip() for g in (f.get("OTHER GOOD PICKS") or "").split(",")
                if g.strip()]
        conf = (val("CONFIDENCE") or "").lower()
        conf = {"h": "high", "m": "medium", "l": "low"}.get(conf[:1]) if conf else None
        cases.append({
            "party": f["PARTY_KEYS"].split(),
            "gears": gears,
            "need": val("PRIMARY NEED"),
            "best": val("BEST PICK") or val("YOUR PICK"),
            "good": good,
            "bad": val("BAD PICK"),
            "confidence": conf,
            "reason": val("REASON"),
        })
    return cases


def _metrics(rows):
    """The Task-1D metric set over scored case rows. Deliberately never
    collapsed into one accuracy number."""
    n = len(rows) or 1
    ranks = [r["rank"] for r in rows if r.get("rank") is not None]
    need = [r for r in rows if r.get("need_hit") is not None]
    bad = [r for r in rows if r.get("bad_in_top3") is not None]
    wsum = sum(CONF_W.get(r.get("confidence"), 0.6) for r in rows)
    return {
        "n": len(rows),
        "top1": sum(1 for r in rows if r.get("top1")) / n,
        "top3": sum(1 for r in rows if r.get("top3")) / n,
        "acceptable_top3": sum(1 for r in rows if r.get("acceptable")) / n,
        "mean_rank": (sum(ranks) / len(ranks)) if ranks else None,
        "median_rank": statistics.median(ranks) if ranks else None,
        "rank_n": len(ranks),
        "outside_pool": sum(1 for r in rows if r.get("rank") is None),
        "need_agreement": (sum(1 for r in need if r["need_hit"]) / len(need))
                          if need else None,
        "need_n": len(need),
        "bad_pick_rate": (sum(1 for r in bad if r["bad_in_top3"]) / len(bad))
                         if bad else None,
        "bad_n": len(bad),
        "conf_weighted_top3": (sum(CONF_W.get(r.get("confidence"), 0.6)
                                   for r in rows if r.get("top3")) / wsum)
                              if wsum else None,
    }


def _fmt_pct(v):
    return "-" if v is None else f"{v:.0%}"


def _score_mode(e, cases, mode):
    """Evaluate parsed cases under one gear regime.

    mode 'w': symmetric weapon-only (incumbents naked, candidates naked
    via set_dressing(False)). mode 'd': production dressed (incumbents in
    recorded gear else doctrine kits; candidates dressed). Returns
    (rows, unresolved, case_lines)."""
    e.set_dressing(mode == "d")
    rows, unresolved, case_lines = [], [], []
    try:
        for i, c in enumerate(cases, 1):
            gl = None
            gsrc = ["naked"] * len(c["party"])
            if mode == "d":
                if c["gears"] and len(c["gears"]) == len(c["party"]):
                    gl = []
                    for j, kit in enumerate(c["gears"]):
                        norm = [x for x in (gear_join.normalize_gear_id(k, e.gear)
                                            for k in (kit or [])) if x]
                        gl.append(norm or None)
                        gsrc[j] = "actual" if norm else "naked"
                else:
                    gl = gear_join.doctrine_gears(e, c["party"])
                    gsrc = ["doctrine" if k else "naked" for k in gl]
            want = _resolve(e, c["best"])
            if want is None:
                if (c["best"] or "").strip():
                    unresolved.append((i, c["best"].strip()))
                continue
            full = e.recommend(c["party"], FULL_RANK, gears=gl)
            order = [r["weapon"] for r in full]
            top3 = order[:TOP_N]
            rank = order.index(want) + 1 if want in order else None
            acc = {want} | {k for k in (_resolve(e, x) for x in c["good"]) if k}
            bad_key = _resolve(e, c["bad"])
            need_cap = NEED_CAPS.get((c["need"] or "").strip().lower())
            need_hit = None
            if need_cap:
                weak = [g["cap"] for g in e.weaknesses(c["party"], 3, None, gl)]
                need_hit = need_cap in weak
            rows.append({
                "case": i, "want": want, "rank": rank,
                "top1": order[:1] == [want], "top3": want in top3,
                "acceptable": any(k in top3 for k in acc),
                "bad_in_top3": (bad_key in top3) if bad_key else None,
                "need_hit": need_hit, "confidence": c["confidence"],
                "gear_source": gsrc, "engine_top3": top3,
            })
            case_lines.append(
                f"{i:<4}{e.weapons[want]['display_name']:<22}"
                f"{'YES' if want in top3 else 'no':<8}"
                f"{'r' + str(rank) if rank else 'out-of-pool':<12}"
                f"{', '.join(e.weapons[w]['display_name'] for w in top3)}")
    finally:
        e.set_dressing(True)
    return rows, unresolved, case_lines


MODE_NAMES = {"w": "V3-W weapon-only (symmetric naked benchmark)",
              "d": "V3-D dressed (production metric — THE GATE)"}


def score(args):
    with open(args.form, encoding="utf-8") as f:
        text = f.read()
    # A form generated since 2026-08-27 carries its own context — scoring
    # under the wrong content/size/style silently invalidates a round.
    m = re.search(r"^-[ \t]*FORM_CONTEXT:[ \t]*(\S+)[ \t]+(\d+)[ \t]+(\S+)",
                  text, re.MULTILINE)
    if m:
        content, size, style = m.group(1), int(m.group(2)), m.group(3)
        if args.size != 7 and args.size != size:
            print(f"note: form declares size {size}; overriding --size")
        e = Engine(content=content, size=size, style=style)
    else:
        e = Engine(size=args.size)
    cases = _parse_cases(text)
    if not cases:
        sys.exit("no cases found — is this a filled form from `generate`?")

    modes = ["w", "d"] if args.mode == "both" else [args.mode]
    report, gate_rate = {}, None
    for mode in modes:
        rows, unresolved, case_lines = _score_mode(e, cases, mode)
        m = _metrics(rows)
        report[mode] = {"metrics": m, "rows": rows,
                        "unresolved": unresolved}
        print(f"\n=== {MODE_NAMES[mode]} ===")
        print(f"{'#':<4}{'expert pick':<22}{'top-3':<8}{'rank':<12}engine top-3")
        print("-" * 96)
        for line in case_lines:
            print(line)
        print("-" * 96)
        if not rows:
            print("no answers filled in yet")
            continue
        print(f"top-1 {_fmt_pct(m['top1'])}   top-{TOP_N} {_fmt_pct(m['top3'])}   "
              f"acceptable top-{TOP_N} {_fmt_pct(m['acceptable_top3'])}   "
              f"conf-weighted {_fmt_pct(m['conf_weighted_top3'])}")
        mr = "-" if m["mean_rank"] is None else f"{m['mean_rank']:.1f}"
        print(f"expert-pick rank: mean {mr} median {m['median_rank']} "
              f"(n={m['rank_n']}, outside pool {m['outside_pool']})")
        print(f"primary-need agreement {_fmt_pct(m['need_agreement'])} "
              f"(n={m['need_n']})   bad-pick-in-top3 rate "
              f"{_fmt_pct(m['bad_pick_rate'])} (n={m['bad_n']})")
        if unresolved:
            print("unresolved answers (fix spelling or use PARTY_KEYS names):")
            for i, p in unresolved:
                print(f"  case {i}: {p!r}")
        if mode == "d":
            gate_rate = m["top3"] if rows else None

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=1, sort_keys=True)
        print(f"\nwrote {args.json}")

    if "d" not in modes:
        print("\n(no V3-D section scored — the gate applies to V3-D; "
              "this run is benchmark-only)")
        return 0
    if gate_rate is None:
        sys.exit("no answers filled in yet")
    print(f"\ngate (V3-D top-{TOP_N}): {gate_rate:.0%} vs {GATE:.0%} -> "
          f"{'PASS' if gate_rate >= GATE else 'FAIL'}")
    if gate_rate < GATE:
        print("Per VALIDATION.md: a miss where the expert is right becomes a "
              "new golden case in tests/test_golden.py. Review misses before "
              "retuning.")
    return 0 if gate_rate >= GATE else 1


# The Deadlyhooker comp is tagged with the content it was written for, which
# is broader than any single template; map to the closest fitted one.
V4_CONTENT_MAP = {"large_scale_zvz": "territory_defense"}

V4_CLASSES = ("weapon_only", "doctrine_inferred", "actual_gear")


def v4(args):
    """Meta-comp reproduction (leave-one-out) against data/published_comps/.

    For every weapon slot in every real comp party: remove it, ask the engine
    for its top-N at that party's size, and score two ways —
      weapon-level: any of the slot's listed weapons (alternatives count) is
                    in the top-N;
      role-level:   for healer/tank slots, ANY weapon of that role is in the
                    top-N ("propose the missing member's ROLE", VALIDATION V4).
    Battlemount slots are outside the weapon model and are skipped.

    DRESSED (2026-08-27): each drop is scored under the three incumbent-gear
    classes documented in the module docstring. The exit-code gate stays on
    the legacy weapon_only role metric until an owner ruling re-bases it.

    CIRCULARITY CAVEATS (printed in the report): the 20-size templates took
    role-ratio calibration from these same comps, so treat results as a
    weak-form check until comps from uninvolved callers exist; and the kit
    DOCTRINE was mined from these same comps' slots, so doctrine_inferred
    reproduction is doubly weak-form (actual_gear incumbents dodge that,
    but the CANDIDATE's doctrine kit still descends from these comps).
    """
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    if not os.path.exists(args.comps):
        sys.exit(f"{args.comps} not found — see data/published_comps/ for the "
                 "schema; comps must be REAL, never invented.")
    # A directory of published_comp docs (data/published_comps/, the
    # production evidence layer) or a single file — which may be one
    # published_comp doc or the legacy {comps: [...]} shape.
    paths = (sorted(glob.glob(os.path.join(args.comps, "*.yaml")))
             if os.path.isdir(args.comps) else [args.comps])
    comps = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if isinstance(doc, dict) and doc.get("kind") == "published_comp":
            comps.append(doc)
        elif isinstance(doc, dict):
            comps += doc.get("comps", [])
        elif isinstance(doc, list):
            comps += doc

    probe = Engine()
    role_sets = probe.scoring.get("role_sets", {})
    ROLE_POOLS = {"healer": set(role_sets.get("healers", [])),
                  "tank": set(role_sets.get("frontline", [])),
                  "main_tank": set(role_sets.get("frontline", []))}
    try:
        builds_flat = gear_join.load_builds_flat(ROOT)
    except OSError:
        builds_flat = {}
        print("  note: builds_index.json unavailable — actual_gear class "
              "will resolve nothing")

    tallies = {cl: {"w_hits": 0, "w_total": 0, "r_hits": 0, "r_total": 0,
                    "misses": []} for cl in V4_CLASSES}
    divergences = []
    resolution = []
    for comp in comps:
        content = V4_CONTENT_MAP.get(comp.get("content"), comp.get("content"))
        if content not in probe.data["templates"]:
            print(f"  skip {comp.get('id','?')}: no template for content "
                  f"{comp.get('content')!r}")
            continue
        # A comp is evaluated under its own declared style (the comp doc's
        # `style:`, quoted from the comp's source — e.g. Timothy's blap is
        # "(brawl comp)"). Default balanced. Scoring a deliberate melee ball
        # under balanced misreads its missing ranged core as a deficiency.
        # 2026-08-28: a record may be EXCLUDED outright (PvE content, the
        # bomb-squad archetype, or a party its own author says is not built
        # properly) — an excluded record is still evidence for other work,
        # it just never teaches the model what a comp should look like.
        if comp.get("fit_exclude"):
            print(f"  skip {comp.get('id','?')}: fit_exclude — "
                  f"{(comp['fit_exclude'].get('reason') or '').strip()[:80]}")
            continue
        style = comp.get("style", "balanced")
        for party in comp.get("parties", []):
            # per-party style/exclusion (this file's parties are not one comp
            # shape); the record-level value is the fallback
            if party.get("fit_exclude"):
                print(f"  skip {comp.get('id','?')}:{party.get('name','?')}: "
                      "fit_exclude — "
                      f"{(party['fit_exclude'].get('reason') or '').strip()[:70]}")
                continue
            style = party.get("style") or comp.get("style", "balanced")
            all_slots = party.get("slots", [])
            # the builds_index join indexes the FULL slot list (battlemounts
            # included) — keep the original enumeration alongside the filter
            slots = [(j, s) for j, s in enumerate(all_slots)
                     if s.get("weapons") and s.get("role") != "battlemount"]
            members = [s["weapons"][0] for _, s in slots]
            e = Engine(content=content, size=len(members), style=style)
            actual, res_n, rec_n = [], 0, 0
            for j, _s in slots:
                bid = f"{comp.get('id','?')}:{party.get('name','?')}:{j}"
                gl, res, rec = gear_join.slot_gears(builds_flat.get(bid), e.gear)
                actual.append(gl)
                res_n += res
                rec_n += rec
            doctrine = gear_join.doctrine_gears(e, members)
            resolution.append((comp.get("id", "?"), party.get("name", "?"),
                               len(members), res_n, rec_n,
                               sum(1 for a in actual if a)))
            for i, (_j, slot) in enumerate(slots):
                rest = members[:i] + members[i + 1:]
                tops = {}
                for cl, gl in (("weapon_only", None),
                               ("doctrine_inferred",
                                doctrine[:i] + doctrine[i + 1:]),
                               ("actual_gear", actual[:i] + actual[i + 1:])):
                    top = [r["weapon"] for r in e.recommend(rest, TOP_N,
                                                            gears=gl)]
                    tops[cl] = top
                    t = tallies[cl]
                    hit = any(alt in top for alt in slot["weapons"])
                    t["w_hits"] += hit
                    t["w_total"] += 1
                    pool = ROLE_POOLS.get(slot.get("role"))
                    if pool:
                        t["r_hits"] += any(w in pool for w in top)
                        t["r_total"] += 1
                    if not hit:
                        t["misses"].append(
                            f"{comp.get('id','?')}/{party.get('name','?')} "
                            f"dropped {slot.get('raw','?')} "
                            f"({slot.get('role','?')}) -> "
                            f"{', '.join(e.weapons[w]['display_name'] for w in top)}")
                if tops["weapon_only"] != tops["actual_gear"]:
                    divergences.append(
                        f"{comp.get('id','?')}/{party.get('name','?')} "
                        f"dropped {slot.get('raw','?')}: naked top-3 "
                        f"{', '.join(e.weapons[w]['display_name'] for w in tops['weapon_only'])}"
                        f" | actual-gear top-3 "
                        f"{', '.join(e.weapons[w]['display_name'] for w in tops['actual_gear'])}")

    base = tallies["weapon_only"]
    if not base["w_total"]:
        sys.exit("no scoreable slots")

    print(f"V4 leave-one-out over {base['w_total']} slots "
          f"(top-{TOP_N}, battlemounts excluded):")
    for cl in V4_CLASSES:
        t = tallies[cl]
        rl = (f"role-level {t['r_hits']}/{t['r_total']} = "
              f"{t['r_hits'] / t['r_total']:.0%}" if t["r_total"] else "role-level n/a")
        print(f"  [{cl:<17}] weapon-level: {t['w_hits']}/{t['w_total']} = "
              f"{t['w_hits'] / t['w_total']:.0%}   {rl}")
    print("  incumbent-gear resolution per party (actual_gear class):")
    for cid, pname, n_mem, res, rec, dressed_n in resolution:
        print(f"    {cid}/{pname}: {dressed_n}/{n_mem} members dressed, "
              f"{res}/{rec} recorded pieces resolved into the curated catalog")
    print(f"  dressed-vs-naked top-3 divergence: {len(divergences)}/"
          f"{base['w_total']} slots")
    r = base
    print(f"  gate {GATE:.0%} applies to the weapon_only ROLE metric "
          f"(legacy — re-basing to a dressed class is an owner ruling) -> "
          f"{'PASS' if r['r_total'] and r['r_hits'] / r['r_total'] >= GATE else 'FAIL/insufficient'}")
    print("  caveat: 20-size templates were role-ratio calibrated on these "
          "same comps — weak-form evidence until independent comps exist.")
    print("  caveat: kit doctrine was mined from these same comps' slots — "
          "doctrine_inferred is doubly weak-form; actual_gear incumbents "
          "avoid that, the candidate's doctrine kit does not.")
    if args.verbose:
        for cl in V4_CLASSES:
            if tallies[cl]["misses"]:
                print(f"\n[{cl}] weapon-level misses:")
                for m in tallies[cl]["misses"]:
                    print(f"  {m}")
        if divergences:
            print("\ndressed-vs-naked divergences:")
            for d in divergences:
                print(f"  {d}")
    if args.json:
        payload = {
            "classes": {cl: {k: v for k, v in tallies[cl].items()
                             if k != "misses"} for cl in V4_CLASSES},
            "misses": {cl: tallies[cl]["misses"] for cl in V4_CLASSES},
            "divergences": divergences,
            "resolution": [{"comp": c, "party": p, "members": n,
                            "resolved": res, "recorded": rec,
                            "members_dressed": d}
                           for c, p, n, res, rec, d in resolution],
        }
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=1, sort_keys=True)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate"); g.set_defaults(fn=generate)
    g.add_argument("--n", type=int, default=12)
    g.add_argument("--size", type=int, default=7)
    g.add_argument("--seed", type=int, default=20260812)
    g.add_argument("--content", default="castle_outpost")
    g.add_argument("--style", default="balanced")
    g.add_argument("--out", default="tier2_form.md")

    s = sub.add_parser("score"); s.set_defaults(fn=score)
    s.add_argument("form")
    s.add_argument("--size", type=int, default=7)
    s.add_argument("--mode", choices=["both", "w", "d"], default="both")
    s.add_argument("--json", default=None, help="dump per-case rows + metrics")

    v = sub.add_parser("v4"); v.set_defaults(fn=v4)
    v.add_argument("comps", nargs="?",
                   default=os.path.join(ROOT, "data", "published_comps"))
    v.add_argument("--verbose", action="store_true", help="list weapon-level misses")
    v.add_argument("--json", default=None, help="dump per-class tallies")

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
