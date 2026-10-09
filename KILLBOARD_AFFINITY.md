# Killboard affinity pass

A second, display-only evidence channel beside CompEngine's mechanical
recommendation. Originated in PR #5; the cohort and observed-context
surfaces were integrated into the mainline dashboard. The decision-first
surface itself landed separately via PR #4 and was kept as the headline UI,
with its regressions repaired on main: the forge honesty reports
(`#warn-slot`) are never hidden — placed per width band by
`dashboard/_layout.css` since the density redesign — the click-to-add
alternatives live inside the pick card, the observed-context note and the
after-pick preview render in both the pick card and the why-panel, and the
layout overrides follow the shell's own breakpoints instead of `!important`.

## What a cohort is

A cohort is one **killer party**: the group the kill event itself lists
(`GroupMembers` on the official API, harvested by
`pipeline/sample_parties.py` into `out/party_rosters.json.gz` and
deduplicated per battle by member overlap). `pipeline/derive_usage.py`
derives the cohorts and the fight-size prevalence from that artifact,
offline, into `pipeline/out/weapon_usage_v2.json`. The party harvest is the
one killboard sampler.

The frame is every harvested battle of 6+ players that started in the 28
days before the newest battle in the artifact. Two axes are kept apart:

- **prevalence** is by FIGHT size (total players, both sides) over
  combatants with a build: killers, victims and kill participants;
- **cohorts** are by PARTY size: a party of N keys to the bucket a fight of
  2N falls in (2-5 / 6-15 / 16+), so a 20-man plan reads parties of 16-20
  and never a five-man squad inside a large fight.

Each bucket keeps at most 1,000 parties, spread evenly over the window
(`cohort_meta` states the parties in the window beside the parties kept).
A cohort needs two members and two distinct catalogue weapons.

The page embeds only the anonymous weapon baskets per bucket
(`cohort_baskets`, as indexes into `cohort_keys`): guild names and battle
ids stay in `pipeline/out/weapon_usage_v2.json` for audit and never enter
the page.

