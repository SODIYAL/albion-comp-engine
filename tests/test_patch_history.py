#!/usr/bin/env python3
"""
Unit tests for the patch-history layer (patch_history.py + the staleness
warning in evidence_lint.py). Pure synthetic data — no ao-bin-dumps clone and
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
from evidence_lint import load_patch_index, stale_evidence  # noqa: E402

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

# ---- staleness: load_patch_index + stale_evidence ----------------------------
history = {"patches": [
    {"date": "2026-09-15", "spells": [
        {"id": "CHILD_KNOCKBACK", "roots": ["DIVINE_JUMP"]},
        {"id": "SHRINKINGSMASH_VFX", "roots": ["SHRINKINGSMASH"],
         "balance_relevant": False}]},
    {"date": "2026-05-26", "spells": [
        {"id": "SHRINKINGSMASH_EFFECT_DEBUFF", "roots": ["SHRINKINGSMASH"]}]},
]}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(history, f)
    tmp = f.name
try:
    idx = load_patch_index(tmp)
finally:
    os.unlink(tmp)

check("patch index is keyed by equippable ROOT, not the changed child",
      idx.get("DIVINE_JUMP") == ["2026-09-15"] and "CHILD_KNOCKBACK" not in idx,
      f"got {idx}")
check("cosmetic-only changes are excluded from the staleness index",
      idx.get("SHRINKINGSMASH") == ["2026-05-26"], f"got {idx}")

stale = stale_evidence("2026-08-12", ["DIVINE_JUMP", "SHRINKINGSMASH"], idx)
check("evidence patched AFTER curated_as_of is flagged; earlier patches are not",
      stale == [("DIVINE_JUMP", ["2026-09-15"])], f"got {stale}")
check("no curated_as_of means no staleness check",
      stale_evidence(None, ["DIVINE_JUMP"], idx) == [])
check("uncited spells never flag",
      stale_evidence("2026-08-12", ["ARROWRAIN"], idx) == [])

# yaml parses an unquoted date as datetime.date — the check must survive that
import datetime  # noqa: E402
stale_dt = stale_evidence(datetime.date(2026, 8, 12), ["DIVINE_JUMP"], idx)
check("curated_as_of works as a datetime.date (unquoted YAML)",
      stale_dt == [("DIVINE_JUMP", ["2026-09-15"])], f"got {stale_dt}")

# ---- summary -----------------------------------------------------------------
failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
