# Castle Outpost Comp Book — Design

**Date:** 2026-08-27
**Status:** approved in chat section-by-section; this document is the written record
**Owner decisions embedded:** evidence-first clustering; all four evidence sources; correctness = comp + per-seat kits + budget tiers; vertical slice (castle outposts first); doctrine-coherence tests; stage gates between every step

## 1. Goal and end state

Extend the engine so it can answer, with evidence, "what comps exist in castle
outposts (7-man) and what should each player wear" — as the first vertical
slice of a five-content program (castle outposts, castle fights, territory
battles, faction warfare, blackzone roam). Every later content reuses this
slice's machinery; none of it is built content-specific except the data.

When the slice is done:

1. Content-labeled small-fight rosters exist in `pipeline/out/content_rosters.json`,
   with `castle_outpost` identified by an explicit, committed heuristic
   (zone table + size + wipe quality), each roster citing its battle id.
2. A deterministic builder (`pipeline/build_comp_clusters.py`) mines those
   rosters into `pipeline/out/comp_clusters.json` — candidate comp kinds with
   prevalence, org/battle support, per-seat kits and IP. Display/evidence only.
3. The owner ratifies clusters in blind rounds; ratified kinds land in
   owner-ruled `pipeline/comp_book.yaml` (evidence-cited, release-blocking).
4. The kit doctrine layer and budget bands gain a content dimension for
   outposts (kits observed in outpost fights; IP bands from the same events).
5. Forge generation at castle_outpost can target a ratified comp kind through
   the predicate channel (generation-only; manual parties always score).
   The page gains a comp book surface showing ratified kinds with builds and
   budget tiers.
6. Gates exist per step (see §8): contract tests per artifact, fail-closed
   builders, doctrine-coherence tests, golden pins from rulings, parity.

**Out of scope for the slice:** the other four contents (machinery reuse
comes after), Roads, any scoring change (comp kinds stay descriptive +
generation-gating, never scoring inputs), per-slot price modeling, and any
budget-aware scoring lens.

**Flagged risk:** whether the albionbb API exposes enough zone/context to
identify outpost fights reliably is unverified. §3's scouting step answers it
cheaply; if segmentation proves weak, the fallback is owner-confirmed labeling
of mined candidate fights.

## 2. Approach (chosen: extend existing machinery end-to-end)

Approach A from the chat design round: every stage reuses a pattern the repo
already trusts — sampler discipline from `sample_rosters.py`, mining honesty
from `build_cohort_families.py`, owner-ruled constants from `roles.yaml`
need profiles, generation-only gating from the forge predicate channel, and
the blind-round validation loop from VALIDATION.md. The comp book display
surface absorbs what "approach B" (book-first) would have shipped, as the
display layer of stage 3. Rejected: folding evidence into template retuning
(hides comp kinds inside weights; collides with the anti-circularity rule).

## 3. Evidence layer: outpost-segmented sampling

**Scouting step first (throwaway, ~half a day):** one probe script against
`api.albionbb.com` answers on real data: (a) what battle-level fields exist
for small fights (zone/cluster name, timestamps, party counts), (b) how far
`minPlayers` can drop before noise drowns signal (outpost fights are ~14–20
total players), (c) whether kill events carry full victim/killer equipment +
average item power (feeds kits and budget). The design assumes zone names are
present; if not, the fallback in §1 activates.

**Sampler change:** `sample_rosters.py` gains a `--band small` mode (or a
sibling `sample_small_fights.py` if the code diverges too much — decided at
implementation by whichever keeps the existing `roster_mixes.json` artifact
byte-stable):

- Listing filter drops to `minPlayers≈14`, capped ~30 total players, with the
  kill-density gate rescaled for small fights.
- Each cached battle gets a **content verdict** from an explicit rule table:
  `castle_outpost` = zone in the outpost zone list AND each side ≤ 9
  attributed players; everything else `unlabeled`, never guessed. The zone
  list is committed human-readable YAML (`pipeline/content_zones.yaml`) —
  auditable and correctable, in the spirit of `effect_overrides.yaml`.
- Wiped-side discipline carries over unchanged: deaths ≥ 80% of attributed
  players = near-complete roster; winner sides bucketed separately, never
  merged. All biases recorded in output `_meta`.

**Output:** `pipeline/out/content_rosters.json` — per roster: content label,
weapon list, per-player equipment (chest/head/shoes/cape) + average IP where
events carry it, battle id, org hash. Org identifiers never enter anything
the page embeds. Explicit network step only; `--pages 0` re-analyzes the
cache offline, deterministically.

