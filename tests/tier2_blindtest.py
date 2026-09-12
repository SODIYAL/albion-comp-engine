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
  weapon_only        the legacy naked-incumbent metric. REPORTED, NOT
                     GATED since 2026-08-29: the unit re-fit moved every
                     target into PERSON units, so scoring naked
                     incumbents measures in the unit the model has left.
  doctrine_inferred  incumbents in kit_variants v0 (inferred, and labeled
                     so — the doctrine pools were mined from these same
                     comps, so this class is doubly weak-form)
  actual_gear        incumbents in the gear their published source
                     actually records (builds_index join; published
                     comps carry gear on every slot). Unresolved pieces
                     stay off the member and are counted, never guessed.
                     ** THIS IS THE EXIT-CODE GATE ** (owner ruling
                     2026-08-29). It scores incumbents in their real
                     kits — what the page does — and is the only class
                     whose incumbents are not mined from the same
                     doctrine the engine uses.
Candidates always take the normal dressed path. Weapon-only reproduction
is NOT production recommendation accuracy; the dressed sections are the
production-faithful measurements.

This script does the three mechanical parts. It cannot do the human part.

    generate  build N partial parties and write a blind form (the form shows NO
              engine output — that is what makes it blind)
    score     read the filled form + compare against engine top-3 per mode
    v4        reproduce published meta comps minus one member
    v4h       the same leave-one-out over the killer-party HARVEST (report-only)

Usage:
    py -3 tests/tier2_blindtest.py generate --n 12 --out tier2_form.md
    py -3 tests/tier2_blindtest.py score tier2_form_filled.md [--mode both|w|d]
    py -3 tests/tier2_blindtest.py v4 [--verbose] [--json out.json]
    py -3 tests/tier2_blindtest.py v4h [--n 150] [--drop 3] [--rebuild 5] [--holdout-mod 5]

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
    # GATE RE-BASED to actual_gear (owner ruling 2026-08-29), and it now
    # ENFORCES — the v4 path used to return 0 unconditionally, so the verdict
    # was printed and never checked. Why actual_gear: the unit re-fit moved
    # every target into PERSON units, which makes weapon_only — naked
    # incumbents — a measurement in the unit the model has left. It fell
    # 87% -> 70% on the re-fit for that reason alone, while the dressed
    # classes rose to 87%. actual_gear scores incumbents in their REAL
    # recorded kits, which is what the page does, and it is the one class
    # whose incumbents are not mined from the doctrine the engine also uses
    # (doctrine_inferred is doubly weak-form — see the caveat below).
    r = tallies["actual_gear"]
    gate_ok = bool(r["r_total"]) and r["r_hits"] / r["r_total"] >= GATE
    legacy = base["r_hits"] / base["r_total"] if base["r_total"] else 0.0
    print(f"  GATE {GATE:.0%} on the actual_gear ROLE metric "
          f"(re-based from weapon_only, owner 2026-08-29) -> "
          f"{'PASS' if gate_ok else 'FAIL/insufficient'}"
          f"  [{r['r_hits']}/{r['r_total']}]")
    print(f"  legacy weapon_only role metric, reported not gated: "
          f"{legacy:.0%} — naked incumbents, the pre-re-fit unit")
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
    return 0 if gate_ok else 1


# ---------------------------------------------------------------- V4h ----
V4H_CLASSES = ("weapon_only", "harvest_gear", "harvest_gear_doctrine")
V4H_GEAR_SLOTS = ("Head", "Armor", "Shoes", "Cape", "OffHand", "Potion", "Food")


