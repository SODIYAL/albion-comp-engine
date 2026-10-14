"""The killer-party artifacts on disk and the fold's record of them.

One loader for every reader and the one writer (the files keep growing).
The artifact is the harvest's derived evidence - every build, party and
battle summary the doctrine, the style rows and the meta prior are mined
from. The compressed bytes are what the hash gates in the derive steps
and build_dataset record and compare: the same content writes the same
bytes (gzip header mtime pinned to 0, one compression level).

TWO FILES, ONE PASS. The harvest writes two artifacts from the cache:
the BUILD artifact (NAME) keeps the populations the build and the shipped
tables read (`build_population`): every battle-list battle and every
Dragon Portal battle, parties and builds following their battle. The
FULL artifact (FULL_NAME) keeps every record, the kill-feed poll's
open-world fights included; only derive_usage.py, a display-only fold
step, reads it. Both are derived from the cache, which stays the source
of truth.

LOCAL FILES, ONE COMMITTED RECORD. No artifact is committed: the build
artifact grows about 1 MB a day and GitHub refuses a file over 100 MiB,
and each fold's copy adds its whole size to the history. The harvest
writes the WORKING copies (NAME, FULL_NAME) on every pass; the fold
SEALS them (`seal`): the FOLD copies (FOLD_NAME, FULL_FOLD_NAME) are what
every derive step, the build and the audits read, so a harvest pass
ending mid-fold never changes the file a table is derived from, and the
fold's RECORD (RECORD_NAME, committed) names the fold copy's hash and
counts. Every derived table's `party_rosters_sha256` is checked against
the record (`fold_sha256`), never against a file, so a clone without the
local files still verifies the chain. The fold copy the record names
replaces the previous one, which is kept beside it (PREV_NAME) for the
fold report.

`load` sniffs the gzip magic and falls back to plain JSON, so a tool that
reads an older commit's artifact out of git (compare_fold) keeps working.
Nothing else should open the files directly.

  py -3 pipeline/rosters_io.py status          # the record and the local copies
  py -3 pipeline/rosters_io.py seal            # the fold: working -> fold copy + record
      [--from PATH] [--full-from PATH|none]    # seal other files (a copy taken mid-harvest)
"""
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
NAME = "party_rosters.json.gz"             # the harvest's working copy; local
FULL_NAME = "party_rosters_full.json.gz"   # every record, working copy; local
FOLD_NAME = "party_rosters.fold.json.gz"   # the sealed copy every reader reads; local
FULL_FOLD_NAME = "party_rosters_full.fold.json.gz"   # the sealed full copy; local
PREV_NAME = "party_rosters.fold-prev.json.gz"   # the previous fold's copy; local
RECORD_NAME = "rosters_fold.json"          # the fold's record; COMMITTED
LEGACY_NAME = "party_rosters.json"   # the pre-gzip plain artifact


def path(out_dir=None):
    """The fold copy: the artifact every derive step, the build and the
    audits read (the one the committed record names)."""
    return os.path.join(out_dir or OUT, FOLD_NAME)


def working_path(out_dir=None):
    """The harvest's working copy, rewritten on every pass."""
    return os.path.join(out_dir or OUT, NAME)


def full_path(out_dir=None):
    """The full artifact's working copy, rewritten on every pass."""
    return os.path.join(out_dir or OUT, FULL_NAME)


def full_fold_path(out_dir=None):
    """The full artifact's fold copy (derive_usage reads it)."""
    return os.path.join(out_dir or OUT, FULL_FOLD_NAME)


def prev_path(out_dir=None):
    return os.path.join(out_dir or OUT, PREV_NAME)


def record_path(out_dir=None):
    return os.path.join(out_dir or OUT, RECORD_NAME)


def exists(p=None):
    return os.path.exists(p or path())


def build_population(battle):
    """True for a battle the build artifact keeps: a battle-list battle
    (the population every shipped table was fitted on) or a Dragon Portal
    battle (the pools' rows, role counts and stats). The kill-feed poll's
    other records stay in the full artifact."""
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
    """Write an artifact (default: the working copy): sorted keys,
    one-space indent, LF, gzip with the header mtime pinned so identical
    content is byte-identical."""
    p = p or working_path()
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    with open(p, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0,
                           compresslevel=6) as g:
            g.write(text.encode("utf-8"))


_SHA = {}


def sha256(p=None):
    """SHA-256 of the file's bytes as stored (the compressed bytes) - the
    value the derive steps stamp. Cached per path, size and mtime: a
    build reads it once per gate."""
    p = os.path.abspath(p or path())
    st = os.stat(p)
    key = (p, st.st_size, st.st_mtime_ns)
    if key not in _SHA:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _SHA[key] = h.hexdigest()
    return _SHA[key]


# ---- the fold's record -------------------------------------------------

def record(out_dir=None):
    """The committed record of the fold (RECORD_NAME). Fail closed,
    loudly: a missing or malformed record stops the caller."""
    p = record_path(out_dir)
    if not os.path.exists(p):
        sys.exit(f"out/{RECORD_NAME} missing - the fold's record names the "
                 "rosters artifact every derived table was read from; run "
                 "py -3 pipeline/rosters_io.py seal at the fold")
    with open(p, encoding="utf-8") as f:
        rec = json.load(f) or {}
    sha = rec.get("party_rosters_sha256")
    if not (isinstance(sha, str) and len(sha) == 64):
        sys.exit(f"out/{RECORD_NAME}: party_rosters_sha256 is not a SHA-256")
    return rec


