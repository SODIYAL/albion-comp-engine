#!/usr/bin/env python3
"""
Tier-2 validation harness — V3 (shotcaller blind test) and V4 (meta-comp
reproduction). See tests/VALIDATION.md.

V3 is the project's TRUE accuracy metric: give experienced shotcallers partial
parties, collect their next pick independently, and measure how often that pick
appears in the engine's top-3. Gate: >=70%.

DRESSED VALIDATION: the production engine evaluates DRESSED
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
                     GATED since the unit re-fit, which moved every
                     target into PERSON units, so scoring naked
                     incumbents measures in the unit the model has left.
  doctrine_inferred  incumbents in kit_variants v0 (inferred, and labeled
                     so — the doctrine pools were mined from these same
                     comps, so this class is doubly weak-form)
  actual_gear        incumbents in the gear their published source
                     actually records (builds_index join; published
                     comps carry gear on every slot). Unresolved pieces
                     stay off the member and are counted, never guessed.
                     ** THIS IS THE EXIT-CODE GATE ** (tests/VALIDATION.md
                     gates). It scores incumbents in their real
                     kits — what the page does — and is the only class
                     whose incumbents are not mined from the same
                     doctrine the engine uses.
Candidates always take the normal dressed path. Weapon-only reproduction
is NOT production recommendation accuracy; the dressed sections are the
production-faithful measurements.

BASELINE (spec notes/specs/2026-09-15-skeleton-first-
generation-design.md decision 6): `v4 --baseline` and `v4h --baseline`
also score a role-skeleton-plus-popularity recommender
(baseline_recommend: candidates ranked by need — the role under its band
minimum first, then under its typical — then by the meta prior's solo
share, top-3) through the SAME leave-one-out tallies and hit rules, and
print it as one extra row beside the engine's classes. REPORT-ONLY,
NEVER A GATE, never an exit-code input: the capability model must beat
it or it is not earning its complexity. Without the flag nothing else
changes — every number and the exit code are those of the engine alone.

This script does the three mechanical parts. It cannot do the human part.

    generate  build N partial parties and write a blind form (the form shows NO
              engine output — that is what makes it blind) and, beside it,
              the form's answer key
    score     read the filled form + compare against engine top-3 per mode,
              and against the harvest where the form has a key
    v4        reproduce published meta comps minus one member
    v4h       the same leave-one-out over the killer-party HARVEST (report-only)

Usage:
    py -3 -u tests/tier2_blindtest.py generate --round 3 --content ancient_lands --size 3 --seed 20261008 --out tests/tier2_form_r3_portal3.md
    py -3 tests/tier2_blindtest.py generate --from-pool --n 12 --out tier2_form.md
    py -3 tests/tier2_blindtest.py score tier2_form_filled.md [--mode both|w|d] [--key K]
    py -3 tests/tier2_blindtest.py v4 [--verbose] [--json out.json] [--baseline]
    py -3 tests/tier2_blindtest.py v4h [--n 150] [--drop 3] [--rebuild 5] [--holdout-mod 5] [--baseline]

HARVEST-SEEDED FORMS (the default; harvest_cases): every case is a real
killer party of exactly the form's size, every weapon known and in the
catalog, with a seeded-random number of its members removed (2..size-1
shown; one removed at size 3). The population is the content's evidence
unit (FORM_POPULATIONS: the Dragon Portal reads the dominant killer
parties of the portal harvest, as pipeline/derive_portal_rows.py fits
its rows; every other content reads the battle-list killer parties).
Only the TRAINING split is drawn (battle % 5 != 0: the holdout slice v4h
evaluates is never shown to a grader), never a battle a graded round
showed (pipeline/graded_battles.py) nor one an earlier V3 round's key
records; parties are drawn as v4h draws them, one case per distinct
roster. The form shows the kept
members alone; the source of each case (battle, party index, the removed
weapons) goes to the answer key beside it, `<form>.key.json`, which is
never sent to a grader. `score` reads the key and reports, beside the
engine's agreement, how often the grader's pick names a removed member
(harvest agreement; report-only, never a gate input).

`--from-pool` keeps the draw of V3 rounds 1-2: partial parties sampled
from the whole weapon pool, which put weapons at seven the harvest fields
in under 2% of size-7 killer parties (Glaive, Druidic Staff, Spear, Pike,
Warbow); no key. Party generation is seeded and deterministic in both
modes, so every shotcaller sees the same parties and a re-run reproduces
the same set (a harvest form on the same artifact, whose hash its key
records; `--from-pool` with seed 20260812 still emits the
validation-round-1 parties' PARTY_KEYS unchanged).
"""
import collections, glob, json, os, statistics, sys, argparse, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from engine import Engine  # noqa: E402
import gear_join  # noqa: E402
from graded_battles import GRADED_BATTLES  # noqa: E402

TOP_N = 3          # "shotcaller pick appears in engine top-3"
FULL_RANK = 10 ** 6  # top_n that returns every candidate (the v4h rank metric)
GATE = 0.70        # VALIDATION.md V3 gate
FULL_RANK = 10 ** 6  # top_n large enough to return the whole ranked pool

# Shotcaller PRIMARY NEED vocabulary -> engine capability. PROVISIONAL alias
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