def _harvest_parties(doc, styles, e_probe, min_size, max_size, holdout_mod):
    """Killer parties of [min_size, max_size] with every weapon known and in
    the catalog, each with its weapons-only style label (party_styles.json,
    the descriptive comp_identity read; `balanced` where the label is none /
    split) and its linked builds' gear. `holdout_mod` keeps only battles
    whose id % mod == 0 — a deterministic slice, see the caveat in v4h()."""
    import party_link
    by_battle = party_link.parties_by_battle(doc)
    label = {(x["battle"], x["index"]): x for x in styles.get("parties", [])}
    builds = {}
    for b in doc.get("builds") or []:
        if not b.get("gear"):
            continue
        idx = party_link.link_build(b, by_battle)
        if idx is not None:
            builds.setdefault((b["battle"], idx), []).append(b)
    cat = set(e_probe.weapons)
    out = []
    for battle in sorted(by_battle):
        if holdout_mod and int(battle) % holdout_mod != 0:
            continue
        for p in by_battle[battle]:
            ws = p.get("weapons") or []
            n = p.get("size") or 0
            if not (min_size <= n <= max_size) or p.get("known_weapons") != n:
                continue
            if len(ws) != n or any(w not in cat for w in ws):
                continue
            lab = label.get((battle, p["index"]))
            style = lab["style"] if lab and lab.get("style") in (e_probe.data.get("styles") or {}) else "balanced"
            out.append({"battle": battle, "index": p["index"], "size": n,
                        "weapons": list(ws), "style": style,
                        "builds": builds.get((battle, p["index"]), [])})
    return out


def _harvest_gears(party, e):
    """Per-member recorded kit from the party's linked builds: a build is
    matched to the first still-unmatched member holding its weapon (the
    roster is a multiset; builds carry no slot index). Members with no
    linked build stay None — honestly naked, counted, never guessed.
    Returns (gears, members_dressed, pieces_resolved, pieces_recorded)."""
    gears = [None] * len(party["weapons"])
    taken = set()
    res = rec = 0
    for b in sorted(party["builds"], key=lambda x: (x.get("player") or "", x.get("weapon") or "")):
        for i, w in enumerate(party["weapons"]):
            if i in taken or w != b.get("weapon"):
                continue
            kit = []
            for slot in V4H_GEAR_SLOTS:
                v = (b.get("gear") or {}).get(slot)
                if not v:
                    continue
                rec += 1
                gid = gear_join.normalize_gear_id(v, e.gear)
                if gid is not None:
                    kit.append(gid)
                    res += 1
            gears[i] = kit or None
            taken.add(i)
            break
    return gears, len(taken), res, rec


