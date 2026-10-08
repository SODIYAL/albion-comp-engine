#!/usr/bin/env python3
"""Evidence review record — snapshot-based staleness for every sheet score.

A sheet score rests on the facts of the spell it cites, as the pinned game
snapshot states them. This module fingerprints those facts and keeps, in
sheets/reviewed_evidence.json, the fingerprint each cited piece of evidence
had when the rows citing it were last read. When the snapshot moves
(data/source_pins.yaml, pipeline/README.md "Moving to a new game patch"),
every cited spell whose facts changed fails the lint until a curator has
re-read the rows that cite it and accepted the new facts:

    py -3 pipeline/evidence_review.py --accept SPELL [SPELL ...]

The comparison is between snapshots, not calendar dates: a sheet curated
after a patch but against an older pin is still stale against the new pin.

Fingerprinted facts, all from committed artifacts (no dumps needed):
  spell        out/spell_index.json record (description with its numbers,
               cast range, cooldown, area, channel, flags, targets) plus
               out/effect_catalogue.json spell_effects (the structured
               effect list the lint grounds capabilities on); a
               shapeshifter staff's E also carries its form's abilities
               (out/weapon_lines.json `form_spells`, each one's record and
               effects), since a sheet scores the form through the E
  WEAPON_STATS out/item_stats.json record of the weapon (base stats)
  GEAR_STATS   out/item_stats.json record of the gear item

Coverage: weapon sheets, weapon pools (through the weapons that receive
them), gear sheets, gear pools, and gear self_costs evidence.

usage:
  py -3 pipeline/evidence_review.py                 report stale / unrecorded evidence
  py -3 pipeline/evidence_review.py --accept ID ... record the current facts of ID
  py -3 pipeline/evidence_review.py --accept-unrecorded
                                                    record evidence cited for the first
                                                    time (never overwrites a changed record)
Exit 1 when anything is stale or unrecorded (the lint reports the same).
"""
import glob
import hashlib
import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sheets_lib  # noqa: E402

OUT = os.path.join(HERE, "out")
RECORD = os.path.join(HERE, "sheets", "reviewed_evidence.json")


