# Seat Pooling for Thin Slots — Implementation Plan

> **STATUS 2026-09-08: EXECUTED.** Shipped the same day (R34a/R34b; VALIDATION.md index 09-08 "Seat pooling"). The checkboxes below are the plan as written.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Where a weapon's slot evidence is thin (under 5 votes), dress the slot from the seat's chest-conditioned pool instead of a 2-4 player observation.

**Architecture:** The doctrine miner ships two player-counted pools per seat and band (`kit_pool`, `kit_by_chest`); the one kit reader in both engine ports applies the thin rule per slot after the existing tier/archetype ranking and marks pooled options. Tests pin the dataset shape, the mechanism, and the audit floor.

**Tech Stack:** `py -3`, script-style tests, `engine/app_scoring.js` (binary to grep), `dashboard/build.py`.

**Spec:** `notes/specs/2026-09-08-coherent-style-kits-design.md` section 3.

## Global Constraints

Same as `notes/plans/2026-09-08-coherent-style-kits.md`: `py -3`, LF writers, `git commit -F`, fail closed, both ports + parity, descriptive layers never score, manual kits always score, branch `blind-round-4-grading`, the full gate list before the PR update.

---

### Task 1: Ship the pools

**Files:** `pipeline/build_dataset.py` (`derive_kit_doctrine`, the killboard mining block and the `tgt[...]` writes), `tests/test_roles.py` (`t_seat_pools`, R34a).

**Interfaces:** on every seat record that has `kit`: `kit_pool: {slot: [[item, players], ...]}` (sorted by players desc, id asc; items with >= 2 players; slots head/shoes/cape/potion/food) and `kit_by_chest: {chest_id: {slot: [[item, players], ...]}}` (same slots, chest = the build's own normalized, uniform-legal chest). Gang band writes the same keys under `kit_bands.gang`. Style cells write none.

- [ ] Test R34a: every seat with `kit` carries `kit_pool` with only those five slots and integer player counts >= 2, `kit_by_chest` keyed by catalog chests of the seat's uniform classes (or a weapon's extension), and no style cell carries either key.
- [ ] Run roles, see R34a fail, implement in the killboard block (collect per seat: `pool_players[slot][item] = set(players)` and `chest_players[chest][slot][item] = set(players)` over `kept` builds of member weapons whose chest passes `seat_ok`/`weapon_ok`), write after `tgt["kit"]`, skip when `style is not None`.
- [ ] Rebuild, roles green, commit.

### Task 2: The thin rule in both ports

**Files:** `engine/engine.py` `kit_options` (after archetype fronting), `engine/app_scoring.js` `kitOptions` (same spot), `tests/test_roles.py` (`t_seat_pooling`, R34b), `tests/test_js_parity.py` (no change expected; kit cases carry the front item).

**Interfaces:** option keys `pooled` ("seat|chest" or "seat") and `pooled_n` (int). Engine constant `POOL_MIN_VOTES = 5` (Python class attr; JS `var POOL_MIN_VOTES = 5`). Pooled slots: head, shoes, cape, potion, food.

- [ ] Test R34b (mechanism on the dataset): find a seated weapon at 20 balanced whose head weapon-tier modal has < 5 votes and whose seat `kit_by_chest[chest of its kit][head]` top item has >= 5 players and differs from the thin item; `kit_options(w)["kit"]["head"]` is the pool item with `pooled == "seat|chest"`. And a weapon whose head modal has >= 5 votes keeps its own (no `pooled`). And a thin potion goes to `kit_pool["potion"]` top with `pooled == "seat"`.
- [ ] Run roles, see R34b fail, implement: in the slot loop after `options[slot] = ranked[:top_n]` is computed — actually before slicing: compute `thin = not wslot or max(wslot.values()) < POOL_MIN_VOTES`; if `thin and slot in POOLED_SLOTS and role is not None`: candidates = (`kit_by_chest[chest][slot]` if slot in (head, shoes, cape) and chest known) then `kit_pool[slot]`; the first `[item, players]` with `players >= POOL_MIN_VOTES` and `item` present in `ranked` moves to the front with `pooled`/`pooled_n` set. `chest` = `options["armor"][0]["gear"]` when armor was already ranked (sorted slot order puts armor first), else None.
- [ ] Mirror in JS; rebuild dashboard; parity 60/60; roles green; commit.

### Task 3: Audit floor, display, docs, gates

**Files:** `tests/test_roles.py` R24 (skip slots whose killboard modal has < 5 players, mirrored from R24b), `dashboard/_loadout.js` (engine-kit line names pooled slots), `pipeline/README.md`, `CLAUDE.md`, `HANDOFF.md`, `tests/VALIDATION.md`.

- [ ] R24: add the `who` player sets and `continue` when the modal has < 5 players; roles green.
- [ ] Loadout: prefill records `L._pooled = {slot: source}`; the engine-kit line appends "helmet/boots from the seat's <chest> wearers" style text; cleared with `_eng`.
- [ ] Docs + VALIDATION entry with the measurements above and the after-numbers (tiles by source).
- [ ] Full gate list (14, cohort from PowerShell), commit, push, update PR #18 body.
