#!/usr/bin/env python3
"""
Gear/doctrine blind-test cards (Phase 6, 2026-08-27).

Generates expert-facing cards asking "which piece would you realistically
run in this slot for this seat/comp?" — engine answers are written to a
SEPARATE hidden answers file and never appear in the form (that is what
makes it blind). Scoring reveals the engine ranking, measures agreement,
and records the expert's preferred/acceptable/situational/bad ratings
per item (relative ranking, never fake point precision — Task 6B).

Ratings feed the gear validation report; disagreements become doctrine/
capability review items for the owner, NEVER automatic score changes.

Usage:
    py -3 tests/gear_blindtest.py generate            # writes tests/gear_form.md
                                                      #  + tests/out/gear_form_answers.json
    py -3 tests/gear_blindtest.py score gear_form_filled.md
"""
import argparse
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

SEED = 20260827
FORM = os.path.join(HERE, "gear_form.md")
ANSWERS = os.path.join(HERE, "out", "gear_form_answers.json")
RATINGS_OUT = os.path.join(HERE, "out", "gear_ratings.json")
RATING_WORDS = ("preferred", "acceptable", "situational", "bad")

# (card id, seat-or-function role, slot, style) — the Task-6A matrix.
CARDS = [
    ("engage_tank_head_brawl", "engage_tank", "head", "brawl"),
    ("engage_tank_shoes_brawl", "engage_tank", "shoes", "brawl"),
    ("stopper_tank_cape_brawl", "stopper_tank", "cape", "brawl"),
    ("stopper_tank_offhand_brawl", "stopper_tank", "offhand", "brawl"),
    ("main_healer_offhand", "main_healer", "offhand", "balanced"),
    ("main_healer_potion", "main_healer", "potion", "balanced"),
    ("clap_ranged_dps_chest", "ranged_aoe", "armor", "clap"),
    ("clap_ranged_dps_shoes", "ranged_aoe", "shoes", "clap"),
    ("brawl_dps_chest", "sustained_brawler", "armor", "brawl"),
    ("kite_dps_shoes", "ranged_aoe", "shoes", "kite"),
    ("anti_heal_head_brawl", "anti_heal", "head", "brawl"),
    ("anti_heal_chest_brawl", "anti_heal", "armor", "brawl"),
    ("pierce_support_head_clap", "pierce", "head", "clap"),
    ("pierce_support_chest_clap", "pierce", "armor", "clap"),
    ("defensive_support_head", "shield_support", "head", "balanced"),
    ("defensive_support_chest", "shield_support", "armor", "balanced"),
]

# Real published-comp rosters as card context (weapons only, display text).
STYLE_COMPS = {
    "brawl": "timothy_blap_blackzone_roam_2026_08.yaml",
    "clap": "albioncompo_20v20_competitive_2026_08.yaml",
    "kite": "albioncompo_ss_kite_20_2026_06.yaml",
    "balanced": "albioncompo_bist_roam15_2026_01.yaml",
}
CONTENT = "blackzone_roam"   # carries every capability; sizes scale


def comp_members(style):
    import yaml
    path = os.path.join(ROOT, "data", "published_comps", STYLE_COMPS[style])
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    party = doc["parties"][0]
    return [s["weapons"][0] for s in party.get("slots", [])
            if s.get("weapons") and s.get("role") != "battlemount"], doc["id"]


def card_weapon(e, role_id, slot):
    """Deterministic representative: first (sorted) weapon on the role's
    book membership whose kit_options carries >=2 doctrine options for
    the slot. Function roles (no uniform) fall through to the member's
    own primary seat."""
    rec = e.roles.get(role_id) or {}
    members = sorted({(m.get("id") if isinstance(m, dict) else m)
                      for m in (rec.get("weapons") or [])} - {None})
    for w in members:
        if w not in e.weapons:
            continue
        try:
            ko = e.kit_options(w, top_n=8)
        except Exception:
            continue
        opts = [o for o in (ko["options"].get(slot) or []) if o.get("doctrine")]
        if len(opts) >= 2:
            return w
    return None


def build_card(e, idx, cid, role_id, slot, style, party, comp_id):
    w = card_weapon(e, role_id, slot)
    if w is None:
        return None, f"{cid}: no role member with >=2 doctrine {slot} options"
    rest = list(party)
    if w in rest:
        rest.remove(w)
    ko = e.kit_options(w, party=rest, top_n=8)
    ranked = [o["gear"] for o in (ko["options"].get(slot) or [])]
    doctrine = [o["gear"] for o in (ko["options"].get(slot) or [])
                if o.get("doctrine")]
    picks = doctrine[:3]
    distractor = next((g for g in ranked if g not in picks), None)
    if distractor is None:
        distractor = next((g for g in sorted(e.gear)
                           if (e.gear[g].get("slot") == slot
                               or (slot == "head" and e.gear[g].get("slot") == "head"))
                           and g not in picks), None)
    options = picks + ([distractor] if distractor else [])
    if len(options) < 3:
        return None, f"{cid}: only {len(options)} options"
    rng = random.Random(SEED + idx)
    rng.shuffle(options)
    letters = "ABCD"[:len(options)]
    opt_map = dict(zip(letters, options))
    # engine ranking of exactly these options: ko list order, absents last
    def pos(g):
        return ranked.index(g) if g in ranked else len(ranked)
    engine_rank = sorted(options, key=lambda g: (pos(g), g))
    return {
        "id": cid, "idx": idx, "weapon": w,
        "weapon_name": e.weapons[w]["display_name"],
        "seat_or_function": role_id, "slot": slot, "style": style,
        "comp": comp_id,
        "party_names": [e.weapons[m]["display_name"] for m in party],
        "options": opt_map,
        "option_names": {L: e.gear[g].get("display_name", g)
                         for L, g in opt_map.items()},
        "engine_rank": engine_rank,
        "engine_top": engine_rank[0],
    }, None