def _load(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _digest(obj):
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class Facts:
    """Fingerprints of the evidence the sheets cite, from the committed
    parse of the pinned snapshot."""

    forms = {}   # a shapeshifter E -> its form's abilities; none by default

    def __init__(self):
        self.spells = _load("spell_index.json")
        self.effects = (_load("effect_catalogue.json") or {}).get("spell_effects", {})
        self.items = (_load("item_stats.json") or {}).get("items", {})
        # a shapeshifter E -> its form's abilities (no menu carries them)
        self.forms = {}
        for line in (_load("weapon_lines.json") or {}).values():
            for sid in (line.get("spells") or {}).get("e") or []:
                if line.get("form_spells"):
                    self.forms[sid] = sorted(set(self.forms.get(sid, []))
                                             | set(line["form_spells"]))

    def fingerprint(self, ev_id):
        """ev_id: a spell id, or 'WEAPON_STATS:<weapon>' / 'GEAR_STATS:<item>'.
        None when the snapshot does not carry it (the lint's equippability
        rules already fail such a citation)."""
        if ":" in ev_id:
            _kind, key = ev_id.split(":", 1)
            rec = self.items.get(key)
            return _digest(rec) if rec is not None else None
        if ev_id not in self.spells:
            return None
        facts = {"spell": self.spells.get(ev_id),
                 "effects": self.effects.get(ev_id)}
        if ev_id in self.forms:
            facts["form"] = [[s, self.spells.get(s), self.effects.get(s)]
                             for s in self.forms[ev_id]]
        return _digest(facts)


def cited_evidence():
    """{evidence id: sorted list of 'where' strings} for every nonzero score
    the build reads: composed weapon rows (own + pool), composed gear rows
    (own + gear pool), and gear self-costs."""
    lines = sheets_lib.load_weapon_lines()
    pools = sheets_lib.load_pools()
    gear_pools = sheets_lib.load_gear_pools()
    gear_spells = _load("gear_spells.json")
    cited = {}

    def add(ev, where):
        cited.setdefault(ev, set()).add(where)

    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            docs = yaml.safe_load(f) or []
        for e in docs:
            if not isinstance(e, dict) or not e.get("weapon"):
                continue
            w = e["weapon"]
            for c in sheets_lib.compose(e, lines.get(w), pools):
                ev = c.get("evidence")
                if not ev or not c.get("score"):
                    continue
                add(f"WEAPON_STATS:{w}" if ev == "WEAPON_STATS" else ev, f"{w}.{c.get('cap')}")
    for path in sorted(glob.glob(os.path.join(HERE, "sheets", "gear", "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            docs = yaml.safe_load(f) or []
        for e in docs:
            if not isinstance(e, dict) or not e.get("gear"):
                continue
            g = e["gear"]
            for c in sheets_lib.compose_gear(e, gear_spells.get(g), gear_pools):
                ev = c.get("evidence")
                if not ev or not c.get("score"):
                    continue
                add(f"GEAR_STATS:{g}" if ev == "GEAR_STATS" else ev, f"gear/{g}.{c.get('cap')}")
            for c in e.get("self_costs") or []:
                ev = (c or {}).get("evidence")
                if ev:
                    add(ev, f"gear/{g}.self_cost.{c.get('cap')}")
    return {k: sorted(v) for k, v in cited.items()}


def load_record(path=RECORD):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return (json.load(f) or {}).get("evidence", {})


def write_record(record, path=RECORD):
    doc = {"_meta": {
        "rule": ("The fingerprint of each cited evidence's facts when the rows "
                 "citing it were last read (pipeline/evidence_review.py). A "
                 "changed fingerprint fails the lint until the rows are re-read "
                 "and the new facts accepted with --accept."),
        "facts": ("spell: out/spell_index.json record + out/effect_catalogue.json "
                  "spell_effects; WEAPON_STATS:/GEAR_STATS:<key>: out/item_stats.json record"),
    }, "evidence": {k: record[k] for k in sorted(record)}}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, sort_keys=False, ensure_ascii=False)
        f.write("\n")


def check(facts=None, record=None, cited=None):
    """(stale, unrecorded): stale = [(id, wheres)] whose facts changed since
    the record; unrecorded = [(id, wheres)] never accepted."""
    facts = facts or Facts()
    record = load_record() if record is None else record
    cited = cited_evidence() if cited is None else cited
    stale, unrecorded = [], []
    for ev, wheres in sorted(cited.items()):
        fp = facts.fingerprint(ev)
        if fp is None:
            continue  # not in the snapshot: the lint's equippability rules fail it
        if ev not in record:
            unrecorded.append((ev, wheres))
        elif record[ev] != fp:
            stale.append((ev, wheres))
    return stale, unrecorded


def main(argv):
    facts = Facts()
    record = load_record()
    cited = cited_evidence()
    if "--accept" in argv:
        ids = argv[argv.index("--accept") + 1:]
        if not ids:
            sys.exit("--accept needs at least one evidence id")
        for ev in ids:
            fp = facts.fingerprint(ev)
            if fp is None:
                sys.exit(f"{ev}: not in the pinned snapshot")
            if ev not in cited:
                sys.exit(f"{ev}: no sheet row cites it")
            record[ev] = fp
        write_record(record)
        print(f"accepted {len(ids)} evidence id(s)")
        return 0
    if "--accept-unrecorded" in argv:
        _stale, unrec = check(facts, record, cited)
        for ev, _w in unrec:
            record[ev] = facts.fingerprint(ev)
        # forget evidence no row cites any more
        for ev in [k for k in record if k not in cited]:
            del record[ev]
        write_record(record)
        print(f"recorded {len(unrec)} newly cited evidence id(s)")
        return 0
    stale, unrec = check(facts, record, cited)
    for ev, wheres in stale:
        print(f"STALE       {ev}: its facts changed since the rows citing it were read "
              f"({', '.join(wheres[:6])}{' ...' if len(wheres) > 6 else ''})")
    for ev, wheres in unrec:
        print(f"UNRECORDED  {ev}: cited by {', '.join(wheres[:6])}{' ...' if len(wheres) > 6 else ''}")
    print(f"{len(cited)} cited evidence ids; {len(stale)} stale, {len(unrec)} unrecorded")
    return 1 if (stale or unrec) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
