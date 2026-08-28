#!/usr/bin/env python3
"""
Builds evidence layer — schema, normalization and validation shared by
build_builds.py, the source adapters and the tests (changeschapter2.md §C-§F).

The layer keeps four concepts separate and never lets one masquerade as
another:

  game facts            pinned ao-bin-dumps snapshot (weapon_lines,
                        spell_index, gear_lines, item_stats)
  published builds      caller sheets, MetaBattle, manual Armory imports —
                        records under data/, each with source provenance
  loadout observations  companion party sightings, killboard equipment
                        prevalence — observations, never recommendations
  canonical builds      human-reviewed defaults derived ONLY through the
                        promotion gate below

Statuses: raw -> normalized -> (quarantined | candidate) -> approved,
plus stale and rejected. Imported records are never born approved.

A canonical default requires ONE of (§F):
  - sanctioned/current official Armory evidence + independent validation
  - agreement across >= 2 genuinely independent source FAMILIES
    (records sharing a family — same author/site — never count twice)
  - explicit current shotcaller approval (a shotcaller-authored sheet
    carries this for the author's own comp)

Everything human-maintained stays VERBATIM in data/; every derived value
(spell UniqueNames from "q3", gear keys from "Knight Helmet") is generated,
carries the basis it rests on, and stores unknowns explicitly as None +
an `unknowns` list. Nothing ever silently resolves to option 1.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")
DATA = os.path.join(ROOT, "data")

STATUSES = ("raw", "normalized", "quarantined", "candidate", "approved",
            "stale", "rejected")
SOURCE_KINDS = ("caller_sheet", "metabattle", "armory_manual", "companion",
                "killboard", "manual_link", "murderledger", "solo_1v1")
# 1v1/duel sources are structurally barred from group recommendations (§D.4):
# validation rejects any such record whose party-size range reaches past 2,
# and selection never offers them for larger requests.
ONE_V_ONE_KINDS = ("murderledger", "solo_1v1")
ONE_V_ONE_MAX_SIZE = 2
# The engine's content templates — the legal values for a record's
# `content_candidates` (owner ruling 2026-08-28: one comp can be evidence for
# several contents). Listed literally so this validator stays independent of
# a built dataset; must track pipeline/templates/*.yaml.
KNOWN_CONTENTS = ("blackzone_roam", "castle", "castle_outpost",
                  "faction_war", "roads", "territory_defense")

CONFIDENCE_DIMS = ("item_mapping", "spell_mapping", "patch",
                   "content_context", "party_size", "source_independence",
                   "loadout_completeness", "outcome")

GEAR_FIELD_SLOT = {"helm": "head", "armor": "armor", "boots": "shoes",
                   "cape": "cape", "offhand": "offhand",
                   "potion": "potion", "food": "food"}
SPELL_SLOTS = ("q", "w", "e", "passive")

# ---------------------------------------------------------------- matching
# Free-text -> catalogue key. Drop the tier adjective a catalogue name
# carries ("Adept's", "Minor", "Major"), drop a curator's parenthetical
# ("Leather Hood(cleanse)"), flatten punctuation. NEVER guess — an ambiguous
# name stays raw text and is reported, not silently resolved (§C).
TIER_WORDS = (r"(?:adept's|expert's|master's|grandmaster's|elder's|minor|"
              r"major|beginner's|novice's|journeyman's)")

# CALLER SHORTHAND (2026-08-28). Caller sheets are written for players, not
# parsers: they abbreviate ("RoP"), typo ("Smugglar"), shorten the catalogue
# word ("Guardian Helm" for Helmet), and — most often — name the ABILITY they
# want rather than the item that carries it ("Blink" boots, "GG"). Every entry
# below is either a spelling fact or an owner ruling, and each is slot-scoped
# so a word can mean different items in different slots. This is a
# VOCABULARY, not a guesser: anything not listed still falls through to the
# matcher and stays raw text if it cannot be resolved (the §C rule).
# Owner rulings 2026-08-28, verbatim:
#   "GG might be graveguard boots if it's on boot slot"
#   "blink would be stalker shoes most likely for their double blink ability"
#   "cleanse might be any leather helm with second ability"
GEAR_ALIASES = {
    # (slot, shorthand) -> catalogue name
    ("armor", "rop"): "Robe of Purity",
    ("cape", "smugglar"): "Smuggler Cape",          # typo in Timothy's sheet
    ("shoes", "gg"): "Graveguard Boots",            # owner ruling
    ("shoes", "blink"): "Stalker Shoes",            # owner ruling: double blink
    ("head", "cleanse"): "Hellion Hood",            # owner: a leather helm whose
    ("head", "leather hood cleanse"): "Hellion Hood",  # 2nd ability cleanses
    # Food. A bare "omelette" is ambiguous in the catalogue (Pork Omelette /
    # Avalonian Pork Omelette, both T7), so it needs a listed ruling rather
    # than a matcher tiebreak. Callers name the Avalonian line explicitly
    # ("ava pork omelette") — an unqualified "omelette" is the plain one.
    # INFERRED, not an owner ruling: flag for confirmation.
    ("food", "omelette"): "Pork Omelette",
}
# Callers prefix a tier.enchant marker ("7.1 omelette", "8.1 beef stew",
# "T8 Beef Stew"). It is notation, not part of any item name, and no
# catalogue name begins with a digit — so a LEADING tier token is stripped
# before matching. Trailing/interior digits are left alone.
TIER_NUM_RX = re.compile(r"^\s*t?\d(?:\.\d+)?\s+", re.I)
# "Helm" is the caller's word; the catalogue says "Helmet". Applied before
# matching so "Guardian Helm" and "Soldier Helm" resolve like any other name.
WORD_FIXES = ((r"\bhelm\b", "helmet"),)


def apply_gear_alias(text, slot):
    """Caller shorthand -> catalogue name, or the text unchanged."""
    if not text:
        return text
    text = TIER_NUM_RX.sub("", str(text))
    key = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    key = " ".join(key.split())
    hit = GEAR_ALIASES.get((slot, key))
    if hit:
        return hit
    for pat, rep in WORD_FIXES:
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def norm_text(text):
    text = re.sub(r"\(.*?\)", " ", text or "")
    text = re.sub(TIER_WORDS, " ", text.lower())
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def norm_text_keep_tier(text):
    """Like norm_text but the tier adjective survives — a source that writes
    "Major Gigantify Potion" names an EXACT item and must not be flattened
    onto the plain tier."""
    text = re.sub(r"\(.*?\)", " ", text or "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return " ".join(text.split())


def _token_prefix_match(tokens, name_tokens):
    """Every token is a prefix of a name token, in order — lets a caller's
    "Ava pork omelette" reach "Avalonian Pork Omelette" without letting
    unrelated items through."""
    it = iter(name_tokens)
    return all(any(n.startswith(tok) for n in it) for tok in tokens)


# An item ID: all-caps, underscore-joined, no spaces. Display names never
# take this shape, so the ID path can never capture one.
ITEM_ID_RX = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
KEY_TIER_RX = re.compile(r"^T\d+_")
KEY_ENCH_RX = re.compile(r"@\d+$")


def key_form(key):
    """Catalogue key stripped to its tier- and enchant-independent form:
    'T8_MEAL_STEW@2' -> 'MEAL_STEW'."""
    return KEY_TIER_RX.sub("", KEY_ENCH_RX.sub("", str(key).strip().upper()))


def _match_gear_key(text, slot, catalogue):
    """Exact catalogue key for an item ID, or None."""
    if not text:
        return None
    raw = str(text).strip()
    if not ITEM_ID_RX.match(raw):
        return None
    want = key_form(raw)
    hits = [k for k, v in catalogue.items()
            if v.get("slot") == slot and key_form(k) == want]
    return hits[0] if len(hits) == 1 else None


def match_gear(text, slot, catalogue):
    """A catalogue key for free-text `text` in `slot`, or None when absent or
    ambiguous. An exact ITEM ID is honoured first, then caller shorthand is
    translated (GEAR_ALIASES) so a sheet written for players still resolves;
    anything unlisted falls through and stays raw text rather than being
    guessed."""
    # Most comp sources record gear as game item IDs ("ARMOR_CLOTH_AVALON"),
    # not display names — an ID IS the catalogue key, so it is an identity
    # match, not a guess. Consumable keys carry a tier the sources omit
    # ("MEAL_STEW" for T8_MEAL_STEW), so the tier prefix and any enchant
    # suffix are normalized off both sides. Still slot-checked, and still
    # returns None if two keys collide.
    key_hit = _match_gear_key(text, slot, catalogue)
    if key_hit:
        return key_hit
    text = apply_gear_alias(text, slot)
    want = norm_text(text)
    if not want:
        return None
    # a full-name match INCLUDING the tier adjective is exact and wins before
    # any stripping ("Major Gigantify Potion" -> the Major line, never the
    # plain one)
    want_full = norm_text_keep_tier(text)
    full = [k for k, v in catalogue.items()
            if v["slot"] == slot and norm_text_keep_tier(v["name"]) == want_full]
    if len(full) == 1:
        return full[0]
    cands = [(k, norm_text(v["name"])) for k, v in catalogue.items()
             if v["slot"] == slot]

    def pick(hits):
        if len(hits) == 1:
            return hits[0]
        if not hits:
            return None
        # Consumables are one line PER TIER, so "Gigantify Potion"
        # legitimately matches Minor/base/Major. Prefer the plain tier — the
        # one whose raw name carried no tier adjective.
        plain = [k for k in hits
                 if norm_text(catalogue[k]["name"]) == catalogue[k]["name"].lower()]
        return plain[0] if len(plain) == 1 else None

    hit = pick([k for k, n in cands if n == want])
    if hit:
        return hit
    hit = pick([k for k, n in cands if want in n])
    if hit:
        return hit
    toks = want.split()
    return pick([k for k, n in cands if _token_prefix_match(toks, n.split())])


def match_weapon(text, weapons):
    """Weapon key for a display name ("Elder's Longbow" -> 2H_LONGBOW), or
    None when absent/ambiguous. `weapons` maps key -> {display_name} or the
    weapon_lines shape (key -> {name})."""
    want = norm_text(text)
    if not want:
        return None
    cands = []
    for k, w in weapons.items():
        name = w.get("display_name") or w.get("name") or k
        cands.append((k, norm_text(name)))
    exact = [k for k, n in cands if n == want]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    sub = [k for k, n in cands if want in n or n in want]
    return sub[0] if len(sub) == 1 else None


def match_spell(text, pool, spell_index):
    """Spell UniqueName for a display name within an equippable pool.
    Ambiguity or a miss returns None — the caller records an unknown."""
    want = norm_text(text)
    if not want:
        return None
    hits = [sid for sid in pool
            if norm_text((spell_index.get(sid) or {}).get("name") or sid) == want]
    if len(hits) == 1:
        return hits[0]
    if hits:
        return None
    hits = [sid for sid in pool
            if want in norm_text((spell_index.get(sid) or {}).get("name") or sid)]
    return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------- skills cells
SKILLS_RE = re.compile(r"q(\d+)\D+w(\d+)\D+p(\d+)", re.I)


def parse_skills(cell):
    """Verbatim "q3, w2, p1" -> {"q": 3, "w": 2, "p": 1} (1-based), or None.
    Raw indices are SOURCE DATA and stay attached to the record; the
    canonical identity is the resolved UniqueName (§C)."""
    m = SKILLS_RE.search(cell or "")
    if not m:
        return None
    return {"q": int(m.group(1)), "w": int(m.group(2)), "p": int(m.group(3))}


def resolve_spells(weapon, picks, weapon_lines):
    """(spells, unknowns, quarantined) — exact spell UniqueNames for 1-based
    pick indices against the weapon's equippable pools at the attributed
    snapshot. An index beyond the pool is QUARANTINED (stored None + listed),
    never clamped and never silently swapped for option 1 (§C). The E slot
    resolves automatically only when the pool has exactly one option."""
    pools = ((weapon_lines.get(weapon) or {}).get("spells") or {})
    spells = {s: None for s in SPELL_SLOTS}
    unknowns, quarantined = [], []
    idx_slot = {"q": "q", "w": "w", "p": "passive"}
    for raw_slot, slot in idx_slot.items():
        pool = pools.get(slot) or []
        idx = (picks or {}).get(raw_slot)
        if idx is None:
            unknowns.append(slot)
        elif 1 <= idx <= len(pool):
            spells[slot] = pool[idx - 1]
        else:
            quarantined.append(
                f"{slot}: index {idx} exceeds the {len(pool)}-option pool")
            unknowns.append(slot)
    e_pool = pools.get("e") or []
    if len(e_pool) == 1:
        spells["e"] = e_pool[0]
    else:
        unknowns.append("e")
    return spells, unknowns, quarantined


ALT_SPLIT_RX = re.compile(r"\s*/\s*|\s+or\s+", re.I)


def split_alternatives(text):
    """'Aegis/Taproot' -> ['Aegis', 'Taproot'] — structured alternatives
    rather than slash-delimited text (§C). Callers write the alternation
    with either separator ("Caitiff or Aegis"), so both split. Single values
    come back as a one-item list; None/empty as []. "N/A" means explicitly
    none, and is tested before the split so it never reads as an alternation
    between "N" and "A"."""
    if not text or str(text).strip().lower() in ("n/a", "na", "-", "none"):
        return []
    return [p.strip() for p in ALT_SPLIT_RX.split(str(text)) if p.strip()]


# --------------------------------------------------------- slot -> build
def normalize_slot(slot, comp, weapon_lines, gear_catalogue, spell_index):
    """One verbatim comp slot -> a normalized build record with explicit
    unknowns and per-dimension confidence. Returns None for battlemount
    slots (outside the weapon model) and slots with no weapon."""
    weapons = slot.get("weapons") or []
    if not weapons or slot.get("role") == "battlemount":
        return None
    weapon = weapons[0]
    picks = parse_skills(slot.get("skills"))
    spells, unknowns, quarantined = resolve_spells(weapon, picks, weapon_lines)

    gear, gear_raw, gear_alternatives = {}, {}, {}
    src = dict(slot.get("gear") or {})
    src.setdefault("potion", slot.get("potion"))
    src.setdefault("food", slot.get("food"))
    for field, gslot in GEAR_FIELD_SLOT.items():
        text = src.get(field)
        alts = split_alternatives(text)
        if text and not alts:
            gear[gslot] = None          # source explicitly says none (N/A)
            continue
        if not alts:
            unknowns.append(f"gear.{gslot}")
            continue
        keys = [match_gear(a, gslot, gear_catalogue) for a in alts]
        if keys[0]:
            gear[gslot] = keys[0]
        else:
            gear_raw[gslot] = alts[0]
        if len(alts) > 1:
            gear_alternatives[gslot] = [
                {"raw": a, "key": k, "condition": None}
                for a, k in zip(alts[1:], keys[1:])]

    weapon_alternatives = [
        {"weapon": w, "condition": None} for w in weapons[1:]]

    n_spell = sum(1 for s in SPELL_SLOTS if spells.get(s))
    n_gear = sum(1 for g in GEAR_FIELD_SLOT.values()
                 if g in gear or g in gear_raw)
    mapped_gear = sum(1 for v in gear.values() if v)
    named_gear = mapped_gear + len(gear_raw)
    confidence = {
        "item_mapping": round(mapped_gear / named_gear, 2) if named_gear else None,
        "spell_mapping": (round(n_spell / 4, 2) if picks or n_spell else None),
        "patch": 1.0 if comp.get("patch") else 0.2,
        "content_context": 1.0 if comp.get("content") else 0.2,
        "party_size": 1.0 if comp.get("party_size") else 0.2,
        "source_independence": None,   # judged across records, not per record
        "loadout_completeness": round((n_spell + n_gear + 1) / 12, 2),
        "outcome": None,               # no outcome evidence exists — say so
    }

    status = "quarantined" if quarantined else "normalized"
    return {
        "build_id": f"{comp['id']}:{slot.get('_slot_id')}",
        "weapon": weapon,
        "weapon_alternatives": weapon_alternatives,
        "role": slot.get("role"),
        "role_raw": slot.get("role_raw"),
        "content": comp.get("content"),
        "style": comp.get("style"),
        "party_size": comp.get("party_size"),
        "spells": spells,
        "spells_raw": slot.get("skills"),
        # armor/head/shoes actives exist in the schema; caller sheets do not
        # name them, so they are explicitly unknown rather than absent
        "gear_spells": {"head": None, "armor": None, "shoes": None},
        "gear": gear,
        "gear_raw": gear_raw,
        "gear_alternatives": gear_alternatives,
        # tier/enchant/quality/IP: separate fields, unknown unless stated (§A)
        "tier": None, "enchant": None, "quality": None, "ip": None,
        "membership": "core",
        "unknowns": sorted(set(unknowns)),
        "quarantined_fields": quarantined,
        "status": status,
        "source": comp.get("source"),
        "patch": comp.get("patch"),
        "snapshot_commit": comp.get("snapshot_commit"),
        "published": comp.get("published"),
        "ingested": comp.get("ingested"),
        "observed": comp.get("observed"),
        "approval": comp.get("approval"),
        "confidence": confidence,
        "note": src.get("note"),
    }


# ------------------------------------------------------------- validation
def validate_comp_doc(doc, weapon_lines, templates=None):
    """Schema + referential problems for one published_comp document."""
    problems = []
    ident = doc.get("id", "?")
    for field in ("kind", "id", "source", "content", "party_size",
                  "approval", "parties"):
        if not doc.get(field):
            problems.append(f"{ident}: missing required field {field!r}")
    src = doc.get("source") or {}
    if src.get("kind") not in SOURCE_KINDS:
        problems.append(f"{ident}: unknown source kind {src.get('kind')!r}")
    if not src.get("family"):
        problems.append(f"{ident}: source.family (independence key) required")
    ap = (doc.get("approval") or {}).get("status")
    if ap not in STATUSES:
        problems.append(f"{ident}: approval.status {ap!r} not in {STATUSES}")
    ps = doc.get("party_size") or {}
    if ps and not (isinstance(ps, dict) and "min" in ps and "max" in ps):
        problems.append(f"{ident}: party_size must be {{min, max}}")
    # style is optional (identity Phase C: styles key stored builds to the
    # caller's declared intent) but when stated it must be a real style
    # 2026-08-28: `clap_kite` was missing — the list predates it (the owner
    # identified the fifth playstyle 2026-08-23) and nothing caught the gap
    # until real comps were labelled with it. Kept as a literal tuple rather
    # than read from styles.yaml so this validator stays independent of the
    # dataset build, but it must track styles.yaml: five playstyles plus
    # `balanced`, which declares no intent.
    style = doc.get("style")
    if style and style not in ("balanced", "brawl", "clap", "kite",
                               "brawl_clap", "clap_kite"):
        problems.append(f"{ident}: unknown style {style!r}")
    # CONTENT CANDIDATES (owner ruling 2026-08-28): a record's `content` may
    # name a FORMAT ("zvz_20man") rather than one of the engine's content
    # templates, and one comp can legitimately serve several — "zvz 20man can
    # be blackzone roaming or castle outposts or castle defense ... any comp
    # doing outposts or castles or roaming in blackzone could do so in
    # faction aswell". Validated against the real template list so a typo or
    # a renamed template surfaces here instead of silently dropping the comp
    # out of every fit.
    cands = doc.get("content_candidates")
    if cands is not None:
        if not isinstance(cands, list) or not cands:
            problems.append(f"{ident}: content_candidates must be a non-empty list")
        else:
            for _c in cands:
                if _c not in KNOWN_CONTENTS:
                    problems.append(
                        f"{ident}: content_candidate {_c!r} is not a content "
                        f"template ({sorted(KNOWN_CONTENTS)})")
    # per-party style/exclusion (owner rulings 2026-08-28): one record's
    # parties are not always one comp shape, and a party its own author says
    # is not built properly must never teach the model what a comp looks like
    for _p in (doc.get("parties") or []):
        _ps = _p.get("style")
        if _ps and _ps not in ("balanced", "brawl", "clap", "kite",
                               "brawl_clap", "clap_kite"):
            problems.append(f"{ident}:{_p.get('name','?')}: "
                            f"unknown style {_ps!r}")
        for _scope, _fx in ((f"{ident}", doc.get("fit_exclude")),
                            (f"{ident}:{_p.get('name','?')}",
                             _p.get("fit_exclude"))):
            if _fx and not (_fx.get("reason") or "").strip():
                problems.append(f"{_scope}: fit_exclude needs a reason "
                                "(an exclusion without a stated why is "
                                "indistinguishable from lost data)")
    if src.get("kind") in ONE_V_ONE_KINDS and ps and \
            ps.get("max", 0) > ONE_V_ONE_MAX_SIZE:
        problems.append(
            f"{ident}: {src['kind']} evidence is restricted to solo/1v1 "
            f"contexts — party_size.max {ps.get('max')} > {ONE_V_ONE_MAX_SIZE}")
    for party in doc.get("parties", []) or []:
        for slot in party.get("slots", []) or []:
            for w in slot.get("weapons") or []:
                if w not in weapon_lines:
                    problems.append(
                        f"{ident}/{party.get('name','?')}: weapon {w} not in "
                        "game data")
    return problems


def independent_families(records):
    """The set of genuinely independent source families across records.
    Families are PER-AUTHOR (owner ruling 2026-08-21): `site:author` for
    ingested comps (albioncompo:bist, character_builder:clonepeek),
    `caller:<name>` for caller sheets. Two authors on the same site count
    as two families; copies of one author's build still count once.
    MetaBattle stays one family — a wiki is one editorial voice."""
    return {(r.get("source") or {}).get("family")
            for r in records if (r.get("source") or {}).get("family")}


def promotable(record):
    """A record may back or become a canonical default only when its OWN
    normalization is clean: a quarantined record (invalid spell index, bad
    reference) or a rejected one is evidence that needs fixing, not a
    default to ship (review 2026-08-19 — the quarantined Enigmatic p5 build
    was reaching the dashboard as canonical through its comp-level
    approval)."""
    return record.get("status") not in ("quarantined", "rejected")


def canonical_eligible(records):
    """(ok, basis) — may these records back one canonical default? (§F)
    Quarantined/rejected records carry no promotion weight."""
    records = [r for r in records if promotable(r)]
    if not records:
        return False, "no non-quarantined record"
    approved = [r for r in records
                if (r.get("approval") or {}).get("status") == "approved"]
    armory = [r for r in records
              if (r.get("source") or {}).get("kind") == "armory_manual"]
    fams = independent_families(records)
    if armory and (len(fams) >= 2 or approved):
        return True, "armory evidence + independent validation"
    if len(fams) >= 2:
        return True, f"{len(fams)} independent source families agree"
    for r in approved:
        basis = (r.get("approval") or {}).get("basis", "")
        if "shotcaller" in basis:
            return True, "explicit shotcaller approval"
    return False, ("single source family, no armory evidence, no shotcaller "
                   "approval")


APPROVAL_RANK = {"approved": 0, "candidate": 1, "normalized": 2,
                 "raw": 3, "stale": 4, "quarantined": 5, "rejected": 6}


def selection_order(records):
    """Displayed-build ordering for one (weapon, content) group (§F):
    clean records before quarantined/rejected ones, then approval, patch
    freshness (newer first), confidence/source agreement, stable id. NEVER
    `variants[0]` of arrival order."""
    return sorted(records, key=lambda r: (
        0 if promotable(r) else 1,
        APPROVAL_RANK.get((r.get("approval") or {}).get("status"), 9),
        _neg_date(r.get("patch")),
        -sum(v for v in (r.get("confidence") or {}).values()
             if isinstance(v, (int, float))),
        r.get("build_id") or ""))


def _neg_date(d):
    """Sort helper: newer ISO date first, unknown last."""
    if not d:
        return "9999-99-99"
    s = str(d)
    return "".join(chr(255 - ord(c)) for c in s)


# ------------------------------------------------- companion observations
def normalize_companion_party(party_json, weapon_lines, ingested=None,
                              hash_names=True):
    """Companion /party JSON -> loadout_observation records in the same
    item/spell schema (§D.3). The companion's roster with exact spell
    UniqueNames and IP is a direct party observation — the strongest
    observation source this project has. Personal identities are hashed
    unless explicitly kept."""
    import hashlib
    out = []
    for m in party_json.get("members", []):
        name = m.get("name") or ""
        pid = (hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
               if hash_names and name else name or None)
        weapon = m.get("weapon")
        spells = m.get("spells") or {}
        rec = {
            "kind": "loadout_observation",
            "observation": "companion_party",
            "player": pid,
            "weapon": weapon if weapon in weapon_lines else None,
            "weapon_raw": weapon,
            "spells": {s: spells.get(s) for s in SPELL_SLOTS},
            "equipment": m.get("equipment") or {},
            "ip": m.get("ip"),
            "observed": m.get("observed") or party_json.get("observed"),
            "ingested": ingested,
            "source": {"kind": "companion", "family": "companion:local",
                       "author": None},
            # an observation records what WAS, never what should be
            "status": "normalized",
            "unknowns": [s for s in SPELL_SLOTS if not spells.get(s)],
        }
        out.append(rec)
    return out
