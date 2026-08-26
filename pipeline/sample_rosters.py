#!/usr/bin/env python3
"""
Sample kill-dense battles and mine NEAR-COMPLETE fight rosters — the
evidence layer behind the need profiles (increment 3, owner directive
2026-08-26: "what matters is what the data says").

Source: the albionbb API (api.albionbb.com), the project's sanctioned
battle endpoint (see sample_battles.py). EXPLICIT network step — never
part of a normal build or CI. Analysis is deterministic over the cache:
`--pages 0` re-analyzes without touching the network.

Method (and its honest biases, all recorded in the output):
  - kill events attribute a weapon only to players who appear as killer
    or victim, so a WIPED side (deaths >= 80% of its attributed players)
    is the least-biased roster snapshot — the whole roster is visible.
    Winner-side mixes under-count healers/supports (they rarely appear)
    and are reported separately, never merged.
  - sides are alliance-level (guild fallback): two parties of one
    alliance can merge into a 21-40 row, which the band split discards.
  - battlemount carriers show their carried weapon (the standing
    killboard mount-carrier caveat).
DISPLAY/EVIDENCE ONLY: nothing in the scoring path reads this artifact;
the need profiles it informed are owner-ruled constants in roles.yaml.

Usage:  py -3 pipeline/sample_rosters.py [--pages 60] [--server us]
        py -3 pipeline/sample_rosters.py --pages 0     (offline re-analysis)
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "roster_cache")
UA = {"User-Agent": "albion-comp-engine usage sample "
      "(github.com/SODIYAL/albion-comp-engine)"}

sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402

FUNC = ("pierce", "anti_heal", "purge", "shield_break")
HEAL_SEATS = ("main_healer", "brawl_healer", "kite_healer",
              "unseated_healer")
BANDS = (("gang", 5, 9), ("mid", 10, 14), ("party", 15, 25))


def get_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError,
                TimeoutError, OSError):
            if i == tries - 1:
                raise
            time.sleep(2.0 * (i + 1))


def fetch(api, pages):
    os.makedirs(CACHE, exist_ok=True)
    fetched = 0
    for page in range(1, pages + 1):
        listing = get_json(f"{api}/battles?minPlayers=40&page={page}") or []
        time.sleep(0.45)
        for b in listing:
            if b["totalKills"] < 0.6 * b["totalPlayers"] \
                    or b["totalPlayers"] > 120:
                continue
            path = os.path.join(CACHE, f"{b['albionId']}.json")
            if os.path.exists(path):
                continue
            ev = get_json(f"{api}/battles/kills?ids={b['albionId']}") or []
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(ev, f)
            fetched += 1
            time.sleep(0.45)
        print(f"  page {page}: cache {len(os.listdir(CACHE))} battles",
              flush=True)
    print(f"fetched {fetched} new battles -> out/roster_cache")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=60,
                    help="listing pages to sweep (0 = offline re-analysis)")
    ap.add_argument("--server", default="us")
    args = ap.parse_args()
    if args.pages > 0:
        fetch(f"https://api.albionbb.com/{args.server}", args.pages)
    if not os.path.isdir(CACHE) or not os.listdir(CACHE):
        sys.exit("no cache — run with --pages N first")

    with open(os.path.join(OUT, "dataset-latest.json"),
              encoding="utf-8") as f:
        ds = json.load(f)
    weapons = ds["weapons"]

    def weapon_key(t):
        if not t:
            return None
        k = t.split("@")[0]
        if "_" in k and k.split("_")[0].startswith("T"):
            k = k.split("_", 1)[1]
        return k if k in weapons else None

    def seats_of(wk):
        w = weapons.get(wk) or {}
        menu = w.get("role_menu") or []
        sec = w.get("role_menu_secondary") or []
        primary = menu[0] if menu else \
            "unseated_" + (w.get("role_hint") or "?")
        return primary, {s for s in menu + sec if s in FUNC}

    sides, newest = [], ""
    for name in sorted(os.listdir(CACHE)):
        with open(os.path.join(CACHE, name), encoding="utf-8") as f:
            ev = json.load(f)
        players = {}
        for e in ev:
            newest = max(newest, e.get("TimeStamp") or "")
            for side, is_k in (("Killer", True), ("Victim", False)):
                p = e.get(side) or {}
                nm, wk = p.get("Name"), weapon_key(
                    ((p.get("Equipment") or {})
                     .get("MainHand") or {}).get("Type"))
                if not nm or not wk:
                    continue
                grp = p.get("AllianceName") or p.get("GuildName") or "?"
                rec = players.setdefault(nm, [grp, wk, 0, 0])
                rec[2 if is_k else 3] += 1
        by_side = {}
        for nm, (grp, wk, k, d) in players.items():
            by_side.setdefault(grp, []).append((wk, k, d))
        for grp, ms in by_side.items():
            sides.append({
                "battle": int(name.split(".")[0]),
                "n": len(ms),
                "kills": sum(k for _w, k, _d in ms),
                "deaths_seen": sum(1 for _w, _k, d in ms if d),
                "weapons": sorted(w for w, _k, _d in ms)})

    def analyze(rows):
        agg, tot = {}, 0
        cover = {f: 0 for f in FUNC}
        healers = {}
        mixes = []
        for r in rows:
            funcs_here, heal, mix = set(), 0, {}
            for wk in r["weapons"]:
                s, fs = seats_of(wk)
                agg[s] = agg.get(s, 0) + 1
                mix[s] = mix.get(s, 0) + 1
                funcs_here |= fs
                if s in HEAL_SEATS:
                    heal += 1
            tot += r["n"]
            for f in funcs_here:
                cover[f] += 1
            h20 = round(20 * heal / r["n"])
            healers[str(h20)] = healers.get(str(h20), 0) + 1
            mixes.append({"battle": r["battle"], "n": r["n"],
                          "mix": dict(sorted(mix.items()))})
        if not rows:
            return {"rosters": 0}
        return {"rosters": len(rows), "players": tot,
                "per20": {s: round(20 * c / tot, 2)
                          for s, c in sorted(agg.items())},
                "function_coverage": {f: round(c / len(rows), 2)
                                      for f, c in sorted(cover.items())},
                "healers_per20_hist": dict(sorted(healers.items())),
                "rows": mixes}

    result = {"_meta": {
        "source": "api.albionbb.com kill events (sanctioned endpoint)",
        "battles_cached": len(os.listdir(CACHE)),
        "newest_event": newest,
        "note": ("near-complete = deaths seen for >= 80% of the side's "
                 "attributed players (wiped sides — least-biased roster "
                 "snapshots); winners reported separately, never merged "
                 "(healers/supports under-attribute on winning sides); "
                 "sides are alliance-level; mount carriers show carried "
                 "weapons. DISPLAY/EVIDENCE ONLY — the need profiles it "
                 "informed are owner-ruled constants in roles.yaml.")}}
    for band, lo, hi in BANDS:
        rows = [r for r in sides if lo <= r["n"] <= hi
                and r["deaths_seen"] >= 0.8 * r["n"]]
        result[f"{band}_near_complete"] = analyze(rows)
    result["party_winners_biased"] = analyze(
        [r for r in sides if 15 <= r["n"] <= 25
         and r["kills"] > 2 * r["deaths_seen"]])

    jsonfmt.dump(result, os.path.join(OUT, "roster_mixes.json"))
    pc = result["party_near_complete"]
    print(f"rosters: party {pc.get('rosters', 0)} / "
          f"mid {result['mid_near_complete'].get('rosters', 0)} / "
          f"gang {result['gang_near_complete'].get('rosters', 0)}"
          f"  -> out/roster_mixes.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
