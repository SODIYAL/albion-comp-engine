#!/usr/bin/env python3
"""
The harvest backup: the fold's copies of the killer-party artifacts and the
cache, copied off the harvest machine's disk.

WHY. The raw records live on the harvest machine alone (rosters_io,
LOCAL FILES, ONE COMMITTED RECORD; the cache, party_store.py). A battle
the killboard APIs no longer serve cannot be harvested again, so a lost
disk would lose it. This step copies them to a folder another service
keeps (a synced cloud folder or an external disk), named per machine in
pipeline/harvest_backup.json (gitignored):

  {"dir": "G:/My Drive/<folder>", "keep": 4, "cache": true}

WHAT. Per fold, a folder `fold-<date>-<record hash, 12>` holding the fold
copy, the full fold copy and the fold's record, each copy checked
against its hash after the write; the newest `keep` fold folders stay,
older ones are removed. With `cache` true, one consistent copy of the
cache (party_store.Store.backup), replaced each run. Restoring is the
reverse: the fold folder's files back into pipeline/out/ under the same
names, the cache as pipeline/out/party_cache.sqlite.

A fold step (fold_harvest.ps1, last); runnable alone:

  py -3 pipeline/backup_harvest.py            # back up per the config
  py -3 pipeline/backup_harvest.py --status   # what the target holds

No config: a warning, exit 0 (the fold still completes). A config whose
folder is missing (the drive not mounted) or a copy that does not match
its hash: exit 1.
"""
import datetime
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import party_store  # noqa: E402
import rosters_io  # noqa: E402

CONFIG = os.path.join(HERE, "harvest_backup.json")


def load_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f) or {}
    if not cfg.get("dir"):
        sys.exit(f"{CONFIG}: `dir` is required")
    keep = cfg.get("keep", 4)
    if not (isinstance(keep, int) and keep >= 1):
        sys.exit(f"{CONFIG}: `keep` must be a whole number of folds, 1 or more")
    return {"dir": cfg["dir"], "keep": keep, "cache": bool(cfg.get("cache", True))}


def fold_dirs(target):
    return sorted(d for d in os.listdir(target)
                  if d.startswith("fold-") and os.path.isdir(os.path.join(target, d)))


def copy_checked(src, dst, want=None):
    tmp = dst + ".tmp"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    if want and rosters_io.sha256(dst) != want:
        sys.exit(f"backup: {dst} does not match its hash after the copy")


def status(cfg):
    target = cfg["dir"]
    print(f"target {target} (keep {cfg['keep']}, cache {cfg['cache']})")
    if not os.path.isdir(target):
        print("  the folder is not there (the drive is not mounted?)")
        return
    for d in fold_dirs(target):
        files = sorted(os.listdir(os.path.join(target, d)))
        size = sum(os.path.getsize(os.path.join(target, d, f)) for f in files)
        print(f"  {d}  {len(files)} files, {size / 1e6:.1f} MB")
    cache = os.path.join(target, party_store.NAME)
    if os.path.exists(cache):
        print(f"  {party_store.NAME}  {os.path.getsize(cache) / 1e6:.1f} MB")


def main():
    cfg = load_config()
    if cfg is None:
        print(f"WARNING: no harvest backup configured ({CONFIG} is absent): the raw "
              "killer-party records and the cache exist on this disk alone")
        return 0
    if "--status" in sys.argv:
        status(cfg)
        return 0
    target = cfg["dir"]
    if not os.path.isdir(target):
        print(f"FAIL: backup folder {target} is not there (the drive is not mounted?)")
        return 1
    rec = rosters_io.record()
    sha = rec["party_rosters_sha256"]
    fold = rosters_io.fold_copy()
    if fold is None:
        print(f"FAIL: no fold copy on disk (pipeline/out/{rosters_io.FOLD_NAME})")
        return 1
    name = f"fold-{datetime.date.today().isoformat()}-{sha[:12]}"
    # the same fold backed up twice keeps one folder
    for d in fold_dirs(target):
        if d.endswith(sha[:12]) and d != name:
            os.replace(os.path.join(target, d), os.path.join(target, name))
    dest = os.path.join(target, name)
    os.makedirs(dest, exist_ok=True)
    copy_checked(fold, os.path.join(dest, rosters_io.FOLD_NAME), sha)
    full = rec.get("full") or {}
    if full.get("sha256") and os.path.exists(rosters_io.full_fold_path()):
        copy_checked(rosters_io.full_fold_path(),
                     os.path.join(dest, rosters_io.FULL_FOLD_NAME), full["sha256"])
    copy_checked(rosters_io.record_path(), os.path.join(dest, rosters_io.RECORD_NAME))
    print(f"backed up fold {sha[:12]} to {dest}")
    for d in fold_dirs(target)[:-cfg["keep"]]:
        shutil.rmtree(os.path.join(target, d))
        print(f"removed {d} (keep {cfg['keep']})")
    if cfg["cache"]:
        if not os.path.exists(party_store.DEFAULT):
            print(f"FAIL: no cache at {party_store.DEFAULT}")
            return 1
        with party_store.Store(party_store.DEFAULT, create=False) as st:
            st.backup(os.path.join(target, party_store.NAME))
        print(f"backed up the cache ({os.path.getsize(os.path.join(target, party_store.NAME)) / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
