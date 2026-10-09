#!/usr/bin/env python3
"""
Fight-size equipment prevalence and killer-party cohorts, derived from the
full killer-party artifact (out/party_rosters_full.json.gz, every
population, local: the committed artifact keeps the battle list and the
Dragon Portal alone, rosters_io). Offline and deterministic: the same
artifact writes the same bytes. A fold step (pipeline/fold_harvest.ps1),
never part of a build; it fails closed when the full artifact is missing
(sample_parties.py --pages 0 writes it).

The artifact it writes, out/weapon_usage_v2.json, is the observed-evidence
layer behind the planner's killboard strip and the recurring observed
cores (build_cohort_families.py). DISPLAY EVIDENCE ONLY: nothing here
feeds scoring, a suggestion pool or the forge. Prevalence is not
effectiveness; no win/loss dimension is read.

THE SAMPLING FRAME. Every harvested battle (the battle-list harvest and
the kill-feed poll alike) with

  total players >= MIN_PLAYERS     group fights only; a duel or a 2v2 is
                                   a battle of 2-4 and never enters
  a start inside WINDOW_DAYS       counted back from the NEWEST battle in
                                   the artifact, never from the clock, so
                                   a rebuild is byte-identical

A kill-feed record's total is its roster rebuilt from the events, a lower
bound of the fight; a battle-list record's is the killboard's own count.

TWO AXES, KEPT APART.

  prevalence   by FIGHT size (total players, both sides): the share of
               observed combatants fielding a weapon. A combatant is a
               player with a build in the artifact: a killer, a victim or
               a participant of a kill event, one build per player per
               battle (the fullest sighting), so a loadout swap inside a
               battle is not observable and is stored as unknown.
  cohorts      by PARTY size: a cohort is one killer party, the group the
               kill event itself lists (GroupMembers, deduplicated per
               battle by member overlap in sample_parties.py). A party of
               N keys to the bucket a fight of 2N falls in, the mapping
               the engine's size_bucket and the page's usageBucket apply,
               so a 20-man plan reads parties of 16-20 and never a
               five-man squad inside a large fight.

Side size stays unknown: nothing reconstructs it. Selected abilities stay
unknown: kill events carry equipment only.

THE COHORT SAMPLE. The window holds far more parties than a page can
embed (measured on the artifact this derivation was written against:
65,808 / 46,335 / 12,266 parties of 2-5 / 6-15 / 16-20 in 28 days), so
each bucket keeps COHORT_SAMPLE parties spread evenly over the window in
(start, battle, party index) order: every k-th party, not the newest
ones, which would be one evening of a few guilds. `cohort_meta` states
both the parties in the window and the parties kept. A cohort needs two
members and two distinct catalogue weapons. A squad that fights several
battles is several cohorts; the distinct-organization gate in
build_cohort_families.py is what keeps one squad from being a family.

A killer party scored at least one kill (the harvest's inclusion rule),
so cohorts lean to the winning side; the copy on the page says "killer
parties", never "winning comps".

Run:  py -3 pipeline/derive_usage.py [path/to/party_rosters_full.json.gz]
"""
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsonfmt  # noqa: E402
import rosters_io  # noqa: E402

OUT = os.path.join(HERE, "out")
DATASET = os.path.join(OUT, "dataset-latest.json")
USAGE = os.path.join(OUT, "weapon_usage_v2.json")

MIN_PLAYERS = 6       # the group-fight floor (total players, both sides)
WINDOW_DAYS = 28      # counted back from the newest battle in the artifact
COHORT_SAMPLE = 1000  # killer parties kept per party-size bucket
BUCKETS = ("small", "mid", "large")
STAMP = "%Y-%m-%dT%H:%M:%S"


def bucket_of(n):
    """Fight-size bucket (players in the whole battle, both sides)."""
    return "small" if n < 12 else "mid" if n <= 30 else "large"


def party_bucket(size):
    """A party of N keys to the bucket a fight of 2N falls in."""
    return bucket_of(2 * size)


def stamp_of(battle):
    """A battle's start to the second, or None. The killboard's start for
    a battle-list record, the first kill event for a kill-feed record."""
    s = battle.get("started_at") or battle.get("first_event_at")
    return s[:19] if s else None


