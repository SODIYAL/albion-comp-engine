"""The killer-party artifacts on disk: out/party_rosters.json.gz and
out/party_rosters_full.json.gz.

One loader for every reader and the one writer (the files keep growing).
The artifact is the harvest's derived evidence - every build, party and
battle summary the doctrine, the style rows and the meta prior are mined
from. The compressed bytes are what the hash gates in derive_party_styles
/ derive_meta_prior / build_dataset record and compare: the same content
writes the same bytes (gzip header mtime pinned to 0, one compression
level).

TWO FILES, ONE PASS. The COMMITTED artifact (NAME) keeps the populations
the build and the shipped tables read (`committed`): every battle-list
battle and every Dragon Portal battle, parties and builds following their
battle. The FULL artifact (FULL_NAME, gitignored) keeps every record,
the kill-feed poll's open-world fights included (two-thirds of the
builds on the cache the split was measured on: 92.3 MB gzipped against
29.0 MB for the committed population, near GitHub's 100 MiB per-file
push limit); only derive_usage.py, a display-only fold step, reads it.
Both are derived from the cache, which stays the source of truth.

`load` sniffs the gzip magic and falls back to plain JSON, so a tool that
reads an older commit's artifact out of git (compare_fold) keeps working
across the switch. Nothing else should open the files directly.
"""
import gzip
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "party_rosters.json.gz"
FULL_NAME = "party_rosters_full.json.gz"   # every record; local, never committed
LEGACY_NAME = "party_rosters.json"   # the pre-gzip plain artifact


def path(out_dir=None):
    return os.path.join(out_dir or OUT, NAME)


def full_path(out_dir=None):
    return os.path.join(out_dir or OUT, FULL_NAME)


def exists(p=None):
    return os.path.exists(p or path())


def committed(battle):
    """True for a battle the committed artifact keeps: a battle-list
    battle (the population every shipped table was fitted on) or a Dragon
    Portal battle (the pools' rows, role counts and stats). The kill-feed
    poll's other records stay in the full artifact."""
    return ((battle.get("source") or "battle_list") == "battle_list"
            or (battle.get("content") or "unknown") == "ancient_lands")


def load(p=None, source="battle_list", content=None):
    """The artifact as a dict; gzip or (legacy / git-history) plain JSON.

    POPULATION (sample_parties.py "POPULATION"): battles carry `source`
    (`battle_list`, the albionbb-discovered harvest with an official
    roster; `events_poll`, the kill-feed poll) and `content` (a tag).
    The default keeps the battle-list population only, the one every
    shipped table was fitted on; parties and builds follow their battle.
    `source="all"` keeps everything; `content` keeps one content's
    battles (`"ancient_lands"`, `"open_world"`, ...). Records written
    before the fields existed read as battle-list, content unknown."""
    p = p or path()
    with open(p, "rb") as f:
        head = f.read(2)
    if head == b"\x1f\x8b":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            doc = json.load(f)
    else:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
    return select(doc, source=source, content=content)


def select(doc, source="battle_list", content=None):
    """The population filter `load` applies (see there), on a loaded doc."""
    if not isinstance(doc, dict) or (source == "all" and content is None):
        return doc
    keep = set()
    for b in doc.get("battles") or []:
        src = b.get("source") or "battle_list"
        if source != "all" and src != source:
            continue
        if content is not None and (b.get("content") or "unknown") != content:
            continue
        keep.add(b.get("battle"))
    out = dict(doc)
    out["battles"] = [b for b in doc.get("battles") or [] if b.get("battle") in keep]
    for key in ("parties", "builds"):
        out[key] = [x for x in doc.get(key) or [] if x.get("battle") in keep]
    out["_population"] = {"source": source, "content": content,
                          "battles": len(out["battles"]),
                          "battles_in_file": len(doc.get("battles") or [])}
    return out


def dump(obj, p=None):
    """Write the artifact: sorted keys, one-space indent, LF, gzip with the
    header mtime pinned so identical content is byte-identical."""
    p = p or path()
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    with open(p, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0,
                           compresslevel=6) as g:
            g.write(text.encode("utf-8"))


def sha256(p=None):
    """SHA-256 of the file's bytes as stored (the compressed bytes) - the
    value the derive steps stamp and build_dataset checks."""
    with open(p or path(), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
