#!/usr/bin/env python3
"""
STYLE-LABELLING FORM: a validation round on the engine's identity read.

`Engine.comp_identity` names a roster's playstyle in the caller's own
vocabulary (styles.yaml). A style-labelling form shows a labeller rosters
by their weapons alone; the engine's read of each stays in the answer key
beside the form, `<form>.key.json`, which is never sent. One form, two
sources:

  forged   `Engine(content, size, style).forge(size)` for every content x
           size asked, at most 20 (the forge refuses a single party past
           20): the planner's forge button (dressed, the default
           suggestion pool, no locks). The read is on the forge's own
           combos and kits, as the forge-quality sweep reads a forged
           roster (pipeline/audit_forge_quality.py); the weapons-only read
           sits beside it in the key.
  harvest  battle-list killer parties from the roster artifact of exactly
           the forged sizes a killer party reaches (10-20), so no size on
           the form belongs to one source alone; every weapon known and
           in the catalog (the eligibility rule of
           tests/tier2_blindtest.py), the training split only
           (battle % 5 != 0), never a battle pipeline/graded_battles.py
           lists or one an earlier round's key records, one case per
           distinct roster and none a forged roster. Each engine label's
           quota (labels beside the style under test, so the labeller
           cannot assume one answer) is dealt across the sizes in turn,
           the largest first, which gives every size an equal share. The
           eligible parties, in battle and party order, are shuffled by the
           seed and walked; a party is taken while its size's plan holds a
           slot for its label. A slot its size cannot fill takes the first
           label in quota order the size can still supply, recorded in the
           key. The read is weapons only at the party's size, the read
           pipeline/derive_party_styles.py stamps on the harvest.

The cases are shuffled by the seed. Each shows its size and its weapons by
display name, sorted, and two blank fields: style (kite / clap_kite / clap
/ brawl / brawl_clap / balanced) and confidence (1-3). Deterministic for a
seed, a dataset and an artifact; the key records both hashes. The forge
takes no seed. When the round is graded its harvested battles join
GRADED_BATTLES (pipeline/graded_battles.py), as every roster round's do.

`score` reads a filled form and its key (`--key`, else `<form>.key.json`
beside it; a key whose cases do not show the form's rosters fails loudly)
and prints, per source and size, how often the label agrees with the
engine's read, then the forged rosters the labeller did not call the style
they were forged for. An engine read of no one style (a split identity)
agrees with `balanced`. Report-only: nothing in the build reads a form, a
key or a score.

`generate` loads the roster artifact (several GB of memory at peak).

Usage:
    py -3 -u pipeline/style_blind_round.py generate --round 1 --out tests/style_form_r1_kite.md
    py -3 pipeline/style_blind_round.py score tests/style_form_r1_kite.md [--key K]
"""
import argparse
import collections
import gc
import glob
import hashlib
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTS = os.path.join(ROOT, "tests")
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, HERE)
from graded_battles import GRADED_BATTLES  # noqa: E402
from derive_party_styles import CONTENT as LABEL_CONTENT  # noqa: E402

# the labeller's vocabulary: the five identity styles and `balanced`, a
# roster that commits to no one plan
LABELS = ("kite", "clap_kite", "clap", "brawl", "brawl_clap", "balanced")
HOLDOUT_MOD = 5          # battle % 5 == 0 is the holdout slice v4h evaluates
KEY_GLOBS = ("style_form_*.key.json", "tier2_form_*.key.json")
FORGED_READ = "comp_identity on the forge's own combos and kits"
WEAPONS_READ = (f"comp_identity on the weapons alone (default combos, no kits), "
                f"{LABEL_CONTENT} at the party's size")
# each case's read names its kind; the key's head defines both
READ_TAGS = {FORGED_READ: "forged combos and kits", WEAPONS_READ: "weapons only"}
DEFAULT_QUOTAS = "kite:4,clap_kite:4,clap:2,brawl:2"
BALANCED_GLOSS = "none of the five; the roster commits to no one plan"


def _rel(path):
    """A path as the repository names it (forward slashes, relative to the
    root where it sits inside)."""
    try:
        p = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:            # another drive
        p = ".."
    return (os.path.abspath(path) if p.startswith("..") else p).replace(os.sep, "/")


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _battle_id(b):
    try:
        return int(b)
    except (TypeError, ValueError):
        return b


