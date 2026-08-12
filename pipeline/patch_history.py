#!/usr/bin/env python3
"""
Patch history from ao-bin-dumps git history (design doc §10 risk 9 mitigation).

Every game patch is a commit in ao-data/ao-bin-dumps. Diffing spells.json
between consecutive commits yields exactly which spells changed, in the same
spell IDs the rest of this pipeline speaks — no scraping, no name matching,
and it cannot be bot-blocked the way the wiki and the official forum are
(both Cloudflare-403 automated requests; verified 2026-08).

Output: out/patch_history.json — per patch: date, changed weapon-relevant
spells, the attribute-level before/after values, and which weapon lines each
change reaches. Commit dates match the forum "Combat Balance Changes" threads
one-for-one (e.g. 2026-06-29 ↔ "[29. June 2026] Radiant Wilds Patch 3"), so
the date is a stable join key to the human prose if you ever want to read it.

Consumers:
  evidence_lint.py    warns when a sheet's cited evidence spell changed in a
                      patch AFTER the sheet's `curated_as_of` date
  curate_helper.py    shows recent patch changes on the weapon's worksheet

What patch history is NOT: score evidence. The evidence rule requires every
nonzero score to cite an equippable spell resolved through the effect map;
this file is metadata about when to RE-REVIEW, never grounds for a claim.

Changes resolve TRANSITIVELY, same rule as effect_catalogue.py: a changed
spell maps to every equippable spell whose reference chain reaches it (any
attribute whose value names a real spell is a reference — DIVINE_JUMP chains
its enemy knockback through `dash @endeffect`, so a nerf in that child node
must still flag Hallowfall). Reachability is computed on the NEWEST snapshot;
reference topology changes between patches are rare and self-heal on re-run.

The clone needs HISTORY — the README's `--depth 1` clone cannot diff:

    git clone --filter=blob:none --no-checkout https://github.com/ao-data/ao-bin-dumps.git

(blobless: ~3 MB of history; each diffed snapshot fetches its ~14 MB
spells.json blob on demand, so --patches N downloads N+1 blobs.)

Usage:  py -3 pipeline/patch_history.py <ao-bin-dumps clone> [--patches 8]
"""
import json, os, re, subprocess, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

MAX_DEPTH = 3            # reference recursion limit (mirrors effect_catalogue)
ATTR_DIFF_CAP = 12       # attribute diffs kept per spell; total count always kept

# Attribute paths that cannot move a capability score: VFX, audio, UI sprites,
# and the gamepad-support metadata that the 2026-04-13 patch stamped onto 280
# of its 311 weapon-spell changes (`controllerpreferredtarget: -> enemy`). A
# spell whose EVERY changed path matches is `balance_relevant: false` — kept in
# the output (no silent drops), but the staleness warning skips it. Classified
# against the FULL diff, never the capped excerpt, so truncation can't hide a
# real change behind a cosmetic label.
COSMETIC_PATH = re.compile(
    r"(^|\.)(controller\w*|spellvfx\b[\w.]*|AudioInfo\.\w+|uisprite\w*|"
    r"icon\w*|sound\w*|vfx\w*)", re.I)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), check=True,
                          capture_output=True).stdout


def patch_commits(repo, count):
    """Newest-first (sha, date, message) for commits touching spells.json."""
    raw = git(repo, "log", f"-{count}", "--format=%H%x00%cs%x00%s",
              "--", "spells.json").decode("utf-8")
    rows = [line.split("\x00") for line in raw.splitlines() if line]
    if len(rows) < 2:
        sys.exit("need a clone with HISTORY (the --depth 1 clone cannot diff) — "
                 "see this file's docstring for the right clone command")
    return [(sha, date, msg) for sha, date, msg in rows]


def snapshot(repo, sha):
    """{spell uniquename: node} for one commit's spells.json."""
    root = json.loads(git(repo, "show", f"{sha}:spells.json"))["spells"]
    reg = {}
    for group in ("activespell", "passivespell", "togglespell"):
        entries = root.get(group, [])
        for s in (entries if isinstance(entries, list) else [entries]):
            if isinstance(s, dict) and s.get("@uniquename"):
                reg[s["@uniquename"]] = s
    return reg


def diff_snapshots(prev, cur):
    """{spell_id: kind} where kind is added/removed/changed."""
    out = {}
    for sid, node in cur.items():
        if sid not in prev:
            out[sid] = "added"
        elif prev[sid] != node:
            out[sid] = "changed"
    for sid in prev:
        if sid not in cur:
            out[sid] = "removed"
    return out


def flatten(node, prefix="", out=None, depth=0):
    """Leaf @attributes -> {dotted.path: value}, lists indexed as name[i]."""
    if out is None:
        out = {}
    if not isinstance(node, dict) or depth > 6:
        return out
    for key, val in node.items():
        if key.startswith("@"):
            out[f"{prefix}{key[1:]}"] = val
            continue
        items = val if isinstance(val, list) else [val]
        for i, item in enumerate(items):
            tag = f"{key}[{i}]" if len(items) > 1 else key
            flatten(item, f"{prefix}{tag}.", out, depth + 1)
    return out


