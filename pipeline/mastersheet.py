"""MASTERSHEET.md — the single control surface for curation overrides.

The repo-root MASTERSHEET.md is a literate config: prose explains the
system in plain language, and fenced yaml blocks tagged `tune:<section>`
carry values that OVERRIDE the scattered source files at build time:

    ```yaml tune:scoring
    weights: {alpha: 0.55}
    ```

Sections and what they override (deep-merge: dicts merge, scalars and
lists replace):

    scoring     -> templates/scoring.yaml   (weights, capability_synergies,
                                             meta_prior, swap_advisor)
    mechanics   -> templates/mechanics.yaml (aoe_geometry, ...)
    templates   -> {content: {cap: {target/weight/soft_cap/scales}}}
                   merged into each content template's requirements
    sheets      -> {WEAPON: {cap: score}} — curated score overrides applied
                   to the composed rows BEFORE loadout bundling, so they
                   flow into caps, bundles and the JS engine identically
    guild_builds-> free-form data, shipped verbatim into the dataset for
                   display / future prior layers; never scored directly

FAIL-CLOSED: an unknown section, an unknown content/weapon key, or a
non-dict block is a build ERROR — a typo must never silently do nothing.
tune:sheets holds its own contract at parse time: every key is a weapon
key (MAIN_* / 2H_*) mapping capability names to an int 0-7, where 0
removes the composed row and 1-7 is the sheet scale; a float, a bool, a
value outside 0-7 or an empty mapping is a build ERROR. build_dataset
prints what was overridden and stamps the counts into _meta.mastersheet.
"""
import datetime
import os
import re

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
PATH = os.path.join(ROOT, "MASTERSHEET.md")

SECTIONS = ("scoring", "mechanics", "templates", "sheets", "guild_builds")

_BLOCK_RE = re.compile(
    r"^```yaml[ \t]+tune:([a-z_]+)[ \t]*\r?\n(.*?)^```[ \t]*$",
    re.M | re.S)

# tune:sheets contract: combat weapon keys as weapon_lines.json spells them
# (MAIN_* / 2H_*), capability names in snake_case, the sheet scale with 0
# as the removal.
_WEAPON_KEY_RE = re.compile(r"^(?:MAIN|2H)_[A-Z0-9]+(?:_[A-Z0-9]+)*$")
_CAP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHEET_SCORE_MAX = 7


def load(path=PATH):
    """{section: merged dict} from every tagged block, or {} if no file.
    Raises ValueError on unknown sections, unparseable blocks or a
    tune:sheets value outside its contract."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def parse(text):
    """{section: merged dict} from the tagged blocks of MASTERSHEET text
    (load() reads the file; the gate tests call this directly)."""
    out = {}
    for m in _BLOCK_RE.finditer(text):
        section, body = m.group(1), m.group(2)
        if section not in SECTIONS:
            raise ValueError(
                f"MASTERSHEET.md: unknown tune section '{section}' "
                f"(known: {', '.join(SECTIONS)})")
        try:
            data = yaml.safe_load(body)
        except (yaml.YAMLError, ValueError) as exc:
            raise ValueError(f"MASTERSHEET.md tune:{section}: bad yaml — {exc}")
        if data is None:
            continue                      # empty block = no overrides
        if not isinstance(data, dict):
            raise ValueError(
                f"MASTERSHEET.md tune:{section}: block must be a mapping")
        if section == "sheets":
            problems = sheet_override_problems(data)
            if problems:
                raise ValueError("MASTERSHEET.md tune:sheets: "
                                 + "; ".join(problems))
        out[section] = deep_merge(out.get(section, {}), _jsonify(data))
    return out


def sheet_override_problems(data):
    """Every way one tune:sheets block breaks its contract: {WEAPON: {cap:
    score}} with WEAPON a weapon key, cap a capability name and score an
    int 0-7 (0 removes the row, 1-7 is the sheet scale). Each block is
    checked before the merge, so a value a later block replaces is held to
    the contract too."""
    problems = []
    for weapon, caps in data.items():
        if not isinstance(weapon, str) or not _WEAPON_KEY_RE.match(weapon):
            problems.append(f"{weapon!r} is not a weapon key (MAIN_* or 2H_*)")
            continue
        if not isinstance(caps, dict) or not caps:
            problems.append(f"{weapon} must map capabilities to scores, "
                            f"not {caps!r}")
            continue
        for cap, score in caps.items():
            if not isinstance(cap, str) or not _CAP_NAME_RE.match(cap):
                problems.append(f"{weapon}: {cap!r} is not a capability name")
            elif isinstance(score, bool) or not isinstance(score, int):
                problems.append(f"{weapon}.{cap}: {score!r} is not an "
                                f"integer score")
            elif not 0 <= score <= SHEET_SCORE_MAX:
                problems.append(f"{weapon}.{cap}: {score} is outside "
                                f"0-{SHEET_SCORE_MAX}")
    return problems


def _jsonify(node):
    """yaml parses bare dates (YYYY-MM-DD) into datetime objects, which
    json.dump rejects — normalize them (and any other non-JSON scalar) to
    strings so a mastersheet edit can never crash the dataset write."""
    if isinstance(node, dict):
        return {k: _jsonify(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_jsonify(v) for v in node]
    if isinstance(node, (datetime.date, datetime.datetime)):
        return node.isoformat()
    if node is None or isinstance(node, (str, int, float, bool)):
        return node
    return str(node)


def deep_merge(base, over):
    """dicts merge recursively; scalars and lists REPLACE."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return over
    merged = dict(base)
    for k, v in over.items():
        merged[k] = deep_merge(merged[k], v) if k in merged else v
    return merged


def describe(tune):
    """One-line human summary per section for the build log."""
    lines = []
    for section, data in sorted(tune.items()):
        if section == "sheets":
            n = sum(len(v) for v in data.values() if isinstance(v, dict))
            lines.append(f"sheets: {n} score override(s) on {len(data)} weapon(s)")
        elif section == "templates":
            n = sum(len(v) for v in data.values() if isinstance(v, dict))
            lines.append(f"templates: {n} requirement override(s) in {len(data)} content(s)")
        elif section == "guild_builds":
            lines.append("guild_builds: present (shipped verbatim)")
        else:
            lines.append(f"{section}: {', '.join(sorted(data))}")
    return lines