def _training(battle):
    try:
        return int(battle) % HOLDOUT_MOD != 0
    except (TypeError, ValueError):
        return False


def known_party(p, catalog, min_size, max_size):
    """A killer party of [min_size, max_size] members, every weapon known
    and in the catalog (tests/tier2_blindtest.py `_known_party`)."""
    ws = p.get("weapons") or []
    n = p.get("size") or 0
    return (min_size <= n <= max_size and p.get("known_weapons") == n
            and len(ws) == n and all(w in catalog for w in ws))


def display_names(e):
    """Each catalog weapon's name on the form; a name two weapons share
    reads with the weapon's key beside it."""
    count = collections.Counter(w["display_name"] for w in e.weapons.values())
    return {k: (w["display_name"] if count[w["display_name"]] == 1
                else f"{w['display_name']} ({k})") for k, w in e.weapons.items()}


def weapons_line(names):
    """The weapons of one case, sorted by name; a weapon fielded more than
    once reads `Name xN`."""
    count = collections.Counter(names)
    order = sorted(count, key=lambda n: (n.lower(), n))
    return ", ".join(n if count[n] == 1 else f"{n} x{count[n]}" for n in order)


def parse_names(line):
    """The inverse of weapons_line: the names, one per member, sorted."""
    out = []
    for part in (line or "").split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?) x(\d+)$", part)
        out += [m.group(1)] * int(m.group(2)) if m else [part]
    return sorted(out, key=lambda n: (n.lower(), n))


def read_row(ci, read):
    """One identity read as the key records it. A read with no style is the
    gank read (its archetype), a split identity or a roster still forming."""
    style = ci.get("style")
    if style is None:
        style = (ci.get("archetype")
                 or ("split" if "split" in (ci.get("label") or "") else "forming"))
    return {"read": READ_TAGS.get(read, read), "style": style, "strength": ci.get("strength"),
            "archetype": ci.get("archetype"), "label": ci.get("label"),
            "melee_share": round(ci.get("melee_share") or 0.0, 3),
            "bomb_share": round((ci.get("mode") or {}).get("aoe") or 0.0, 3),
            "kite_tools": ci.get("kite_tools"),
            "kite_tools_min": ci.get("kite_tools_min")}


def parse_quotas(text):
    quotas = collections.OrderedDict()
    for part in (text or "").split(","):
        if not part.strip():
            continue
        label, n = part.split(":")
        if label.strip() not in LABELS:
            raise ValueError(f"quota label {label!r} is not one of {', '.join(LABELS)}")
        quotas[label.strip()] = int(n)
    return quotas


# ------------------------------------------------------------ generate ----
def earlier_key_battles(round_no, own_key, dirs=(TESTS,)):
    """The battles every earlier round's answer key records, and the keys
    read: every V3 key (tier2_form_*), and every style-labelling key of a
    round before `round_no`. The form's own key is never read."""
    own = os.path.normcase(os.path.abspath(own_key))
    paths = sorted({os.path.normcase(os.path.abspath(p)) for d in dirs
                    for g in KEY_GLOBS for p in glob.glob(os.path.join(d, g))})
    battles, used = set(), []
    for path in paths:
        if path == own:
            continue
        with open(path, encoding="utf-8") as f:
            key = json.load(f)
        name = os.path.basename(path)
        r = key.get("round")
        if name.startswith("style_form_") and isinstance(r, int) and r >= round_no:
            continue
        battles |= {_battle_id(c["battle"]) for c in key.get("cases") or []
                    if c.get("battle") is not None}
        used.append(name)
    return battles, used


