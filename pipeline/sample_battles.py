#!/usr/bin/env python3
"""
Sample recent battles and count which weapons real players actually brought,
bucketed by FIGHT size (VALIDATION V7; semantics fixed per changeschapter2.md
§E).

Source: the albionbb API (api.albionbb.com) — the same community killboard
the original V2 spike used. The official gameinfo events endpoint 504s too
often to sample at scale (verified 2026-08-13); albionbb serves the same
kill-event data reliably. Weapons come from kill events (killer + victim),
so coverage is combatants, not lurkers.

WHAT THIS DATA IS — AND IS NOT (§E). A battle's `totalPlayers` is the TOTAL
FIGHT SIZE. It is NOT a party size: parties, side sizes and actual roster
splits are not in the kill feed. These dimensions stay distinct here:

  fight size          totalPlayers — the only size the killboard states
  observed roster     players we saw in kill events — a LOWER BOUND
  side size           unknown (not reconstructed; alliances overlap)
  actual party size   unknown — never inferred from any of the above

So the output is FIGHT-SIZE EQUIPMENT PREVALENCE: "share of observed
combatants fielding X in fights of roughly this size". It is never party-size
evidence, never a build recommendation, and selected abilities are UNKNOWN
(kill events carry equipment only — stored as such, never inferred).
Prevalence is not effectiveness: no win/loss dimension exists here at all.
Display evidence only: nothing here feeds the scoring engine until
validation says it may (design doc §8, Phase 3).

    /us/battles?minPlayers=N&page=P      20 battles per page, recent first
    /us/battles/kills?ids=<battleId>     kill events with Equipment.MainHand
        │
        ▼
    out/battles_cache/<id>.json          per-battle RAW observation cache
    out/weapon_usage_v2.json             {buckets, buckets_battles, meta,
                                          battles, coverage}

Loadout swaps are tracked: a player seen on two weapons counts once for
EACH weapon (players_attributed counts player-weapon pairs), and
`buckets_battles` aggregates at BATTLE level — in how many distinct fights a
weapon appeared — because the players of one battle are correlated, not
independent samples. Battles and events are deduplicated by id.

MainHand Type "T5_2H_SHAPESHIFTER_MORGANA@4" -> catalog key
"2H_SHAPESHIFTER_MORGANA". Unknown keys are tallied for the coverage stat.

OBSERVED ORGANIZATION COHORTS (2026-08-22, from PR #5). For display-only
co-occurrence evidence, actors are ADDITIONALLY grouped when the kill feed
itself states the same AllianceId/AllianceName (preferred) or GuildId/
GuildName. These are organization cohorts, NOT parties and NOT
authoritative sides: pair/partial-roster statistics may say "these weapons
were observed together among members of the same named organization in one
fight" — never that the players were in one party, that the organization
won, or that the pairing caused anything. Unguilded/anonymous or
ambiguous-identity players are excluded rather than guessed; a cohort
needs >=2 observed players and >=2 distinct known weapons. All §E limits
above still hold, and nothing here feeds scoring.

Usage:  py -3 pipeline/sample_battles.py [--battles 200] [--min-players 6]
                                         [--server us]
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "battles_cache")
UA = {"User-Agent": "albion-comp-engine usage sample (github.com/SODIYAL/albion-comp-engine)"}
SLEEP = 0.5
TIER_RE = re.compile(r"^T\d+_")

# fight-size buckets (players in the WHOLE battle, both sides)
def bucket_of(n):
    return "small" if n < 12 else "mid" if n <= 30 else "large"


def get_json(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            code = getattr(e, "code", None)
            if attempt == tries - 1:
                raise
            time.sleep(10 if code == 429 else 3 * (attempt + 1))
    return None


def weapon_key(mh):
    """Prefer the pre-normalized Name; fall back to stripping the Type."""
    if not mh:
        return None
    name = mh.get("Name")
    if name:
        return TIER_RE.sub("", name.split("@")[0])
    t = mh.get("Type")
    return TIER_RE.sub("", t.split("@")[0]) if t else None


def cohort_key(actor):
    """Organization identity as STATED by the feed; never infer a party or
    a side. Alliance preferred (guilds change alliances mid-season; the
    fight-time label is what the feed observed)."""
    if not actor:
        return None
    aid = actor.get("AllianceId") or actor.get("AllianceName")
    if aid:
        return "alliance:" + str(aid)
    gid = actor.get("GuildId") or actor.get("GuildName")
    if gid:
        return "guild:" + str(gid)
    return None


def battle_kills(api, battle_id):
    path = os.path.join(CACHE, f"{battle_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    events = get_json(f"{api}/battles/kills?ids={battle_id}") or []
    time.sleep(SLEEP)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f)
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=200)
    ap.add_argument("--min-players", type=int, default=6)
    ap.add_argument("--server", default="us", choices=["us", "eu", "asia"])
    ap.add_argument("--no-topup", action="store_true",
                    help="skip the large-bucket top-up sweep (e.g. when the API is throttling)")
    args = ap.parse_args()
    api = f"https://api.albionbb.com/{args.server}"

    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    os.makedirs(CACHE, exist_ok=True)

    buckets = {b: {} for b in ("small", "mid", "large")}
    battles_with = {b: {} for b in buckets}          # battle-level aggregation
    meta = {b: {"battles": 0, "players_attributed": 0} for b in buckets}
    cohorts = {b: [] for b in buckets}               # org co-occurrence (PR #5)
    cohort_meta = {b: {"cohorts": 0, "players_observed": 0} for b in buckets}
    battles_index = []
    unknown, no_weapon, sampled, swaps = {}, 0, 0, 0
    seen_battles, seen_events = set(), set()

    def ingest(bid, fight_size, start_time):
        nonlocal sampled, no_weapon, swaps
        try:
            events = battle_kills(api, bid)
        except Exception as e:  # noqa: BLE001
            print(f"  battle {bid} kills failed: {e}")
            return
        # per player, EVERY weapon they were seen on — a swap counts for each
        # kit fielded, instead of whichever sighting arrived first (§E) —
        # plus the organization labels the feed itself stated for them
        per_player = {}
        for ev in events:
            eid = ev.get("EventId") or ev.get("Id")
            if eid is not None:
                if eid in seen_events:
                    continue              # event dedup across battle overlaps
                seen_events.add(eid)
            for a in (ev.get("Killer"), ev.get("Victim")):
                if not a or a.get("Id") is None:
                    continue
                rec = per_player.setdefault(
                    a.get("Id"), {"weapons": set(), "cohorts": set()})
                rec["weapons"].add(
                    weapon_key((a.get("Equipment") or {}).get("MainHand")))
                ck = cohort_key(a)
                if ck:
                    rec["cohorts"].add(ck)
        bucket = bucket_of(fight_size)
        attributed = 0
        weapons_here = set()
        for rec in per_player.values():
            kits = rec["weapons"]
            kits.discard(None)
            if not kits:
                no_weapon += 1
                continue
            if len(kits) > 1:
                swaps += 1
            for wk in kits:
                if wk in known:
                    buckets[bucket][wk] = buckets[bucket].get(wk, 0) + 1
                    weapons_here.add(wk)
                    attributed += 1
                else:
                    unknown[wk] = unknown.get(wk, 0) + 1
        for wk in weapons_here:
            battles_with[bucket][wk] = battles_with[bucket].get(wk, 0) + 1
        # Organization cohorts (PR #5): the safest same-group proxy the kill
        # feed offers. A player whose organization label was ambiguous
        # across observations is EXCLUDED rather than assigned to one.
        org = {}
        for rec in per_player.values():
            valid = {w for w in rec["weapons"] if w in known}
            if not valid or len(rec["cohorts"]) != 1:
                continue
            ck = next(iter(rec["cohorts"]))
            g = org.setdefault(ck, {"players": 0, "weapons": set()})
            g["players"] += 1
            g["weapons"].update(valid)
        for ck, g in sorted(org.items()):
            if g["players"] < 2 or len(g["weapons"]) < 2:
                continue
            cohorts[bucket].append({
                "battle_id": bid,
                "cohort": ck,
                "observed_players": g["players"],
                "weapons": sorted(g["weapons"]),
            })
            cohort_meta[bucket]["cohorts"] += 1
            cohort_meta[bucket]["players_observed"] += g["players"]
        meta[bucket]["battles"] += 1
        meta[bucket]["players_attributed"] += attributed
        battles_index.append({
            "battle_id": bid, "server": args.server,
            "fight_size": fight_size,            # totalPlayers — fight, not party
            "observed_roster": len(per_player),  # lower bound, combatants only
            "party_size": None,                  # unknown — never inferred (§E)
            "side_size": None,                   # unknown — not reconstructed
            "start_time": start_time,
            "attributed": attributed,
            "organization_cohorts": len(org),    # stated-identity groups only
        })
        sampled += 1
        if sampled % 20 == 0:
            print(f"  {sampled} battles "
                  f"(small {meta['small']['battles']} / mid {meta['mid']['battles']} "
                  f"/ large {meta['large']['battles']})", flush=True)

    def sweep(min_players, want, page_cap):
        page = 1
        start = sampled
        while sampled - start < want and page <= page_cap:
            try:
                listing = get_json(f"{api}/battles?minPlayers={min_players}&page={page}")
            except Exception as e:  # noqa: BLE001
                print(f"  battle list page {page} failed: {e}")
                break
            time.sleep(SLEEP)
            page += 1
            if not listing:
                break
            for b in listing:
                if sampled - start >= want:
                    break
                bid, n_players = b.get("albionId"), b.get("totalPlayers", 0)
                if not bid or bid in seen_battles:
                    continue                     # battle dedup
                seen_battles.add(bid)
                ingest(bid, n_players, b.get("startTime"))

    # phase 1: the general sweep; phase 2: top up the large bucket, which
    # recent-battle listings underrepresent (big fights are rare)
    sweep(args.min_players, args.battles, 60)
    if not args.no_topup and meta["large"]["battles"] < 40:
        print("  topping up the large bucket (minPlayers=31)...", flush=True)
        sweep(31, 40 - meta["large"]["battles"], 20)

    total_attr = sum(m["players_attributed"] for m in meta.values())
    total_unknown = sum(unknown.values())
    coverage = total_attr / max(1, total_attr + no_weapon + total_unknown)
    out = {
        "semantics": ("FIGHT-SIZE EQUIPMENT PREVALENCE plus OBSERVED "
                      "ORGANIZATION COHORTS. Buckets are total fight size "
                      "(both sides). Party size, side size and selected "
                      "abilities are UNKNOWN — kill events carry equipment "
                      "only. Cohorts group actors ONLY by the Alliance/Guild "
                      "identity the feed itself states; they are NOT parties "
                      "or authoritative sides. Prevalence is not "
                      "effectiveness; no win/loss dimension exists here. "
                      "Display evidence only; never feeds scoring."),
        "sampling_frame": {"axis": "fight_size",
                           "buckets": {"small": "<12", "mid": "12-30",
                                       "large": ">30"},
                           "source": "albionbb kill events (killer+victim)",
                           "coverage_is": "combatants, not lurkers"},
        "cohort_semantics": ("Same stated AllianceId/AllianceName, else "
                             "GuildId/GuildName, within ONE battle; players "
                             "with ambiguous identity excluded; minimum 2 "
                             "observed players and 2 distinct known weapons. "
                             "An organization-level co-occurrence proxy — "
                             "never party reconstruction."),
        "abilities": "unknown",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "server": args.server, "battles_sampled": sampled,
        "buckets": buckets,                  # player-weapon pairs per bucket
        "buckets_battles": battles_with,     # distinct fights containing the
                                             # weapon — battle-level confidence
        "meta": meta,
        "cohorts": cohorts,                  # org co-occurrence baskets (PR #5)
        "cohort_meta": cohort_meta,
        "battles": battles_index,            # raw per-battle observation index
        "players_with_swaps": swaps,
        "coverage": round(coverage, 3),
        "unknown_keys_top": dict(sorted(unknown.items(), key=lambda kv: -kv[1])[:20]),
    }
    with open(os.path.join(OUT, "weapon_usage_v2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"sampled {sampled} battles; weapon attribution {coverage:.0%} "
          f"({total_attr} player-weapon pairs, {swaps} players swapped kits, "
          f"{total_unknown} unknown key, {no_weapon} no weapon)")
    print("wrote out/weapon_usage_v2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