# ------------------------------------------------------------ generate ----
# The harvest population a form reads, by content: the evidence unit the
# content's rows were fitted on. The Dragon Portal's is the dominant killer
# party of the pool (no deaths, a kill) in the portal harvest, as
# pipeline/derive_portal_rows.py fits its rows and v4h reads its pools;
# every other content reads the battle-list killer parties (v4h's default).
FORM_POPULATIONS = {
    "ancient_lands": {"source": "all", "content": "ancient_lands", "dominant": True},
}
FORM_POPULATION_DEFAULT = {"source": "battle_list", "content": None, "dominant": False}
# battles with id % 5 == 0 are the holdout slice v4h evaluates and every
# harvest-derived table leaves out; a form never shows one to a grader
FORM_HOLDOUT_MOD = 5
KEY_GLOB = "tier2_form_*.key.json"


def _known_party(p, catalog, min_size, max_size, dominant=False):
    """A killer party of [min_size, max_size] members with every weapon
    known and in the catalog; `dominant` also asks that it took no deaths
    and a kill in its battle (the portal pools' unit). The one eligibility
    rule of the harvest readers here (v4h and the forms)."""
    ws = p.get("weapons") or []
    n = p.get("size") or 0
    if not (min_size <= n <= max_size) or p.get("known_weapons") != n:
        return False
    if len(ws) != n or any(w not in catalog for w in ws):
        return False
    return not dominant or ((p.get("deaths") or 0) == 0 and (p.get("kills") or 0) > 0)


def _battle_id(b):
    try:
        return int(b)
    except (TypeError, ValueError):
        return b


def _training(battle, holdout_mod):
    """Training-split membership: battle % holdout_mod != 0. An id that is
    not a number sits in no split."""
    if not holdout_mod:
        return True
    try:
        return int(battle) % holdout_mod != 0
    except (TypeError, ValueError):
        return False


def harvest_cases(doc, catalog, size, n, seed, dominant=False, excluded=None,
                  holdout_mod=FORM_HOLDOUT_MOD):
    """The cases of a harvest-seeded form, from a loaded roster artifact.

    Eligible: a killer party of exactly `size` members with every weapon
    known and in `catalog` (`dominant`: no deaths and a kill), in a battle
    of the training split (battle % holdout_mod != 0) and in no battle of
    `excluded` ({reason: battle ids}: the graded battles, the battles of
    earlier rounds' forms). The eligible parties, in battle-id and
    party-index order, are shuffled by `seed` and drawn as v4h draws them
    (by party, so a roster fielded more often is drawn more often); each
    drawn party keeps a seeded-random 2..size-1 of its members (one
    removed at size 3), and a party whose roster (the weapon multiset) or
    partial party an earlier case already shows is passed over: one case
    per distinct roster. Deterministic for a seed and an artifact.

    Returns (cases, counts): a case is {battle, party, sightings, shown,
    removed} (`party` the party's index in its battle, `sightings` the
    eligible parties fielding its roster); counts are `parties` of the
    size in the population, `not_training`, one per excluded reason,
    `eligible` and `rosters` (distinct among the eligible)."""
    import party_link
    if size < 3:
        raise ValueError("a harvest-seeded form needs a size of 3 or more "
                         "(2..size-1 members shown)")
    excluded = {r: {_battle_id(b) for b in ids} for r, ids in (excluded or {}).items()}
    counts = {"parties": 0, "not_training": 0}
    counts.update({r: 0 for r in excluded})
    eligible, sightings = [], collections.Counter()
    by_battle = party_link.parties_by_battle(doc)
    for battle in sorted(by_battle, key=lambda b: (type(b).__name__, b)):
        for p in sorted(by_battle[battle], key=lambda q: q["index"]):
            if not _known_party(p, catalog, size, size, dominant):
                continue
            counts["parties"] += 1
            if not _training(battle, holdout_mod):
                counts["not_training"] += 1
                continue
            why = next((r for r in sorted(excluded)
                        if _battle_id(battle) in excluded[r]), None)
            if why:
                counts[why] += 1
                continue
            eligible.append((battle, p["index"], list(p["weapons"])))
            sightings[tuple(sorted(p["weapons"]))] += 1
    counts["eligible"] = len(eligible)
    counts["rosters"] = len(sightings)
    rng = random.Random(seed)
    cases, rosters_shown, partials_shown = [], set(), set()
    for battle, index, ws in rng.sample(eligible, len(eligible)):
        if len(cases) >= n:
            break
        roster = tuple(sorted(ws))
        if roster in rosters_shown:
            continue
        kept = set(rng.sample(range(size), rng.randint(2, size - 1)))
        shown = [w for i, w in enumerate(ws) if i in kept]
        if tuple(sorted(shown)) in partials_shown:
            continue
        rosters_shown.add(roster)
        partials_shown.add(tuple(sorted(shown)))
        cases.append({"battle": battle, "party": index,
                      "sightings": sightings[roster], "shown": shown,
                      "removed": [w for i, w in enumerate(ws) if i not in kept]})
    return cases, counts


def form_key_battles(round_no, keys_dirs=(HERE,), skip=()):
    """The battles the answer keys of EARLIER V3 rounds record (KEY_GLOB in
    `keys_dirs`, a key without a round read as earlier), and the keys read.
    A battle a form has shown is never shown again. Keys of this round or
    a later one are not read, so a round's forms reproduce in any order of
    generation; `skip` names key paths never read (the form's own key)."""
    skip = {os.path.normcase(os.path.abspath(p)) for p in skip}
    battles, used = set(), []
    paths = sorted({os.path.normcase(os.path.abspath(p)) for d in keys_dirs
                    for p in glob.glob(os.path.join(d, KEY_GLOB))})
    for path in paths:
        if path in skip:
            continue
        with open(path, encoding="utf-8") as f:
            key = json.load(f)
        r = key.get("round")
        if isinstance(r, int) and r >= round_no:
            continue
        battles |= {_battle_id(c["battle"]) for c in key.get("cases") or []
                    if c.get("battle") is not None}
        used.append(os.path.basename(path))
    return battles, used