def eligible_parties(doc, catalog, sizes, excluded):
    """The harvest's eligible parties as (battle, index, weapons), in battle
    and party order: killer parties of exactly one of `sizes`. The counts
    behind them, in all and per size: `parties` of the sizes in the
    population, `not_training`, one per excluded reason ({reason: battle
    ids}), `eligible` and `rosters` (distinct among the eligible)."""
    import party_link
    keys = ["parties", "not_training"] + sorted(excluded) + ["eligible", "rosters"]
    counts = {k: 0 for k in keys}
    by_size = {str(n): {k: 0 for k in keys} for n in sorted(sizes)}
    eligible, rosters = [], set()
    by_battle = party_link.parties_by_battle(doc)
    for battle in sorted(by_battle, key=lambda b: (type(b).__name__, b)):
        for p in sorted(by_battle[battle], key=lambda q: q["index"]):
            n = p.get("size") or 0
            if n not in sizes or not known_party(p, catalog, n, n):
                continue
            mine = by_size[str(n)]
            why = ("not_training" if not _training(battle) else
                   next((r for r in sorted(excluded)
                         if _battle_id(battle) in excluded[r]), None))
            for c in (counts, mine):
                c["parties"] += 1
                if why:
                    c[why] += 1
            if why:
                continue
            eligible.append((battle, p["index"], list(p["weapons"])))
            roster = tuple(sorted(p["weapons"]))
            for c in (counts, mine):
                c["eligible"] += 1
                c["rosters"] += roster not in rosters
            rosters.add(roster)
    counts["by_size"] = by_size
    return eligible, counts


def deal(quotas, sizes):
    """The per-size plan: each label's quota dealt across the sizes in turn,
    the largest size first, the turn carrying over from one label to the
    next, so every size takes an equal share of the cases (12 over 10, 15
    and 20: four each) and the focal labels reach every size."""
    order = sorted(sizes, reverse=True)
    plan = {n: collections.OrderedDict() for n in order}
    turn = 0
    for label, count in quotas.items():
        for _ in range(count):
            n = order[turn % len(order)]
            plan[n][label] = plan[n].get(label, 0) + 1
            turn += 1
    return plan


def draw_harvest(eligible, plan, labels, rng, read, skip=()):
    """Walk the eligible parties in a seeded order and take each party whose
    size's plan still holds a slot for its engine label; a roster already
    taken (or in `skip`, the forged rosters) is passed over, so every case
    is a distinct roster. A slot the walk leaves open (its size has no
    further roster of the label) takes the first label of `labels` the size
    can still supply, recorded as a substitution. `read(weapons)` returns
    the comp_identity read; a case records its `sightings`, the eligible
    parties fielding its roster. Returns (cases, walked, substitutions,
    short): `walked` the distinct rosters read before every slot filled,
    `short` the slots no roster of the size could fill (none on a full
    draw)."""
    sightings = collections.Counter(tuple(sorted(ws)) for _b, _i, ws in eligible)
    need = {n: dict(slots) for n, slots in plan.items()}
    used = set(skip)
    reads = {}
    cases = []

    def label_of(ws):
        roster = tuple(sorted(ws))
        if roster not in reads:
            reads[roster] = read_row(read(ws), WEAPONS_READ)
        return reads[roster]

    def take(battle, index, ws, row):
        used.add(tuple(sorted(ws)))
        cases.append({"source": "harvest", "battle": battle, "party": index,
                      "sightings": sightings[tuple(sorted(ws))], "weapons": list(ws),
                      "engine": row})

    order = rng.sample(eligible, len(eligible))
    for battle, index, ws in order:
        if not any(v for slots in need.values() for v in slots.values()):
            break
        slots = need.get(len(ws))
        if not slots or not any(slots.values()) or tuple(sorted(ws)) in used:
            continue
        row = label_of(ws)
        if slots.get(row["style"], 0) > 0:
            slots[row["style"]] -= 1
            take(battle, index, ws, row)
    walked = len(reads)
    substitutions = []
    for n in sorted(need):
        for label in list(need[n]):
            while need[n][label] > 0:
                got = None
                for alt in (x for x in labels if x != label):
                    got = next(((b, i, ws) for b, i, ws in order if len(ws) == n
                                and tuple(sorted(ws)) not in used
                                and label_of(ws)["style"] == alt), None)
                    if got:
                        break
                if not got:
                    break
                need[n][label] -= 1
                take(*got, label_of(got[2]))
                substitutions.append({"size": n, "wanted": label, "took": alt})
    short = {str(n): {k: v for k, v in slots.items() if v}
             for n, slots in sorted(need.items()) if any(slots.values())}
    return cases, walked, substitutions, short


