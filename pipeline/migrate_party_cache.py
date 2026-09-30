#!/usr/bin/env python3
"""
One-off: move the per-battle JSON files of out/party_cache/ into the
SQLite store (party_store.py), verify every record round-trips, then set
the directory aside as out/party_cache_files_migrated/ (never deleted by
this script). Stop the poll and harvest tasks first; a file written
while this runs is reported as skipped, not silently lost.

  py -3 pipeline/migrate_party_cache.py            # migrate + verify + set aside
  py -3 pipeline/migrate_party_cache.py --verify   # compare only, touch nothing
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import party_store  # noqa: E402

OUT = os.path.join(HERE, "out")
FILES = os.path.join(OUT, "party_cache")
ASIDE = os.path.join(OUT, "party_cache_files_migrated")


def records():
    """(battle id, record, filename) for every readable *.json file."""
    for name in sorted(os.listdir(FILES)):
        if not name.endswith(".json"):
            yield None, None, name
            continue
        try:
            bid = int(name[:-5])
            with open(os.path.join(FILES, name), encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            yield None, None, name
            continue
        if not isinstance(rec, dict) or rec.get("battle") != bid:
            yield None, None, name
            continue
        yield bid, rec, name


def migrate(st):
    t0 = time.time()
    n, skipped = 0, []
    for bid, rec, name in records():
        if bid is None:
            skipped.append(name)
            continue
        st.put(bid, rec, commit=False)
        n += 1
        if n % 2000 == 0:
            st.commit()
            print(f"  {n} records in, {time.time() - t0:.0f} s", flush=True)
    st.commit()
    print(f"migrate: {n} records stored in {time.time() - t0:.0f} s; "
          f"{len(skipped)} file(s) skipped" + (": " + ", ".join(skipped[:10]) if skipped else ""),
          flush=True)
    return n, skipped


def verify(st):
    """Every file's record equals the stored one (a dict compare, so key
    order and formatting cannot matter); the file count equals the store's
    count minus what the poll wrote to the store since."""
    t0 = time.time()
    n, missing, differ, skipped = 0, [], [], []
    for bid, rec, name in records():
        if bid is None:
            skipped.append(name)
            continue
        got = st.get(bid)
        if got is None:
            missing.append(name)
        elif got != rec:
            differ.append(name)
        n += 1
    print(f"verify: {n} files compared in {time.time() - t0:.0f} s; "
          f"store holds {st.count()}; missing {len(missing)}, differing {len(differ)}, "
          f"unreadable {len(skipped)}", flush=True)
    for label, xs in (("missing", missing), ("differing", differ)):
        if xs:
            print(f"  {label}: " + ", ".join(xs[:10]))
    return not missing and not differ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="compare only")
    args = ap.parse_args()
    if not os.path.isdir(FILES):
        sys.exit(f"nothing to migrate: {FILES} is not a directory")
    if os.path.exists(ASIDE):
        sys.exit(f"{ASIDE} already exists: a previous migration ran; move it first")
    with party_store.Store(party_store.DEFAULT) as st:
        if not args.verify:
            migrate(st)
        ok = verify(st)
    if not ok:
        sys.exit("verify FAILED: the files stay where they are")
    if args.verify:
        return
    os.rename(FILES, ASIDE)
    size = os.path.getsize(party_store.DEFAULT)
    print(f"done: {FILES} -> {ASIDE}; store {party_store.DEFAULT} is {size / 1e6:.0f} MB. "
          f"Delete the set-aside directory once a fold has run clean.")


if __name__ == "__main__":
    main()