def generate(_args):
    lines = [
        "# Gear doctrine blind test (2026-08-27)",
        "",
        "For each card: which piece would you REALISTICALLY run? Fill",
        "YOUR CHOICE with one letter. Optionally rate every option:",
        "preferred / acceptable / situational / bad (relative judgement,",
        "not points). The engine's answer is deliberately not shown.",
        "",
    ]
    answers, skipped = {}, []
    idx = 0
    for cid, role_id, slot, style in CARDS:
        party, comp_id = comp_members(style)
        e = Engine(content=CONTENT, size=len(party), style=style)
        card, err = build_card(e, idx, cid, role_id, slot, style, party,
                               comp_id)
        if err:
            skipped.append(err)
            continue
        idx += 1
        names = ", ".join(card["party_names"][:10])
        more = len(card["party_names"]) - 10
        lines += [
            f"### Card {idx} — {cid.replace('_', ' ')}",
            f"- Context: {CONTENT} {style}, {len(card['party_names'])} players "
            f"(source comp: {card['comp']})",
            f"- Comp: {names}{f' … +{more} more' if more > 0 else ''}",
            f"- Weapon: {card['weapon_name']}",
            f"- Slot: {slot}",
            "- Options:",
        ]
        for L in sorted(card["options"]):
            lines.append(f"  - {L}. {card['option_names'][L]}")
        lines += ["- YOUR CHOICE: ",
                  "- RATE EACH: " + " ".join(f"{L}=" for L in
                                             sorted(card["options"])),
                  "- REASON: ",
                  ""]
        answers[str(idx)] = card
    with open(FORM, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    os.makedirs(os.path.dirname(ANSWERS), exist_ok=True)
    with open(ANSWERS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(answers, f, indent=1, sort_keys=True)
    print(f"wrote {FORM}: {idx} cards ({len(skipped)} skipped)")
    for s in skipped:
        print(f"  skip {s}")
    print(f"wrote hidden answer key {ANSWERS} — do NOT show it to experts")
    # blindness self-check: no engine ordering hint may appear in the form
    text = "\n".join(lines)
    assert "engine_rank" not in text and "engine_top" not in text
    return 0


def score(args):
    with open(args.form, encoding="utf-8") as f:
        text = f.read()
    with open(ANSWERS, encoding="utf-8") as f:
        answers = json.load(f)
    blocks = re.split(r"(?m)^###[ \t]*Card[ \t]*(\d+)[^\n]*$", text)[1:]
    cards = {blocks[i]: blocks[i + 1] for i in range(0, len(blocks), 2)}
    scored, top1 = 0, 0
    ratings = {}
    print(f"{'card':<6}{'expert':<26}{'engine top':<26}agree")
    print("-" * 78)
    for num in sorted(answers, key=int):
        a = answers[num]
        block = cards.get(num, "")
        m = re.search(r"^-[ \t]*YOUR CHOICE:[ \t]*([A-D])\b", block,
                      re.MULTILINE | re.IGNORECASE)
        if not m:
            continue
        choice = m.group(1).upper()
        gid = a["options"].get(choice)
        if gid is None:
            continue
        scored += 1
        hit = gid == a["engine_top"]
        top1 += hit
        print(f"{num:<6}{a['option_names'][choice]:<26}"
              f"{a['option_names'][[L for L, g in a['options'].items() if g == a['engine_top']][0]]:<26}"
              f"{'YES' if hit else 'no'}")
        rm = re.search(r"^-[ \t]*RATE EACH:[ \t]*(.+)$", block, re.MULTILINE)
        if rm:
            for L, word in re.findall(r"([A-D])[ \t]*=[ \t]*([a-z/]+)",
                                      rm.group(1), re.IGNORECASE):
                word = word.lower()
                if word in RATING_WORDS and L.upper() in a["options"]:
                    item = a["options"][L.upper()]
                    ratings.setdefault(item, []).append(
                        {"card": num, "rating": word,
                         "seat": a["seat_or_function"], "slot": a["slot"]})
    print("-" * 78)
    if not scored:
        sys.exit("no answers filled in yet")
    print(f"engine-top agreement: {top1}/{scored} = {top1 / scored:.0%}")
    print("(relative-ranking validation — disagreements are doctrine/"
          "capability review items for the owner, never automatic changes)")
    if ratings:
        os.makedirs(os.path.dirname(RATINGS_OUT), exist_ok=True)
        with open(RATINGS_OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ratings, f, indent=1, sort_keys=True)
        print(f"wrote per-item ratings {RATINGS_OUT}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.set_defaults(fn=generate)
    s = sub.add_parser("score")
    s.set_defaults(fn=score)
    s.add_argument("form")
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)