A killer party scored at least one kill (the harvest's inclusion rule), so
the cohorts lean to the winning side. The UI therefore says "killer
parties" and "fielded together", never "winning comp" or "successful comp".

## Metrics shown

The bucket quoted is the size the comp is **planned for** (`usageBucket()` = 2 × `PLAN()`), not the roster count added so far — a 20-man plan quotes parties of 16+ from its first pick. For the weapons already selected in the planner, the dashboard finds killer parties containing at least one selected weapon, or at least two once the user has selected two or more unique weapons. Candidate weapons are ranked by:

1. number of matching parties;
2. pair affinity (lift) as a tie-breaker;
3. average partial-roster overlap.

Pair affinity for weapons A and B is:

`P(A and B) / (P(A) * P(B))`

implemented as `both * N / (countA * countB)` over the killer parties in the current bucket. This corrects for globally popular weapons: a ubiquitous weapon does not look special merely because it appears often.

## Recommendation integration

None. This is deliberate.

The engine's recommendation score, capability values, templates, priors, viability rules, floors, synergies and recommendation order are unchanged. The best-next-pick card may show an observed-context note for the engine's pick, but that note is evidence alongside the recommendation, not an input to it.

The generic killboard prevalence strip becomes contextual when the current bucket has cohort data and the roster has a weapon; thin data falls back to the prevalence view.

## Refreshing the data

`pipeline/fold_harvest.ps1` runs it weekly. By hand:

```bash
py -3 pipeline/derive_usage.py
py -3 pipeline/build_cohort_families.py
py -3 dashboard/build.py
```

The first command rewrites `pipeline/out/weapon_usage_v2.json` from the full rosters artifact, `pipeline/out/party_rosters_full.json.gz` (every population, local; no network; the same artifact writes the same bytes); the second re-mines the observed families from it (`out/cohort_families.json` — skipping it ships new baskets against stale families); the third embeds both into the static dashboard. Analysis is a reviewed step (pipeline/README.md weekly cadence), never automated.

## Important limitations

- prevalence is by total battle size, not party size; cohorts are by party size, and side size is unknown on both;
- a kill-feed record's fight size is its roster rebuilt from the events, a lower bound;
- a killer party scored at least one kill: a side that scored none is not in the sample;
- a squad that fights several battles is several cohorts (the distinct-organization gate below is what keeps one squad from being a family);
- a party member who never killed, died or dealt damage is known by weapon alone;
- selected abilities remain unknown, and a loadout swap inside a battle is not observable;
- no win/loss or causal effectiveness claim is made;
- affinity is suppressed until the current bucket has at least eight usable cohorts;
- **mount-carrier bias** (verified on the Bloodletter case): battlemount pilots hold a high-mobility weapon they never fight with, so such weapons ride into cohort baskets without being comp slots — weapon presence in a cohort is "was held by a party member", not "was a fielded comp pick";
- all killboard information remains display-only.

## Partial-roster neighbours

The neighbour view is live (`cohortNeighbours()` in `dashboard/_app.js`, covered by `tests/test_display_math.js`): the contextual strip shows up to three anonymized killer-party baskets that share at least two of the selected unique weapons, ranked by shared count, then Jaccard similarity over unique weapons (a wide basket ranks below an exact roster echo), then original basket order. Shared picks are highlighted, the remaining weapons render as muted dossier links (capped at 14 icons with a "+N more" tail), and the full matched-party count is stated. A basket is the party's DISTINCT weapons: copies are not shown. All the limitations above apply verbatim; the copy says "observed rosters", never "winning comp".

## Recurring observed families

The clustering step shipped display-only as **anchor-pair families** (`pipeline/build_cohort_families.py` → `out/cohort_families.json`, embedded as `FAMILIES`, rendered as "Recurring observed cores" in both killboard-strip modes).

A family is the strongest recurring pair, its cohorts (removed from the pool — families are disjoint, counts never double-count), and the weapons fielded in ≥40% of those cohorts with their shares. The gates: the pair recurs in at least 2% of the bucket's usable cohorts (never under 5), across ≥3 distinct organizations and ≥3 distinct battles, at pair lift ≥1.2. An organization is a group of parties linked by a shared guild, transitively: a guild fielding its lineup with different guests each night is one organization. The cohort floor is a share so the gate keeps its meaning as the sample grows (at 1,000 cohorts a bucket, an absolute floor of 5 admitted 44 / 40 / 15 families at 2-5 / 6-15 / 16+). All thresholds are PROVISIONAL constants in the builder (curation judgment); revisit them with the sample, not by loosening gates until families appear.

Pairs, not roster clusters: two random killer parties share little (Jaccard over distinct weapons: median 0.00 / p90 0.17 at 2-5, 0.07 / 0.19 at 6-15, 0.22 / 0.41 at 16+). Whole-roster clustering was measured and rejected on the earlier partial-basket sample; on full parties it is untested.

The artifact carries counts only — guild names and battle identifiers stay in `weapon_usage_v2.json` — and `tests/test_cohort_families.py` pins determinism, disjointness, the gates, and the no-identifier rule. `tests/test_usage_derive.py` pins the derivation: the frame, the two axes, the even sample.

## Near-complete roster mixes (increment-3 evidence, frozen)

`out/roster_mixes.json` is a frozen record: kill-dense battles mined for near-complete sides (a side whose deaths enumerate ≥80% of its attributed players has its whole roster visible with equipment), with winner-side mixes reported separately and never merged. Per-band (gang/mid/party) seat mixes per 20, function coverage shares, healer distributions. Its sampler is retired: the artifact has no code reader, and the party harvest records killer parties, never a side that scored no kill, so it cannot re-derive a wiped side.

**The sanctioned uses**: (1) the roster mixes are the cited EVIDENCE behind the `need_profiles` constants in `pipeline/roles.yaml` — the profiles are curated constants, the artifact is why. (2) "Observed effect quotas" renders in the killboard strip (`effectQuotaRows()` in `dashboard/_app.js`, display-math case 14): the roster's SET chests counted against the median effect carriers near-complete reference rosters field — quota medians come from the reference-build evidence layer (`roles_report` `effect_quotas`), PLAN-scaled, armed at 15+, and members without gear set are counted as unknown, never as missing. Advice language only; nothing scores.

**Still parked behind review**: ANY empirical/scoring integration beyond the two sanctioned uses above and the harvest-generated meta prior (solo share and best observed partner — derived from `out/party_rosters.json.gz` on the training split, never from the display cohorts here; standing rule 7). Neighbours, families, roster mixes and quotas aggregate nothing into a score, a suggestion pool, or the forge's objective, and must stay that way without a logged decision in `tests/VALIDATION.md`.
