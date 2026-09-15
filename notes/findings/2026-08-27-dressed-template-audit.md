# Dressed template audit — summary (2026-08-27)

Findings record. Artifact: `pipeline/out/dressed_template_audit.json`
(`py -3 pipeline/audit_dressed_templates.py`). REPORT-ONLY: a template
retune needs a maintainer decision (anti-circularity, `tests/VALIDATION.md`).

## Context

16 published-comp parties audited across 4 fitted templates (9 further comps map via the content-covers table; hellgate/bomb-squad/tracking comps have no template and are listed skipped). Four supply states per party: weapon-only, +recorded combos, +actual recorded gear ("dressed"), +doctrine kits. Flags per capability: does gear ALONE flip target coverage, break the soft cap, clear a hard floor; is the gear delta ≥50% of target (threshold PROVISIONAL).

## Finding: capabilities most affected by gear (dressed vs combo, % of target)

| capability | worst template mean delta | pattern |
|---|---|---|
| **tankiness** | **+419% → +622% everywhere** | breaks the soft cap in 11/12 large-template parties; the single largest distortion in the model |
| mobility | +109% → +451% | flips target in most 7-man comps; 23 gear items supply it |
| peel | +88% → +442% | soft cap broken in most blackzone/territory parties |
| purge | +132% → +222% | soft cap broken in 4/4 territory parties (roads too) |
| damage_debuff | +266% (blackzone) | target flipped in 3/4 parties from a 0.9-unit target |
| heal_sustain / heal_burst | +40% → +77% | meaningful but bounded — only 2–3 heal items exist |
| resist_shred | +39% → +77% | modest; pierce stays weapon territory |

Frequently-saturated set (soft cap exceeded once dressed, most parties): tankiness, peel, purge, mobility, heal_sustain (large templates).

### Hard-floor anomalies

None on the real comps — every published comp clears its floors on weapons alone (`gear_clears_floor` 0/16 across the board). The floor anomaly appears only in adversarial no-tank parties (`pipeline/out/frontline_floor_audit.json`): ordinary doctrine gear alone clears the castle-outpost tankiness floor from a standing start of zero. See the tankiness/frontline finding.

### Suspicious soft-cap behavior

The soft caps were comp-fitted (2026-08-21) in weapon-loadout units, pre-dating both dressed evaluation and the 129-piece catalog. Once dressed, real comps sit 1.5–6× above the caps on the affected capabilities, so the over-stack asymptote (`overstack_max 0.5`, x/(1+x)) — not the calibrated band structure — is doing the work, and marginal supply of these caps is near-worthless. This is the supply-side mechanism behind the dressed V4 role-demand collapse.

## Evidence

Hand-verified anchor: blap tankiness 13.0 naked → 54.56 dressed vs target 9.2 / soft 13.4; a plate-chested Occult gains +3.22u (more than Heavy Mace's own 2.0u weapon supply). The artifact carries, per comp-party × capability: target, soft cap, floor, the four supply states, coverage, the gear delta and the four flags.

## What this audit does not license

No retune. The template unit scale and the dressed supply live in different currencies; which currency each rule reads (floors: Option C in the tankiness finding; targets and soft caps: the calibration validation rounds) is a decision, not a patch.

## Changes

None in this pass. Follow-up 2026-08-29: the unit half of this finding was answered by the unit re-fit (targets and soft caps now speak person units — `tests/VALIDATION.md` "THE UNIT RE-FIT"); the floor half by Option C (hard floors read weapon+loadout supply only).