**Labeled ingest for the other three sources:** albioncompo/MetaBattle records
mapping to outposts get `content: castle_outpost` through the existing
ingesters via a committed mapping table from their activity tags to our
contents; owner-submitted comps are ordinary `published_comp` records.

## 4. Clustering: `pipeline/build_comp_clusters.py`

**Two-level method built on the role layer** (weapon-exact clustering
over-fragments; whole-basket distance clustering already failed on partial
data — see `build_cohort_families.py` header):

1. **Shape first:** each near-complete roster maps to its seat signature via
   the existing role book (`detect_role` over observed weapon + worn kit).
   Rosters group by identical signatures, then signatures differing by
   exactly one seat substitution merge into the larger group (deterministic:
   process signatures in descending support, lexicographic tie-break) —
   candidate **comp shapes**.
2. **Cores within shape:** inside each shape, mine recurring weapon cores
   greedily and disjointly (the cohort-families algorithm, allowed beyond
   pairs since rosters are near-complete). Every cluster records: seat
   signature, core weapons with per-seat observed alternatives and shares,
   support counts (rosters / distinct orgs / distinct battles), per-seat kit
   and IP aggregates.

**Honesty gates (verbatim in spirit from cohort families):** minimum
rosters/orgs/battles per cluster — provisional thresholds chosen by
inspecting the first real sample, revisited only with more data, never
loosened until clusters appear; weapon keys filtered against the built
dataset; pure counting, lexicographic tie-breaks, LF output; runs after
`build_dataset.py`.

**Stated bias:** near-complete rosters are mostly wiped sides — the comps
that died. Clusters describe what the community fields, never what wins.
Win-context is reported per cluster (share of rosters that were the wiped
side) and is explicitly non-evaluative. Recorded in artifact `_meta` and the
page copy (KILLBOARD_AFFINITY.md discipline).

**Artifact:** `pipeline/out/comp_clusters.json`, deterministic ordering;
battle ids kept for audit; org identifiers never in the page embed. Display/
evidence only — nothing in scoring reads it. Published-comp sources do not
enter the clustering math; they are shown beside clusters at ratification so
intent-labeled and observed evidence stay distinguishable.

## 5. Ratification: blind rounds and `pipeline/comp_book.yaml`

**Protocol (the VALIDATION.md loop, blind discipline unchanged):**

1. Each candidate cluster is presented as a case card: seat signature, core
   weapons + alternatives with shares, kit/IP aggregates, matching published
   comps, fight count — WITHOUT the engine's style label or fit verdicts.
2. The owner calls first: name / merge / split / kill. The call is logged in
   VALIDATION.md before the engine's label is revealed.
3. Disagreements convert same-day into a ruling, an override, or a golden
   pin. A mislabeling by the engine is a finding about the style/identity
   layer — a hypothesis for the owner under the anti-circularity rule, never
   an auto-retune.

**Book schema (owner-ruled constants, roles.yaml mold):**

```yaml
castle_outpost:
  - id: outpost_dive
    name: "Dive squad"
    ruled: 2026-09-01          # (example) owner ruling date; must match a VALIDATION.md round
    style: brawl               # must exist in styles.yaml
    size: 7
    seats: {engage_tank: 1, main_healer: 1, curse: 1, melee_dps: 3, ranged_dps: 1}
    core: [...]                # weapon keys; per-seat alternatives allowed
    evidence:
      clusters: [comp_clusters cluster ids]
      published: [published_comp record ids]
    kits: ...                  # per-seat kit doctrine refs (§6)
    budget: ...                # IP/cost band refs (§6)
    notes: "owner doctrine commentary"
```

**Build gates:** `build_dataset.py` parses the book fail-closed — unknown
weapon keys, seats not in the role book, styles not in styles.yaml, dangling
evidence citations all block the release. Uncited entries allowed only with
explicit `basis: owner_experience`. Book entries never touch scoring weights;
machine consumers are the forge's generation targets and the display layer.

## 6. Kits and budget tiers: the content dimension

**Kits.** The doctrine layer gains a second, parallel evidence class: kits
observed on killboard rosters in a specific content, cited by battle id —
kept distinguishable from curated reference builds in the artifact.

- `kit_options(seat)` grows a content parameter: with a `castle_outpost`
  target and ratified book entries, slot ranking prefers the content-observed
  doctrine tier; falls back to global seat doctrine when observations are
  thin (explicit minimum-count threshold; the UI states which tier it shows —
  never a silent fallback).
- Unmoved invariants: chest pool hard-gates to the seat uniform; passive
  doctrine stays dumps-resolved; `cc_mult_caps` stays a physics channel;
  generated kits only — manual builds always score.
