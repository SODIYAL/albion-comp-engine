"""MASTERSHEET.md — the expert's single control surface (2026-08-20).

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
    sheets      -> {WEAPON: {cap: score}} — expert score overrides applied
                   to the composed rows BEFORE loadout bundling, so they
                   flow into caps, bundles and the JS engine identically
    guild_builds-> free-form data, shipped verbatim into the dataset for
                   display / future prior layers; never scored directly

FAIL-CLOSED: an unknown section, an unknown content/weapon key, or a
non-dict block is a build ERROR (exit 2) — a typo must never silently do
nothing. build_dataset prints what was overridden and stamps the counts
into _meta.mastersheet.
"""
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


def load(path=PATH):
    """{section: merged dict} from every tagged block, or {} if no file.
    Raises ValueError on unknown sections or unparseable blocks."""
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8").read()
    out = {}
    for m in _BLOCK_RE.finditer(text):
        section, body = m.group(1), m.group(2)
        if section not in SECTIONS:
            raise ValueError(
                f"MASTERSHEET.md: unknown tune section '{section}' "
                f"(known: {', '.join(SECTIONS)})")
        try:
            data = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            raise ValueError(f"MASTERSHEET.md tune:{section}: bad yaml — {exc}")
        if data is None:
            continue                      # empty block = no overrides
        if not isinstance(data, dict):
            raise ValueError(
                f"MASTERSHEET.md tune:{section}: block must be a mapping")
        out[section] = deep_merge(out.get(section, {}), data)
    return out


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