def _display_names(e):
    """Each catalog weapon's display name on a form. A name the catalog
    holds once reads as it is (the in-game names already tell a one-handed
    weapon from its two-handed line: Arcane Staff, Great Arcane Staff); a
    name two weapons share reads with the weapon's key beside it."""
    count = collections.Counter(w["display_name"] for w in e.weapons.values())
    return {k: (w["display_name"] if count[w["display_name"]] == 1
                else f"{w['display_name']} ({k})")
            for k, w in e.weapons.items()}


def form_lines(e, content, size, style, seed, parties):
    """The blind form's lines: instructions, the form's context and one
    case per partial party. It carries the shown members alone, never a
    case's source or the members removed from it."""
    name = _display_names(e)
    pool = (((e.template.get("size_prompt") or {}).get("labels") or {})
            .get(str(size)))
    lines = [
        f"# Tier-2 V3 — shotcaller blind test  ({e.template['name']}, size {size})",
        "",
    ]
    if pool:
        lines += [f"{e.template['name']}: {pool}.", ""]
    lines += [
        "For each case fill in **BEST PICK** — the next player to add.",
        "The other fields are optional; each one filled in makes the round",
        "count for more:",
        "",
        "- PRIMARY NEED — what the party lacks most, in plain words",
        "- OTHER GOOD PICKS — acceptable alternatives, comma-separated",
        "- BAD PICK — a pick to veto if the engine suggested it",
        "- CONFIDENCE — High / Medium / Low",
        "- REASON — one line on why",
        "",
        "Answer from judgement alone — the engine's answer is deliberately",
        "not shown. Use weapons' common names (e.g. `Heavy Mace`, `Hallowfall`).",
        "",
        f"Generated with seed {seed} — send every shotcaller this same file.",
        "",
        f"- FORM_CONTEXT: {content} {size} {style} {seed}",
        "",
    ]
    for i, p in enumerate(parties, 1):
        lines += [f"### Case {i}",
                  f"- Party ({len(p)}/{size}): {', '.join(name[w] for w in p)}",
                  f"- PARTY_KEYS: {' '.join(p)}",
                  "- PRIMARY NEED: ",
                  "- BEST PICK: ",
                  "- OTHER GOOD PICKS: ",
                  "- BAD PICK: ",
                  "- CONFIDENCE: ",
                  "- REASON: ",
                  ""]
    return lines


def _pool_parties(e, args):
    """The draw of V3 rounds 1-2: partial parties of 2..size-1 sampled from
    the whole weapon pool, without replacement (unchanged, so a seed
    reproduces its round's PARTY_KEYS)."""
    pool = sorted(e.weapons)
    rng = random.Random(args.seed)
    parties = []
    while len(parties) < args.n:
        k = rng.randint(2, max(2, args.size - 1))
        p = rng.sample(pool, k)
        if p not in parties:
            parties.append(p)
    return parties


def _rel(path):
    """A path as the repository names it (forward slashes, relative to the
    root where it sits inside)."""
    p = os.path.relpath(os.path.abspath(path), os.path.abspath(ROOT))
    return (os.path.abspath(path) if p.startswith("..") else p).replace(os.sep, "/")


def _harvest_form(e, args, key_path):
    """The partial parties of a harvest-seeded form and its answer key."""
    import rosters_io
    if args.round is None:
        sys.exit("--round N is required: a harvest-seeded form belongs to a V3 "
                 "round, and every battle an earlier round's key records is excluded")
    if args.size < 3:
        sys.exit("a harvest-seeded form needs --size 3 or more (2..size-1 members shown)")
    pop = dict(FORM_POPULATIONS.get(args.content, FORM_POPULATION_DEFAULT))
    if args.harvest_source:
        pop["source"] = args.harvest_source
    if args.harvest_content:
        pop["content"] = args.harvest_content
    if args.dominant:
        pop["dominant"] = True
    path = args.rosters or rosters_io.path(os.path.join(ROOT, "pipeline", "out"))
    if not os.path.exists(path):
        sys.exit(f"{path} missing — run the harvest fold first")
    doc = rosters_io.load(path, source=pop["source"], content=pop["content"])
    earlier, key_files = form_key_battles(
        args.round, (HERE, os.path.dirname(os.path.abspath(args.out))), skip=(key_path,))
    cases, counts = harvest_cases(
        doc, set(e.weapons), args.size, args.n, args.seed, dominant=pop["dominant"],
        excluded={"graded_battles": set(GRADED_BATTLES), "earlier_forms": earlier})
    if len(cases) < args.n:
        print(f"note: {len(cases)} cases, the eligible rosters hold no more distinct partial parties")
    name = _display_names(e)
    order = lambda ws: sorted(ws, key=lambda w: (name[w].lower(), w))
    for c in cases:
        c["shown"], c["removed"] = order(c["shown"]), order(c["removed"])
    unit = ("killer party of exactly the form's size, every weapon known and in the catalog"
            + (", no deaths and a kill" if pop["dominant"] else ""))
    key = {
        "_note": "The answer key of the form named below: each case's source and the "
                 "members removed from it. Never sent with the form.",
        "form": _rel(args.out),
        "round": args.round,
        "context": {"content": args.content, "size": args.size,
                    "style": args.style, "seed": args.seed},
        "population": {"source": pop["source"], "content": pop["content"],
                       "dominant": pop["dominant"], "unit": unit,
                       "split": f"training: battle % {FORM_HOLDOUT_MOD} != 0"},
        "rosters": {"path": _rel(path), "sha256": rosters_io.sha256(path),
                    "battles": len(doc.get("battles") or [])},
        "counts": counts,
        "excluded": {"graded_battles": "pipeline/graded_battles.py "
                                       f"({len(GRADED_BATTLES)} battles)",
                     "earlier_forms": key_files},
        "cases": [dict(c, case=i) for i, c in enumerate(cases, 1)],
    }
    print(f"population: source {pop['source']}, content {pop['content'] or 'any'}, {unit}, "
          f"size {args.size}")
    print(f"parties {counts['parties']}: not on the training split {counts['not_training']}, "
          f"in a graded battle {counts['graded_battles']}, in an earlier round's form "
          f"{counts['earlier_forms']} ({', '.join(key_files) or 'no earlier key'}) -> "
          f"eligible {counts['eligible']} parties, {counts['rosters']} distinct rosters")
    return [c["shown"] for c in cases], key


