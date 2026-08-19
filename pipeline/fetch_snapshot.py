#!/usr/bin/env python3
"""
Fetch the PINNED game-data snapshot (changeschapter2.md §A).

    data/source_pins.yaml            the one exact ao-bin-dumps commit
        │
        ▼
    out/dumps_cache/<sha12>/…        raw files, cached BY COMMIT
    out/source_manifest.json         repository, commit, timestamps, patch,
                                     environment, SHA-256 per file

Every input — items, spells, localization, formatted names — comes from the
same commit; nothing follows `master`. Re-running is idempotent: files already
in the commit's cache directory are verified against the recorded hash rather
than re-downloaded. This script is the ONLY place the game-data pipeline
touches the network for dumps; the derivation steps (parse_dumps.py,
fetch_item_stats.py, fetch_gear_lines.py) read the cache offline.

Usage:  py -3 pipeline/fetch_snapshot.py [--refresh] [--verify-only]
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PINS_PATH = os.path.join(ROOT, "data", "source_pins.yaml")
UA = {"User-Agent": "albion-comp-engine snapshot fetch "
                    "(github.com/SODIYAL/albion-comp-engine)"}

sys.path.insert(0, HERE)
from provenance import (load_manifest, save_manifest, sha256_file,  # noqa: E402
                        snapshot_dir)


def load_pin():
    with open(PINS_PATH, encoding="utf-8") as f:
        pins = yaml.safe_load(f)
    pin = pins["ao-bin-dumps"]
    if len(pin["commit"]) != 40:
        sys.exit(f"pin commit {pin['commit']!r} is not a full 40-char SHA")
    return pin


def fetch(pin, name, dest):
    url = (pin["repository"].replace("https://github.com/",
                                     "https://raw.githubusercontent.com/")
           + f"/{pin['commit']}/{name}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  downloading {name} @ {pin['commit'][:12]} …", flush=True)
    req = urllib.request.Request(url, headers=UA)
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download even if the commit cache has the file")
    ap.add_argument("--verify-only", action="store_true",
                    help="no network: verify existing cache against the manifest")
    args = ap.parse_args()

    pin = load_pin()
    cache = snapshot_dir(pin["commit"])
    manifest = load_manifest() or {}
    recorded = (manifest.get("sources") or {})
    same_commit = recorded.get("commit") == pin["commit"]
    files = recorded.get("files", {}) if same_commit else {}

    problems, fetched = [], 0
    for name in pin["files"]:
        dest = os.path.join(cache, name.replace("/", os.sep))
        have = os.path.exists(dest) and not args.refresh
        if not have:
            if args.verify_only:
                problems.append(f"{name}: missing from {os.path.relpath(cache, HERE)}")
                continue
            fetch(pin, name, dest)
            fetched += 1
        digest = sha256_file(dest)
        prior = (files.get(name) or {}).get("sha256")
        if prior and prior != digest:
            problems.append(
                f"{name}: hash changed for the SAME commit "
                f"({prior[:12]}… -> {digest[:12]}…) — a pinned file must be "
                "immutable; refusing to update the manifest")
            continue
        files[name] = {"sha256": digest, "bytes": os.path.getsize(dest)}
        print(f"  {'fetched ' if not have else 'verified'} {name}  "
              f"sha256 {digest[:12]}…  {os.path.getsize(dest) // 1024} KB")

    if problems:
        for p in problems:
            print(f"  ERROR {p}")
        return 1

    manifest["sources"] = {
        "repository": pin["repository"],
        "commit": pin["commit"],
        "commit_timestamp": pin["commit_timestamp"],
        "environment": pin.get("environment", "live"),
        "game_patch": pin.get("game_patch", {}),
        "fetch_timestamp_utc": (recorded.get("fetch_timestamp_utc")
                                if same_commit and not fetched and not args.refresh
                                else datetime.now(timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%SZ")),
        "files": {k: files[k] for k in sorted(files)},
    }
    # Auxiliary art source, recorded for completeness: icons come from the
    # official render service, are cosmetic, and are deliberately NOT part of
    # the pinned data chain (catalog inclusion must never depend on art).
    manifest.setdefault("auxiliary", {})["render_service"] = \
        "https://render.albiononline.com/v1 (icons only, not pinned)"
    save_manifest(manifest)
    print(f"snapshot {pin['commit'][:12]} complete: {len(files)}/"
          f"{len(pin['files'])} files verified in "
          f"{os.path.relpath(cache, HERE)}")
    print("wrote out/source_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
