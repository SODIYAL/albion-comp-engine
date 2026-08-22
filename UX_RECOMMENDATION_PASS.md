# Decision-first UX pass

This branch implements the first surface-level recommendation from the ChatGPT review without changing CompEngine scoring.

## Goal

Make the first screen answer, in order:

1. Is this comp healthy?
2. What is the biggest problem?
3. What should the next player bring?
4. Why does that pick help?
5. What remains weak afterwards?

The existing wheel, weakness list, capability board, evidence drawer, killboard prevalence, loadouts and live-party tooling remain available as deeper analysis.

## What is implemented

- A **Comp status** summary derived from current hard floors, weighted deficits and overstacking.
- A **Biggest need** card that promotes a hard-floor failure ahead of softer deficiencies.
- A **Best next pick** hero card using the existing recommendation result, existing `whySentence()`, and existing marginal explanation terms.
- A **Still weak after this pick** preview calculated in the one-ahead engine context.
- Fitness is retained as a compact summary rather than the main headline.
- No scoring constants, capability values, templates, priors or recommendation ordering are changed.

## Preview

The normal production page is intentionally untouched while this UX direction is reviewed.

```bash
py -3 pipeline/build_dashboard.py
py -3 pipeline/build_ux_preview.py
```

Then open `dashboard/ux-preview.html`. The second command also writes `docs/ux-preview.html` for a branch deployment workflow.

## Files

- `dashboard/_decision_layer.js` — translation layer over existing engine/UI state.
- `dashboard/_decision_layer.css` — decision-first presentation.
- `pipeline/build_ux_preview.py` — injects the layer into the normal generated dashboard for review.

## Next passes if approved

- Replace generic killboard prevalence with roster-contextual co-occurrence/affinity once battle-level composition data is available.
- Add player weapon-pool candidate filtering.
- Add swap-impact comparison (before/after capability deltas).
- Add a playstyle-derived fight-chain visualization as explanation only, not a second scoring model.