def generate(args):
    e = Engine(content=args.content, size=args.size, style=args.style)
    key_path = os.path.splitext(args.out)[0] + ".key.json"
    key = None
    if args.from_pool:
        parties = _pool_parties(e, args)
    else:
        parties, key = _harvest_form(e, args, key_path)
    lines = form_lines(e, args.content, args.size, args.style, args.seed, parties)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {args.out}: {len(parties)} cases, size {args.size}, seed {args.seed}")
    if key is not None:
        with open(key_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(key, f, indent=1, sort_keys=True)
            f.write("\n")
        print(f"wrote {key_path}: the answer key (each case's source and removed members)")
        print("Send the SAME form to 3+ shotcallers, never the key. Do not show them engine output.")
    else:
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
    hv = [r for r in rows if r.get("harvest_hit") is not None]
    wsum = sum(CONF_W.get(r.get("confidence"), 0.6) for r in rows)
    return {
        # HARVEST AGREEMENT (forms with an answer key): the grader's best
        # pick, or any pick the grader lists as good, names a member the
        # harvested party fielded and the form removed. Report-only.
        "harvest_agreement": (sum(1 for r in hv if r["harvest_hit"]) / len(hv))
                             if hv else None,
        "harvest_acceptable": (sum(1 for r in hv if r["harvest_acceptable"]) / len(hv))
                              if hv else None,
        "harvest_n": len(hv),
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


def _score_mode(e, cases, mode, removed=None):
    """Evaluate parsed cases under one gear regime.

    mode 'w': symmetric weapon-only (incumbents naked, candidates naked
    via set_dressing(False)). mode 'd': production dressed (incumbents in
    recorded gear else doctrine kits; candidates dressed). `removed`, from
    the form's answer key, lists per case the members the form removed
    from the harvested party; each row then records whether the grader's
    picks name one (harvest agreement). Returns (rows, unresolved,
    case_lines)."""
    e.set_dressing(mode == "d")
    rows, unresolved, case_lines = [], [], []
    try:
        for i, c in enumerate(cases, 1):
            harvest = set(removed[i - 1]) if removed is not None else None
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
                "harvest_hit": (want in harvest) if harvest is not None else None,
                "harvest_acceptable": (any(k in harvest for k in acc)
                                       if harvest is not None else None),
            })
            case_lines.append(
                f"{i:<4}{e.weapons[want]['display_name']:<22}"
                f"{'YES' if want in top3 else 'no':<8}"
                f"{'r' + str(rank) if rank else 'out-of-pool':<12}"
                + (f"{'YES' if want in harvest else 'no':<9}" if harvest is not None else "")
                + f"{', '.join(e.weapons[w]['display_name'] for w in top3)}")
    finally:
        e.set_dressing(True)
    return rows, unresolved, case_lines


MODE_NAMES = {"w": "V3-W weapon-only (symmetric naked benchmark)",
              "d": "V3-D dressed (production metric — THE GATE)"}


_CONTEXT_RE = re.compile(r"^-[ \t]*FORM_CONTEXT:[ \t]*(\S+)[ \t]+(\d+)[ \t]+(\S+)",
                         re.MULTILINE)


def form_engine(text, size_arg=7):
    """The engine a form scores in, and the form's context. A form from
    the current generator carries its own FORM_CONTEXT (content, size,
    style) and scores in exactly that context in every mode (a Dragon
    Portal form at 3, 5 or 7 reads that pool's rows and fielded list);
    scoring under the wrong content or size silently invalidates a round.
    A form without the line (round 1) scores castle_outpost at
    `size_arg`."""
    m = _CONTEXT_RE.search(text)
    if not m:
        return Engine(size=size_arg), None
    content, size, style = m.group(1), int(m.group(2)), m.group(3)
    if size_arg != 7 and size_arg != size:
        print(f"note: form declares size {size}; overriding --size")
    return (Engine(content=content, size=size, style=style),
            {"content": content, "size": size, "style": style})


def _key_matches(key, cases):
    """True when the key's cases show exactly the form's parties, case by
    case (as multisets)."""
    return ([sorted(c.get("shown") or []) for c in key.get("cases") or []]
            == [sorted(c["party"]) for c in cases])


