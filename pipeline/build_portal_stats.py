#!/usr/bin/env python3
"""
Dragon Portal stats: what wins inside the Ancient Lands, per matchmaking
pool, from the kill-feed records the Ancient Bone marks (sample_parties.py
"CONTENT MARKER"). DISPLAY ONLY: this artifact feeds dashboard/portal.html
and nothing else; no scoring input reads it (standing rule: prevalence is
not effectiveness, the killboard surfaces never score).

THE UNIT. A killer party at kill time, deduplicated per battle by member
overlap exactly as the artifact's parties are. Solo is the lone killer.
The pools follow the game's matchmaking: solo, 2-3, 4-5, 6-7 (the 5-7
pool less the fives, which the 4-5 pool holds) and 15-20.

WHAT "DOING WELL" READS. Every party here scored at least one kill. Its
kills and deaths are the battle's per-name tallies summed over its
members (for a kill-feed record: times named as killer and as victim in
that battle's events). `dominant` = the party took no deaths in the
battle; `kd` = kills over deaths (deaths floored at one). Both are
reported beside the counts, never folded into one number.

BUILDS. Per weapon and pool, the modal item per slot over the WINNING
builds (a member of a killer party: seen as killer or participant, never
the victim), one player one vote (a player's fullest sighting per weapon),
shown from three votes. Beside the modal item each slot lists what else
the winners wore there (`others`, most worn first). Victims' builds are what died and are not
"best builds". A comp row carries the same read per member over the
comp's own sightings (`members`): the modal item per slot, one vote per
sighting of the member, from the comp's sighting floor, so the page can
show what the winners of THAT comp wore beside the pool-wide build of
each weapon.

SHAPES AND THE ROSTER PROFILE (pools of six and more). An exact comp is
every member's weapon, copy for copy; past five members it stops
recurring (measured: 93 distinct comps in 95 full 15-20 parties). The
read that recurs is the SHAPE: the party's members per role class
(frontline / healer / support / dps), each weapon read through its
primary seat exactly as the planner reads it (one role read). A shape
row carries the count per class, its sightings, dominant share and K/D,
and the weapons most fielded in each class inside that shape. Where even
shapes are sparse (15-20: 78 distinct in 95) the `profile` states the
pool as a whole: the quartiles of each class's count over the full
parties and the weapons that fill each class, with the share of parties
fielding one and the median copies where fielded.

Usage:  py -3 pipeline/build_portal_stats.py [--rosters PATH]  -> out/portal_stats.json
  --rosters names another roster artifact (a git-shown copy while the poll
  rewrites the working file).
"""
import collections
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import rosters_io  # noqa: E402

CONTENT = "ancient_lands"
POOLS = (("solo", "Solo", 1, 1), ("trio", "3v3", 2, 3), ("five", "5v5", 4, 5),
         ("seven", "7v7", 6, 7), ("large", "20v20", 15, 20))
SLOTS = ("Head", "Armor", "Shoes", "Cape", "OffHand", "Potion", "Food")
MIN_VOTES = 3          # a slot's modal item shows from this many distinct players
MIN_COMP = 2           # a comp shows from this many sightings
TOP_WEAPONS = 40
TOP_COMPS = 40
OTHERS = 8             # alternatives listed per slot beside the modal item
SHAPE_MIN_SIZE = 6     # pools from this size carry shapes and the roster profile
TOP_SHAPES = 30
ROLE_ORDER = ("frontline", "healer", "support", "dps", "other")
SHAPE_WEAPONS = 5      # weapons listed per class inside a shape
PROFILE_WEAPONS = 10   # weapons listed per class in the pool's profile


def _quartile(vals, q):
    """Nearest-rank quantile of a non-empty list."""
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def _pretty(gear_id):
    k = re.sub(r"^T\d+_", "", str(gear_id)).replace("@", " +")
    return k.replace("_", " ").title()


def pool_of(size):
    for key, _label, lo, hi in POOLS:
        if lo <= size <= hi:
            return key
    return None