def v4h(args):
    """V4 on the killer-party HARVEST (report-only, 2026-09-10): the same
    leave-one-out as v4, over harvested parties of 10+ instead of the 23
    published-comp slots. A killer party is a roster that took kills in a
    real fight — win-conditioned evidence of what gets fielded, not a
    ruling on what should be. Three incumbent-gear classes:

      weapon_only            naked incumbents (the pre-re-fit unit; reported
                             for continuity with v4)
      harvest_gear           incumbents in the gear their own linked
                             killboard build records; members with no
                             linked build stay NAKED and are counted
      harvest_gear_doctrine  as above, unlinked members in their doctrine
                             kit (kit_variants v0) — inferred and labeled

    Each sampled party drops `--drop` members (leave-one-out, the v4
    metric) and, with `--rebuild k`, also removes its LAST k members at
    once and rebuilds greedily (top-1, add, repeat) — V4b: the published
    corpus is too small for it, the harvest is not. A rebuild step is a
    weapon hit when the pick is one of the still-missing removed weapons,
    a role hit when its role pool (healer / tank) is one still missing —
    recall per removed member, each consumed by the first pick that
    supplies it.

    CIRCULARITY, stated plainly: `templates/style_bands.yaml` and the meta
    prior are DERIVED from this same harvest (labelled rosters -> p10/p90
    rows; distinct players -> prior). `--holdout-mod M` evaluates only
    battles with id % M == 0 as a deterministic slice, but
    derive_style_bands.py does NOT yet exclude that slice when fitting —
    until it does, every number here is weak-form on the styled rows.
    Content is not recorded on a killer party; `--content` sets the
    template (default blackzone_roam, the ZvZ roam rows); the style is the
    party's weapons-only label (party_styles.json) or balanced.

    NOT A GATE. Prints beside v4 so the two can be compared; promotion to a
    gate is an owner decision once the holdout split is honoured end to end.
    """
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import rosters_io
    rosters_path = rosters_io.path(os.path.join(ROOT, "pipeline", "out"))
    styles_path = os.path.join(ROOT, "pipeline", "out", "party_styles.json")
    if not os.path.exists(rosters_path):
        sys.exit(f"{rosters_path} missing — run the harvest fold first")
    doc = rosters_io.load(rosters_path)
    styles = {}
    if os.path.exists(styles_path):
        with open(styles_path, encoding="utf-8") as f:
            styles = json.load(f)
    probe = Engine()
    if args.content not in probe.data["templates"]:
        sys.exit(f"no template for content {args.content!r}")
    role_sets = probe.scoring.get("role_sets", {})
    pools = {"healer": set(role_sets.get("healers", [])),
             "tank": set(role_sets.get("frontline", []))}

    def role_of(w):
        for r, pool in pools.items():
            if w in pool:
                return r
        return None

    parties = _harvest_parties(doc, styles, probe, args.min_size, args.max_size,
                               args.holdout_mod)
    if not parties:
        sys.exit("no harvested parties match the filter")
    rng = random.Random(args.seed)
    sample = parties if args.n >= len(parties) else rng.sample(parties, args.n)
    sample.sort(key=lambda p: (p["battle"], p["index"]))

    tallies = {cl: {"w_hits": 0, "w_total": 0, "r_hits": 0, "r_total": 0}
               for cl in V4H_CLASSES}
    rebuild = {cl: {"w_hits": 0, "r_hits": 0, "r_total": 0, "total": 0}
               for cl in V4H_CLASSES}
    dressed_n = res_n = rec_n = members_n = 0
    by_style = {}
    engines = {}
    for p in sample:
        key = (p["size"], p["style"])
        e = engines.get(key)
        if e is None:
            e = engines[key] = Engine(content=args.content, size=p["size"], style=p["style"])
        ws = p["weapons"]
        actual, dn, res, rec = _harvest_gears(p, e)
        doctrine = gear_join.doctrine_gears(e, ws)
        mixed = [a if a else d for a, d in zip(actual, doctrine)]
        dressed_n += dn; res_n += res; rec_n += rec; members_n += len(ws)
        classes = {"weapon_only": None, "harvest_gear": actual,
                   "harvest_gear_doctrine": mixed}
        drops = list(range(len(ws)))
        if args.drop < len(ws):
            drops = sorted(rng.sample(drops, args.drop))
        st = by_style.setdefault(p["style"], {"r_hits": 0, "r_total": 0, "parties": 0})
        st["parties"] += 1
        for i in drops:
            rest = ws[:i] + ws[i + 1:]
            role = role_of(ws[i])
            for cl, gl in classes.items():
                g = None if gl is None else gl[:i] + gl[i + 1:]
                top = [r["weapon"] for r in e.recommend(rest, TOP_N, gears=g)]
                t = tallies[cl]
                t["w_hits"] += ws[i] in top
                t["w_total"] += 1
                if role:
                    hit = any(w in pools[role] for w in top)
                    t["r_hits"] += hit
                    t["r_total"] += 1
                    if cl == "harvest_gear":
                        st["r_hits"] += hit
                        st["r_total"] += 1
        k = args.rebuild
        if k and k < len(ws):
            removed = ws[-k:]
            for cl, gl in classes.items():
                cur = list(ws[:-k])
                g = None if gl is None else list(gl[:-k])
                # recall per removed member: weapons still missing, and the
                # role pools (healer / tank) still missing, each consumed by
                # the first pick that supplies it
                missing_w = list(removed)
                missing_r = [role_of(m) for m in removed if role_of(m)]
                rb = rebuild[cl]
                rb["total"] += len(removed)
                rb["r_total"] += len(missing_r)
                for _step in range(k):
                    top = [r["weapon"] for r in e.recommend(cur, 1, gears=g)]
                    if not top:
                        break
                    pick = top[0]
                    if pick in missing_w:
                        rb["w_hits"] += 1
                        missing_w.remove(pick)
                    pr = role_of(pick)
                    if pr and pr in missing_r:
                        rb["r_hits"] += 1
                        missing_r.remove(pr)
                    cur.append(pick)
                    if g is not None:
                        g.append(dict(e.kit_variants(pick)).get("v0"))

    base = tallies["weapon_only"]
    print(f"V4h leave-one-out over the killer-party harvest: {len(sample)} parties "
          f"of {len(parties)} eligible (size {args.min_size}-{args.max_size}, "
          f"{'battles id%' + str(args.holdout_mod) + '==0' if args.holdout_mod else 'all battles'}, "
          f"seed {args.seed}), {args.drop} drops per party = {base['w_total']} drops; "
          f"content {args.content}, style = the party's weapons-only label")
    for cl in V4H_CLASSES:
        t = tallies[cl]
        rl = (f"role-level {t['r_hits']}/{t['r_total']} = {t['r_hits'] / t['r_total']:.0%}"
              if t["r_total"] else "role-level n/a")
        print(f"  [{cl:<22}] weapon-level: {t['w_hits']}/{t['w_total']} = "
              f"{t['w_hits'] / t['w_total']:.0%}   {rl}")
    print(f"  incumbent gear (harvest_gear class): {dressed_n}/{members_n} members "
          f"carry a linked build ({dressed_n / members_n:.0%}); {res_n}/{rec_n} recorded "
          f"pieces resolved into the curated catalog; the rest are honestly naked")
    print("  role-level by style label (harvest_gear):")
    for sty in sorted(by_style):
        st = by_style[sty]
        rl = f"{st['r_hits']}/{st['r_total']} = {st['r_hits'] / st['r_total']:.0%}" if st["r_total"] else "n/a"
        print(f"    {sty:<11} {st['parties']:>4} parties   {rl}")
    if args.rebuild:
        print(f"  V4b rebuild of the last {args.rebuild} members (greedy top-1):")
        for cl in V4H_CLASSES:
            rb = rebuild[cl]
            if rb["total"]:
                rl = f"role {rb['r_hits']}/{rb['r_total']} = {rb['r_hits'] / rb['r_total']:.0%}" if rb["r_total"] else "role n/a"
                print(f"    [{cl:<22}] weapon {rb['w_hits']}/{rb['total']} = "
                      f"{rb['w_hits'] / rb['total']:.0%}   {rl}")
    print("  caveat: style_bands.yaml rows and the meta prior are derived from this "
          "same harvest; the --holdout-mod slice is not yet excluded by "
          "derive_style_bands.py, so styled numbers are weak-form.")
    print("  caveat: a killer party is win-conditioned evidence of what is fielded, "
          "never a ruling; NOT A GATE - reported beside v4 for the owner.")
    if args.json:
        payload = {"parties": len(sample), "eligible": len(parties),
                   "filter": {"min_size": args.min_size, "max_size": args.max_size,
                              "holdout_mod": args.holdout_mod, "seed": args.seed,
                              "drop": args.drop, "rebuild": args.rebuild,
                              "content": args.content},
                   "classes": tallies, "rebuild": rebuild, "by_style": by_style,
                   "gear": {"members": members_n, "dressed": dressed_n,
                            "resolved": res_n, "recorded": rec_n}}
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

    h = sub.add_parser("v4h"); h.set_defaults(fn=v4h)
    h.add_argument("--n", type=int, default=150, help="parties to sample")
    h.add_argument("--drop", type=int, default=3, help="leave-one-out drops per party")
    h.add_argument("--rebuild", type=int, default=0, help="V4b: rebuild the last k members")
    h.add_argument("--min-size", type=int, default=10)
    h.add_argument("--max-size", type=int, default=20)
    h.add_argument("--holdout-mod", type=int, default=5,
                   help="evaluate battles with id %% M == 0 only (0 = all)")
    h.add_argument("--content", default="blackzone_roam")
    h.add_argument("--seed", type=int, default=20260910)
    h.add_argument("--json", default=None)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
