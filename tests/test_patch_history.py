#!/usr/bin/env python3
"""
Unit tests for the patch-history layer (patch_history.py) and the
snapshot staleness record (evidence_review.py). Pure synthetic data — no ao-bin-dumps clone and
no network needed, so this runs everywhere the golden suite runs.

The transitive-reach case mirrors the real bug class that motivated the
design: DIVINE_JUMP carries its enemy knockback in a CHILD spell referenced
through `dash @endeffect`, and SHRINKINGSMASH's 2026-05-26 Max-Health-debuff
nerf (-0.25 -> -0.20) landed in SHRINKINGSMASH_EFFECT_DEBUFF, not in the
equippable spell's own node. A differ that only looks at root nodes reports
"nothing changed" for both.

Run:  py -3 tests/test_patch_history.py        (Windows)
      python3 tests/test_patch_history.py
"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "pipeline"))

from patch_history import (attr_changes, balance_relevant, diff_snapshots,
                           flatten, reverse_reach)  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if not cond else ""))


# ---- flatten / attr_changes -------------------------------------------------
old = {"@uniquename": "SPELL_A", "@cooldown": "20",
       "buffovertime": [{"@value": "-0.25"}, {"@value": "0.1"}],
       "channelingspell": {"@duration": "3"}}
new = {"@uniquename": "SPELL_A", "@cooldown": "15",
       "buffovertime": [{"@value": "-0.20"}, {"@value": "0.1"}],
       "channelingspell": {"@duration": "3"}}

flat = flatten(old)
check("flatten indexes lists and strips @",
      flat.get("buffovertime[0].value") == "-0.25" and flat.get("cooldown") == "20",
      f"got {flat}")

changes = attr_changes(old, new)
paths = {c["path"]: (c["old"], c["new"]) for c in changes}
check("attr_changes finds the two real diffs and nothing else",
      len(changes) == 2
      and paths.get("cooldown") == ("20", "15")
      and paths.get("buffovertime[0].value") == ("-0.25", "-0.20"),
      f"got {changes}")

# ---- balance_relevant: cosmetic churn must not trigger re-review -------------
cosmetic = [{"path": "controllerpreferredtarget", "old": None, "new": "enemy"},
            {"path": "spellvfx.soundinit", "old": "x", "new": None},
            {"path": "AudioInfo.name", "old": None, "new": "HIT_MEDIUM"}]
real = cosmetic + [{"path": "recastdelay", "old": "10", "new": "12"}]
check("all-cosmetic change set is not balance-relevant",
      balance_relevant(cosmetic) is False)
check("one real change among cosmetics makes the spell balance-relevant",
      balance_relevant(real) is True)
check("an added/removed spell (no diffs) is always balance-relevant",
      balance_relevant([]) is True)

# ---- diff_snapshots ----------------------------------------------------------
prev = {"KEEP": {"@x": "1"}, "CHANGE": {"@x": "1"}, "GONE": {"@x": "1"}}
cur = {"KEEP": {"@x": "1"}, "CHANGE": {"@x": "2"}, "NEW": {"@x": "1"}}
d = diff_snapshots(prev, cur)
check("diff_snapshots classifies added/removed/changed and skips unchanged",
      d == {"CHANGE": "changed", "NEW": "added", "GONE": "removed"}, f"got {d}")

# ---- reverse_reach: the DIVINE_JUMP / SHRINKINGSMASH case --------------------
reg = {
    "ROOT_E":       {"@uniquename": "ROOT_E",
                     "dash": {"@endeffect": "CHILD_KNOCKBACK"}},
    "CHILD_KNOCKBACK": {"@uniquename": "CHILD_KNOCKBACK",
                        "applyspell": {"@spell": "GRANDCHILD_DEBUFF"}},
    "GRANDCHILD_DEBUFF": {"@uniquename": "GRANDCHILD_DEBUFF"},
    "UNRELATED":    {"@uniquename": "UNRELATED"},
}
reach = reverse_reach(reg, {"ROOT_E"})
check("a change two references deep maps back to the equippable root",
      reach.get("GRANDCHILD_DEBUFF") == {"ROOT_E"}
      and reach.get("CHILD_KNOCKBACK") == {"ROOT_E"}, f"got {reach}")
check("spells outside the reference chain map to nothing",
      "UNRELATED" not in reach)

# ---- staleness: the evidence review record (evidence_review.py) ---------------
# A sheet score rests on the facts of the spell it cites as the pinned
# snapshot states them. The record (sheets/reviewed_evidence.json) keeps each
# cited spell's fingerprint from when the rows citing it were last read; a
# changed fingerprint fails the lint until the rows are re-read and the new
# facts accepted. Snapshot against snapshot, never a calendar date: a sheet
# curated after a patch but against the older pin is still stale against
# the new one.
import evidence_review  # noqa: E402


class FakeFacts(evidence_review.Facts):
    def __init__(self, spells, effects=None, items=None):
        self.spells = spells
        self.effects = effects or {}
        self.items = items or {}


cited = {"DIVINE_JUMP": ["2H_HOLYSTAFF.peel"],
         "ARROWRAIN": ["2H_LONGBOW.burst_aoe"],
         "WEAPON_STATS:2H_BOW": ["2H_BOW.sustained_dps"]}
old_facts = FakeFacts(
    {"DIVINE_JUMP": {"description": "Knocks back by 6."},
     "ARROWRAIN": {"description": "Rains arrows on an area."}},
    effects={"DIVINE_JUMP": [{"effect": "knockback", "dirs": ["enemy"]}]},
    items={"2H_BOW": {"stats": {"attackdamage": 50}}})
record = {k: old_facts.fingerprint(k) for k in cited}
st, un = evidence_review.check(old_facts, record, cited)
check("a record taken on the current snapshot reads clean", not st and not un,
      f"stale={st} unrecorded={un}")

new_facts = FakeFacts(
    {"DIVINE_JUMP": {"description": "Knocks back by 8."},
     "ARROWRAIN": {"description": "Rains arrows on an area."}},
    effects={"DIVINE_JUMP": [{"effect": "knockback", "dirs": ["enemy"]}]},
    items={"2H_BOW": {"stats": {"attackdamage": 55}}})
st, un = evidence_review.check(new_facts, record, cited)
check("a cited spell whose facts changed is stale, an unchanged one is not, "
      "and a base-stat row is stale when the item's stats change",
      [s for s, _w in st] == ["DIVINE_JUMP", "WEAPON_STATS:2H_BOW"] and not un,
      f"stale={st}")

fx_effect = FakeFacts(
    dict(old_facts.spells),
    effects={"DIVINE_JUMP": [{"effect": "knockback", "dirs": ["self"]}]},
    items=dict(old_facts.items))
st, _un = evidence_review.check(fx_effect, record, cited)
check("a change in the structured effects alone makes the spell stale",
      [s for s, _w in st] == ["DIVINE_JUMP"], f"stale={st}")

# a shapeshifter E's fingerprint carries its form's abilities (the form sits
# on no menu, so no row cites it): a change to a form ability stales the
# E's rows, and leaves every other fingerprint as it was
fx_form = FakeFacts(dict(old_facts.spells, ENT_HEAL_AREA={"description": "Heals 40."}),
                    effects=dict(old_facts.effects), items=dict(old_facts.items))
fx_form.forms = {"DIVINE_JUMP": ["ENT_HEAL_AREA"]}
form_record = {k: fx_form.fingerprint(k) for k in cited}
fx_form2 = FakeFacts(dict(old_facts.spells, ENT_HEAL_AREA={"description": "Heals 50."}),
                     effects=dict(old_facts.effects), items=dict(old_facts.items))
fx_form2.forms = fx_form.forms
st, un = evidence_review.check(fx_form2, form_record, cited)
check("a change to a form ability stales the E whose form it is, and no other "
      "evidence; without forms the fingerprint is the spell's own",
      [s for s, _w in st] == ["DIVINE_JUMP"] and not un
      and form_record["ARROWRAIN"] == record["ARROWRAIN"]
      and form_record["DIVINE_JUMP"] != record["DIVINE_JUMP"],
      f"stale={st}")

cited_new = dict(cited, SNARE=["MAIN_MACE.root"])
fx_cite = FakeFacts(dict(old_facts.spells, SNARE={"description": "Roots."}),
                    effects=dict(old_facts.effects), items=dict(old_facts.items))
st, un = evidence_review.check(fx_cite, record, cited_new)
check("a spell cited for the first time is unrecorded until accepted",
      not st and [u for u, _w in un] == ["SNARE"], f"unrecorded={un}")

with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, "reviewed_evidence.json")
    evidence_review.write_record(record, path)
    check("the record round-trips through its file",
          evidence_review.load_record(path) == record)

st, un = evidence_review.check()
check("the committed record covers every cited evidence id and none is stale "
      "on the pinned snapshot", not st and not un,
      f"stale={[s for s, _w in st][:5]} unrecorded={[u for u, _w in un][:5]}")

# ---- summary -----------------------------------------------------------------
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
