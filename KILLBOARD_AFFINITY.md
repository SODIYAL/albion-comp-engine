# Killboard affinity pass

A second, display-only evidence channel beside CompEngine's mechanical
recommendation. Originated in PR #5 (chatgpt/killboard-affinity); the
cohort sampler and observed-context surfaces were integrated into the
mainline dashboard (2026-08-22). The decision-first surface itself
landed separately via PR #4 and was kept as the headline UI, with its
regressions repaired on main: the forge honesty reports moved to a
full-width slot above the wheel stage (never hidden; since 2026-08-23 it
lives under the wheel), the click-to-add
alternatives live inside the pick card, the observed-context note and
the after-pick preview render in both the pick card and the why-panel,
and the layout overrides now follow the shell's own breakpoints instead
of `!important`.

## What changed

`pipeline/sample_battles.py` now preserves **observed organization cohorts** per fight-size bucket. A player joins a cohort only when the kill event itself states the same Alliance identity (preferred) or Guild identity. Anonymous players are excluded; ambiguous organization observations are excluded; cohorts need at least two observed players and two known weapons.

The page embeds only the anonymous weapon baskets per bucket
(`cohort_baskets`): organization identifiers and battle ids stay in
`pipeline/out/weapon_usage_v2.json` for audit and never enter the page.

This is intentionally **not party reconstruction**. AlbionBB kill events do not state authoritative party membership or side rosters. The UI therefore says "observed together" / "organization cohort", never "teammates", "party", "winning comp", or "successful comp".

## Metrics shown

The fight-size bucket quoted is the size the comp is **planned for** (`usageBucket()` = 2 × `PLAN()`, 2026-08-22 fix), not the roster count added so far — a 20-man plan quotes large-fight cohorts from its first pick. For the weapons already selected in the planner, the dashboard finds organization cohorts containing at least one selected weapon, or at least two once the user has selected two or more unique weapons. Candidate weapons are ranked by:

1. number of matching cohorts;
2. pair affinity (lift) as a tie-breaker;
3. average partial-roster overlap.

Pair affinity for weapons A and B is:

`P(A and B) / (P(A) * P(B))`

implemented as `both * N / (countA * countB)` over organization cohorts in the current fight-size bucket. This corrects for globally popular weapons: a ubiquitous weapon does not look special merely because it appears often.

## Recommendation integration

None. This is deliberate.

The engine's recommendation score, capability values, templates, priors, viability rules, floors, synergies and recommendation order are unchanged. The best-next-pick card may show an observed-context note for the engine's pick, but that note is evidence alongside the recommendation, not an input to it.

The old generic killboard popularity strip becomes contextual when cohort data exists. Older `weapon_usage_v2.json` files without `cohorts` automatically fall back to the previous prevalence view.

## Refreshing the data

Run:

```bash
py -3 pipeline/sample_battles.py --battles 200 --server us
py -3 dashboard/build.py
```

The first command rewrites `pipeline/out/weapon_usage_v2.json` with the new `cohorts` and `cohort_meta` fields. The second embeds it into the static dashboard.

## Important limitations

- fight size is still total battle size, not party size;
- organization cohort is an Alliance/Guild proxy, not a party;
- kill-event coverage is combatants observed in events, not every person present;
- selected abilities remain unknown;
- no win/loss or causal effectiveness claim is made;
- affinity is suppressed until the current bucket has at least eight usable cohorts;
- **mount-carrier bias** (owner-confirmed 2026-08-24, the Bloodletter case): battlemount pilots hold a high-mobility weapon they never fight with, so such weapons ride into cohort baskets without being comp slots — weapon presence in a cohort is "was held by an observed combatant", not "was a fielded comp pick";
- all killboard information remains display-only.

## Partial-roster neighbours — shipped 2026-08-24

The neighbour view described below is now live (`cohortNeighbours()` in `dashboard/_app.js`, covered by `tests/test_display_math.js`): the contextual strip shows up to three anonymized observed organization baskets that share at least two of the selected unique weapons, ranked by shared count, then Jaccard similarity over unique weapons (a huge alliance basket ranks below an exact roster echo), then original basket order. Shared picks are highlighted, the remaining weapons render as muted dossier links (capped at 14 icons with a "+N more" tail), and the full matched-cohort count is stated. All the limitations above apply verbatim; the copy still says "observed rosters", never "party" or "winning comp".

## Recurring observed families — shipped 2026-08-24 (owner-directed)

The owner directed the clustering step in-chat on 2026-08-24; it shipped display-only as **anchor-pair families** (`pipeline/build_cohort_families.py` → `out/cohort_families.json`, embedded as `FAMILIES`, rendered as "Recurring observed cores" in both killboard-strip modes).

Whole-roster clustering was measured and rejected for this sample: the baskets are partial observations (most carry 2–5 weapons of a full lineup), cross-org basket Jaccard has median 0.0 / p90 0.17, and the lift-gated co-occurrence graph collapses into one connected component at every threshold tried — distance clusters here would separate observation coverage, not compositions. Pairs are the largest itemset with real support, so a family is the strongest recurring pair (≥5 cohorts, ≥3 distinct organizations, ≥3 distinct battles, pair lift ≥1.2), its cohorts (removed from the pool — families are disjoint, counts never double-count), and the weapons observed in ≥40% of those cohorts with their shares. All thresholds are PROVISIONAL constants in the builder; revisit them with a larger sample, not by loosening gates until families appear (the small bucket yields zero families and must stay empty-handed until the data says otherwise).

The artifact carries counts only — organization and battle identifiers stay in `weapon_usage_v2.json` — and `tests/test_cohort_families.py` pins determinism, disjointness, the gates, and the no-identifier rule.

## Near-complete roster mixes — shipped 2026-08-26 (increment-3 evidence)

`pipeline/sample_rosters.py` (explicit network step, same sanctioned albionbb endpoint) mines KILL-DENSE battles and keeps only near-complete sides: a side whose deaths enumerate ≥80% of its attributed players has its whole roster visible with equipment — the least-biased roster snapshot kill events can give. Winner-side mixes are reported separately and never merged (healers/supports under-appear on winning sides — the standing support-undercount, now measured). Output: `out/roster_mixes.json` — per-band (gang/mid/party) seat mixes per 20, function coverage shares, healer distributions. All limitations above apply, plus: alliance-level sides can merge two parties (the band split discards >25 rows), and one sample = one meta window.

**The sanctioned uses** (owner directives 2026-08-26): (1) the roster mixes are the cited EVIDENCE behind the owner-ruled `need_profiles` in `pipeline/roles.yaml` — the profiles are constants the owner ruled, the artifact is why; a re-sample never retunes them by itself. (2) "Observed effect quotas" renders in the killboard strip (`effectQuotaRows()` in `dashboard/_app.js`, display-math case 14): the roster's SET chests counted against the median effect carriers near-complete reference rosters field — quota medians come from the reference-build evidence layer (`roles_report` `effect_quotas`), PLAN-scaled, armed at 15+, and members without gear set are counted as unknown, never as missing. Advice language only; nothing scores.

**Still parked behind review**: ANY empirical/scoring integration beyond the two owner-ruled uses above. Neighbours, families, roster mixes and quotas aggregate nothing into a score, a suggestion pool, or the forge's objective, and must stay that way without an explicit owner ruling.
