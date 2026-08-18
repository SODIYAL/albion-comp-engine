#!/usr/bin/env python3
"""
Fetch weapon icons from the Albion Online Render Service and pack them into
a data-URI manifest the dashboard embeds (single-file pages can't hotlink —
the artifact host's CSP blocks external hosts, and file:// use is offline).

    out/dataset-latest.json   which weapons need icons (curated set)
    out/weapon_lines.json     key -> example_item (T4_...) for the render URL
    out/gear_lines.json       the loadout half: head/armor/shoes/cape/offhand
                              + potion/food (fetch_gear_lines.py)
        │
        ▼
    out/icons/<KEY>.webp      local cache — service is hit ONCE per weapon
    out/icon_data.json        {key: "data:image/webp;base64,..."}  (committed;
                              the cache directory is gitignored)

Icons are © Sandbox Interactive GmbH, served by their official community
render service (render.albiononline.com). Re-run after a patch adds weapons;
--force re-downloads everything (icon art rarely changes).

Usage:  py -3 pipeline/fetch_icons.py [--force]
"""
import argparse, base64, io, json, os, sys, time, urllib.request

try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow — needed to re-encode icons to webp")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "icons")
MANIFEST = os.path.join(OUT, "icon_data.json")
URL = "https://render.albiononline.com/v1/item/{item}.png?size=96"
SIZE = 96  # 2.2x the largest list display (44px) — crisp on retina; rerun with --force after bumping
UA = {"User-Agent": "albion-comp-engine icon fetch (github.com/SODIYAL/albion-comp-engine)"}


def fetch_png(item):
    req = urllib.request.Request(URL.format(item=item), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def to_webp(png_bytes):
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    img.thumbnail((SIZE, SIZE))
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80, method=6)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args()

    with open(os.path.join(OUT, "dataset-latest.json"), encoding="utf-8") as f:
        weapons = sorted(json.load(f)["weapons"])
    with open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8") as f:
        lines = json.load(f)

    # Gear is optional so a checkout without it still packs weapon icons —
    # run fetch_gear_lines.py to populate it.
    gear_path = os.path.join(OUT, "gear_lines.json")
    gear = {}
    if os.path.exists(gear_path):
        with open(gear_path, encoding="utf-8") as f:
            gear = json.load(f)
    else:
        print("note: out/gear_lines.json absent — run fetch_gear_lines.py "
              "for loadout icons; packing weapons only")

    # One namespace, no collisions: weapons are 2H_*/MAIN_*, gear is
    # HEAD_*/ARMOR_*/SHOES_*/CAPE*/OFF_*/POTION_*/MEAL_*.
    wanted = {k: (lines.get(k) or {}).get("example_item") for k in weapons}
    wanted.update({k: v.get("example_item") for k, v in sorted(gear.items())})

    os.makedirs(CACHE, exist_ok=True)
    manifest, fetched, cached, failed = {}, 0, 0, []
    for key, item in wanted.items():
        path = os.path.join(CACHE, key + ".webp")
        if args.force or not os.path.exists(path):
            if not item:
                failed.append((key, "no example_item in the line catalogue"))
                continue
            try:
                webp = to_webp(fetch_png(item))
            except Exception as e:  # noqa: BLE001 — report per-item, keep going
                failed.append((key, str(e)))
                continue
            with open(path, "wb") as f:
                f.write(webp)
            fetched += 1
            time.sleep(0.05)  # be polite to the render service
        else:
            cached += 1
        with open(path, "rb") as f:
            manifest[key] = "data:image/webp;base64," + base64.b64encode(f.read()).decode()

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=0, sort_keys=True)

    total = sum(len(v) for v in manifest.values())
    n_gear = sum(1 for k in manifest if k in gear)
    print(f"icons: {len(manifest)}/{len(wanted)} packed "
          f"({len(manifest) - n_gear} weapon, {n_gear} gear; "
          f"{fetched} fetched, {cached} from cache), manifest {total // 1024} KB")
    for key, err in failed:
        print(f"  MISSING {key}: {err}")
    print(f"wrote {os.path.relpath(MANIFEST, os.path.join(HERE, os.pardir))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