def form_lines(cases, round_no, seed, blurbs):
    """The form: the task, the vocabulary, and per case its size, its
    weapons and two blank fields. Nothing of a case's source or of the
    engine's read is on it."""
    lines = [
        f"# Style labelling, round {round_no}",
        "",
        f"{len(cases)} rosters, each one party: its size and its weapons, sorted by",
        "name (a weapon fielded more than once reads `Name xN`). Call each",
        "roster's playstyle from the weapons alone, before opening anything",
        "else: no planner, no killboard, no other file of this repository.",
        "",
        "Fill in two fields per case:",
        "",
        "- style: one of " + " / ".join(LABELS),
        "- confidence (1-3): 1 a guess, 2 likely, 3 sure",
        "",
        "The styles, in the planner's words:",
        "",
    ]
    for label in LABELS:
        lines.append(f"- {label}: {blurbs.get(label) or BALANCED_GLOSS}")
    lines += [
        "",
        "Any style may stand on any number of cases. The cases are in a seeded",
        f"random order (seed {seed}). Send every labeller this same file; each",
        "returns it filled in.",
        "",
    ]
    for c in cases:
        lines += [f"### Case {c['case']}",
                  "",
                  f"- size: {c['size']}",
                  f"- weapons: {weapons_line(c['names'])}",
                  "- style:",
                  "- confidence (1-3):",
                  ""]
    return lines


