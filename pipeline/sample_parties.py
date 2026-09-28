#!/usr/bin/env python3
"""
Sample REAL PARTY COMPOSITIONS from the killboard.

WHY THIS EXISTS. Every other evidence layer in this project sees weapons but
not parties. `sample_battles.py` counts weapons from kill events (killer +
victim), so a player who neither killed nor died is invisible, and nothing
groups players into the squads they actually fought in. `sample_rosters.py`
reconstructs alliance-level roster MIXES but stores seat labels, not
weapons. Meanwhile the comp corpus is 36 published compositions — plans
people wrote down, not parties that fought.

The official gameinfo API carries `GroupMembers` on every kill event: the
KILLER'S PARTY at the moment of the kill, each member with their equipment.
That is a real party roster, which is exactly the unit the engine models.
albionbb strips the field; the official API keeps it (verified: the old
note that the official gameinfo events endpoint 504s constantly no longer
holds — every endpoint tested, list and detail, answered 200 in under a
second).

THREE-STEP PIPELINE (each step exists because the one before it cannot
answer the question):

  1. DISCOVERY   albionbb /battles?minPlayers=N   — the only source with a
                 size filter, so large fights can be found without crawling
                 everything. Gives `totalPlayers`, the stated fight size.
  2. ROSTER      official /battles/{id}           — EVERY player in the
                 fight (name, guild, alliance, kills, deaths). No equipment,
                 but it is the honest DENOMINATOR: coverage becomes measured
                 rather than assumed.
  3. PARTIES     official /events/{id} per kill   — `GroupMembers` (the
                 killer's party, with equipment) and `Participants` (who
                 damaged the victim, with equipment).

WHAT THIS DATA IS — AND IS NOT.
  * A party here is a GroupMembers set: players grouped in-game at kill
    time. It is NOT a comp. A 300-player battle is a coalition of many
    parties; this samples the parties, which is the useful unit.
  * THE FILTER IS "SCORED AT LEAST ONE KILL", NOT "WON" — and it was
    MEASURED rather than assumed, because "winner-biased" overstates it.
    Of 354 captured parties: 61% dominant (2x+ K/D), 19% traded roughly
    even, and 20% took MORE DEATHS THAN KILLS. Losing parties are well
    represented; they only had to kill someone first. What drops out is
    the 10% of players in no captured party at all, whose combined record
    is 34 kills against 475 deaths (K/D 0.07) — they died about once each
    and killed almost nothing. Rule: a party that could not score a single
    kill is not worth recording. Coverage is 90% of all players across the
    sampled battles. Prevalence is still not effectiveness — that standing
    rule is unchanged.
  * DEDUPLICATED per battle by member-name set. A party that gets 20 kills
    emits 20 identical GroupMembers arrays; counting those as 20 parties
    would multiply whatever that squad ran by its kill count, which is the
    exact bias this data exists to remove.
  * Equipment is as recorded at that event. Players who swap mid-fight can
    appear under two weapons; the party is keyed on names, not gear.
  * DISPLAY / EVIDENCE ONLY. Nothing here feeds scoring. Like every observed
    layer, it may inform a rule; it never becomes a scoring input on its
    own.

Usage:  py -3 pipeline/sample_parties.py [--battles 25] [--min-players 25]
                                         [--max-players 0] [--max-events 120]
                                         [--server us] [--pages 40]
        py -3 pipeline/sample_parties.py --pages 0     (offline re-analysis)
        py -3 pipeline/sample_parties.py --poll-events  (kill-feed poll, cache only)

CONTENT TAG. Every kill event carries `KillArea` (the content classifier
the API exposes: OPEN_WORLD, and one value per instanced content) beside
`Location` and `Category`, which the API leaves null on current traffic.
The cache records all three per event, a per-battle and per-party tally of
KillArea, and the KillArea each build was captured in; `analyze()` stamps
a `content` tag on every battle, party and build (`open_world`, or the
lower-cased KillArea of an instanced content). The harvest never filters
on it: the tag exists so a derive step can select one content's parties.
Records written before the tag existed carry no tally and read `unknown`.

CONTENT MARKER. The API labels every Ancient Lands kill OPEN_WORLD and
leaves `Location` and the battle's `clusterName` null (34,499 events over
one day, every one OPEN_WORLD), so KillArea alone cannot separate the
portal fights. The kill event also carries the VICTIM's inventory, and
the Ancient Bone (`QUESTITEM_TOKEN_DRAGONS`, "Bring it to an Ancient
Altar") is a quest item earned from Drakes and chests inside the Ancient
Lands and spent at its altars, and the two Drake shards mark the same
(CONTENT_MARKERS, with the measurement). A victim carrying one died inside; the
killer's party on that event fought inside; a battle holding such an
event is an Ancient Lands battle (an instance's kills form their own
battle). Measured on the first day: victims with the bone are killed by
solo parties 76%, trios 14%, fives 4% (all kills: 50 / 11 / 4), at a
victim item power p90 of 1,291 against 1,417 overall (the 1,200 soft
cap), between 07:00 and 18:00 UTC. A kill whose victim had not yet earned
a bone is not marked: the rule undercounts, it never invents. Each
record keeps the marker tally (`content_marks`) beside the raw KillArea
tally (`kill_areas`); `content_tag()` reads the instanced KillArea
first, the marker second. `--retag` rebuilds the tallies of every
kill-feed record from its stored events, offline.

POPULATION. The poll samples the whole server's kill feed, so its records
are dominated by 1-5 man open-world ganks, a population the battle-list
harvest never sampled (its floors are 25 and 8 players). Every reader of
the artifact goes through `rosters_io.load`, whose default population is
the battle-list records only; a derive step that wants the poll's
records asks for them by `source` and `content`. The shipped tables
therefore keep the population they were fitted on until a decision
admits another (BACKLOG, the Dragon Portal evidence unit).

STORAGE. A kill-feed record keeps its events SLIMMED (`slim_event`: ids,
stamps, the classifier fields, every combat role's name / guild /
alliance / item power / equipment types, the victim's inventory item
types, the killer party's names and main hands) so a record is a pure
function of what the tallies read and a day of polling is tens of
megabytes, not hundreds. Every cache write is atomic (a temp file in the
same directory, then `os.replace`), because the poll, the twice-daily
harvest and the fold read and write one directory at the same time; an
unreadable file is skipped and reported, never overwritten and never
fatal. A battle-list harvest that reaches a poll record while the
official battle record still lags (404) keeps the poll record.

KILL-FEED POLL (`--poll-events`). The battle list is the wrong discovery
for the Ancient Lands portal pools of 2-3, 4-5 and 5-7 players: their
fights are 4-14 players, albionbb lists fights by a player floor, and the
official battle record lags the kills. The public events feed exposes the
newest ~1,000 kills with the killer's party and every combat role's
equipment in the list itself, so a poll every few minutes catches each
small-bracket kill without a per-event detail fetch. Events are grouped by
BattleId and merged into per-battle cache records (`source: events_poll`,
deduplicated by EventId across polls); the roster of such a record is
rebuilt from the events (kills = times named as killer, deaths = times
named as victim), so its coverage is against the seen set, not an
official roster. A later full harvest of the same battle replaces the poll
record with the official one. The poll writes the cache only; the artifact
is re-derived by the fold.

FIGHT-SIZE BAND. `--min-players` is the discovery floor albionbb filters on;
`--max-players` (0 = none) is a local ceiling on the listed `totalPlayers`,
so a pass can be pointed at one size class — `--min-players 10
--max-players 14` walks the 5v5 / 7v7 band (a focused night on 7v7 and
5v5 fights) and spends its `--battles` budget only on fights in the band;
everything larger is skipped, not fetched. The band is a DISCOVERY
choice: the cache keeps every battle ever fetched and `analyze()` reads all
of it, so a banded night adds to the corpus and never narrows it.
"""
import argparse
import hashlib
import collections
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rosters_io  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "party_cache")
UA = {"User-Agent": "bion-comp-engine/sample_parties (albion comp research)"}
GAMEINFO = "https://gameinfo.albiononline.com/api/gameinfo"


