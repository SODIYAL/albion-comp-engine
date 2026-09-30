#!/usr/bin/env python3
"""
The killer-party cache as ONE SQLite file: out/party_cache.sqlite.

WHY ONE FILE. The cache used to be one JSON file per battle in
out/party_cache/. The kill-feed poll adds about forty battles a minute,
so the directory passed 127,000 files and 1.8 GB: every directory
listing, file watcher, backup and antivirus pass crawled all of it, and
the three processes sharing it (the poll, the harvest, the fold) relied
on atomic renames and "skip what is mid-write". A table keyed by battle
id holds the same records with the same content, compressed about seven
to one, and SQLite's write-ahead log lets the poll write while an audit
reads a consistent snapshot. Nothing about a record changes: `get`
returns exactly the dict `put` stored, so every reader's logic and every
derived artifact stay as they were.

WHAT A ROW IS. `battle` is the primary key; `source`, `schema`,
`started_at`, `first_event_at` and `total_players` are copied out of the
record so a caller can filter without decompressing; `rec` is the whole
record as zlib-compressed JSON (sorted keys, so equal records are equal
bytes). `updated_at` is the UTC time of the last `put`.

USE. `Store()` opens the default file (create on first write);
`Store(path)` another. One connection per thread: the harvest's worker
threads each open their own (`check_same_thread` stays on). Writers wait
up to 30 s on a lock held by another process; the poll's single pass and
the harvest's per-battle puts never hold one for long.

  py -3 pipeline/party_store.py            # count by source, file size
  py -3 pipeline/party_store.py --count    # the bare battle count
"""
import argparse
import datetime
import json
import os
import sqlite3
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "party_cache.sqlite"
DEFAULT = os.path.join(OUT, NAME)

SCHEMA = """
CREATE TABLE IF NOT EXISTS battles (
    battle         INTEGER PRIMARY KEY,
    source         TEXT    NOT NULL,
    schema         INTEGER,
    started_at     TEXT,
    first_event_at TEXT,
    total_players  INTEGER,
    updated_at     TEXT    NOT NULL,
    rec            BLOB    NOT NULL
);
CREATE INDEX IF NOT EXISTS battles_source ON battles (source);
"""


def encode(rec):
    """A record to its stored bytes (sorted keys, compact, zlib)."""
    return zlib.compress(
        json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8"), 6)


def decode(blob):
    return json.loads(zlib.decompress(blob).decode("utf-8"))


class Store:
    def __init__(self, path=None, create=True):
        self.path = path or DEFAULT
        if not create and not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    # ---- reads ---------------------------------------------------------
    def count(self, source=None):
        if source:
            row = self.db.execute("SELECT COUNT(*) FROM battles WHERE source=?", (source,)).fetchone()
        else:
            row = self.db.execute("SELECT COUNT(*) FROM battles").fetchone()
        return row[0]

    def has(self, bid):
        return self.db.execute("SELECT 1 FROM battles WHERE battle=?", (int(bid),)).fetchone() is not None

    def meta(self, bid):
        """The filter columns of one battle without decompressing it, or
        None: (source, schema, started_at, total_players)."""
        row = self.db.execute(
            "SELECT source, schema, started_at, total_players FROM battles WHERE battle=?",
            (int(bid),)).fetchone()
        return tuple(row) if row else None

    def get(self, bid):
        row = self.db.execute("SELECT rec FROM battles WHERE battle=?", (int(bid),)).fetchone()
        return decode(row[0]) if row else None

    def ids(self, source=None):
        """Every battle id in ascending order: the snapshot a two-pass
        reader takes once, so a battle the poll adds mid-run cannot appear
        in one pass and not the other."""
        if source:
            rows = self.db.execute(
                "SELECT battle FROM battles WHERE source=? ORDER BY battle", (source,))
        else:
            rows = self.db.execute("SELECT battle FROM battles ORDER BY battle")
        return [r[0] for r in rows]

    def iter_records(self, ids=None, source=None):
        """(battle, record) in ascending id order. With `ids`, exactly
        those (a battle deleted meanwhile is skipped); otherwise every row
        of the store, or of one source, read under one snapshot."""
        if ids is not None:
            for bid in ids:
                rec = self.get(bid)
                if rec is not None:
                    yield bid, rec
            return
        if source:
            cur = self.db.execute(
                "SELECT battle, rec FROM battles WHERE source=? ORDER BY battle", (source,))
        else:
            cur = self.db.execute("SELECT battle, rec FROM battles ORDER BY battle")
        for bid, blob in cur:
            yield bid, decode(blob)

    # ---- writes --------------------------------------------------------
    def put(self, bid, rec, commit=True):
        """Store one record whole (insert or replace)."""
        self.db.execute(
            "INSERT OR REPLACE INTO battles (battle, source, schema, started_at, "
            "first_event_at, total_players, updated_at, rec) VALUES (?,?,?,?,?,?,?,?)",
            (int(bid), rec.get("source") or "battle_list", rec.get("schema"),
             rec.get("started_at"), rec.get("first_event_at"),
             rec.get("total_players"),
             datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             encode(rec)))
        if commit:
            self.db.commit()

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=None)
    ap.add_argument("--count", action="store_true", help="print the battle count only")
    args = ap.parse_args()
    path = args.path or DEFAULT
    if not os.path.exists(path):
        print(0 if args.count else f"no store at {path}")
        return
    with Store(path, create=False) as st:
        if args.count:
            print(st.count())
            return
        by_source = dict(st.db.execute(
            "SELECT source, COUNT(*) FROM battles GROUP BY source ORDER BY source"))
        newest = st.db.execute("SELECT MAX(updated_at) FROM battles").fetchone()[0]
        size = os.path.getsize(path)
        print(f"{path}: {st.count()} battles, {size / 1e6:.1f} MB, last write {newest}")
        for s, n in by_source.items():
            print(f"  {s}: {n}")


if __name__ == "__main__":
    main()
