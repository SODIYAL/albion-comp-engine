# Decision-first UX pass

This branch implements the surface-level recommendation from the ChatGPT review without changing CompEngine scoring.

## Goal

Make the first screen answer, in order:

1. Is this comp healthy?
2. What is the biggest problem?
3. What should the next player bring?
4. Why does that pick help?
5. What remains weak afterwards?

The weapon wheel, capability board, evidence drawer, killboard prevalence, loadouts and live-party tooling remain available as deeper analysis.

## What is implemented

- A **Comp status** summary derived from current hard floors, weighted deficits and overstacking.
- A **Biggest need** card that promotes a hard-floor failure ahead of softer deficiencies.
- A **Best next pick** hero card using the existing recommendation result, existing `whySentence()`, and existing marginal explanation terms.
- A **Still weak after this pick** preview calculated in the same one-ahead context and with the same resolved loadouts used by the recommendation engine.
- Fitness is retained as a compact supporting summary rather than the headline.
- The previous right-hand fitness/weakness/recommendation flank is removed from the visible layout because it duplicated the new decision surface. Its underlying render code remains untouched.
- The wheel is retained as the exploration tool beneath the caller-first answer.
- The full capability board remains below as the deep diagnostic layer.
- No scoring constants, capability values, templates, priors or recommendation ordering are changed.

## This is now the real branch UI

There is no separate preview build anymore. The normal builder includes the decision layer:

```bash
py -3 dashboard/build.py
```

That generates the branch's normal `dashboard/index.html` and `docs/index.html` with the decision-first hierarchy included.

## Files

- `dashboard/_decision_layer.js` — translation layer over existing engine/UI state.
- `dashboard/_decision_layer.css` — decision-first layout and hierarchy.
- `dashboard/build.py` — normal build path now injects both files into the generated dashboard and GitHub Pages output.

## Intentionally deferred

These are separate features rather than part of this hierarchy pass:

- Roster-contextual killboard weapon co-occurrence / affinity.
- Player weapon-pool candidate filtering.
- Swap-impact comparison (before/after capability deltas).
- Playstyle-derived fight-chain visualization as explanation only, not a second scoring model.
