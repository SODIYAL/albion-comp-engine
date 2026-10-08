"""Back up the killer-party cache (pipeline/out/party_cache.sqlite, the one
copy of the harvest's evidence) into a folder another machine can reach (a
synced folder, a second drive). A BACKUP, never a build input: nothing in
the build or the gates reads the copy.

The copy is consistent while the kill-feed poll keeps writing: SQLite's
online backup reads one snapshot of the database. It is written to a
temporary file beside the destination and renamed over the last copy only
after an integrity check passes, so a synced folder never holds a half
written file and a failed run leaves the previous copy in place.

    py -3 pipeline/backup_cache.py --dest <folder>
    py -3 pipeline/backup_cache.py --dest <folder> --cache <another cache file>

harvest_overnight.ps1 runs it after the harvest's passes when a destination
is set (its -BackupDir parameter, else the COMPFORGE_BACKUP_DIR environment
variable). A fresh machine copies the backup to pipeline/out/party_cache.sqlite
and re-derives the artifacts from it (pipeline/README.md, "Harvest").
"""
import argparse
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import party_store  # noqa: E402

NAME = "party_cache.sqlite"


def backup(cache, dest_dir):
    if not os.path.exists(cache):
        raise SystemExit(f"no cache at {cache}")
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, NAME)
    tmp = final + ".partial"
    if os.path.exists(tmp):
        os.remove(tmp)
    t0 = time.time()
    src = sqlite3.connect(f"file:{cache}?mode=ro", uri=True, timeout=60)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA quick_check").fetchone()[0]
        battles = dst.execute("SELECT count(*) FROM battles").fetchone()[0] \
            if dst.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='battles'").fetchone() else None
    finally:
        dst.close()
        src.close()
    if ok != "ok":
        os.remove(tmp)
        raise SystemExit(f"the copy failed its integrity check ({ok}); the last backup stands")
    os.replace(tmp, final)
    size = os.path.getsize(final)
    return final, size, battles, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dest", required=True, help="the folder the copy is written to")
    ap.add_argument("--cache", default=party_store.DEFAULT, help="the cache to copy (default: the harvest's)")
    a = ap.parse_args()
    final, size, battles, secs = backup(a.cache, a.dest)
    print(f"backed up {a.cache} -> {final}: {size / 2**20:.0f} MB"
          + (f", {battles} battles" if battles is not None else "") + f", {secs:.0f} s")


if __name__ == "__main__":
    main()