def form_key(form_path, cases, key_path=None):
    """The answer key of a harvest-seeded form, as (path, key), or (None,
    None) for a form without one. `key_path`, else `<form>.key.json`
    beside the form; a key named either way that does not show the form's
    parties fails loudly. Otherwise (a renamed copy of the form) the key in
    the form's directory or tests/ that shows exactly its parties."""
    sibling = os.path.splitext(form_path)[0] + ".key.json"
    named = key_path or (sibling if os.path.exists(sibling) else None)
    if named:
        with open(named, encoding="utf-8") as f:
            key = json.load(f)
        if not _key_matches(key, cases):
            sys.exit(f"{named}: its cases do not show this form's parties — "
                     "not this form's key")
        return named, key
    dirs = (os.path.dirname(os.path.abspath(form_path)), HERE)
    for path in sorted({os.path.abspath(p) for d in dirs
                        for p in glob.glob(os.path.join(d, "*.key.json"))}):
        with open(path, encoding="utf-8") as f:
            key = json.load(f)
        if _key_matches(key, cases):
            return path, key
    return None, None


def score(args):
    with open(args.form, encoding="utf-8") as f:
        text = f.read()
    e, context = form_engine(text, args.size)
    print(f"scoring in {e.content} at {e.size}, style {e.style}"
          + ("" if context else " (the form has no FORM_CONTEXT line)"))
    cases = _parse_cases(text)
    if not cases:
        sys.exit("no cases found — is this a filled form from `generate`?")
    key_path, key = form_key(args.form, cases, args.key)
    removed = [c.get("removed") or [] for c in key["cases"]] if key else None
    if key:
        print(f"answer key: {key_path} (harvest agreement reported; report-only, "
              "never a gate input)")

    modes = ["w", "d"] if args.mode == "both" else [args.mode]
    report, gate_rate = {}, None
    for mode in modes:
        rows, unresolved, case_lines = _score_mode(e, cases, mode, removed)
        m = _metrics(rows)
        report[mode] = {"metrics": m, "rows": rows,
                        "unresolved": unresolved}
        print(f"\n=== {MODE_NAMES[mode]} ===")
        print(f"{'#':<4}{'shotcaller pick':<22}{'top-3':<8}{'rank':<12}"
              + (f"{'harvest':<9}" if key else "") + "engine top-3")
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
        print(f"shotcaller-pick rank: mean {mr} median {m['median_rank']} "
              f"(n={m['rank_n']}, outside pool {m['outside_pool']})")
        print(f"primary-need agreement {_fmt_pct(m['need_agreement'])} "
              f"(n={m['need_n']})   bad-pick-in-top3 rate "
              f"{_fmt_pct(m['bad_pick_rate'])} (n={m['bad_n']})")
        if key:
            hits = sum(1 for r in rows if r.get("harvest_hit"))
            print(f"harvest agreement: the best pick names a removed member "
                  f"{_fmt_pct(m['harvest_agreement'])} ({hits}/{m['harvest_n']}), "
                  f"any listed pick {_fmt_pct(m['harvest_acceptable'])} "
                  "(report-only)")
        if unresolved:
            print("unresolved answers (fix spelling or use PARTY_KEYS names):")
            for i, p in unresolved:
                print(f"  case {i}: {p!r}")
        if mode == "d":
            gate_rate = m["top3"] if rows else None

    if args.json:
        report["context"] = {"content": e.content, "size": e.size, "style": e.style}
        if key:
            report["key"] = _rel(key_path)
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
        print("Per VALIDATION.md: a miss where the shotcaller is right "
              "becomes a new golden case in tests/test_golden.py. Review "
              "misses before retuning.")
    return 0 if gate_rate >= GATE else 1


# The Deadlyhooker comp is tagged with the content it was written for, which
# is broader than any single template; map to the closest fitted one.
V4_CONTENT_MAP = {"large_scale_zvz": "territory_defense"}

V4_CLASSES = ("weapon_only", "doctrine_inferred", "actual_gear")


def _tally_line(label, t, width):
    """One class row of a leave-one-out table — 'hits/total = pct' at the
    weapon and role levels. The engine's classes and the baseline share
    this one shape so the two read side by side."""
    rl = (f"role-level {t['r_hits']}/{t['r_total']} = "
          f"{t['r_hits'] / t['r_total']:.0%}" if t["r_total"] else "role-level n/a")
    return (f"  [{label:<{width}}] weapon-level: {t['w_hits']}/{t['w_total']} = "
            f"{t['w_hits'] / t['w_total']:.0%}   {rl}")


def _rank_summary(ranks):
    """Rank metrics over one class's drops. `ranks` holds each dropped
    weapon's 1-based position in the full ranking, None when the weapon
    sits outside the suggestion pool. MRR counts an outside-pool drop as
    0 (the ranker never proposes it); the median rank reads in-pool drops
    only, and the outside count is reported beside it so the two stay
    honest together."""
    inside = [r for r in ranks if r is not None]
    return {
        "drops": len(ranks),
        "outside_pool": len(ranks) - len(inside),
        "median_rank": statistics.median(inside) if inside else None,
        "top10": sum(1 for r in inside if r <= 10),
        "mrr": (round(sum(1.0 / r for r in inside) / len(ranks), 4)
                if ranks else None),
    }


def _rank_line(label, ranks, width):
    s = _rank_summary(ranks)
    if not s["drops"]:
        return f"  [{label:<{width}}] no drops"
    med = "n/a" if s["median_rank"] is None else f"{s['median_rank']:g}"
    return (f"  [{label:<{width}}] median rank {med} (in pool)   "
            f"top-10 {s['top10']}/{s['drops']} = {s['top10'] / s['drops']:.0%}   "
            f"MRR {s['mrr']:.3f}   outside pool {s['outside_pool']}/{s['drops']}")


