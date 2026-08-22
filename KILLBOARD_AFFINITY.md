# Killboard affinity pass

This branch adds a second, display-only evidence channel beside CompEngine's mechanical recommendation.

## What changed

`pipeline/sample_battles.py` now preserves **observed organization cohorts** per fight-size bucket. A player joins a cohort only when the kill event itself states the same Alliance identity (preferred) or Guild identity. Anonymous players are excluded; ambiguous organization observations are excluded; cohorts need at least two observed players and two known weapons.

This is intentionally **not party reconstruction**. AlbionBB kill events do not state authoritative party membership or side rosters. The UI therefore says "observed together" / "organization cohort", never "teammates", "party", "winning comp", or "successful comp".

## Metrics shown

For the weapons already selected in the planner, the dashboard finds organization cohorts containing at least one selected weapon, or at least two once the user has selected two or more unique weapons. Candidate weapons are ranked by:

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
py -3 pipeline/build_dashboard.py
```

The first command rewrites `pipeline/out/weapon_usage_v2.json` with the new `cohorts` and `cohort_meta` fields. The second embeds it into the static dashboard.

## Important limitations

- fight size is still total battle size, not party size;
- organization cohort is an Alliance/Guild proxy, not a party;
- kill-event coverage is combatants observed in events, not every person present;
- selected abilities remain unknown;
- no win/loss or causal effectiveness claim is made;
- affinity is suppressed until the current bucket has at least eight usable cohorts;
- all killboard information remains display-only.

## Next step after validation

Once the cohort sample is large enough, the same baskets can support a stronger **partial-roster neighbour** view: show a few anonymized observed organization rosters that overlap the user's selected weapons, rather than only aggregating the candidate weapons across those neighbours. That should be reviewed before any clustering or empirical scoring work.