def fold_sha256(out_dir=None):
    """The hash every derived table's `party_rosters_sha256` must carry:
    the fold copy's, as the committed record states it."""
    return record(out_dir)["party_rosters_sha256"]


def fold_copy(out_dir=None):
    """The fold copy's path when it is on disk and is the file the record
    names; None when it is absent (a clone or CI: the derived tables are
    read as committed). A fold copy the record does not name stops the
    caller: a table derived from it would carry a hash nothing records."""
    p = path(out_dir)
    if not os.path.exists(p) or os.environ.get("BION_NO_FOLD_COPY"):
        # BION_NO_FOLD_COPY is test plumbing (test_provenance H21): the
        # build reads as a clone without the fold copy would
        return None
    want = fold_sha256(out_dir)
    if sha256(p) != want:
        sys.exit(f"out/{FOLD_NAME} is not the file out/{RECORD_NAME} names "
                 f"(record {want[:12]}, file {sha256(p)[:12]}) - restore the "
                 "fold's copy (the harvest backup) or seal a fold")
    return p


def require(label, out_dir=None):
    """The fold copy for a check that reads raw records. Absent on a
    machine with the CI variable set: the check is skipped and says so;
    absent anywhere else: stop (the harvest machine always holds it)."""
    p = fold_copy(out_dir)
    if p is None:
        if os.environ.get("CI"):
            print(f"SKIP {label}: the raw harvest records are local to the "
                  "harvest machine (the derived tables are checked against "
                  f"out/{RECORD_NAME})")
            return None
        sys.exit(f"{label}: out/{FOLD_NAME} missing - restore the fold's "
                 "copy (the harvest backup) or seal a fold")
    return p


def _committed_record_sha():
    """The record's hash at git HEAD, None when HEAD holds no record."""
    try:
        r = subprocess.run(["git", "show", f"HEAD:pipeline/out/{RECORD_NAME}"],
                           cwd=ROOT, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        return (json.loads(r.stdout.decode("utf-8")) or {}).get(
            "party_rosters_sha256")
    except ValueError:
        return None


def _copy(src, dst):
    tmp = dst + ".tmp"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def seal(out_dir=None, src=None, full_src=None):
    """THE FOLD'S SEAL: the working copies become the fold copies and the
    record names them. The fold copy the committed record (git HEAD)
    names moves to PREV_NAME first, so the fold report reads the previous
    fold; a fold copy no commit records (a fold run twice) is replaced
    and the previous one kept. `src` / `full_src` seal other files (a
    copy taken while a harvest pass could rewrite the working ones).
    Returns the record."""
    out_dir = out_dir or OUT
    src = src or working_path(out_dir)
    full_src = full_src if full_src is not None else full_path(out_dir)
    if not os.path.exists(src):
        sys.exit(f"seal: {src} missing - run sample_parties.py --pages 0 first")
    doc = load(src, source="all")
    cur = path(out_dir)
    committed_sha = _committed_record_sha()
    if os.path.exists(cur) and committed_sha and sha256(cur) == committed_sha:
        _copy(cur, prev_path(out_dir))
    _copy(src, cur)
    full = None
    if full_src and os.path.exists(full_src):
        _copy(full_src, full_fold_path(out_dir))
        fp = full_fold_path(out_dir)
        full = {"sha256": sha256(fp), "bytes": os.path.getsize(fp)}
    rec = {
        "_note": ("The fold's record of the killer-party artifact every "
                  "derived table and the build read. The artifact stays on "
                  "the harvest machine (pipeline/out/" + FOLD_NAME + ", "
                  "gitignored, kept in the harvest backup); every derived "
                  "table's party_rosters_sha256 must equal "
                  "party_rosters_sha256 here."),
        "party_rosters_sha256": sha256(cur),
        "bytes": os.path.getsize(cur),
        "battles": len(doc.get("battles") or []),
        "parties": len(doc.get("parties") or []),
        "builds": len(doc.get("builds") or []),
        "previous_sha256": committed_sha,
        "full": full,
    }
    with open(record_path(out_dir), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    return rec


def status(out_dir=None):
    out_dir = out_dir or OUT
    rec = record(out_dir)
    print(f"record: {rec['party_rosters_sha256'][:12]}  {rec['battles']} battles, "
          f"{rec['parties']} parties, {rec['builds']} builds, {rec['bytes']} bytes")
    for label, p in (("fold copy", path(out_dir)), ("previous", prev_path(out_dir)),
                     ("full fold copy", full_fold_path(out_dir)),
                     ("working copy", working_path(out_dir)),
                     ("full working copy", full_path(out_dir))):
        if not os.path.exists(p):
            print(f"{label:18s} absent")
            continue
        sha = sha256(p)
        note = ("= record" if sha == rec["party_rosters_sha256"]
                else "= previous" if sha == rec.get("previous_sha256")
                else "= full" if sha == (rec.get("full") or {}).get("sha256")
                else "")
        print(f"{label:18s} {sha[:12]}  {os.path.getsize(p):>11d} bytes  {note}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "status"

    def _opt(name):
        return argv[argv.index(name) + 1] if name in argv else None
    if cmd == "seal":
        full_from = _opt("--full-from")
        r = seal(src=_opt("--from"),
                 full_src="" if full_from == "none" else full_from)
        print(f"sealed {r['party_rosters_sha256'][:12]}: {r['battles']} battles, "
              f"{r['parties']} parties, {r['builds']} builds; wrote out/{RECORD_NAME}")
    elif cmd == "status":
        status()
    else:
        sys.exit("usage: rosters_io.py [status|seal]")