- Parity-carried: `kit_options` changes land in both engine ports with cases.

**Budget tiers.** Item power is not in the dumps and never enters a score.

- The cluster artifact carries observed IP distributions (median/quartiles)
  per content and per cluster.
- The owner rules named bands per book entry (e.g. budget/standard/prime)
  with approximate IP ranges and gear-tier guidance — owner-ruled constants
  informed by evidence, the need-profiles pattern.
- Machine consumers: display (bands shown with the ratified comp), and
  optionally the existing cost gate (`off_budget`) tightening at generation
  when the user selects a band. Scoring untouched; manual picks always score,
  flagged in swap review.

## 7. Forge and UI integration

**Forge:** a comp-book target rides the predicate channel, the need-profiles
pattern:

- Seat bands from the entry's `seats` map feed the forge predicates; per-slot
  suggestion pools prefer the entry's per-seat core + observed alternatives,
  then the normal capability-ranked pool.
- Generation-only, pinned by a new F-series test. Manual parties always
  score; a manual off-book pick is flagged `off_book` in swap review
  (joining `off_comp`/`off_style`/`off_budget`), never blocked or penalized.
- No book entry selected → forge behaves exactly as today. The book is
  additive.

**Identity:** `comp_identity` gains a descriptive book matcher — "matches
*Dive squad* (castle outpost), 6/7 seats aligned" — computed bottom-up from
the loaded party, golden-pinned to prove fitness is untouched. The matcher's
call vs the owner's is the ongoing blind-round signal.

**UI:** a comp book panel in the planner (source-edited in `dashboard/_app.js`
/ `_shell.html`, built by `build.py`): per content, ratified kinds as cards —
name, seat structure, core weapons with alternatives, per-seat kit doctrine,
budget bands, evidence line. One click loads the comp through the central
`data-add` handlers (loadout reset, provenance, role-sorting stay
centralized). The observed-evidence strip shows cluster prevalence beside the
book, clearly marked observed/display-only, with the wiped-side caveat in the
page copy; org ids never embedded.

**Both ports:** the book matcher and any `suggest_pool`/forge changes land in
`engine/engine.py` + `engine/app_scoring.js` with parity cases at 1e-9.

## 8. Testing, gates, and error handling

### 8a. Contract tests (script-style, exit 0 = pass)

- `tests/test_content_rosters.py` — step-1 gate: labels only from the ruled
  zone table, unlabeled never guessed, wiped-side rule enforced, LF and
  determinism on offline re-analysis, `_meta` completeness (schema version,
  zone-table hash, bias notes, counts).
- `tests/test_comp_clusters.py` — mirroring `test_cohort_families.py`:
  byte-identical determinism, disjointness, honesty gates enforced (a
  fixture below MIN_ORGS yields no cluster), no org ids in the artifact,
  weapon keys all in the dataset, wiped-side bias recorded in `_meta`.
- `tests/test_comp_book.py` — schema; weapon keys/seats/styles resolve
  against dataset + role book + styles.yaml; evidence citations
  dangle-checked; `basis: owner_experience` required when uncited; `ruled:`
  date cross-checked against a VALIDATION.md round; LF discipline.
- New F-series case in `tests/test_forge.py` — `off_book` contract: book
  targets shape generation pools only; a manual off-book party's score is
  bit-identical with and without a book target selected.
- New golden cases in `tests/test_golden.py` — one per ratification-round
  disagreement; plus a pin that the book matcher never moves fitness.
- `tests/test_js_parity.py` extension — book matcher, content-aware
  `kit_options`, pool changes; the embedded browser fixture gets a
  book-targeted case.
- `tier2_blindtest` gains castle_outpost leave-one-out cases once enough
  labeled comps exist. Honestly stated: this may trail the slice — "not
  enough evidence yet" is a reported state, never a fudged pass.

### 8b. Doctrine-coherence tests (`tests/test_doctrine.py`)

Semantic truth of forged output, not just contracts. Core mechanism:
**generation–analyzer agreement** — the forge builds top-down from a
style/book target; `comp_identity` labels bottom-up from the party alone
(independent code path). Forge a comp requesting style S at content C → the
bottom-up label must be S, every member fit verdict "fits", no analyzer
light red.

Style-truth cases (per style × validated size):

- **Kite/clap_kite disengage floor** — aggregate disengage + mobility supply
  meets the style's floor: every member has a personal escape OR the comp
  carries group disengage.
- **Cloth-on-DPS in kite styles** — for every DPS seat in a clap_kite/kite
  forge, `kit_options` top-ranks cloth chests (proves the seat-uniform +
  cloth-damage-passive chain end-to-end).