def _board_holdout_mod():
    """The holdout_mod the committed style x size board learned under
    (its `split` header), or None when the board predates the flag."""
    import yaml
    path = os.path.join(ROOT, "pipeline", "templates", "style_bands.yaml")
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except OSError:
        return None
    return (doc.get("split") or {}).get("holdout_mod")


# --------------------------------------------------------- baseline ----
BASELINE_NOTE = ("  baseline = role skeleton (under band min, then under typical) "
                 "+ meta-prior solo share, top-3; REPORT-ONLY, NEVER A GATE, "
                 "no exit-code input — the capability model must beat it "
                 "(the skeleton-first generation spec, decision 6).")


def baseline_recommend(e, party, top_n=TOP_N):
    """The role-skeleton-plus-popularity BASELINE (spec notes/specs/
    2026-09-15-skeleton-first-generation-design.md decision 6): the
    recommender the capability model must beat, or it is not earning its
    complexity. REPORT-ONLY, NEVER A GATE; it lives in the harness, never
    in the engine, and no scoring path may read it.

    Candidates are the engine's own suggest_pool() — the pool recommend()
    ranks — ordered by NEED, then POPULARITY, then weapon id:
      need 2  the candidate's constraint role (role_of) has fewer members
              in `party` than its band MINIMUM at this size and style
              (e._band, which already carries the style's per-five healer
              minima);
      need 1  fewer than the role's TYPICAL count (the band row's
              `typical`, where one exists), or the candidate's primary
              seat (seat_of) has fewer members than its skeleton typical
              (e._seat_typ — GENERATED; empty below the style floor, so
              no seat is under-typical there);
      need 0  otherwise;
      popularity  the meta prior's SOLO share at the roster's size bucket
              (e._solo_of; absent = 0.0) — no pair term: this is a
              popularity table, not a partner model;
      weapon id ascending, so ties resolve the same way every run.
    It reads no capability, synergy, gear or fight chain: it knows what a
    role checklist and a popularity table know, nothing more."""
    band = e._band or {}
    seat_typ = e._seat_typ or {}
    role_n, seat_n = {}, {}
    for m in party:
        role_n[e.role_of(m)] = role_n.get(e.role_of(m), 0) + 1
        seat = e.seat_of(m)
        if seat is not None:
            seat_n[seat] = seat_n.get(seat, 0) + 1

    def need(w):
        role = e.role_of(w)
        rule = band.get(role) if isinstance(band.get(role), dict) else {}
        have = role_n.get(role, 0)
        if have < (rule.get("min") or 0):
            return 2
        seat = e.seat_of(w)
        if (rule.get("typical") is not None and have < rule["typical"]) or (
                seat is not None and seat_n.get(seat, 0) < seat_typ.get(seat, 0)):
            return 1
        return 0

    ranked = sorted(e.suggest_pool(), key=lambda w: (-need(w), -e._solo_of(w), w))
    return ranked[:top_n]