def generate(args):
    from engine import DATASET, Engine
    import rosters_io
    quotas = parse_quotas(args.quotas)
    contents = [c.strip() for c in args.contents.split(",") if c.strip()]
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    key_path = os.path.splitext(args.out)[0] + ".key.json"
    # the harvest stands at the forged sizes a killer party reaches, so no
    # size on the form belongs to one source alone
    harvest_sizes = sorted({n for n in sizes if args.min_size <= n <= args.max_size})
    if not harvest_sizes:
        sys.exit(f"no forged size lies in {args.min_size}-{args.max_size}, the killer parties' sizes")
    plan = deal(quotas, harvest_sizes)

    # the forged rosters first, with no artifact in memory
    forged, probe = [], None
    for content in contents:
        for size in sizes:
            e = Engine(content=content, size=size, style=args.style)
            r = e.forge(size)
            party = list(r["party"])
            row = read_row(e.comp_identity(party, r["combos"], r["gears"]), FORGED_READ)
            forged.append({"source": "forged", "content": content, "style": args.style,
                           "forge_size": size, "feasible": bool(r["feasible"]),
                           "weapons": party, "engine": row})
            print(f"forged {content} {size} {args.style}: {len(party)} members, "
                  f"feasible {r['feasible']}; read {row['style']} ({row['strength']})",
                  flush=True)
            probe = e
    rosters_forged = [tuple(sorted(c["weapons"])) for c in forged]
    if len(set(rosters_forged)) < len(rosters_forged):
        print("note: two forged cells return the same roster; both stay on the form")
    catalog = set(probe.weapons)
    name = display_names(probe)
    blurbs = {k: (v.get("blurb") if k != "balanced" else None)
              for k, v in (probe.data.get("styles") or {}).items()}
    for w in catalog:
        if "," in name[w] or re.search(r" x\d+$", name[w]):
            sys.exit(f"display name {name[w]!r} cannot be written on a form line")

    # the harvest: eligible parties, then the artifact leaves memory
    path = args.rosters or rosters_io.path()
    if not os.path.exists(path):
        sys.exit(f"{path} missing: run the harvest fold first")
    rosters_sha = rosters_io.sha256(path)
    doc = rosters_io.load(path)
    n_battles = len(doc.get("battles") or [])
    earlier, key_files = earlier_key_battles(args.round, key_path,
                                             (TESTS, os.path.dirname(os.path.abspath(args.out))))
    eligible, counts = eligible_parties(
        doc, catalog, set(harvest_sizes),
        {"graded_battles": {_battle_id(b) for b in GRADED_BATTLES}, "earlier_forms": earlier})
    del doc
    gc.collect()
    for n, c in [("all", counts)] + sorted(counts["by_size"].items(), key=lambda t: int(t[0])):
        print(f"harvest {n}: {c['parties']} parties, not on the training split "
              f"{c['not_training']}, in a graded battle {c['graded_battles']}, in an earlier "
              f"round's key {c['earlier_forms']} -> eligible {c['eligible']} parties, "
              f"{c['rosters']} distinct rosters", flush=True)
    print(f"earlier keys read: {', '.join(key_files) or 'none'}")

    readers = {}

    def read(ws):
        """The weapons-only read, as derive_party_styles stamps it."""
        n = len(ws)
        if n not in readers:
            readers[n] = Engine(content=LABEL_CONTENT, size=n)
        return readers[n].comp_identity(ws)

    for c in forged:
        c["engine_weapons_only"] = read_row(read(c["weapons"]), WEAPONS_READ)
    rng = random.Random(args.seed)
    taken, walked, subs, short = draw_harvest(eligible, plan, list(quotas), rng, read,
                                              skip=set(rosters_forged))
    if short:
        sys.exit(f"too few distinct rosters at a size to fill its slots: {short}")
    for s in subs:
        print(f"note: size {s['size']} supplies no further {s['wanted']}; the slot takes {s['took']}")

    cases = forged + taken
    rng.shuffle(cases)
    for i, c in enumerate(cases, 1):
        order = sorted(c["weapons"], key=lambda w: (name[w].lower(), w))
        c["weapons"] = order
        c["names"] = [name[w] for w in order]
        c["size"] = len(order)
        c["case"] = i
    lines = form_lines(cases, args.round, args.seed, blurbs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    mix = collections.Counter(c["engine"]["style"] for c in taken)
    mix_by_size = {str(n): dict(sorted(collections.Counter(
        c["engine"]["style"] for c in taken if c["size"] == n).items())) for n in harvest_sizes}
    key = {
        "_note": "The answer key of the form named below: each case's source and the "
                 "engine's identity read of it. Never sent with the form.",
        "form": _rel(args.out),
        "round": args.round,
        "seed": args.seed,
        "seed_use": "orders the cases and draws the harvested parties; the forge takes no seed",
        "labels": list(LABELS),
        "dataset": {"path": _rel(DATASET), "sha256": _sha256(DATASET)},
        "forged": {"call": "Engine(content, size, style).forge(size)", "style": args.style,
                   "contents": contents, "sizes": sizes, "read": FORGED_READ,
                   "read_beside": WEAPONS_READ},
        "harvest": {"population": "battle-list killer parties, every weapon known and in "
                                  "the catalog",
                    "sizes": harvest_sizes,
                    "sizes_rule": "the forged sizes a killer party reaches "
                                  f"({args.min_size}-{args.max_size}), so no size on the "
                                  "form belongs to one source alone",
                    "split": f"training: battle % {HOLDOUT_MOD} != 0",
                    "read": WEAPONS_READ, "quotas": dict(quotas),
                    "plan": {str(n): dict(plan[n]) for n in harvest_sizes},
                    "plan_rule": "each label's quota dealt across the sizes in turn, the "
                                 "largest size first, the turn carrying over from one label "
                                 "to the next",
                    "substitutions": subs,
                    "substitution_rule": "a slot whose size supplies no further roster of "
                                         "its label takes the first label in quota order "
                                         "the size can still supply",
                    "mix": dict(sorted(mix.items())), "mix_by_size": mix_by_size,
                    "walked": walked},
        "rosters": {"path": _rel(path), "sha256": rosters_sha, "battles": n_battles},
        "counts": counts,
        "excluded": {"graded_battles": "pipeline/graded_battles.py "
                                       f"({len(GRADED_BATTLES)} battles)",
                     "earlier_forms": key_files},
        "cases": cases,
    }
    with open(key_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(key, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {_rel(args.out)}: {len(cases)} cases ({len(forged)} forged, "
          f"{len(taken)} harvested: {', '.join(f'{k} {v}' for k, v in sorted(mix.items()))}), "
          f"seed {args.seed}")
    for n in harvest_sizes:
        print(f"  harvested at {n}: "
              + ", ".join(f"{k} {v}" for k, v in mix_by_size[str(n)].items())
              + f" (plan: {', '.join(f'{k} {v}' for k, v in plan[n].items())})")
    print(f"wrote {_rel(key_path)}: the answer key; never send it with the form")
    for c in cases:
        src = (f"forged {c['content']} {c['forge_size']}" if c["source"] == "forged"
               else f"harvest battle {c['battle']} party {c['party']}")
        bare = (c.get("engine_weapons_only") or {}).get("style")
        print(f"  case {c['case']:>2}: size {c['size']:>2}, {src}: {c['engine']['style']}"
              + (f" (weapons only: {bare})" if bare and bare != c["engine"]["style"] else ""))
    return 0


# --------------------------------------------------------------- score ----
_FIELD = re.compile(r"^-[ \t]*(size|weapons|style|confidence[ \t]*\(1-3\))[ \t]*:[ \t]*(.*?)[ \t]*$",
                    re.IGNORECASE)


def parse_form(text):
    """A (filled) form's cases: {case, size, names, style, confidence}, the
    raw answer text kept (blank = unanswered)."""
    parts = re.split(r"(?m)^###[ \t]*Case[ \t]*(\d+)[ \t]*$", text)
    cases = []
    for num, block in zip(parts[1::2], parts[2::2]):
        f = {}
        for line in block.splitlines():
            m = _FIELD.match(line.strip())
            if m:
                k = m.group(1).lower()
                f["confidence" if k.startswith("confidence") else k] = m.group(2)
        size = (f.get("size") or "").strip()
        cases.append({"case": int(num), "size": int(size) if size.isdigit() else None,
                      "names": parse_names(f.get("weapons")),
                      "style": (f.get("style") or "").strip(),
                      "confidence": (f.get("confidence") or "").strip()})
    return cases


def norm_label(text):
    """A typed label in the form's vocabulary (case, hyphens and spaces
    aside: `Clap-Kite` is clap_kite), or None for a word outside it."""
    t = re.sub(r"[\s\-]+", "_", (text or "").strip().lower()).strip("_")
    return t if t in LABELS else None


def vocab(style):
    """The engine's read in the form's vocabulary: a read of no one style
    (split, forming, gank) is `balanced`."""
    return style if style in LABELS else "balanced"


def match_key(cases, key):
    """True when the key's cases show exactly the form's rosters, case by
    case: the same case numbers, sizes and weapons."""
    kc = sorted(key.get("cases") or [], key=lambda c: c["case"])
    by_name = lambda n: (n.lower(), n)
    return ([c["case"] for c in cases] == [c["case"] for c in kc]
            and all(c["size"] == k.get("size")
                    and c["names"] == sorted(k.get("names") or [], key=by_name)
                    for c, k in zip(cases, kc)))


def evaluate(cases, key):
    """Per case the label against the engine's read, and the agreement per
    source and size (a forged roster at the size it was forged at)."""
    by = {c["case"]: c for c in key["cases"]}
    rows, unresolved = [], []
    for c in cases:
        k = by[c["case"]]
        label = norm_label(c["style"]) if c["style"] else None
        if c["style"] and label is None:
            unresolved.append((c["case"], c["style"]))
        conf = int(c["confidence"]) if c["confidence"] in ("1", "2", "3") else None
        engine = k["engine"]["style"]
        bare = (k.get("engine_weapons_only") or {}).get("style")
        rows.append({
            "case": c["case"], "source": k["source"], "size": k["size"],
            "group": str(k["forge_size"] if k["source"] == "forged" else k["size"]),
            "content": k.get("content"), "forged_for": k.get("style"),
            "battle": k.get("battle"), "engine": engine,
            "strength": k["engine"].get("strength"),
            "engine_weapons_only": bare, "label": label, "confidence": conf,
            "agree": (label == vocab(engine)) if label else None,
            "agree_weapons_only": (label == vocab(bare)) if label and bare else None,
        })

    def tally(rs):
        ans = [r for r in rs if r["label"]]
        return {"cases": len(rs), "answered": len(ans),
                "agree": sum(1 for r in ans if r["agree"])}

    first = lambda g: int(re.match(r"\d+", g).group())
    groups = collections.OrderedDict()
    for source in ("forged", "harvest"):
        mine = [r for r in rows if r["source"] == source]
        for g in sorted({r["group"] for r in mine}, key=first):
            groups[(source, g)] = tally([r for r in mine if r["group"] == g])
        if mine:
            groups[(source, "all")] = tally(mine)
    groups[("all", "all")] = tally(rows)
    missed = [r for r in rows if r["source"] == "forged" and r["label"]
              and r["label"] != r["forged_for"]]
    return {"rows": rows, "groups": groups, "missed": missed, "unresolved": unresolved,
            "answered": sum(1 for r in rows if r["label"])}


def find_key(form_path, key_path=None):
    path = key_path or os.path.splitext(form_path)[0] + ".key.json"
    if not os.path.exists(path):
        sys.exit(f"{path} missing: name the form's key with --key")
    with open(path, encoding="utf-8") as f:
        return path, json.load(f)


def _pct(a, n):
    return f"{a}/{n} {a / n:.0%}" if n else "-"


def score(args):
    with open(args.form, encoding="utf-8") as f:
        cases = parse_form(f.read())
    if not cases:
        sys.exit("no cases found: is this a form from `generate`?")
    key_path, key = find_key(args.form, args.key)
    if not match_key(cases, key):
        sys.exit(f"{key_path}: its cases do not show this form's rosters: not this form's key")
    res = evaluate(cases, key)
    print(f"{_rel(args.form)} against {_rel(key_path)} (round {key.get('round')}, "
          f"{len(cases)} cases): {res['answered']} answered")
    print(f"\n{'case':<6}{'source':<9}{'size':<6}{'engine read':<22}{'label':<12}"
          f"{'conf':<6}agree")
    for r in res["rows"]:
        eng = f"{r['engine']} ({r['strength']})" if r["strength"] else r["engine"]
        agree = "-" if r["agree"] is None else ("yes" if r["agree"] else "no")
        print(f"{r['case']:<6}{r['source']:<9}{r['size']:<6}{eng:<22}{r['label'] or '-':<12}"
              f"{r['confidence'] or '-':<6}{agree}"
              + (f"   (weapons only: {r['engine_weapons_only']})"
                 if r["engine_weapons_only"] and r["engine_weapons_only"] != r["engine"] else ""))
    print("\nagreement with the engine's read (answered cases, per source and size):")
    for (source, group), n in res["groups"].items():
        print(f"  {source:<9}{group:<7}{_pct(n['agree'], n['answered']):<12}"
              f"({n['answered']} of {n['cases']} answered)")
    forged = [r for r in res["rows"] if r["source"] == "forged" and r["label"]]
    if any(r["agree_weapons_only"] is not None and r["agree_weapons_only"] != r["agree"]
           for r in forged):
        a = sum(1 for r in forged if r["agree_weapons_only"])
        print(f"  forged against the weapons-only read: {_pct(a, len(forged))}")
    styles = sorted({r["forged_for"] for r in res["rows"] if r["source"] == "forged"})
    print(f"\nforged rosters not called the style they were forged for ({', '.join(styles)}):")
    for r in res["missed"]:
        print(f"  case {r['case']}: {r['content']} {r['size']}, labelled {r['label']}"
              f" (confidence {r['confidence'] or '-'}), engine read {r['engine']}")
    if not res["missed"]:
        print("  none" if forged else "  no forged roster answered yet")
    if res["unresolved"]:
        print("\nlabels outside the vocabulary (" + " / ".join(LABELS) + "):")
        for i, text in res["unresolved"]:
            print(f"  case {i}: {text!r}")
    if not res["answered"]:
        print("\nno answers filled in yet")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Style-labelling forms (module docstring).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.set_defaults(fn=generate)
    g.add_argument("--round", type=int, required=True,
                   help="the round the form belongs to: every battle an earlier round's key "
                        "records is excluded")
    g.add_argument("--out", required=True, help="the form; its key is written beside it")
    g.add_argument("--seed", type=int, default=20261009)
    g.add_argument("--style", default="kite", help="the style the forged rosters are forged for")
    g.add_argument("--contents", default="blackzone_roam,territory_defense")
    g.add_argument("--sizes", default="10,15,20",
                   help="the forged sizes, at most 20 (a single party caps at 20)")
    g.add_argument("--quotas", default=DEFAULT_QUOTAS,
                   help="harvested parties per engine label, label:n comma-separated, "
                        "dealt across the harvested sizes")
    g.add_argument("--min-size", type=int, default=10,
                   help="harvested parties stand at the forged sizes from min-size to max-size")
    g.add_argument("--max-size", type=int, default=20)
    g.add_argument("--rosters", default=None,
                   help="the roster artifact (default: pipeline/out/party_rosters.json.gz)")
    s = sub.add_parser("score")
    s.set_defaults(fn=score)
    s.add_argument("form")
    s.add_argument("--key", default=None, help="the form's key (default: <form>.key.json beside it)")
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
