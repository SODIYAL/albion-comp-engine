# The Engine

The scoring core of Comp Forge, in two parity-locked ports:

- `engine.py` — the canonical implementation. Every scoring decision is
  authored here first.
- `app_scoring.js` — the browser twin, inlined into the generated dashboard
  by `dashboard/build.py`. **Change one, change both**, then rerun
  `py -3 tests/test_js_parity.py` (60 random parties, 1e-9 tolerance, plus a
  check that the built pages embed this exact source).

## Boundary

- **Consumes** exactly one input: `pipeline/out/dataset-latest.json`, built by
  the engine domain's data layer (`pipeline/` — sheets, templates,
  MASTERSHEET rulings, provenance gates). No other file feeds scoring.
- **Exposes** `CompEngine` (recommend / fitness / weaknesses / explain /
  swapReview / forge). The frontend calls this API and translates its
  output; it never computes a score of its own.
- **Never** reads UI state, killboard/usage evidence, or reference builds —
  those are display-only layers by standing rule (popularity is not
  effectiveness).

Score semantics live in `MASTERSHEET.md` (the expert control surface — its
`tune:` blocks override the underlying config at build time) and the design
doc. Regression truth lives in `tests/test_golden.py` and `tests/test_forge.py`.
