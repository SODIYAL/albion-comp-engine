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
- **Validation affordances** (2026-08-27, both ports, parity-pinned):
  `set_dressing(false)` makes every CANDIDATE evaluate naked through the
  identity short-circuit into the naked scorer — the V3-W symmetric
  weapon-only mode; same formula, no second scoring path; default is
  dressed and nothing in the product turns it off. Python-only:
  `BION_DATASET` overrides the default dataset PATH so the calibration
  sweep can point test suites at patched coefficient copies — path
  plumbing, never set in production or normal test runs.
- **Synergy is weapon-interaction synergy** (documented 2026-08-27):
  `synergy()` deliberately prices weapons only — worn-gear capabilities
  count in fitness, never in the pair bonuses (finding:
  `docs/superpowers/findings/2026-08-27-gear-synergy-finding.md`).
- **Structural floors are source-aware** (Option C, owner ruling
  2026-08-27): hard floors read the weapon+loadout supply in `fitness`
  and every marginal path — worn gear improves coverage/headroom/
  overstack, never floor relief, on parties AND candidates alike.
- **Locked gear is sacred** (owner ruling 2026-08-27):
  `forge(locked_gears=)` scores a locked member in exactly the supplied
  kit and never re-dresses it (naked when none — nothing is invented);
  `refine(gears=)` runs the dressed local search and returns
  `{party, gears}` (gears=None keeps the legacy weapon-only list).
- **Never** reads UI state, killboard/usage evidence, or reference builds —
  those are display-only layers by standing rule (popularity is not
  effectiveness).

Score semantics live in `MASTERSHEET.md` (the expert control surface — its
`tune:` blocks override the underlying config at build time) and the design
doc. Forge STRUCTURE (role bands, need profiles, style bands) is owner-ruled
data in `pipeline/roles.yaml` + `pipeline/templates/` — shipped inside the
dataset, generation-only, never a bar to scoring a manual party. Regression
truth lives in `tests/test_golden.py`, `tests/test_forge.py` and
`tests/test_roles.py`.