# Why a request came back empty, tallied across a pass so the coverage line
# can say whether a miss was the API lacking the event (404 — nothing to
# fetch) or the harvest being throttled (429 / 5xx — lower --workers).
ERRORS = collections.Counter()


def get_json(url, tries=4, pause=1.5):
    """One request with backoff. Returns None rather than raising — the
    gameinfo API returns intermittent 502s and a single miss must not kill
    a long harvest. Thread-safe: no state beyond the ERRORS tally."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as ex:
            last = str(ex.code)
            if ex.code in (429, 502, 503, 504):
                time.sleep(pause * (attempt + 1))
                continue
            break
        except Exception as ex:
            last = type(ex).__name__
            time.sleep(pause * (attempt + 1))
    ERRORS[last or "unknown"] += 1
    return None


EQUIP_SLOTS = ("MainHand", "OffHand", "Head", "Armor", "Shoes", "Cape",
               "Potion", "Food")


def _slim_member(m, inventory=False):
    if not isinstance(m, dict):
        return None
    eq = m.get("Equipment") or {}
    out = {"Name": m.get("Name"), "GuildName": m.get("GuildName"),
           "AllianceName": m.get("AllianceName"),
           "AverageItemPower": m.get("AverageItemPower"),
           "Equipment": {s: {"Type": (eq.get(s) or {}).get("Type")}
                         for s in EQUIP_SLOTS
                         if isinstance(eq.get(s), dict) and (eq.get(s) or {}).get("Type")}}
    if inventory:
        out["Inventory"] = [{"Type": x["Type"]} for x in (m.get("Inventory") or [])
                            if isinstance(x, dict) and x.get("Type")]
    return out


def slim_event(d):
    """The part of a kill event the tallies read (see STORAGE above).
    Idempotent: a slimmed event slims to itself."""
    return {
        "EventId": d.get("EventId"), "BattleId": d.get("BattleId"),
        "TimeStamp": d.get("TimeStamp"), "KillArea": d.get("KillArea"),
        "Location": d.get("Location"), "Category": d.get("Category"),
        "Type": d.get("Type"),
        "Killer": _slim_member(d.get("Killer")),
        "Victim": _slim_member(d.get("Victim"), inventory=True),
        "Participants": [x for x in (_slim_member(m) for m in (d.get("Participants") or [])) if x],
        "GroupMembers": [x for x in (_slim_member(m) for m in (d.get("GroupMembers") or [])) if x],
    }


def write_json_atomic(path, obj):
    """A cache record lands whole or not at all: three processes share
    the directory (the poll, the harvest, the fold's analysis)."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def read_json(path):
    """A cache record, or None when the file is unreadable (mid-write,
    truncated by a task kill): reported by the caller, never fatal."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# Items that exist only inside one content, read off the VICTIM's inventory
# on the kill event ("CONTENT MARKER" above). An id matches as a prefix of
# the item type with its tier and enchant stripped.
CONTENT_MARKERS = {
    # The Ancient Bone (a quest item spent at the altars inside) and the two
    # Drake shards (fragments dropped by the Drakes inside; tradable, so a
    # victim may carry one out). Measured over two days of the kill feed
    # against the bone: shard-only victims read a killer-party mix of solo
    # 37% / trio 41% / 4-7 21%, an item power p90 of about 1,295 against
    # 1,442 for the open world, and 52% of them died in a battle that also
    # holds a bone victim (2% for an untagged event). They add about a
    # fifth more portal battles, mostly group fights, which the bone misses
    # most. The per-item tally under "content:item" keeps the shards
    # auditable, so they can be dropped without touching the records.
    "ancient_lands": ("QUESTITEM_TOKEN_DRAGONS",
                      "SHARD_RANDOM_DUNGEON_ELITE_DRAGON_TOKEN",
                      "SHARD_FIRE_DRAGON"),
}


def event_marker(d, item=False):
    """The content an event's victim inventory marks, or None; with
    `item`, the (content, marker id) pair (the first marker in table
    order that the inventory carries)."""
    inv = ((d.get("Victim") or {}).get("Inventory") or [])
    keys = set()
    for x in inv:
        t = (x or {}).get("Type") if isinstance(x, dict) else None
        if t:
            keys.add(re.sub(r"^T\d+_", "", str(t).split("@")[0]))
    for content, ids in CONTENT_MARKERS.items():
        for m in ids:
            if any(k.startswith(m) for k in keys):
                return (content, m) if item else content
    return None


def content_tag(areas, marks=None):
    """The content a record belongs to: the lower-cased label of the
    dominant instanced KillArea when the API labels one; else the content
    a marker item names on any event of the record; else `open_world`;
    `unknown` for a record written before the tallies existed. A tag,
    never a filter."""
    if not areas:
        return "unknown"
    inst = {a: n for a, n in areas.items() if a and a != "OPEN_WORLD"
            and a != "UNKNOWN"}
    if inst:
        return max(inst.items(), key=lambda kv: (kv[1], kv[0]))[0].lower()
    marked = {c: n for c, n in (marks or {}).items() if c and n and ":" not in c}
    if marked:
        return max(marked.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return "open_world"


def weapon_key(t, known):
    """Item id -> catalogue key, tier and enchant stripped."""
    if not t:
        return None
    k = str(t).split("@")[0]
    k = re.sub(r"^T\d+_", "", k)
    return k if k in known else None


def ingest_event(d, known, builds, parties, participants, areas, stamps,
                 marks=None):
    """One kill event into the per-battle sinks. FULL BUILDS come from
    Killer / Victim / Participants, which carry 7 of 8 equipment slots
    plus item power. GroupMembers does NOT: as measured, it fills MainHand
    only and reports AverageItemPower 0. So party STRUCTURE comes from
    GroupMembers and BUILDS come from the combat roles; a member who
    never killed, died or dealt damage yields a weapon and nothing else,
    and is recorded that way rather than guessed. Every sink also keeps
    the event's KillArea: the tally per battle (`areas`), per party
    (`kill_areas`) and per build (`kill_area`, the event the fullest
    sighting came from)."""
    area = d.get("KillArea") or "UNKNOWN"
    areas[area] += 1
    pair = event_marker(d, item=True)
    mark = pair[0] if pair else None
    if pair and marks is not None:
        marks[pair[0]] += 1
        marks[f"{pair[0]}:{pair[1]}"] += 1     # the per-item tally, audit only
    if d.get("TimeStamp"):
        stamps.append(d["TimeStamp"])
    pool = [("killer", d.get("Killer")),
            ("victim", d.get("Victim"))]
    pool += [("participant", m) for m in (d.get("Participants")
                                          or [])]
    for how, m in pool:
        if not isinstance(m, dict) or not m.get("Name"):
            continue
        eq = m.get("Equipment") or {}
        gear = {}
        for slot in ("MainHand", "OffHand", "Head", "Armor",
                     "Shoes", "Cape", "Potion", "Food"):
            v = eq.get(slot)
            gear[slot] = (v or {}).get("Type") if isinstance(
                v, dict) else None
        n_filled = sum(1 for v in gear.values() if v)
        prev = builds.get(m["Name"])
        if prev is None or n_filled > prev["slots_filled"]:
            builds[m["Name"]] = {
                "name": m["Name"],
                "guild": m.get("GuildName") or None,
                "alliance": m.get("AllianceName") or None,
                "item_power": m.get("AverageItemPower"),
                "seen_as": how,
                "slots_filled": n_filled,
                "kill_area": area,
                "content_mark": mark,
                "location": d.get("Location"),
                "gear": gear}
    for field, sink in (("GroupMembers", parties),
                        ("Participants", participants)):
        members = d.get(field) or []
        if not members:
            continue
        named = []
        for m in members:
            nm = m.get("Name")
            if not nm:
                continue
            w = weapon_key(
                ((m.get("Equipment") or {}).get("MainHand")
                 or {}).get("Type"), known)
            named.append({
                "name": nm, "weapon": w,
                "guild": m.get("GuildName") or None,
                "alliance": m.get("AllianceName") or None})
        if not named:
            continue
        # DEDUPE: a party that gets 20 kills must count ONCE
        key = "|".join(sorted(m["name"] for m in named))
        prev = sink.get(key)
        if prev is None or sum(
                1 for m in named if m["weapon"]) > sum(
                1 for m in prev["members"] if m["weapon"]):
            sink[key] = {"members": named,
                         "seen_in_events": (prev or {}).get("seen_in_events", 0),
                         "kill_areas": dict((prev or {}).get("kill_areas") or {})}
        sink[key]["seen_in_events"] += 1
        sink[key]["kill_areas"][area] = sink[key]["kill_areas"].get(area, 0) + 1


def rebuild_poll_record(bid, raw, known):
    """A kill-feed record as a pure function of its event set: the sinks,
    the roster rebuilt from the events (kills = times named as killer,
    deaths = times named as victim), the tallies."""
    builds, parties, participants = {}, {}, {}
    areas, marks, stamps = collections.Counter(), collections.Counter(), []
    kills_by, deaths_by, guild_of = collections.Counter(), collections.Counter(), {}
    raw = {eid: slim_event(d) for eid, d in raw.items()}
    for d in sorted(raw.values(), key=lambda e: (e.get("TimeStamp") or "", e.get("EventId") or 0)):
        ingest_event(d, known, builds, parties, participants, areas, stamps,
                     marks)
        k, v = d.get("Killer") or {}, d.get("Victim") or {}
        if k.get("Name"):
            kills_by[k["Name"]] += 1
            guild_of[k["Name"]] = (k.get("GuildName"), k.get("AllianceName"))
        if v.get("Name"):
            deaths_by[v["Name"]] += 1
            guild_of[v["Name"]] = (v.get("GuildName"), v.get("AllianceName"))
        for m in (d.get("Participants") or []) + (d.get("GroupMembers") or []):
            if isinstance(m, dict) and m.get("Name"):
                guild_of.setdefault(m["Name"], (m.get("GuildName"), m.get("AllianceName")))
    roster = [{"name": nm, "guild": g[0] or None, "alliance": g[1] or None,
               "kills": kills_by.get(nm, 0), "deaths": deaths_by.get(nm, 0)}
              for nm, g in sorted(guild_of.items())]
    return {
        "schema": 2,
        "source": "events_poll",
        "roster_source": "events",
        "battle": bid,
        "builds": list(builds.values()),
        "started_at": min(stamps) if stamps else None,
        "total_players": len(roster),
        "total_kills": len(raw),
        "roster": roster,
        "kill_events": len(raw),
        "events_fetched": len(raw),
        "kill_areas": dict(areas),
        "content_marks": dict(marks),
        "first_event_at": min(stamps) if stamps else None,
        "last_event_at": max(stamps) if stamps else None,
        "parties": list(parties.values()),
        "participant_sets": list(participants.values()),
        "raw_events": sorted(raw.values(), key=lambda e: e["EventId"]),
    }


def retag(known):
    """Rebuild every kill-feed record from its stored events, offline:
    the way a new marker or a changed tag rule reaches records already
    collected. Battle-list records keep no events and are not touched."""
    n, marks = 0, collections.Counter()
    for name in sorted(os.listdir(CACHE)):
        path = os.path.join(CACHE, name)
        rec = read_json(path)
        if not rec or not rec.get("raw_events"):
            continue
        raw = {e["EventId"]: e for e in rec["raw_events"] if e.get("EventId")}
        if rec.get("source") == "events_poll":
            out = rebuild_poll_record(rec["battle"], raw, known)
        else:
            # a battle-list record keeps its official roster and sinks;
            # only the tallies are recomputed from the stored events
            mk = collections.Counter()
            for d in raw.values():
                pair = event_marker(d, item=True)
                if pair:
                    mk[pair[0]] += 1
                    mk[f"{pair[0]}:{pair[1]}"] += 1
            out = dict(rec)
            out["content_marks"] = dict(mk)
        marks.update({k: v for k, v in out["content_marks"].items() if ":" not in k})
        write_json_atomic(path, out)
        n += 1
    print(f"retag: {n} kill-feed record(s) rebuilt; content markers: " + (", ".join(
        f"{c} x{k}" for c, k in marks.most_common()) or "none"), flush=True)


REMARK_SINCE = "2026-08-31"   # the Dragonfire update: no portal fight before it


def remark(args, known):
    """Battle-list records harvested before the marker existed carry no
    `content_marks` and keep no events (records written since keep their
    slimmed events and are a `--retag` away), so `--retag` cannot reach them:
    re-fetch their kill events (the official detail carries the victim's
    inventory) and rewrite them through harvest_battle. Network step; a
    one-off after a marker lands, never part of a build."""
    todo = []
    for name in sorted(os.listdir(CACHE)):
        rec = read_json(os.path.join(CACHE, name))
        if not rec or rec.get("source") == "events_poll":
            continue
        if "content_marks" in rec and rec.get("raw_events"):
            continue
        # the Ancient Lands opened with the Dragonfire update: a battle
        # before it cannot hold a portal fight
        if (rec.get("started_at") or "") < REMARK_SINCE:
            continue
        if args.remark_min_players and (rec.get("total_players") or 0) < args.remark_min_players:
            continue
        if args.remark_max_players and (rec.get("total_players") or 0) > args.remark_max_players:
            continue
        todo.append((rec, rec["battle"], rec.get("total_players") or 0,
                     os.path.join(CACHE, name)))
    todo.sort(key=lambda t: t[0].get("started_at") or "", reverse=True)   # newest first
    print(f"remark: {len(todo)} battle-list record(s) without marks to re-fetch, "
          f"{max(1, args.workers)} worker(s)", flush=True)
    import concurrent.futures as cf
    marked = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(harvest_battle, args, known, {}, bid, total, path)
                for _rec, bid, total, path in todo]
        for fut, (_rec, bid, _t, path) in zip(futs, todo):
            try:
                line, _k, _e = fut.result()
            except Exception as ex:
                print(f"  battle {bid} failed: {ex!r}", flush=True)
                continue
            new = read_json(path) or {}
            if (new.get("content_marks") or {}).get("ancient_lands"):
                marked += 1
                line += "   ANCIENT LANDS"
            print(line, flush=True)
    print(f"remark: {marked} of {len(todo)} re-fetched battles carry a portal mark", flush=True)


def poll_events(args, known):
    """The kill-feed poll: the newest events, grouped by battle, merged
    into per-battle cache records. Cache only. Prints the KillArea tally
    of what it saw, which is how an instanced content's label is first
    observed."""
    os.makedirs(CACHE, exist_ok=True)
    by_battle, seen_events, pages = {}, 0, 0
    for off in range(0, max(51, args.poll_depth), 51):
        lst = get_json(f"{GAMEINFO}/events?limit=51&offset={off}")
        if not lst:
            break
        pages += 1
        for d in lst:
            bid, eid = d.get("BattleId"), d.get("EventId")
            if not bid or not eid:
                continue
            seen_events += 1
            by_battle.setdefault(bid, {})[eid] = d
        if len(lst) < 51:
            break
    new_events, touched, tally = 0, 0, collections.Counter()
    marks_tally, unreadable = collections.Counter(), 0
    for bid, evs in sorted(by_battle.items()):
        path = os.path.join(CACHE, f"{bid}.json")
        rec = None
        if os.path.exists(path):
            rec = read_json(path)
            if rec is None:
                unreadable += 1
                continue        # mid-write or damaged: never overwrite it
            if rec.get("source") != "events_poll":
                continue        # the full harvest already holds this battle
        # rebuild the sinks from the stored raw events plus the new ones:
        # the record stays a pure function of its event set
        raw = {e["EventId"]: e for e in (rec or {}).get("raw_events") or []}
        fresh = [d for eid, d in evs.items() if eid not in raw]
        if not fresh:
            continue
        for d in fresh:
            raw[d["EventId"]] = d
        new_events += len(fresh)
        touched += 1
        out = rebuild_poll_record(bid, raw, known)
        tally.update(out["kill_areas"])
        marks_tally.update(out["content_marks"])
        write_json_atomic(path, out)
    sizes = collections.Counter(
        len(d.get("GroupMembers") or []) for evs in by_battle.values() for d in evs.values())
    print(f"poll: {seen_events} events on {pages} page(s), {len(by_battle)} battles, "
          f"{new_events} new events into {touched} record(s)", flush=True)
    print("  KillArea this poll: " + (", ".join(
        f"{a} x{n}" for a, n in tally.most_common()) or "none new"), flush=True)
    print("  content markers this poll: " + (", ".join(
        f"{c} x{n}" for c, n in marks_tally.most_common()) or "none"), flush=True)
    print("  killer-party sizes seen: " + ", ".join(
        f"{k}:{v}" for k, v in sorted(sizes.items())), flush=True)
    errs = ", ".join(f"{k} x{v}" for k, v in sorted(ERRORS.items())) or "none"
    print(f"  request misses after retries: {errs}"
          + (f"; {unreadable} record(s) unreadable, left alone" if unreadable else ""),
          flush=True)


def harvest_battle(args, known, b, bid, total, path):
    """Steps 2-3 for ONE battle: the official roster, the kill list, every
    kill event's parties and builds, written to its own cache file. Runs
    on a worker thread (`--workers`): the per-battle work is
    independent — one file per battle, no shared state — so battles run
    side by side while each battle's events stay sequential, and the file
    a worker writes is byte-identical to what the old sequential loop
    wrote. Returns (log line, kills counted, events fetched)."""
    server = args.server
    # step 2 — the full roster (denominator)
    detail = get_json(f"{GAMEINFO}/battles/{bid}")
    if detail is None and os.path.exists(path):
        prev = read_json(path)
        if prev and prev.get("source") == "events_poll":
            # the official record lags the kills: the poll record, with its
            # event-built roster, is the better one until it exists
            return (f"  battle {bid}: official record not yet available, "
                    f"kill-feed record kept", 0, 0)
    roster = list((detail or {}).get("players", {}).values())

    # step 3 — per-kill parties
    kills = get_json(
        f"https://api.albionbb.com/{server}/battles/kills?ids={bid}"
    ) or []
    parties, participants, ev_ok = {}, {}, 0
    builds, areas, stamps = {}, collections.Counter(), []
    marks, raw_kept = collections.Counter(), []
    for x in kills[:args.max_events]:
        eid = x.get("EventId")
        if not eid:
            continue
        # three tries (was two): daytime 502s ran ~4% per call
        # and a second 502 lost the event; the third try, 4.5 s later,
        # costs nothing while other workers keep fetching
        d = get_json(f"{GAMEINFO}/events/{eid}", tries=3)
        if not d:
            continue
        ev_ok += 1
        raw_kept.append(slim_event(d))
        ingest_event(d, known, builds, parties, participants, areas, stamps,
                     marks)

    rec = {
        "schema": 2,          # 2 = carries full builds; 1 did not
        "battle": bid,
        "builds": list(builds.values()),
        "started_at": b.get("startedAt"),
        "total_players": total,
        "total_kills": b.get("totalKills"),
        "roster": [{"name": p.get("name"),
                    "guild": p.get("guildName") or None,
                    "alliance": p.get("allianceName") or None,
                    "kills": p.get("kills"), "deaths": p.get("deaths")}
                   for p in roster],
        "kill_events": len(kills),
        "events_fetched": ev_ok,
        "kill_areas": dict(areas),
        "content_marks": dict(marks),
        "first_event_at": min(stamps) if stamps else None,
        "last_event_at": max(stamps) if stamps else None,
        "parties": list(parties.values()),
        "participant_sets": list(participants.values()),
        # the slimmed events: a marker added later reaches this record
        # through --retag, never another fetch
        "raw_events": sorted(raw_kept, key=lambda e: e.get("EventId") or 0),
    }
    prev = read_json(path) if os.path.exists(path) else None
    if prev and prev.get("source") == "events_poll":
        # the poll saw this battle first: its marks and stored events ride
        # along, so a capped or partial event fetch can never lose a tag
        for c, n in (prev.get("content_marks") or {}).items():
            rec["content_marks"][c] = max(rec["content_marks"].get(c, 0), n)
        if prev.get("raw_events"):
            have = {e.get("EventId") for e in rec["raw_events"]}
            rec["raw_events"] = sorted(
                rec["raw_events"] + [e for e in prev["raw_events"] if e.get("EventId") not in have],
                key=lambda e: e.get("EventId") or 0)
    write_json_atomic(path, rec)
    return (f"  battle {bid}: {total} players, {len(kills)} kills, "
            f"{ev_ok} events fetched, {len(parties)} distinct parties",
            min(len(kills), args.max_events), ev_ok)


def fetch(args, known):
    os.makedirs(CACHE, exist_ok=True)
    server = args.server
    seen_battles = 0
    page = 1
    max_pages = args.pages if args.pages and args.pages > 0 else 40
    todo = []          # (b, bid, total, path) not yet in the cache
    while seen_battles < args.battles and page <= max_pages:
        url = (f"https://api.albionbb.com/{server}/battles"
               f"?minPlayers={args.min_players}&page={page}")
        lst = get_json(url) or []
        if not lst:
            break
        for b in lst:
            if seen_battles >= args.battles:
                break
            bid = b.get("albionId")
            total = b.get("totalPlayers") or 0
            if not bid or total < args.min_players:
                continue
            if args.max_players and total > args.max_players:
                continue        # outside the requested size band
            path = os.path.join(CACHE, f"{bid}.json")
            if os.path.exists(path):
                # schema 1 cached weapons only — re-fetch it for the builds
                cached = read_json(path) or {}
                # a kill-feed poll record has no official roster;
                # the battle-list harvest replaces it
                if (cached.get("schema", 1) >= 2
                        and cached.get("source") != "events_poll"):
                    seen_battles += 1
                    continue
            todo.append((b, bid, total, path))
            seen_battles += 1
        page += 1
    # FETCH IN PARALLEL: the harvest's cost is the kill-event
    # detail fetch, ~1.8 s per event sequentially and one HTTP call each.
    # Battles are independent units of work (own cache file, own log line),
    # so a small pool runs them side by side; events within a battle stay
    # sequential. `--workers 1` is the old loop. Coverage is reported at
    # the end so a rate-limited night (429s exhaust get_json's retries and
    # the event is skipped, not raised) is visible rather than silent:
    # the sequential baseline was 0.987 (one nightly pass).
    import concurrent.futures as cf
    kills_total = events_total = 0
    workers = max(1, args.workers)
    print(f"{len(todo)} battles to fetch, {workers} worker(s)", flush=True)
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(harvest_battle, args, known, *t) for t in todo]
        for fut in cf.as_completed(futs):
            try:
                line, k, e = fut.result()
            except Exception as ex:      # one bad battle must not kill a night
                print(f"  battle failed: {ex!r}", flush=True)
                continue
            kills_total += k
            events_total += e
            print(line, flush=True)
    cov = (events_total / kills_total) if kills_total else 1.0
    flag = "" if cov >= 0.95 else "   WARNING: below the 0.95 floor — rate limited? lower --workers"
    errs = ", ".join(f"{k} x{v}" for k, v in sorted(ERRORS.items())) or "none"
    print(f"event coverage this pass: {events_total}/{kills_total} = {cov:.3f}"
          f"  (request misses after retries: {errs}){flag}", flush=True)
    print(f"cache holds {len(os.listdir(CACHE))} battles", flush=True)


def analyze(known):
    if not os.path.isdir(CACHE) or not os.listdir(CACHE):
        sys.exit("no cache — run without --pages 0 first")
    battles, parties = [], []
    battle_party_index = {}   # battle -> {member name: party index}
    # one directory snapshot for both passes: the poll adds files while
    # this runs, and a battle must not appear in builds but not in battles
    cache_names = sorted(os.listdir(CACHE))
    unreadable = []
    for name in cache_names:
        rec = read_json(os.path.join(CACHE, name))
        if not rec:
            unreadable.append(name)
            continue
        total = rec.get("total_players") or 0
        from_poll = rec.get("source") == "events_poll"
        seen = {m["name"] for p in rec.get("parties", [])
                for m in p["members"]}
        seen |= {m["name"] for p in rec.get("participant_sets", [])
                 for m in p["members"]}
        # COVERAGE IS AGAINST THE OFFICIAL ROSTER, NOT totalPlayers.
        # GroupMembers reports the killer's WHOLE party, including members
        # who were not at this battle — a 20-man party with 8 people here
        # still lists 20. Dividing by totalPlayers therefore produced
        # coverage above 1.0 (measured 1.061 on the first run). The official
        # battle roster is the only ground truth for who was actually in the
        # fight, so the seen set is intersected with it, and the leftovers
        # are reported separately rather than silently inflating the number.
        roster_names = {p["name"] for p in (rec.get("roster") or [])
                        if p.get("name")}
        in_fight = seen & roster_names if roster_names else set()
        outside = seen - roster_names if roster_names else set()
        # a kill-feed record's roster IS the seen set (rebuilt from the
        # events), so coverage against it is 1.0 by construction: stored
        # as None, never as a measurement
        if from_poll:
            in_fight, outside = set(), set()
        areas = rec.get("kill_areas")
        content = content_tag(areas, rec.get("content_marks"))
        battles.append({
            "battle": rec["battle"], "total_players": total,
            "source": rec.get("source") or "battle_list",
            "started_at": rec.get("started_at"),
            "first_event_at": rec.get("first_event_at"),
            "kill_areas": dict(areas) if areas else None,
            "content_marks": dict(rec["content_marks"]) if rec.get("content_marks") else None,
            "content": content,
            "roster_known": len(roster_names),
            "players_with_gear": len(in_fight) if not from_poll else None,
            "coverage": (round(len(in_fight) / len(roster_names), 3)
                         if roster_names and not from_poll else None),
            "party_members_not_in_this_battle": len(outside) if not from_poll else None,
            "kill_events": rec.get("kill_events"),
            "events_fetched": rec.get("events_fetched"),
            "parties": len(rec.get("parties") or [])})
        # SECOND DEDUPE — by MEMBER OVERLAP, not exact set. Keying on the
        # exact name-set is not enough: a squad loses members as they die,
        # so one 19-man party emits 19/18/15/14/13-member arrays across a
        # battle and reads as five distinct parties. Every size statistic
        # built on that would be wrong, and the same squad's weapons would
        # be counted five times. Sets sharing more than half their members
        # are the same squad; the LARGEST observation wins, being the
        # fullest view of it.
        raw = sorted(rec.get("parties", []),
                     key=lambda p: -len(p["members"]))
        clusters = []
        for p in raw:
            names = {m["name"] for m in p["members"]}
            for c in clusters:
                inter = len(names & c["names"])
                if inter and inter / min(len(names), len(c["names"])) > 0.5:
                    c["events"] += p.get("seen_in_events", 1)
                    break
            else:
                clusters.append({"names": names, "party": p,
                                 "events": p.get("seen_in_events", 1)})
        # PARTY INDEX (pipeline/party_link.py): each cluster's
        # ordinal in this battle, stamped on the party record AND on every
        # member's build (`party`) so a build links to its party exactly —
        # the (battle, weapon) fallback in party_link is for artifacts
        # harvested before this field existed. A name seen in several
        # clusters keeps the largest (clusters are size-descending, the
        # same rule size_by_name uses).
        party_of_name = {}
        for idx, c in enumerate(clusters):
            for nm in c["names"]:
                if nm and nm not in party_of_name:
                    party_of_name[nm] = idx
        battle_party_index[rec["battle"]] = party_of_name
        # PARTY OUTCOME (the outcome layer): the official battle roster
        # carries every player's kills and deaths; a party's record is the
        # sum over its members who were in this fight. Members listed by
        # GroupMembers but absent from the roster fought elsewhere and add
        # nothing. A cache record with no roster yields None — unknown,
        # never zero. EVIDENCE ONLY: pipeline/audit_capability_outcomes.py
        # reads it report-only; nothing here is a scoring input.
        kd_by_name = {r["name"]: r for r in (rec.get("roster") or [])
                      if r.get("name")}
        for idx, c in enumerate(clusters):
            p = c["party"]
            ws = [m["weapon"] for m in p["members"] if m["weapon"]]
            here = [kd_by_name[m["name"]] for m in p["members"]
                    if m.get("name") in kd_by_name]
            parties.append({
                "battle": rec["battle"],
                "index": idx,
                "content": (content_tag(p.get("kill_areas"), rec.get("content_marks"))
                            if p.get("kill_areas") else content),
                "size": len(p["members"]),
                "known_weapons": len(ws),
                "weapons": sorted(ws),
                "guilds": sorted({m["guild"] for m in p["members"]
                                  if m["guild"]}),
                "seen_in_events": c["events"],
                "in_fight": len(here) if kd_by_name else None,
                "kills": (sum(r.get("kills") or 0 for r in here)
                          if kd_by_name else None),
                "deaths": (sum(r.get("deaths") or 0 for r in here)
                           if kd_by_name else None)})
    # OBSERVED BUILDS — full kits, and the weapon -> armour-class evidence
    # that role assignment can actually be tested against. Armour class is
    # a strong role tell (curation judgment: cloth wearing is a reliable
    # indicator), and unlike the hand-curated role menus it is measurable.
    strip = lambda t: (re.sub(r"^T\d+_", "", str(t).split("@")[0])
                       if t else None)
    def armour_class(t):
        k = (strip(t) or "").upper()
        for cls in ("CLOTH", "LEATHER", "PLATE"):
            if f"ARMOR_{cls}" in k:
                return cls.lower()
        return None
    builds, by_weapon = [], {}
    for name in cache_names:
        if name in unreadable:
            continue
        rec = read_json(os.path.join(CACHE, name))
        if not rec:
            continue
        # PARTY SIZE per build (the Grailseeker case): the
        # battle floor admits 2-8 man gank parties fighting inside a
        # 20+ battle, and their kits (Hunter Shoes, Demon Cape, Poison
        # Potion) were being mined as ZvZ doctrine. The party the killer
        # belonged to is the real evidence unit; a build inherits the
        # size of the largest deduped party carrying its player name in
        # this battle. Victims are in no party record -> None (honest:
        # unknown, never guessed).
        rec_content = content_tag(rec.get("kill_areas"), rec.get("content_marks"))
        size_by_name = {}
        for p in rec.get("parties", []):
            n_members = len(p.get("members") or [])
            for m in p.get("members") or []:
                nm = m.get("name")
                if nm:
                    size_by_name[nm] = max(size_by_name.get(nm, 0),
                                           n_members)
        for bd in rec.get("builds", []):
            g = bd.get("gear") or {}
            w = strip(g.get("MainHand"))
            if not w or w not in known:
                continue
            ac = armour_class(g.get("Armor"))
            # PLAYER KEY (distinct-player floors): a build is
            # one player in one battle, and a third of a weapon's builds
            # are repeat sightings of the same people (median 0.67
            # distinct players per build; Heavy Crossbow: one player in 7
            # of 20). Doctrine counts one player, one vote per weapon, so
            # every build carries a stable, non-reversible player key —
            # the name itself never leaves the cache.
            nm = bd.get("name")
            builds.append({
                "battle": rec["battle"], "weapon": w,
                "content": (content_tag({bd["kill_area"]: 1}, rec.get("content_marks"))
                            if bd.get("kill_area") else rec_content),
                "armour_class": ac,
                "item_power": bd.get("item_power"),
                "seen_as": bd.get("seen_as"),
                "party_size": size_by_name.get(nm),
                "party": battle_party_index.get(rec["battle"], {}).get(nm),
                "player": (hashlib.sha1(nm.encode("utf-8")).hexdigest()[:12]
                           if nm else None),
                "slots_filled": bd.get("slots_filled"),
                "gear": {s: strip(v) for s, v in g.items() if v}})
            e = by_weapon.setdefault(w, {"n": 0, "cloth": 0, "leather": 0,
                                         "plate": 0, "ip_sum": 0.0,
                                         "ip_n": 0})
            e["n"] += 1
            if ac:
                e[ac] += 1
            if bd.get("item_power"):
                e["ip_sum"] += bd["item_power"]
                e["ip_n"] += 1
    for w, e in by_weapon.items():
        seen_ac = e["cloth"] + e["leather"] + e["plate"]
        e["armour_majority"] = (max(("cloth", "leather", "plate"),
                                    key=lambda c: e[c]) if seen_ac else None)
        e["armour_majority_share"] = (round(max(e["cloth"], e["leather"],
                                                e["plate"]) / seen_ac, 3)
                                      if seen_ac else None)
        e["mean_item_power"] = (round(e["ip_sum"] / e["ip_n"], 1)
                                if e["ip_n"] else None)
        e.pop("ip_sum", None)

    out = {
        "kind": "party_rosters",
        "builds": sorted(builds, key=lambda b: (b["weapon"], b["battle"])),
        "weapon_armour": dict(sorted(by_weapon.items())),
        "semantics": (
            "GroupMembers from official gameinfo kill events: the KILLER'S "
            "PARTY at kill time, deduplicated per battle by member OVERLAP "
            "(>50% of the smaller set) so one squad shedding members as they "
            "die is not counted several times. INCLUSION FILTER: the party "
            "scored at least one kill — measured 2026-08-29, not assumed: "
            "61% of captured parties are dominant, 19% traded even, 20% took "
            "more deaths than kills, so losing parties ARE represented; the "
            "10% of players in no captured party hold 34 kills against 475 "
            "deaths between them. Rule (2026-08-29): a party that could "
            "not get a single kill is not worth recording. Coverage 90% of "
            "players across sampled battles. A party is NOT a comp: a large "
            "battle is a coalition of parties. Prevalence is not "
            "effectiveness. DISPLAY/EVIDENCE ONLY, never a scoring input."),
        "battles": sorted(battles, key=lambda b: -(b["total_players"] or 0)),
        "parties": sorted(parties, key=lambda p: -p["size"]),
        "summary": {
            "battles": len(battles),
            "battles_by_content": dict(collections.Counter(
                b["content"] for b in battles)),
            "parties_by_content": dict(collections.Counter(
                p["content"] for p in parties)),
            "parties": len(parties),
            "parties_5plus": sum(1 for p in parties if p["size"] >= 5),
            "parties_full_gear": sum(1 for p in parties
                                     if p["size"] and
                                     p["known_weapons"] == p["size"]),
            "builds": len(builds),
            "builds_full_kit": sum(1 for b in builds
                                   if (b["slots_filled"] or 0) >= 6),
            "weapons_with_armour_evidence": sum(
                1 for e in by_weapon.values() if e["armour_majority"]),
            "median_coverage": (lambda xs: xs[len(xs) // 2] if xs else None)(
                sorted(b["coverage"] for b in battles if b["coverage"] is not None)),
            "unreadable_cache_files": len(unreadable),
        },
    }
    path = rosters_io.path(OUT)
    rosters_io.dump(out, path)      # gzipped, deterministic
    s = out["summary"]
    print(f"\n{s['battles']} battles, {s['parties']} distinct parties "
          f"({s['parties_5plus']} of size 5+, {s['parties_full_gear']} with "
          f"every member's weapon known)")
    print(f"median per-battle gear coverage: {s['median_coverage']}")
    print(f"{s['builds']} observed BUILDS ({s['builds_full_kit']} with 6+ "
          f"equipment slots), armour evidence on "
          f"{s['weapons_with_armour_evidence']} weapons")
    if unreadable:
        print(f"WARNING: {len(unreadable)} cache file(s) unreadable and skipped: "
              + ", ".join(unreadable[:5]))
    print(f"wrote out/{rosters_io.NAME}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=25)
    ap.add_argument("--min-players", type=int, default=25)
    ap.add_argument("--max-players", type=int, default=0,
                    help="skip listed fights above this totalPlayers "
                         "(0 = no ceiling); --min-players 10 --max-players "
                         "14 is the 5v5 / 7v7 band")
    ap.add_argument("--max-events", type=int, default=120,
                    help="cap per battle; a 300-man fight has ~180 kills")
    ap.add_argument("--server", default="us", choices=["us", "eu", "asia"])
    ap.add_argument("--workers", type=int, default=4,
                    help="battles fetched side by side (1 = sequential); "
                         "the pass reports its event coverage")
    ap.add_argument("--pages", type=int, default=None,
                    help="0 = offline re-analysis, no network; N > 0 = "
                         "discovery page cap (default 40, 20 battles each)")
    ap.add_argument("--poll-events", action="store_true",
                    help="kill-feed poll: the newest events grouped by "
                         "battle into the cache; no battle list, no "
                         "artifact rewrite (add --analyze to re-derive)")
    ap.add_argument("--poll-depth", type=int, default=1020,
                    help="events to read per poll, newest first (51 per "
                         "page; the feed exposes about 1,000)")
    ap.add_argument("--analyze", action="store_true",
                    help="with --poll-events: also rewrite the artifact")
    ap.add_argument("--remark", action="store_true",
                    help="network: re-fetch the events of battle-list records "
                         "that predate the content marker and rewrite them "
                         "with marks (a one-off after a marker lands)")
    ap.add_argument("--remark-min-players", type=int, default=0,
                    help="with --remark: only records of this many listed "
                         "players or more")
    ap.add_argument("--remark-max-players", type=int, default=0,
                    help="with --remark: only records of this many listed "
                         "players or fewer (0 = no ceiling); 8-14 is the "
                         "5v5 / 7v7 portal band")
    ap.add_argument("--retag", action="store_true",
                    help="offline: rebuild every kill-feed record's tallies "
                         "from its stored events (a new marker reaching "
                         "records already collected); no artifact rewrite")
    args = ap.parse_args()
    if args.max_players and args.max_players < args.min_players:
        sys.exit("--max-players must be >= --min-players")

    ds = os.path.join(OUT, "dataset-latest.json")
    with open(ds, encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])

    if args.retag:
        retag(known)
        return
    if args.remark:
        remark(args, known)
        return
    if args.poll_events:
        poll_events(args, known)
        if args.analyze:
            analyze(known)
        return
    if args.pages != 0:
        fetch(args, known)
    analyze(known)


if __name__ == "__main__":
    main()
