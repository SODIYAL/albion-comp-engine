"""The killer-party artifact on disk: out/party_rosters.json.gz.

One loader for every reader and the one writer (2026-09-11, owner: "this
file will keep growing"). The artifact is the harvest's derived evidence -
every build, party and battle summary the doctrine, the style rows and
the meta prior are mined from - and it grows ~10 KB per harvested battle:
77 MB raw at 7,652 battles, past GitHub's 100 MB per-file push limit at
~10,000, which the twice-daily harvest reaches in days. Gzipped it is
4.6 MB, ~24 MB at 40,000 battles. The compressed bytes are what the hash
gates in derive_party_styles / derive_meta_prior / build_dataset record
and compare, so provenance is unchanged: the same content writes the same
bytes (gzip header mtime pinned to 0, one compression level).

`load` sniffs the gzip magic and falls back to plain JSON, so a tool that
reads an older commit's artifact out of git (compare_fold) keeps working
across the switch. Nothing else should open the file directly.
"""
import gzip
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "party_rosters.json.gz"
LEGACY_NAME = "party_rosters.json"   # pre-2026-09-11 plain artifact


def path(out_dir=None):
    return os.path.join(out_dir or OUT, NAME)


def exists(p=None):
    return os.path.exists(p or path())


def load(p=None):
    """The artifact as a dict; gzip or (legacy / git-history) plain JSON."""
    p = p or path()
    with open(p, "rb") as f:
        head = f.read(2)
    if head == b"\x1f\x8b":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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