def attr_changes(old, new):
    """FULL [{path, old, new}] — caller caps for serialization."""
    fo, fn = flatten(old or {}), flatten(new or {})
    return [{"path": p, "old": fo.get(p), "new": fn.get(p)}
            for p in sorted(set(fo) | set(fn)) if fo.get(p) != fn.get(p)]


def balance_relevant(changes):
    """False only when every changed path is provably cosmetic."""
    return not changes or any(not COSMETIC_PATH.search(c["path"])
                              for c in changes)


def spell_refs(node, reg, depth=0):
    """Every spell referenced by any attribute value — the effect_catalogue
    rule: matching the registry catches every linking convention in the data."""
    refs = set()
    if not isinstance(node, dict) or depth > 4:
        return refs
    for key, val in node.items():
        if key.startswith("@"):
            if isinstance(val, str) and val in reg:
                refs.add(val)
            continue
        for item in (val if isinstance(val, list) else [val]):
            if isinstance(item, dict):
                refs |= spell_refs(item, reg, depth + 1)
    return refs


def reverse_reach(reg, roots):
    """{spell_id: set(equippable roots whose reference chain reaches it)}."""
    reach, memo = {}, {}

    def refs_of(sid):
        if sid not in memo:
            memo[sid] = spell_refs(reg[sid], reg) if sid in reg else set()
        return memo[sid]

    for root in roots:
        seen, frontier = {root}, {root}
        for _ in range(MAX_DEPTH):
            nxt = set()
            for sid in frontier:
                nxt |= refs_of(sid) - seen
            if not nxt:
                break
            seen |= nxt
            frontier = nxt
        for sid in seen:
            reach.setdefault(sid, set()).add(root)
    return reach


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_repo", help="ao-bin-dumps clone WITH history")
    ap.add_argument("--patches", type=int, default=8,
                    help="how many patches back to diff (default 8)")
    args = ap.parse_args()

    weapon_lines = json.load(open(os.path.join(OUT, "weapon_lines.json"),
                                  encoding="utf-8"))
    spell_names = json.load(open(os.path.join(OUT, "spell_index.json"),
                                 encoding="utf-8"))
    lines_of = {}
    for wkey, line in weapon_lines.items():
        for slot_ids in line["spells"].values():
            for sid in slot_ids:
                lines_of.setdefault(sid, set()).add(wkey)

    commits = patch_commits(args.dump_repo, args.patches + 1)
    print(f"diffing {len(commits) - 1} patch(es), "
          f"{commits[-1][1]} .. {commits[0][1]}")

    newest = snapshot(args.dump_repo, commits[0][0])
    reach = reverse_reach(newest, set(lines_of))

    patches = []
    cur = newest
    for i in range(len(commits) - 1):
        sha, date, msg = commits[i]
        prev = snapshot(args.dump_repo, commits[i + 1][0])
        spells, other = [], 0
        for sid, kind in sorted(diff_snapshots(prev, cur).items()):
            roots = sorted(reach.get(sid, ()))
            if not roots:
                other += 1               # mob/gear/consumable spell — not ours
                continue
            changes = attr_changes(prev.get(sid), cur.get(sid))
            spells.append({
                "id": sid,
                "name": spell_names.get(sid, {}).get("name", sid),
                "kind": kind,
                "roots": roots,
                "lines": sorted({w for r in roots for w in lines_of.get(r, ())}),
                "balance_relevant": balance_relevant(changes),
                "changes": changes[:ATTR_DIFF_CAP],
                "changes_total": len(changes),
            })
        relevant = [s for s in spells if s["balance_relevant"]]
        patches.append({
            "date": date, "commit": sha, "message": msg,
            "spells": spells,
            "lines_affected": sorted({w for s in relevant for w in s["lines"]}),
            "non_weapon_changes": other,
        })
        print(f"  {date}  {msg:<24} {len(relevant):>4} balance-relevant spell(s) "
              f"(+{len(spells) - len(relevant)} cosmetic, {other} non-weapon), "
              f"{len(patches[-1]['lines_affected'])} line(s)")
        cur = prev

    result = {
        "_meta": {
            "source": "ao-data/ao-bin-dumps spells.json git history",
            "newest_commit": commits[0][0],
            "oldest_commit": commits[-1][0],
            "patches": len(patches),
            "attr_diff_cap": ATTR_DIFF_CAP,
            "note": ("Metadata for staleness detection and curation context — "
                     "NEVER score evidence (the evidence rule requires citing "
                     "equippable spells through the effect map)."),
        },
        "patches": patches,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "patch_history.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, sort_keys=True)
    print("wrote out/patch_history.json")


if __name__ == "__main__":
    main()