- **Clap burst concentration** — clap/clap_kite comps grade above floor on
  the `fight_chain` clap stage, with burst deliverable in-window per the
  style's delivery mechanics — not slow DoT supply that merely sums equal.
- **Brawl sustain/frontline floor** — brawl comps carry the engage tank and
  the sustain the chain's extended stages demand.
- **Chain completeness** — no stage of the style's fight chain grades zero
  with no member sourcing it.

Overstacking cases:

- **Saturation honesty** — no capability of a forged comp sits in
  `analyze`'s saturated band; supply overshoot beyond target + tolerance
  fails.
- **Non-stacking duplicates** — `duplicate_conflicts` empty on every forged
  comp, including the cursed-line rule, through the whole forge.
- **Function redundancy** — need-profile functions (pierce, heal-cut)
  covered but not tripled at sizes where one carrier suffices.

**Threshold discipline:** floors ("sufficient disengage", "enough sustain")
are judgment calls → owner-ruled constants captured during ratification
rounds, cited in the test file, never invented. Until a floor is ruled, its
case runs report-only (prints the measure, doesn't gate); findings become
blind-round material per the anti-circularity rule.

### 8c. Stage gates: each step blocks the next

Every step consumes the previous step's artifact only through a validated
contract (the `build_dataset.py` fail-closed pattern, extended):

1. **Sampler → rosters:** `content_rosters.json` `_meta` carries schema
   version, zone-table hash, bias notes, counts. `test_content_rosters.py`
   is the gate.
2. **Rosters → clusters:** `build_comp_clusters.py` refuses to run (exit 2,
   loud) unless the rosters artifact passes contract check and
   `dataset-latest.json` is current; it stamps the SHA-256 of every input
   into its own `_meta` (source-manifest pattern). `test_comp_clusters.py`
   is the gate.
3. **Clusters → book:** `build_dataset.py` resolves every book evidence
   citation against the actual cluster artifact (ids exist, hashes chain
   back) and blocks the release on any dangle — a book entry cannot outlive
   or precede its evidence. Ratification is process-gated: `ruled:` dates
   cross-checked against VALIDATION.md.
4. **Book → kits/budget:** doctrine tiers and budget bands cite build ids /
   battle ids that must resolve; a content-observed tier below the
   minimum-observation threshold cannot be emitted as primary (fallback
   explicit, tested).
5. **Kits/forge → ship:** the forge sees book targets only through the built
   dataset (never raw YAML). Ship gate = full existing list — golden, forge
   F-series incl. `off_book`, parity with the book-targeted browser fixture,
   plus `test_doctrine.py` on every ratified entry.

Net effect: step N's builder will not run with step N−1 unverified, and
gates exist per artifact, not just at the end.

### 8d. Fail-closed placements

- `comp_book.yaml` parse/validation errors block `build_dataset.py` (like
  MASTERSHEET and style_overrides).
- `content_zones.yaml` unknown zone keys or an unparseable rule table fail
  the sampler run — never a silent label.
- Cluster building refuses to run before `build_dataset.py`.
- Sampler network steps stay explicit and out of normal builds; `--pages 0`
  re-analysis stays deterministic.

## 9. Standing invariants as acceptance criteria

- Clusters and rosters are display/evidence only — nothing in scoring reads
  them.
- The book gates generation pools only; manual parties always score.
- Anti-circularity: gate findings are hypotheses for the owner; template or
  style retunes the evidence suggests require an owner ruling.
- Unknowns stay explicit: unlabeled fights never receive a guessed content.
- Popularity is not effectiveness: cluster prevalence and win-context are
  descriptive, stated with the wiped-side bias, and never scoring inputs.

## 10. Sequencing within the slice

1. Scouting probe (throwaway) → go/no-go on zone segmentation.
2. Sampler `--band small` + `content_zones.yaml` + `test_content_rosters.py`.
3. `build_comp_clusters.py` + `test_comp_clusters.py`.
4. First blind round → initial `comp_book.yaml` + `test_comp_book.py` +
   golden pins + VALIDATION.md round log.
5. Content-aware `kit_options` + budget bands (both ports + parity).
6. Forge book targets + `off_book` + F-series case; identity book matcher +
   golden pin.
7. Comp book UI panel + page evidence strip.
8. `test_doctrine.py` (report-only where floors are unruled → ruled floors
   land as gates in follow-up rounds).

Steps 2–3 are useful standalone even if later steps slip: labeled evidence
accumulates from the moment step 2 lands.
