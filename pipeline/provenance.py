#!/usr/bin/env python3
"""
Provenance bookkeeping shared by every game-data derivation step
(changeschapter2.md §A).

One manifest, `out/source_manifest.json`, records:

  sources   what fetch_snapshot.py actually downloaded — repository, exact
            commit, commit timestamp, fetch timestamp, environment, game
            patch, and the SHA-256 of every raw file
  derived   what each adapter produced FROM those sources — the adapter's
            version, the commit its inputs came from, the raw files it read,
            and the SHA-256 of its committed output

`build_dataset.py` verifies the `derived` section against the files on disk:
every input must exist, hash-match the manifest, come from the SAME commit,
and be produced by the adapter version the current code carries. A mismatch
means someone mixed snapshots, hand-edited an output, or forgot a rebuild —
the release fails closed rather than shipping silently inconsistent data.

The manifest is committed. Raw dumps stay gitignored (out/dumps_cache/), so a
fresh checkout verifies the derived chain offline; raw hashes are re-verified
whenever the cache exists or fetch_snapshot.py runs.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(HERE, "out", "source_manifest.json")
MANIFEST_SCHEMA_VERSION = 1


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(required=False):
    if not os.path.exists(MANIFEST_PATH):
        if required:
            raise FileNotFoundError(
                "out/source_manifest.json missing — run: "
                "py -3 pipeline/fetch_snapshot.py")
        return None
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest):
    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
        f.write("\n")


def record_derived(output_name, output_path, adapter, adapter_version,
                   source_commit, source_files):
    """Stamp one derived output into the manifest. Called by the adapter that
    just wrote `output_path`. `source_commit` is the snapshot commit the
    inputs came from — "local-override" when the adapter was pointed at an
    unpinned directory, which build_dataset treats as a provenance failure."""
    manifest = load_manifest() or {}
    derived = manifest.setdefault("derived", {})
    derived[output_name] = {
        "adapter": adapter,
        "adapter_version": adapter_version,
        "source_commit": source_commit,
        "source_files": sorted(source_files),
        "sha256": sha256_file(output_path),
    }
    save_manifest(manifest)


def verify_derived(names, expected_versions):
    """Check the derived chain for the given output names against the files
    on disk. Returns a list of problem strings — empty means verified.

    expected_versions: {output_name: (adapter, adapter_version)} — what the
    CURRENT code would produce; a manifest recorded by older code fails until
    the outputs are regenerated."""
    problems = []
    manifest = load_manifest()
    if manifest is None:
        return ["out/source_manifest.json missing — run fetch_snapshot.py "
                "and the derivation steps"]
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        problems.append(
            f"manifest schema_version {manifest.get('schema_version')!r} != "
            f"{MANIFEST_SCHEMA_VERSION} — regenerate the manifest")
    derived = manifest.get("derived", {})
    commits = set()
    for name in names:
        rec = derived.get(name)
        if rec is None:
            problems.append(f"{name}: no provenance record — rerun its adapter")
            continue
        path = os.path.join(HERE, "out", os.path.basename(name))
        if not os.path.exists(path):
            problems.append(f"{name}: recorded in manifest but file missing")
            continue
        actual = sha256_file(path)
        if actual != rec.get("sha256"):
            problems.append(
                f"{name}: file hash {actual[:12]}… != manifest "
                f"{str(rec.get('sha256'))[:12]}… — stale or hand-edited; "
                "rerun its adapter")
        want = expected_versions.get(name)
        if want and (rec.get("adapter"), rec.get("adapter_version")) != want:
            problems.append(
                f"{name}: built by {rec.get('adapter')} "
                f"v{rec.get('adapter_version')}, current code is "
                f"{want[0]} v{want[1]} — rebuild")
        commits.add(rec.get("source_commit"))
    if len(commits) > 1:
        problems.append(
            f"mixed source commits across derived inputs: {sorted(commits)} "
            "— every input must come from the one pinned snapshot")
    elif commits and "local-override" in commits:
        problems.append(
            "derived inputs were built from an unpinned local directory — "
            "rebuild from the pinned snapshot (fetch_snapshot.py)")
    pinned = (manifest.get("sources") or {}).get("commit")
    if pinned and commits and commits != {pinned} and "local-override" not in commits:
        problems.append(
            f"derived inputs come from commit {sorted(commits)} but the "
            f"fetched snapshot is {pinned} — refetch or rebuild")
    return problems


def snapshot_commit():
    """The commit of the fetched snapshot, or None."""
    manifest = load_manifest()
    if not manifest:
        return None
    return (manifest.get("sources") or {}).get("commit")


def snapshot_dir(commit=None):
    """Cache directory for a snapshot commit (keyed by commit, never an
    anonymous forever-cache)."""
    commit = commit or snapshot_commit()
    if not commit:
        return None
    return os.path.join(HERE, "out", "dumps_cache", commit[:12])