def build(doc, weapons_meta, gear_meta, items, roles=None):
    """`roles` is the dataset's role book (a list of seats with their
    class): with it, pools of SHAPE_MIN_SIZE and more carry shapes and the
    roster profile; without it they carry neither."""
    seat_class = {r.get("id"): r.get("class") for r in (roles or []) if isinstance(r, dict)}

    def role_of(w):
        seat = ((weapons_meta.get(w) or {}).get("label") or {}).get("seat")
        return seat_class.get(seat) or "other"

    parties = doc.get("parties") or []
    builds = doc.get("builds") or []
    battles = doc.get("battles") or []
    stamps = [b.get("first_event_at") or b.get("started_at") for b in battles]
    stamps = [s for s in stamps if s]
    if not stamps:
        # an artifact folded before the battle summaries carried stamps:
        # read the window off the marked cache records themselves
        import party_store
        ids = {b.get("battle") for b in battles if b.get("battle")}
        if ids and os.path.exists(party_store.DEFAULT):
            with party_store.Store(party_store.DEFAULT, create=False) as store:
                for bid in ids:
                    meta = store.meta(bid)
                    if not meta:
                        continue
                    st = (store.get(bid) or {}).get("first_event_at") or meta[2]
                    if st:
                        stamps.append(st)
    wname = lambda w: (weapons_meta.get(w) or {}).get("display_name") or w
    # a curated item is named by its key or, for consumables curated at one
    # representative tier (T7_POTION_REVIVE), by its tier-stripped form
    by_form = {}
    for gk, gv in gear_meta.items():
        form = re.sub(r"^T\d+_", "", gk).split("@")[0]
        by_form.setdefault(form, (gv or {}).get("display_name"))
    gname = lambda g: ((gear_meta.get(g) or {}).get("display_name")
                       or by_form.get(re.sub(r"^T\d+_", "", g).split("@")[0]) or _pretty(g))
    # winner builds keyed by (battle, party index) -> members' builds
    by_party = collections.defaultdict(list)
    for b in builds:
        if b.get("seen_as") == "victim" or b.get("party") is None:
            continue
        by_party[(b.get("battle"), b.get("party"))].append(b)
    out_pools = {}
    for key, label, lo, hi in POOLS:
        ps = [p for p in parties if lo <= (p.get("size") or 0) <= hi]
        wstat = collections.defaultdict(lambda: {"parties": 0, "dominant": 0, "scored": 0,
                                                 "kills": 0, "deaths": 0, "players": set()})
        comps = collections.defaultdict(lambda: {"n": 0, "dominant": 0, "scored": 0,
                                                 "kills": 0, "deaths": 0})
        kits = collections.defaultdict(lambda: collections.defaultdict(dict))  # w -> player -> build
        comp_kits = collections.defaultdict(lambda: collections.defaultdict(dict))  # ck -> (w, player) -> build
        dom_total = scored_total = 0
        for p in ps:
            k, d = p.get("kills"), p.get("deaths")
            scored = k is not None and d is not None
            dominant = bool(scored and (d or 0) == 0 and (k or 0) >= 1)
            if scored:
                scored_total += 1
                dom_total += dominant
            members = by_party.get((p.get("battle"), p.get("index"))) or []
            for w in set(p.get("weapons") or []):
                st = wstat[w]
                st["parties"] += 1
                if scored:
                    st["scored"] += 1
                    st["dominant"] += dominant
                    st["kills"] += k or 0
                    st["deaths"] += d or 0
            for b in members:
                w = b.get("weapon")
                if not w or not b.get("player"):
                    continue
                wstat[w]["players"].add(b["player"])
                prev = kits[w].get(b["player"])
                if prev is None or (b.get("slots_filled") or 0) > (prev.get("slots_filled") or 0):
                    kits[w][b["player"]] = b
            if lo >= 2 and p.get("known_weapons") == p.get("size") and p.get("weapons"):
                ck = "|".join(sorted(p["weapons"]))
                c = comps[ck]
                c["n"] += 1
                if scored:
                    c["scored"] += 1
                    c["dominant"] += dominant
                    c["kills"] += k or 0
                    c["deaths"] += d or 0
                for b in members:
                    w = b.get("weapon")
                    if not w or not b.get("player") or w not in p["weapons"]:
                        continue
                    # one vote per sighting: the comp's unit is the party seen
                    # in a battle, so the same players wearing the same kit
                    # three times are three sightings of that kit
                    sk = (w, b["player"], p.get("battle"))
                    prev = comp_kits[ck].get(sk)
                    if prev is None or (b.get("slots_filled") or 0) > (prev.get("slots_filled") or 0):
                        comp_kits[ck][sk] = b
        n_parties = len(ps)

        def modal_build(bs, floor):
            """The modal item per slot over builds `bs`, one build one vote,
            a slot shown from `floor` votes."""
            best = {}
            for slot in SLOTS:
                cnt = collections.Counter()
                for b in bs:
                    g = (b.get("gear") or {}).get(slot)
                    if g:
                        cnt[re.sub(r"@\d+$", "", g)] += 1
                total = sum(cnt.values())
                if not cnt or total < floor:
                    continue
                item, n = max(cnt.items(), key=lambda kv: (kv[1], kv[0]))
                # the rest of the slot's field, most worn first, so the page
                # can show what else the winners wore there
                others = [{"id": g, "name": gname(g), "votes": c, "share": round(c / total, 3)}
                          for g, c in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
                          if g != item][:OTHERS]
                best[slot.lower()] = {"id": item, "name": gname(item), "votes": n,
                                      "share": round(n / total, 3), "of": total,
                                      "others": others}
            return best

        weapons = []
        for w, st in wstat.items():
            best = modal_build(kits[w].values(), MIN_VOTES)
            ips = [b.get("item_power") for b in kits[w].values() if b.get("item_power")]
            weapons.append({
                "id": w, "name": wname(w), "icon": items.get(w) or f"T6_{w}",
                "parties": st["parties"], "share": round(st["parties"] / n_parties, 3) if n_parties else 0.0,
                "players": len(st["players"]),
                "scored": st["scored"],
                "dominant_share": round(st["dominant"] / st["scored"], 3) if st["scored"] else None,
                "kd": round(st["kills"] / max(1, st["deaths"]), 2) if st["scored"] else None,
                "kills": st["kills"], "deaths": st["deaths"],
                "median_ip": int(sorted(ips)[len(ips) // 2]) if ips else None,
                "build": best,
            })
        weapons.sort(key=lambda r: (-r["parties"], -(r["dominant_share"] or 0), r["name"]))
        comp_rows = []
        for ck, c in comps.items():
            if c["n"] < MIN_COMP:
                continue
            ws = ck.split("|")
            members = []
            for w in ws:
                bs = [b for (bw, _pl, _bt), b in comp_kits[ck].items() if bw == w]
                members.append({"id": w, "name": wname(w), "icon": items.get(w) or f"T6_{w}",
                                "sightings": len(bs), "build": modal_build(bs, MIN_COMP)})
            comp_rows.append({
                "weapons": [{"id": w, "name": wname(w), "icon": items.get(w) or f"T6_{w}"} for w in ws],
                "members": members,
                "n": c["n"], "scored": c["scored"],
                "dominant_share": round(c["dominant"] / c["scored"], 3) if c["scored"] else None,
                "kd": round(c["kills"] / max(1, c["deaths"]), 2) if c["scored"] else None,
            })
        comp_rows.sort(key=lambda r: (-r["n"], -(r["dominant_share"] or 0), [w["name"] for w in r["weapons"]]))
        out_pools[key] = {
            "label": label, "sizes": [lo, hi], "parties": n_parties,
            "scored": scored_total,
            "dominant_share": round(dom_total / scored_total, 3) if scored_total else None,
            "weapons": weapons[:TOP_WEAPONS], "weapons_total": len(weapons),
            "comps": comp_rows[:TOP_COMPS], "comps_total": len(comp_rows),
        }
        if lo >= SHAPE_MIN_SIZE and seat_class:
            full = [p for p in ps if p.get("known_weapons") == p.get("size") and p.get("weapons")]
            wrow = lambda w: {"id": w, "name": wname(w), "icon": items.get(w) or f"T6_{w}"}

            def class_weapons(group, top):
                """Per class, the weapons most fielded across `group`: the
                parties fielding one, their share of the group, and the
                median copies where fielded."""
                out = {}
                for cls in ROLE_ORDER:
                    fielded = collections.defaultdict(list)   # weapon -> copies per fielding party
                    for p in group:
                        for w, n in collections.Counter(p["weapons"]).items():
                            if role_of(w) == cls:
                                fielded[w].append(n)
                    rows = [dict(wrow(w), parties=len(c), share=round(len(c) / len(group), 3),
                                 copies=_quartile(c, 0.5))
                            for w, c in fielded.items()]
                    rows.sort(key=lambda r: (-r["parties"], r["name"]))
                    if rows:
                        out[cls] = rows[:top]
                return out

            by_shape = collections.defaultdict(list)
            for p in full:
                c = collections.Counter(role_of(w) for w in p["weapons"])
                by_shape[tuple(c.get(k, 0) for k in ROLE_ORDER)].append(p)
            shape_rows = []
            for shape, group in by_shape.items():
                if len(group) < MIN_COMP:
                    continue
                sc = [p for p in group if p.get("kills") is not None and p.get("deaths") is not None]
                dom = sum(1 for p in sc if (p.get("deaths") or 0) == 0 and (p.get("kills") or 0) >= 1)
                shape_rows.append({
                    "counts": {k: v for k, v in zip(ROLE_ORDER, shape) if v or k != "other"},
                    "size": sum(shape), "n": len(group), "scored": len(sc),
                    "dominant_share": round(dom / len(sc), 3) if sc else None,
                    "kd": (round(sum(p.get("kills") or 0 for p in sc)
                                 / max(1, sum(p.get("deaths") or 0 for p in sc)), 2) if sc else None),
                    "weapons": class_weapons(group, SHAPE_WEAPONS),
                })
            shape_rows.sort(key=lambda r: (-r["n"], -(r["dominant_share"] or 0),
                                           [-r["counts"].get(k, 0) for k in ROLE_ORDER]))
            profile = None
            if full:
                per_class = {k: [sum(1 for w in p["weapons"] if role_of(w) == k) for p in full]
                             for k in ROLE_ORDER}
                profile = {
                    "parties": len(full),
                    "shapes_distinct": len(by_shape),
                    "roles": {k: {"p25": _quartile(v, 0.25), "p50": _quartile(v, 0.5),
                                  "p75": _quartile(v, 0.75), "min": min(v), "max": max(v)}
                              for k, v in per_class.items() if k != "other" or max(v)},
                    "weapons": class_weapons(full, PROFILE_WEAPONS),
                }
            out_pools[key]["shapes"] = shape_rows[:TOP_SHAPES]
            out_pools[key]["shapes_total"] = len(shape_rows)
            out_pools[key]["profile"] = profile
    return {
        "kind": "portal_stats",
        "content": CONTENT,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": ("kill-feed poll records marked by the Ancient Bone in the victim's "
                   "inventory (sample_parties.py CONTENT MARKER); killer parties only; "
                   "display only, never a scoring input"),
        "window": {"first": min(stamps)[:16] if stamps else None,
                   "last": max(stamps)[:16] if stamps else None},
        "battles": len(battles), "parties": len(parties),
        "thresholds": {"slot_votes": MIN_VOTES, "comp_sightings": MIN_COMP},
        "pools": out_pools,
    }


def main():
    path_arg = None
    if "--rosters" in sys.argv:
        path_arg = sys.argv[sys.argv.index("--rosters") + 1]
    doc = rosters_io.load(path_arg, source="all", content=CONTENT)
    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        ds = json.load(f)
    items = {}
    wl = os.path.join(OUT, "weapon_lines.json")
    if os.path.exists(wl):
        with open(wl, encoding="utf-8") as f:
            for k, v in (json.load(f) or {}).items():
                if isinstance(v, dict) and v.get("example_item"):
                    items[k] = v["example_item"]
    stats = build(doc, ds.get("weapons") or {}, ds.get("gear") or {}, items,
                  ds.get("roles") or [])
    path = os.path.join(OUT, "portal_stats.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, indent=1, sort_keys=True)
        f.write("\n")
    pools = stats["pools"]
    print(f"portal stats: {stats['battles']} battles, {stats['parties']} killer parties, "
          f"window {stats['window']['first']} .. {stats['window']['last']}")
    for key, _l, _lo, _hi in POOLS:
        p = pools[key]
        print(f"  {p['label']:6s} parties {p['parties']:5d}  weapons {p['weapons_total']:3d}  "
              f"comps {p['comps_total']:3d}  dominant {p['dominant_share']}"
              + (f"  shapes {p['shapes_total']:3d}" if "shapes_total" in p else ""))
    print(f"wrote out/portal_stats.json")


if __name__ == "__main__":
    main()