def even_sample(rows, k):
    """k rows spread evenly over an ordered list; all of it when shorter."""
    n = len(rows)
    if n <= k:
        return list(rows)
    return [rows[(i * n) // k] for i in range(k)]


def derive(doc, known):
    """The usage artifact from a loaded killer-party artifact (every
    population) and the catalogue's weapon keys. Pure: no clock, no I/O."""
    stamps = {b["battle"]: stamp_of(b) for b in doc.get("battles") or []}
    dated = [s for s in stamps.values() if s]
    if not dated:
        raise ValueError("no dated battle in the artifact")
    newest = max(dated)
    start = (datetime.strptime(newest, STAMP)
             - timedelta(days=WINDOW_DAYS)).strftime(STAMP)
    frame = {}
    for b in doc.get("battles") or []:
        s = stamps[b["battle"]]
        total = b.get("total_players") or 0
        if s and s >= start and total >= MIN_PLAYERS:
            frame[b["battle"]] = (bucket_of(total), s)

    buckets = {k: {} for k in BUCKETS}
    in_battles = {k: {} for k in BUCKETS}
    meta = {k: {"battles": 0, "players_attributed": 0} for k in BUCKETS}
    for bucket, _s in frame.values():
        meta[bucket]["battles"] += 1
    seen_pairs = set()
    for bd in doc.get("builds") or []:
        hit = frame.get(bd.get("battle"))
        w = bd.get("weapon")
        if not hit or w not in known:
            continue
        bucket = hit[0]
        buckets[bucket][w] = buckets[bucket].get(w, 0) + 1
        meta[bucket]["players_attributed"] += 1
        pair = (bd["battle"], w)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            in_battles[bucket][w] = in_battles[bucket].get(w, 0) + 1

    pools = {k: [] for k in BUCKETS}
    for p in doc.get("parties") or []:
        hit = frame.get(p.get("battle"))
        size = p.get("size") or 0
        if not hit or size < 2:
            continue
        ws = sorted({w for w in p.get("weapons") or [] if w in known})
        if len(ws) < 2:
            continue
        pools[party_bucket(size)].append(
            (hit[1], p["battle"], p.get("index") or 0,
             {"battle_id": p["battle"], "party": p.get("index") or 0,
              "size": size, "guilds": sorted(p.get("guilds") or []),
              "weapons": ws}))
    cohorts, cohort_meta = {}, {}
    for bucket in BUCKETS:
        rows = sorted(pools[bucket], key=lambda r: r[:3])
        kept = [r[3] for r in even_sample(rows, COHORT_SAMPLE)]
        cohorts[bucket] = kept
        cohort_meta[bucket] = {
            "cohorts": len(kept),
            "parties_in_window": len(rows),
            "players_observed": sum(c["size"] for c in kept)}

    return {
        "semantics": (
            "FIGHT-SIZE EQUIPMENT PREVALENCE plus KILLER-PARTY COHORTS, "
            "derived from the killer-party harvest. Prevalence buckets are "
            "total fight size (both sides) over observed combatants. A "
            "cohort is one killer party as the kill event lists it, "
            "bucketed by party size. Side size and selected abilities are "
            "UNKNOWN. Prevalence is not effectiveness; no win/loss "
            "dimension is read. Display evidence only; never feeds "
            "scoring."),
        "source": "out/party_rosters_full.json.gz (every population; local, never committed)",
        "window": {"days": WINDOW_DAYS, "from": start, "to": newest,
                   "anchored_on": "the newest battle in the artifact"},
        "sampling_frame": {
            "axis": "fight_size", "min_players": MIN_PLAYERS,
            "buckets": {"small": "<12", "mid": "12-30", "large": ">30"},
            "coverage_is": ("combatants with a build: killers, victims "
                            "and kill participants, one build per player "
                            "per battle")},
        "cohort_frame": {
            "axis": "party_size", "unit": "killer party",
            "buckets": {"small": "2-5", "mid": "6-15", "large": "16+"},
            "sample": ("at most %d parties per bucket, spread evenly over "
                       "the window" % COHORT_SAMPLE),
            "minimum": "2 members and 2 distinct catalogue weapons"},
        "side_size": "unknown",
        "abilities": "unknown",
        "loadout_swaps": "unknown",
        "battles_sampled": len(frame),
        "buckets": buckets,              # player-weapon pairs per bucket
        "buckets_battles": in_battles,   # distinct fights carrying the weapon
        "meta": meta,
        "cohorts": cohorts,
        "cohort_meta": cohort_meta,
    }


def main():
    import json
    src = sys.argv[1] if len(sys.argv) > 1 else rosters_io.full_path()
    if not os.path.exists(src):
        print(f"FAIL: {src} missing - nothing to derive from (the usage reads "
              f"every population; sample_parties.py --pages 0 writes the full "
              f"artifact beside the committed one)")
        return 2
    if not os.path.exists(DATASET):
        print("FAIL: out/dataset-latest.json missing - run build_dataset.py "
              "first (weapon keys are filtered against the catalogue)")
        return 2
    with open(DATASET, encoding="utf-8") as f:
        known = set(json.load(f)["weapons"])
    out = derive(rosters_io.load(src, source="all"), known)
    jsonfmt.dump(out, USAGE)
    w = out["window"]
    print(f"window {w['from']} .. {w['to']} ({w['days']} days), "
          f"{out['battles_sampled']} battles of {MIN_PLAYERS}+")
    for b in BUCKETS:
        m, c = out["meta"][b], out["cohort_meta"][b]
        print(f"  {b:5}: {m['battles']} battles, "
              f"{m['players_attributed']} combatants; "
              f"{c['cohorts']} of {c['parties_in_window']} killer parties")
    print("wrote out/weapon_usage_v2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