def v4(args):
    """Meta-comp reproduction (leave-one-out) against data/published_comps/.

    For every weapon slot in every real comp party: remove it, ask the engine
    for its top-N at that party's size, and score two ways —
      weapon-level: any of the slot's listed weapons (alternatives count) is
                    in the top-N;
      role-level:   for healer/tank slots, ANY weapon of that role is in the
                    top-N ("propose the missing member's ROLE", VALIDATION V4).
    Battlemount slots are outside the weapon model and are skipped.

    DRESSED: each drop is scored under the three incumbent-gear classes
    documented in the module docstring. The exit-code gate reads the
    actual_gear role metric (re-based from weapon_only; VALIDATION.md gates).

    BASELINE: with --baseline every drop is ALSO put to
    baseline_recommend() under the same hit rules, tallied once (it scores
    no gear) and printed as a `baseline` row. Report-only, never a gate —
    the exit code reads actual_gear alone.

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
                    "misses": []}
               for cl in V4_CLASSES + (("baseline",) if args.baseline else ())}
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
        # A record may be EXCLUDED outright (PvE content, the
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

            def tally(cl, slot, top):
                """The v4 hit rules, one place for every class AND the
                baseline: weapon-level = any listed alternative of the
                dropped slot is in the top-N; role-level (healer / tank
                slots) = any weapon of that role pool is."""
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
                    tally(cl, slot, top)
                if args.baseline:
                    # the skeleton + popularity baseline at the same drop,
                    # one class (it scores no gear) — report-only
                    tally("baseline", slot, baseline_recommend(e, rest, TOP_N))
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
        print(_tally_line(cl, tallies[cl], 17))
    if args.baseline:
        print(_tally_line("baseline", tallies["baseline"], 17))
        print(BASELINE_NOTE)
    print("  incumbent-gear resolution per party (actual_gear class):")
    for cid, pname, n_mem, res, rec, dressed_n in resolution:
        print(f"    {cid}/{pname}: {dressed_n}/{n_mem} members dressed, "
              f"{res}/{rec} recorded pieces resolved into the curated catalog")
    print(f"  dressed-vs-naked top-3 divergence: {len(divergences)}/"
          f"{base['w_total']} slots")
    # GATE RE-BASED to actual_gear (tests/VALIDATION.md gates), and it now
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
          f"(re-based from weapon_only) -> "
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
        for cl in tallies:
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
        if args.baseline:
            payload["baseline"] = dict(tallies["baseline"],
                                       note="report-only, never a gate")
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=1, sort_keys=True)
        print(f"\nwrote {args.json}")
    return 0 if gate_ok else 1


# ---------------------------------------------------------------- V4h ----
V4H_CLASSES = ("weapon_only", "harvest_gear", "harvest_gear_doctrine")
V4H_GEAR_SLOTS = ("Head", "Armor", "Shoes", "Cape", "OffHand", "Potion", "Food")


def _harvest_parties(doc, styles, e_probe, min_size, max_size, holdout_mod, dominant=False):
    """Killer parties of [min_size, max_size] with every weapon known and in
    the catalog, each with its weapons-only style label (party_styles.json,
    the descriptive comp_identity read; `balanced` where the label is none /
    split) and its linked builds' gear. `holdout_mod` keeps only battles
    whose id % mod == 0 — a deterministic slice, see the caveat in v4h().
    `dominant` keeps the parties that took no deaths and a kill in their
    battle (the portal pools' unit)."""
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
            if not _known_party(p, cat, min_size, max_size, dominant):
                continue
            ws = p["weapons"]
            n = p["size"]
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
    """V4 on the killer-party HARVEST (report-only): the same
    leave-one-out as v4, over harvested parties of 10+ instead of the 23
    published-comp slots. A killer party is a roster that took kills in a
    real fight — win-conditioned evidence of what gets fielded, not a
    verdict on what should be. Three incumbent-gear classes:

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
    battles with id % M == 0 as a deterministic slice. The prior, the role
    counts, the seat skeleton and the style board learn from the other
    slice; the report reads the board's `split` header and says whether
    the evaluated slice is unseen, or weak-form when the two disagree.

    RANK METRIC: beside the top-3 hit rates, every drop records the
    dropped weapon's position in the full ranking — median rank, top-10
    share, MRR and the outside-pool count per class (_rank_summary).
    Content is not recorded on a killer party; `--content` sets the
    template (default blackzone_roam, the ZvZ roam rows); the style is the
    party's weapons-only label (party_styles.json) or balanced.

    BASELINE: with --baseline every drop — and every rebuild
    step — is ALSO put to baseline_recommend() under the same hit rules,
    tallied once (it scores no gear) and printed as a `baseline` row.
    Report-only like everything here.

    NOT A GATE. Prints beside v4 so the two can be compared; the holdout
    split is honoured end to end, so promotion to a gate is a maintainer
    decision.

    THE PORTAL POOLS: `--harvest-source all --harvest-content ancient_lands
    --dominant --min-size 2 --max-size 7 --content ancient_lands` reads
    the kill-feed poll's portal-tagged parties on the unit
    pipeline/derive_portal_rows.py fits the Dragon Portal rows from (a
    dominant killer party of the pool's size, no deaths, a kill), still
    on the holdout slice; the same report, per pool.
    """
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import rosters_io
    rosters_path = rosters_io.path(os.path.join(ROOT, "pipeline", "out"))
    styles_path = os.path.join(ROOT, "pipeline", "out", "party_styles.json")
    if not os.path.exists(rosters_path):
        sys.exit(f"{rosters_path} missing — run the harvest fold first")
    doc = rosters_io.load(rosters_path, source=args.harvest_source, content=args.harvest_content)
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
                               args.holdout_mod, dominant=args.dominant)
    if not parties:
        sys.exit("no harvested parties match the filter")
    rng = random.Random(args.seed)
    sample = parties if args.n >= len(parties) else rng.sample(parties, args.n)
    sample.sort(key=lambda p: (p["battle"], p["index"]))

    labels = V4H_CLASSES + (("baseline",) if args.baseline else ())
    # `ranks`: the dropped weapon's 1-based position in the FULL ranking
    # (None = outside the suggestion pool). Top-3 hits are coarse — a pick
    # moving from rank 40 to rank 5 reads as no change — so the rank
    # summary (_rank_line) is printed beside every hit rate.
    tallies = {cl: {"w_hits": 0, "w_total": 0, "r_hits": 0, "r_total": 0,
                    "ranks": []}
               for cl in labels}
    rebuild = {cl: {"w_hits": 0, "r_hits": 0, "r_total": 0, "total": 0}
               for cl in labels}
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
        # (class, incumbent gear, ranker): the engine's classes rank through
        # recommend() dressed in that gear; the report-only baseline ranks
        # through baseline_recommend() and wears nothing
        runs = [(cl, gl, lambda party, g, n: [r["weapon"] for r in
                                              e.recommend(party, n, gears=g)])
                for cl, gl in classes.items()]
        if args.baseline:
            runs.append(("baseline", None,
                         lambda party, g, n: baseline_recommend(e, party, n)))
        drops = list(range(len(ws)))
        if args.drop < len(ws):
            drops = sorted(rng.sample(drops, args.drop))
        st = by_style.setdefault(p["style"], {"r_hits": 0, "r_total": 0, "parties": 0})
        st["parties"] += 1
        for i in drops:
            rest = ws[:i] + ws[i + 1:]
            role = role_of(ws[i])
            for cl, gl, rank in runs:
                g = None if gl is None else gl[:i] + gl[i + 1:]
                full = rank(rest, g, FULL_RANK)
                top = full[:TOP_N]
                t = tallies[cl]
                t["w_hits"] += ws[i] in top
                t["w_total"] += 1
                t["ranks"].append(full.index(ws[i]) + 1 if ws[i] in full
                                  else None)
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
            for cl, gl, rank in runs:
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
                    top = rank(cur, g, 1)
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
          f"content {args.content}, style = the party's weapons-only label; harvest {args.harvest_source}"
          f"{' / ' + args.harvest_content if args.harvest_content else ''}{', dominant parties' if args.dominant else ''}")
    for cl in V4H_CLASSES:
        print(_tally_line(cl, tallies[cl], 22))
    if args.baseline:
        print(_tally_line("baseline", tallies["baseline"], 22))
        print(BASELINE_NOTE)
    print("  rank of the dropped weapon in the full ranking:")
    for cl in labels:
        print(_rank_line(cl, tallies[cl]["ranks"], 22))
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
        for cl in labels:
            rb = rebuild[cl]
            if rb["total"]:
                rl = f"role {rb['r_hits']}/{rb['r_total']} = {rb['r_hits'] / rb['r_total']:.0%}" if rb["r_total"] else "role n/a"
                print(f"    [{cl:<22}] weapon {rb['w_hits']}/{rb['total']} = "
                      f"{rb['w_hits'] / rb['total']:.0%}   {rl}"
                      + ("   <- baseline: REPORT-ONLY, never a gate"
                         if cl == "baseline" else ""))
    board_mod = _board_holdout_mod()
    if args.holdout_mod and board_mod == args.holdout_mod:
        print(f"  holdout: the style board, meta prior, role counts and seat "
              f"skeleton learn from battles id%{board_mod}!=0; this slice is "
              f"unseen by every harvest-derived table.")
    else:
        print(f"  caveat: the committed style board records holdout_mod "
              f"{board_mod!r}, this run evaluates "
              f"{args.holdout_mod or 'all battles'} - styled numbers are "
              f"weak-form (the board learned from the evaluated battles).")
    print("  caveat: a killer party is win-conditioned evidence of what is "
          "fielded, never a verdict on what should be; NOT A GATE - reported "
          "beside v4.")
    if args.json:
        for cl in labels:
            tallies[cl]["rank_summary"] = _rank_summary(tallies[cl]["ranks"])
        payload = {"parties": len(sample), "eligible": len(parties),
                   "filter": {"min_size": args.min_size, "max_size": args.max_size,
                              "holdout_mod": args.holdout_mod, "seed": args.seed,
                              "drop": args.drop, "rebuild": args.rebuild,
                              "content": args.content},
                   "classes": tallies, "rebuild": rebuild, "by_style": by_style,
                   "gear": {"members": members_n, "dressed": dressed_n,
                            "resolved": res_n, "recorded": rec_n}}
        if args.baseline:
            payload["baseline"] = ("report-only, never a gate: classes.baseline "
                                   "and rebuild.baseline")
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
    g.add_argument("--round", type=int, default=None,
                   help="the V3 round the form belongs to (required for a harvest-seeded "
                        "form): every battle an earlier round's key records is excluded")
    g.add_argument("--from-pool", action="store_true",
                   help="the draw of V3 rounds 1-2: partial parties sampled from the "
                        "whole weapon pool, no answer key")
    g.add_argument("--rosters", default=None,
                   help="the roster artifact (default: pipeline/out/party_rosters.json.gz)")
    g.add_argument("--harvest-source", default=None, choices=["battle_list", "all"],
                   help="override the content's population (FORM_POPULATIONS): which harvest")
    g.add_argument("--harvest-content", default=None,
                   help="override the content's population: one content tag's battles")
    g.add_argument("--dominant", action="store_true", default=None,
                   help="dominant killer parties only (no deaths, a kill); the portal's unit")

    s = sub.add_parser("score"); s.set_defaults(fn=score)
    s.add_argument("form")
    s.add_argument("--size", type=int, default=7)
    s.add_argument("--mode", choices=["both", "w", "d"], default="both")
    s.add_argument("--json", default=None, help="dump per-case rows + metrics")
    s.add_argument("--key", default=None,
                   help="the form's answer key (default: <form>.key.json beside it, else "
                        "the key in its directory or tests/ that shows its parties)")

    v = sub.add_parser("v4"); v.set_defaults(fn=v4)
    v.add_argument("comps", nargs="?",
                   default=os.path.join(ROOT, "data", "published_comps"))
    v.add_argument("--verbose", action="store_true", help="list weapon-level misses")
    v.add_argument("--json", default=None, help="dump per-class tallies")
    v.add_argument("--baseline", action="store_true",
                   help="also score the role-skeleton + popularity baseline "
                        "(report-only, never a gate)")

    h = sub.add_parser("v4h"); h.set_defaults(fn=v4h)
    h.add_argument("--n", type=int, default=150, help="parties to sample")
    h.add_argument("--drop", type=int, default=3, help="leave-one-out drops per party")
    h.add_argument("--rebuild", type=int, default=0, help="V4b: rebuild the last k members")
    h.add_argument("--min-size", type=int, default=10)
    h.add_argument("--max-size", type=int, default=20)
    h.add_argument("--holdout-mod", type=int, default=5,
                   help="evaluate battles with id %% M == 0 only (0 = all)")
    h.add_argument("--content", default="blackzone_roam")
    h.add_argument("--harvest-source", default="battle_list", choices=["battle_list", "all"],
                   help="which harvest population to read (all = the kill-feed poll's records too)")
    h.add_argument("--harvest-content", default=None,
                   help="keep one content tag's battles (ancient_lands = the Dragon Portal pools)")
    h.add_argument("--dominant", action="store_true",
                   help="killer parties with no deaths and a kill only (the portal pools' unit)")
    h.add_argument("--seed", type=int, default=20260910)
    h.add_argument("--json", default=None)
    h.add_argument("--baseline", action="store_true",
                   help="also score the role-skeleton + popularity baseline "
                        "(report-only, never a gate)")

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
