#!/usr/bin/env python3
"""The usage derivation (pipeline/derive_usage.py): the sampling frame
(group-fight floor, a window anchored on the newest battle), prevalence
on the fight-size axis, killer-party cohorts on the party-size axis, the
even cohort sample, and determinism. A pure function over a synthetic
artifact: no network, no cache, no committed artifact read.
Script-style: exit 0 = pass."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import derive_usage as du  # noqa: E402
import jsonfmt  # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n      {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


KNOWN = {"A", "B", "C", "D"}


def battle(bid, total, started, source="battle_list"):
    key = "started_at" if source == "battle_list" else "first_event_at"
    return {"battle": bid, "total_players": total, "source": source, key: started}


def build(bid, weapon, player):
    return {"battle": bid, "weapon": weapon, "player": player, "seen_as": "killer"}


def party(bid, index, weapons, guilds=("G",), size=None):
    return {"battle": bid, "index": index, "size": size or len(weapons),
            "weapons": list(weapons), "guilds": list(guilds)}


DOC = {
    "battles": [
        battle(1, 40, "2026-09-30T20:00:00.123Z"),            # newest: anchors the window
        battle(2, 10, "2026-09-10T20:00:00Z"),
        battle(3, 20, "2026-09-02T20:00:01Z", "events_poll"),   # one second inside
        battle(4, 50, "2026-09-02T19:59:59Z"),                  # one second outside
        battle(5, 5, "2026-09-29T20:00:00Z"),                   # under the floor
        battle(6, 30, None),                                    # undated
    ],
    "builds": [
        build(1, "A", "p1"), build(1, "A", "p2"), build(1, "B", "p3"),
        build(1, "ZZZ", "p4"),                 # not in the catalogue
        build(2, "A", "p1"), build(2, "C", "p5"),
        build(3, "D", "p6"),
        build(4, "A", "p7"), build(5, "A", "p8"), build(6, "A", "p9"),
    ],
    "parties": [
        party(1, 0, ["A"] * 10 + ["B"] * 8),            # 18: large on the party axis
        party(1, 1, ["A", "B", "C"]),                   # 3 in a 40-player fight: small
        party(2, 0, ["A", "C", "C", "ZZZ", "D", "B"]),  # 6: mid, the unknown key dropped
        party(3, 0, ["D", "D"]),                        # one distinct weapon: no cohort
        party(3, 1, ["D"], size=1),                     # one member: no cohort
        party(4, 0, ["A", "B"]), party(5, 0, ["A", "B"]), party(6, 0, ["A", "B"]),
    ],
}

out = du.derive(DOC, KNOWN)

check("U1 the window is counted back from the newest battle, to the second",
      out["window"] == {"days": 28, "from": "2026-09-02T20:00:00",
                        "to": "2026-09-30T20:00:00",
                        "anchored_on": "the newest battle in the artifact"},
      str(out["window"]))
check("U2 the frame keeps dated group fights inside the window: the "
      "battle one second out, the one under the floor and the undated one "
      "are left out; a kill-feed record dates by its first event",
      out["battles_sampled"] == 3
      and out["meta"] == {"small": {"battles": 1, "players_attributed": 2},
                          "mid": {"battles": 1, "players_attributed": 1},
                          "large": {"battles": 1, "players_attributed": 3}},
      str(out["meta"]))
check("U3 prevalence is by FIGHT size, one count per build, catalogue "
      "keys only, with the distinct-battle count beside it",
      out["buckets"] == {"small": {"A": 1, "C": 1}, "mid": {"D": 1},
                         "large": {"A": 2, "B": 1}}
      and out["buckets_battles"]["large"] == {"A": 1, "B": 1},
      str(out["buckets"]))
rows = out["cohorts"]
check("U4 cohorts are killer parties by PARTY size: a 3-man in a "
      "40-player fight is a small cohort, an 18-man a large one",
      [(c["battle_id"], c["party"], c["size"]) for c in rows["large"]] == [(1, 0, 18)]
      and [(c["battle_id"], c["party"], c["size"]) for c in rows["small"]] == [(1, 1, 3)]
      and [(c["battle_id"], c["party"], c["size"]) for c in rows["mid"]] == [(2, 0, 6)],
      str({b: [(c["battle_id"], c["party"]) for c in r] for b, r in rows.items()}))
check("U5 a cohort carries distinct catalogue weapons, sorted; a party "
      "of one member or one distinct weapon is no cohort",
      rows["mid"][0]["weapons"] == ["A", "B", "C", "D"]
      and rows["large"][0]["weapons"] == ["A", "B"]
      and sum(len(r) for r in rows.values()) == 3)
check("U6 the bucket mapping: a party of N keys to a fight of 2N",
      [du.party_bucket(n) for n in (2, 5, 6, 15, 16, 20)]
      == ["small", "small", "mid", "mid", "large", "large"]
      and [du.bucket_of(n) for n in (6, 11, 12, 30, 31)]
      == ["small", "small", "mid", "mid", "large"])
check("U7 the cohort sample is spread evenly over the ordered window, "
      "and is the whole list when shorter",
      du.even_sample(list(range(10)), 5) == [0, 2, 4, 6, 8]
      and du.even_sample(list(range(7)), 3) == [0, 2, 4]
      and du.even_sample([1, 2], 5) == [1, 2])
many = dict(DOC, parties=[party(1, i, ["A", "B"] * 9) for i in range(2500)])
capped = du.derive(many, KNOWN)
check("U8 a bucket keeps at most COHORT_SAMPLE parties and states the "
      "parties it was drawn from",
      capped["cohort_meta"]["large"] == {
          "cohorts": du.COHORT_SAMPLE, "parties_in_window": 2500,
          "players_observed": 18 * du.COHORT_SAMPLE}
      and [c["party"] for c in capped["cohorts"]["large"][:3]] == [0, 2, 5],
      str(capped["cohort_meta"]["large"]))
check("U9 what stays unknown is stored as unknown, and the two axes are named",
      out["abilities"] == "unknown" and out["side_size"] == "unknown"
      and out["loadout_swaps"] == "unknown"
      and out["sampling_frame"]["axis"] == "fight_size"
      and out["cohort_frame"]["axis"] == "party_size")
shuffled = {k: list(reversed(v)) for k, v in DOC.items()}
check("U10 the derivation reads no clock and no input order: the same "
      "artifact writes the same bytes",
      jsonfmt.dumps(du.derive(DOC, KNOWN)) == jsonfmt.dumps(out)
      == jsonfmt.dumps(du.derive(shuffled, KNOWN)))
try:
    du.derive({"battles": [battle(6, 30, None)], "builds": [], "parties": []}, KNOWN)
    undated = False
except ValueError:
    undated = True
check("U11 an artifact with no dated battle fails loudly", undated)

print("=" * 74)
print(f"{11 - len(FAILURES)}/11 usage-derivation tests passed")
sys.exit(1 if FAILURES else 0)
