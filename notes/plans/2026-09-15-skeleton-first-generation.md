# Skeleton-first generation — implementation plan

Spec: `notes/specs/2026-09-15-skeleton-first-generation-design.md`.
Owner ruling: 2026-09-15, "full autonomy". Every step ends with the gates
it touches green; nothing is committed here (the owner commits).

Status 2026-09-15: steps 1-11 done (step 4's regeneration of the style
board waits for the harvest checkout; a plan-tool step — the standoff
minimum — was added between 8 and 9 once the seat gate alone left the
forged kite reading as a clap). Log: `notes/validation/2026-09b.md`.

1. Record the "before" gates on the tree as found (it carries the
   uncommitted 2026-09-15 rho / Permafrost / ranged-override rulings).
2. `pipeline/derive_skeletons.py` → `out/skeletons.json` (training split,
   distinct rosters, seat typicals per exact size with windows, copy
   allowances per style × band, distinct-weapon stats). Print a board.
3. `pipeline/derive_role_counts.py --holdout-mod 5` (default) + `_split`;
   regenerate `out/role_counts.json`; `build_dataset.py` refuses a
   role-count artifact without a training split.
4. `pipeline/audit_style_rosters.py --holdout-mod 5` + `_split` in the
   evidence json; `derive_style_bands.py` carries it into the yaml header;
   `build_dataset.py` prints whether the committed board honours it.
5. `build_dataset.py`: `load_skeletons()` (hash-gated, split-gated,
   validated), attach `composition.skeleton` and
   `composition.duplication.per_weapon_cells`; refuse a hand `per_weapon`;
   retire the hand list in `composition.yaml` (citations kept as comment).
6. Engine, Python: `seat_of`, `_seat_typical`, `_dup_cell`, `_forge_counts`
   seat keys, `_forge_ctx` seat context, `_typ_ok` seat branch.
7. Engine, JS: the same, line for line where the ports already mirror.
8. `tests/test_skeletons.py`; update `tests/test_forge.py` F18 pins to the
   generated allowances; rebuild dataset + dashboard; run every gate; fix
   what the ruling explains, investigate what it does not.
9. `tests/tier2_blindtest.py --baseline` for v4 and v4h; run both and
   record the numbers.
10. Forge probes after: identity of the forged kite / balanced / hybrids at
    20, distinct-weapon counts, overlap with the real kite 20 — the
    numbers the assessment measured, re-measured.
11. Docs: HANDOFF, CLAUDE.md gate list, MASTERSHEET dial table, BACKLOG
    (done / deferred with reasons), `tests/VALIDATION.md` index rows and
    standing-rule amendments, `notes/validation/2026-09b.md` log,
    `pipeline/README.md` rerun order, `.github/workflows/gates.yml`.
