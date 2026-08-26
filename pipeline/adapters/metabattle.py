#!/usr/bin/env python3
"""
MetaBattle published-build adapter (changeschapter2.md §D.1) — the first
automated adapter, built on MetaBattle's MediaWiki Action API, never HTML
scraping.

    fetch   EXPLICIT network step (never part of normal builds or CI):
            capture the member lists of every group-PvP build category
            (CATEGORIES — ZvZ, Hellgate 5v5/10v10, Crystal League/Arena,
            Ganking; owner sample-growth request 2026-08-26), the wiki's
            license info, and every build page's wikitext + revision
            id/timestamp, as raw API responses under
            pipeline/tests/fixtures/metabattle/. The captures are
            committed — they are both the import's source snapshot and
            the offline test fixtures.

    parse   OFFLINE: read the captured responses, parse the {{Build}} and
            {{Build equipment}} templates, map display names to exact Albion
            UniqueNames against the pinned game snapshot, and write
            data/published_builds/metabattle.yaml — every record starts
            as `candidate`, never `approved` (§F); `content` derives from
            the page's own mode category (MODE_CONTENT priority). Names
            that cannot be resolved unambiguously land in the record's
            unknowns/quarantine fields and in the printed review report —
            nothing silently resolves to the first match.

MetaBattle content is CC BY-SA; each record carries attribution metadata
(page URL, revision, license, credit).

Usage:  py -3 pipeline/adapters/metabattle.py fetch     (explicit, network)
        py -3 pipeline/adapters/metabattle.py parse     (offline)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(HERE, os.pardir)
ROOT = os.path.join(PIPELINE, os.pardir)
OUT = os.path.join(PIPELINE, "out")
FIXTURES = os.path.join(PIPELINE, "tests", "fixtures", "metabattle")
DEST = os.path.join(ROOT, "data", "published_builds", "metabattle.yaml")

sys.path.insert(0, PIPELINE)
import builds_lib as bl  # noqa: E402

API = "https://metabattle.com/albion/api.php"
# Group-PvP build categories (owner 2026-08-26: "increasing the sample
# even more so we get more accurate stats"). Solo/PvE categories
# (Corrupted, Mists, Dungeons, Gathering) stay out — the engine models
# party composition.
CATEGORIES = ["Category:ZvZ builds",
              "Category:Hellgate 10v10 builds",
              "Category:Hellgate 5v5 builds",
              "Category:Crystal League builds",
              "Category:Crystal Arena builds",
              "Category:Ganking builds"]
# page mode-category -> evidence content bucket; FIRST match wins when a
# page sits in several modes (largest scale first — its kit evidence is
# then judged under the stricter context).
MODE_CONTENT = [("ZvZ_builds", "zvz"),
                ("Hellgate_10v10_builds", "hellgate_10v10"),
                ("Hellgate_5v5_builds", "hellgate_5v5"),
                ("Crystal_League_builds", "crystal_5v5"),
                ("Crystal_Arena_builds", "crystal_arena_5v5"),
                ("Ganking_builds", "ganking_smallscale")]
PAGE_URL = "https://metabattle.com/albion/{title}"
UA = {"User-Agent": "albion-comp-engine build adapter "
                    "(github.com/SODIYAL/albion-comp-engine)"}
ADAPTER = "metabattle"
ADAPTER_VERSION = "2"

ROLE_BY_CATEGORY = {
    "Healer_builds": "healer", "Melee_DPS_builds": "dps",
    "Range_DPS_builds": "dps", "Support_builds": "support",
    "Tank_builds": "tank",
}
GEAR_FIELDS = {"off hand weapon": "offhand", "head": "head", "cape": "cape",
               "armor": "armor", "shoes": "shoes", "potion": "potion",
               "food": "food"}


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def save(name, obj):
    os.makedirs(FIXTURES, exist_ok=True)
    with open(os.path.join(FIXTURES, name), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(obj, f, indent=1, sort_keys=True, ensure_ascii=False)


def fetch(_args):
    # clear stale captures so removed pages/categories can't linger
    if os.path.isdir(FIXTURES):
        for name in os.listdir(FIXTURES):
            if name.startswith(("page_", "category")):
                os.remove(os.path.join(FIXTURES, name))
    pages, seen = [], set()
    for cat in CATEGORIES:
        print(f"capturing {cat} via the MediaWiki Action API …")
        members = api({"action": "query", "list": "categorymembers",
                       "cmtitle": cat, "cmlimit": "500"})
        slug = cat.split(":", 1)[1].lower().replace(" ", "_")
        save(f"category_{slug}.json", members)
        for m in members["query"]["categorymembers"]:
            if m["pageid"] not in seen:
                seen.add(m["pageid"])
                pages.append(m)
        time.sleep(0.5)
    rights = api({"action": "query", "meta": "siteinfo",
                  "siprop": "rightsinfo|general"})
    save("rightsinfo.json", rights)
    # this wiki's rightsinfo points at its MediaWiki:Copyright page rather
    # than stating the license — capture the page's actual statement too
    save("copyright.json", api({"action": "parse",
                                "page": "MediaWiki:Copyright",
                                "prop": "wikitext"}))
    for m in pages:
        pid = m["pageid"]
        parsed = api({"action": "parse", "pageid": pid,
                      "prop": "wikitext|revid|categories"})
        revs = api({"action": "query", "pageids": pid, "prop": "revisions",
                    "rvprop": "ids|timestamp"})
        save(f"page_{pid}.json", {"parse": parsed, "revisions": revs})
        rev = parsed["parse"]["revid"]
        print(f"  {pid} rev {rev}  {m['title']}")
        time.sleep(0.5)                    # be polite
    print(f"captured {len(pages)} pages -> "
          f"{os.path.relpath(FIXTURES, ROOT)}")
    return 0


# ---------------------------------------------------------------- wikitext
def template_params(wikitext, name):
    """Named params of the first {{name ...}} template as {key: value}.
    Values are plain text on these pages; nested {{Item|X}} references are
    unwrapped to X."""
    m = re.search(r"\{\{" + re.escape(name) + r"\s*(\||\}\})", wikitext)
    if not m:
        return None
    depth, i = 2, m.start()
    start = i + 2
    j = start
    while j < len(wikitext) and depth > 0:
        if wikitext.startswith("{{", j):
            depth += 2
            j += 2
        elif wikitext.startswith("}}", j):
            depth -= 2
            j += 2
        else:
            j += 1
    body = wikitext[start:j - 2]
    # split on top-level pipes only
    parts, buf, d = [], "", 0
    for ch in body:
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
        if ch == "|" and d == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    out = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        v = re.sub(r"\{\{Item\|([^}|]+)[^}]*\}\}", r"\1", v)
        out[k.strip().lower()] = v.strip()
    return out


def split_list(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def resolve_weapon_spells(weapon, names, weapon_lines, spell_index):
    """MetaBattle lists 'main hand weapon skills' as ordered display names
    (Q, W, E, passive). Resolve each against the weapon's own pools; a name
    that matches nothing (or two things) stays unresolved — reported, never
    guessed."""
    pools = ((weapon_lines.get(weapon) or {}).get("spells") or {})
    spells = {s: None for s in bl.SPELL_SLOTS}
    unresolved = []
    for name in names:
        hit_slot, hit_sid = None, None
        for slot in bl.SPELL_SLOTS:
            sid = bl.match_spell(name, pools.get(slot) or [], spell_index)
            if sid:
                if hit_sid:
                    hit_slot, hit_sid = None, None   # ambiguous across slots
                    break
                hit_slot, hit_sid = slot, sid
        if hit_sid and spells.get(hit_slot) is None:
            spells[hit_slot] = hit_sid
        else:
            unresolved.append(name)
    return spells, unresolved


def parse(_args):
    try:
        import yaml
    except ImportError:
        sys.exit("pip install pyyaml")
    if not os.path.isdir(FIXTURES):
        sys.exit("no captures — run: py -3 pipeline/adapters/metabattle.py fetch")

    def _load(name):
        with open(os.path.join(OUT, name), encoding="utf-8") as f:
            return json.load(f)
    weapon_lines = _load("weapon_lines.json")
    spell_index = _load("spell_index.json")
    gear_lines = _load("gear_lines.json")
    manifest_path = os.path.join(OUT, "source_manifest.json")
    snapshot = None
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            snapshot = (json.load(f).get("sources") or {}).get("commit")

    with open(os.path.join(FIXTURES, "rightsinfo.json"), encoding="utf-8") as f:
        ri = json.load(f)["query"]
    license_text = (ri.get("rightsinfo") or {}).get("text") or ""
    license_url = (ri.get("rightsinfo") or {}).get("url") or ""
    # resolve a page-reference license to the page's actual statement
    cr_path = os.path.join(FIXTURES, "copyright.json")
    if os.path.exists(cr_path):
        with open(cr_path, encoding="utf-8") as f:
            stmt = json.load(f)["parse"]["wikitext"]["*"]
        stmt = re.sub(r"<[^>]+>", " ", stmt)
        m = re.search(r"Content is available under[^.]*\.", stmt)
        if m:
            license_text = m.group(0).strip()

    builds, review = [], []
    for name in sorted(os.listdir(FIXTURES)):
        if not name.startswith("page_"):
            continue
        with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
            cap = json.load(f)
        p = cap["parse"]["parse"]
        title, pid, revid = p["title"], p["pageid"], p["revid"]
        rev = next(iter(cap["revisions"]["query"]["pages"].values()))
        rev0 = (rev.get("revisions") or [{}])[0]
        timestamp = rev0.get("timestamp")
        wikitext = p["wikitext"]["*"]
        cats = [c["*"] for c in p.get("categories", [])]
        role = next((ROLE_BY_CATEGORY[c] for c in cats
                     if c in ROLE_BY_CATEGORY), None)
        content = next((c for cat_name, c in MODE_CONTENT
                        if cat_name in cats), None)
        if content is None:
            review.append(f"{title}: no recognized group-PvP mode "
                          f"category — skipped")
            continue

        eq = template_params(wikitext, "Build equipment")
        info = template_params(wikitext, "Build") or {}
        if not eq:
            review.append(f"{title}: no {{{{Build equipment}}}} template — skipped")
            continue

        unknowns, quarantined = [], []
        raw_weapon = eq.get("main hand weapon", "")
        weapon = bl.match_weapon(raw_weapon, weapon_lines)
        if not weapon:
            quarantined.append(f"weapon: unresolved {raw_weapon!r}")

        spells, unresolved = ({s: None for s in bl.SPELL_SLOTS}, [])
        if weapon:
            spells, unresolved = resolve_weapon_spells(
                weapon, split_list(eq.get("main hand weapon skills")),
                weapon_lines, spell_index)
        unknowns += [s for s in bl.SPELL_SLOTS if not spells.get(s)]
        for nm in unresolved:
            quarantined.append(f"spell: unresolved {nm!r}")

        two_handed = bool((weapon_lines.get(weapon) or {}).get("two_handed"))
        gear, gear_raw = {}, {}
        for field, slot in GEAR_FIELDS.items():
            text = eq.get(field)
            if not text:
                if slot == "offhand" and two_handed:
                    gear[slot] = None     # a 2H weapon HAS no offhand: none,
                    continue              # which is knowledge, not an unknown
                unknowns.append(f"gear.{slot}")
                continue
            key = bl.match_gear(text, slot, gear_lines)
            if key:
                gear[slot] = key
            else:
                gear_raw[slot] = text
                review.append(f"{title}: gear.{slot} unresolved {text!r}")
        # armor/head/shoes actives are named by the source but the project
        # has no gear-spell index yet — keep them RAW + unknown, never guessed
        gear_spells_raw = {s: eq.get(f"{f} skills")
                           for f, s in (("head", "head"), ("armor", "armor"),
                                        ("shoes", "shoes"), ("cape", "cape"))
                           if eq.get(f"{f} skills")}

        builds.append({
            "build_id": f"metabattle:{pid}:{revid}",
            "weapon": weapon,
            "weapon_raw": raw_weapon,
            "weapon_alternatives": [],
            "role": role,
            "role_raw": info.get("focus"),
            "content": content,
            "style": None,
            "party_size": None,           # the source states no group size
            "spells": spells,
            "spells_raw": eq.get("main hand weapon skills"),
            "gear_spells": {"head": None, "armor": None, "shoes": None},
            "gear_spells_raw": gear_spells_raw,
            "gear": gear,
            "gear_raw": gear_raw,
            "gear_alternatives": {},
            "tier": None, "enchant": None, "quality": None, "ip": None,
            "membership": "core",
            "unknowns": sorted(set(unknowns)),
            "quarantined_fields": quarantined,
            "status": "quarantined" if quarantined else "candidate",
            "approval": {"status": "candidate",
                         "basis": "automated import — awaiting review"},
            "source": {
                "kind": "metabattle",
                "family": "metabattle",
                "author": "MetaBattle contributors",
                "url": PAGE_URL.format(title=title.replace(" ", "_")),
                "record": f"pageid {pid}, revision {revid}",
            },
            "published": timestamp,
            "ingested": None,             # stamped by the batch envelope
            "patch": info.get("patch") or None,
            "claimed_freshness": info.get("mode"),
            "attribution": {"license": license_text,
                            "license_url": license_url,
                            "credit": "MetaBattle contributors"},
            "confidence": {
                "item_mapping": (round(len(gear) / (len(gear) + len(gear_raw)), 2)
                                 if gear or gear_raw else None),
                "spell_mapping": round(sum(1 for s in bl.SPELL_SLOTS
                                           if spells.get(s)) / 4, 2),
                "patch": 0.2,             # the wiki states no exact patch
                "content_context": 0.6,   # "ZvZ" is broad, not a template
                "party_size": 0.2,
                "source_independence": None,
                "loadout_completeness": round(
                    (sum(1 for s in bl.SPELL_SLOTS if spells.get(s))
                     + len(gear) + len(gear_raw) + (1 if weapon else 0)) / 12, 2),
                "outcome": None,
            },
        })

    batch = {
        "kind": "published_build_batch",
        "id": "metabattle",
        "source": {"kind": "metabattle", "family": "metabattle",
                   "author": "MetaBattle contributors",
                   "url": "https://metabattle.com/albion/Builds",
                   "license": license_text},
        "snapshot_commit": snapshot,
        "fetched_fixtures": os.path.relpath(FIXTURES, ROOT).replace("\\", "/"),
        "builds": builds,
    }
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with open(DEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("# GENERATED by pipeline/adapters/metabattle.py parse — do not\n"
                "# hand-edit records; re-run the adapter. Imported records are\n"
                "# CANDIDATES until reviewed (changeschapter2.md §D.1/§F).\n"
                "# Content is CC BY-SA — attribution travels on every record.\n")
        yaml.safe_dump(batch, f, sort_keys=False, allow_unicode=True, width=100)

    n_q = sum(1 for b in builds if b["status"] == "quarantined")
    print(f"parsed {len(builds)} builds -> {os.path.relpath(DEST, ROOT)}")
    print(f"  candidate {len(builds) - n_q}, quarantined {n_q}")
    if review:
        print(f"  review report ({len(review)}):")
        for r in review:
            print(f"   {r}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=fetch)
    sub.add_parser("parse").set_defaults(fn=parse)
    a = ap.parse_args()
    sys.exit(a.fn(a))
