# Dashboard Density Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Comp Forge planner's first screen as a four-column card grid with edge-anchored flyout panels, so capability supply, kill pressure, role check and caller tools are visible without scrolling.

**Architecture:** All layout rules consolidate into one new source file, `dashboard/_layout.css`, inlined last so it wins on source order without `!important`. The existing right-edge party panel (`.pdash`) generalises into a reusable `.epanel[data-edge]` component; the in-flow setup rail is deleted and becomes a left-edge panel. `.main` becomes a four-column grid at >=1700px. This is a display-layer change only — no scoring, engine, forge or pipeline code is touched.

**Tech Stack:** Vanilla HTML/CSS/JS single-file bundle. Python 3 bundler (`dashboard/build.py`). Script-style tests (NOT pytest) run directly with `py -3` / `node`.

**Spec:** `docs/superpowers/specs/2026-09-02-dashboard-density-redesign-design.md`

## Global Constraints

- **Branch:** `dashboard-density-redesign`, already created off `origin/main` (`12b4597`).
- **Windows environment:** use `py -3`, never `python`/`python3`. Commit messages MUST go via `git commit -F <file>` — PowerShell 5.1 mangles quoted here-strings into pathspec args. Write the message file BOM-less; `Set-Content -Encoding utf8` prepends a BOM that lands in the commit subject. Every commit step below writes it with `io.open(..., newline="\n")`.
- **`/tmp` does not exist for Windows Python.** Git Bash maps it, `py -3` does not — `io.open('/tmp/x')` raises `FileNotFoundError`. The commit steps below write to `.git/cm.txt`, which always exists and is never committed.
- **Never hand-edit generated pages.** `dashboard/index.html`, `dashboard/how-it-works.html`, `docs/index.html`, `docs/how-it-works.html` are build output. Edit the `_`-prefixed sources and run `py -3 dashboard/build.py`.
- **Display only.** No capability numbers and no scoring math may enter `dashboard/`. The only permitted engine calls are the twelve already present (pinned by the allowlist in Task 1).
- **Never pipe a build through `grep`/`tail`/`Select-Object`** in the same pipeline you read `$LASTEXITCODE` from — it masks the exit code. Run bare, or redirect to a file.
- **LF newlines.** Every writer of a committed artifact in `build.py` opens with `newline="\n"`.
- **`engine/app_scoring.js` reads as BINARY** to grep/ripgrep (embedded NUL byte). Use `Select-String` or the Read tool. You should not need to touch it.
- **Tests are script-style**, not pytest — they run at import and call `sys.exit`. Run each directly; exit 0 = pass.
- **Do not change** `#meta-sec` (killboard), scoring, forge structure, need profiles, the role book, or `_explainer.html`.

---

### Task 1: Layout contract test + `_layout.css` wired into the build

Establishes the test harness the rest of the plan is verified against, and the empty file every later task moves rules into.

**Files:**
- Create: `tests/test_dashboard_layout.py`
- Create: `dashboard/_layout.css`
- Modify: `dashboard/build.py:106-110`

**Interfaces:**
- Consumes: nothing.
- Produces: `dashboard/_layout.css`, inlined into `_shell.html`'s `<style>` block *after* `_decision_layer.css`. `tests/test_dashboard_layout.py`, a script-style test exiting 0 on pass and 1 on failure, with a `check(cond, label, detail="")` helper that later tasks add contracts to.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dashboard_layout.py`:

```python
"""Dashboard layout contracts.

Script-style (NOT pytest): runs at import, exits 0 on pass. The dashboard is
a display layer — these contracts pin the layout's structure and guard the
display-only boundary against new engine calls.

    py -3 tests/test_dashboard_layout.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "dashboard")

FAILURES = []


def read(name):
    with open(os.path.join(DASH, name), encoding="utf-8") as f:
        return f.read()


def check(cond, label, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s%s" % (label, (" — " + detail) if detail else ""))
        FAILURES.append(label)


SHELL = read("_shell.html")
DECISION_CSS = read("_decision_layer.css")
DECISION_JS = read("_decision_layer.js")
APP = read("_app.js")
LAYOUT = read("_layout.css")
BUILD = open(os.path.join(DASH, "build.py"), encoding="utf-8").read()

print("L1 — layout source exists and is wired into the build")

check(LAYOUT.strip() != "", "L1a _layout.css is non-empty")
check("_layout.css" in BUILD, "L1b build.py reads _layout.css")
check(
    BUILD.index("_decision_layer.css") < BUILD.index("_layout.css"),
    "L1c _layout.css is inlined AFTER _decision_layer.css",
    "source order is what lets layout rules win without !important",
)

print("L2 — display-only boundary: no new engine calls")

ENG_ALLOWED = {
    "compIdentity", "effectiveSupply", "fightChain", "fitness",
    "killPressure", "pickReport", "recommend", "roleAdvisory",
    "rolesBook", "target", "weaknesses", "weight",
}
used = set(re.findall(r"ENG\.([a-zA-Z_]+)", DECISION_JS))
check(
    used <= ENG_ALLOWED,
    "L2a _decision_layer.js calls only allowlisted engine members",
    "new: %s" % sorted(used - ENG_ALLOWED),
)

print("L2 (cont.) — roster mutations stay centralised")

for anchor in ["sortPartyByRole", "data-add", "data-swapat"]:
    check(anchor in APP, "L2b %s still routes roster mutation" % anchor,
          "layout work must not introduce a second mutation path")
check(
    APP.count("function sortPartyByRole") == 1,
    "L2c exactly one sortPartyByRole definition",
)

if FAILURES:
    print("\n%d contract(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall dashboard layout contracts pass")
sys.exit(0)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL — a `FileNotFoundError` on `_layout.css`, because the file does not exist yet.

- [ ] **Step 3: Create `dashboard/_layout.css`**

Create the file with only its header comment — later tasks fill it:

```css
/* LAYOUT — the single home for every rule that decides where things sit.
   Inlined LAST into _shell.html's <style> block by build.py, so these rules
   win on source order without needing !important. Component chrome (colour,
   type, borders, motion) stays in _shell.html and _decision_layer.css; only
   grid, flow, position, breakpoints and the edge-panel system live here.

   Owns: .shell / .main grid, .wheelstage / .ws-*, the .epanel edge-panel
   system, and every layout @media block. */
```

- [ ] **Step 4: Wire it into `build.py`**

In `dashboard/build.py`, immediately after the `_decision_layer.js` read (around line 108-110), add the read and change the single `</style>` replacement so layout follows decision CSS:

```python
    with open(os.path.join(DASH, "_decision_layer.js"), encoding="utf-8") as f:
        decision_js = f.read()
    # Layout is inlined LAST so its rules win on source order — see
    # dashboard/_layout.css and tests/test_dashboard_layout.py (L1c).
    with open(os.path.join(DASH, "_layout.css"), encoding="utf-8") as f:
        layout_css = f.read()
    shell = shell.replace("</style>", decision_css + "\n" + layout_css + "\n</style>", 1)
```

Delete the old `shell = shell.replace("</style>", decision_css + "\n</style>", 1)` line — it is replaced by the one above, not added to.

- [ ] **Step 5: Run the test to verify it passes**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS — `all dashboard layout contracts pass`, exit 0.

- [ ] **Step 6: Rebuild and confirm the build is still clean**

Run bare (never piped — it masks the exit code):

```
py -3 dashboard/build.py
```

Expected: exit 0. The build embeds a parity fixture, so a clean build also asserts browser scoring still matches `engine.py`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_dashboard_layout.py dashboard/_layout.css dashboard/build.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Layout source file, wired last into the style block\n\nAdds dashboard/_layout.css and a script-style contract test that pins\nits inline order and allowlists the engine calls the decision layer may\nmake. No rules moved yet.\n')"
git commit -F .git/cm.txt
```

---

### Task 2: Move every layout rule into `_layout.css`

A pure refactor: rules move verbatim, the page must look identical. Doing this before any redesign means every later task edits exactly one file.

**Files:**
- Modify: `dashboard/_shell.html` (delete rule blocks at lines 134-179, 314-338, 613-648, 927-950, 1454, and the `@media` layout blocks noted below)
- Modify: `dashboard/_decision_layer.css` (delete lines 92-143 — `.ws-right`, `.wheelstage{display:contents}`, the whole `@media (min-width:1251px)` hero grid)
- Modify: `dashboard/_layout.css` (receive them)
- Modify: `tests/test_dashboard_layout.py` (add contract L3)

**Interfaces:**
- Consumes: `_layout.css` from Task 1.
- Produces: `_layout.css` containing the sole definition of `.shell`, `.main`, `.rail*`, `.rs-*`, `.msetup`, `.wheelstage`, `.ws-flank`, `.ws-center`, `.ws-right`, `.pdash*`, and all layout `@media` blocks. `_shell.html` and `_decision_layer.css` retain only component chrome.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`, immediately before the `if FAILURES:` block:

```python
print("L3 — one home per layout rule")

OWNED = [".shell{", ".main{", ".wheelstage{", ".ws-flank{", ".ws-center{",
         ".pdash{", ".pdash-tab{", ".pdash-body{"]
for sel in OWNED:
    check(sel in LAYOUT, "L3a %s defined in _layout.css" % sel)
    check(sel not in SHELL, "L3b %s NOT left in _shell.html" % sel)
    check(sel not in DECISION_CSS, "L3c %s NOT left in _decision_layer.css" % sel)
check(
    "grid-template-columns" not in DECISION_CSS,
    "L3d _decision_layer.css declares no grid tracks",
    "the hero grid moved to _layout.css",
)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on `L3a .shell{ defined in _layout.css` and the matching `L3b`/`L3c`/`L3d` lines — the rules are still in their old homes.

- [ ] **Step 3: Cut the rule blocks out of `_shell.html`**

Move these ranges **verbatim** (cut, do not retype) from `dashboard/_shell.html` into `dashboard/_layout.css`, preserving their relative order and their comments:

| Lines | What |
|---|---|
| 134-138 | `.shell{...}` + its `max-width:960px` override |
| 140-178 | `.rail`, `.rail-body`, `.rail-toggle`, `.rail-strip`, `.rs-btn`, `.rs-forge`, all `.shell[data-rail="min"]` rules, and the `@media (max-width:960px)` rail block at 171-178 |
| 179 | `.main{...}` |
| 314-338 | the three `.ws-party` popover-placement `@media` blocks |
| 613-648 | `.wheelstage{...}` and its four `@media` blocks (1560 / 1251-1560 / 1250 / 960) |
| 649 | `.ws-flank{...}` |
| 665 | `.ws-center{min-width:0; container-type:inline-size}` |
| 927-950 | `.pdash`, `.pdash[data-open]`, `.pdash-tab`, `.pdash-tab b`, `.pdash-tab:hover`, `.pdash-body`, `.pdash-empty` |
| 1454 | `.msetup{display:none}` and its `@media (max-width:960px)` block at 1456 |

Leave in `_shell.html`: `.ws-fit` and its children (type/colour chrome), `.meter-track`, `.meter-fill`, `.pdash .wf-*` and `.pdash-fly*` (component chrome scoped under the panel, not layout of the panel itself).

- [ ] **Step 4: Cut the hero grid out of `_decision_layer.css`**

Move lines 92-143 of `dashboard/_decision_layer.css` verbatim into `dashboard/_layout.css` — that is the `.ws-right{display:none}` rule, the `HERO GRID` comment, and the entire `@media (min-width:1251px){...}` block.

Append them **after** the `_shell.html` rules you moved in Step 3, so relative precedence is unchanged from the old concatenation order (`_shell.html` first, `_decision_layer.css` second).

- [ ] **Step 5: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 6: Rebuild and verify nothing moved visually**

```
py -3 dashboard/build.py
py -3 -m http.server --directory dashboard 8099
```

With the Playwright MCP, `browser_navigate` to `http://localhost:8099/index.html`, resize to 1867x945, and screenshot into `.playwright-mcp/`. Compare against the pre-refactor page: this task is a pure move, so the layout MUST be visually identical. If anything shifted, a rule was dropped or reordered — find it before continuing.

Note: `file://` navigation is blocked in Playwright MCP; you must use the http server. Hash-only URL changes do NOT reload the page.

- [ ] **Step 7: Commit**

```bash
git add dashboard/_layout.css dashboard/_shell.html dashboard/_decision_layer.css tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Consolidate layout rules into _layout.css\n\nPure move: the shell/main grid, the rail, the wheel stage, the pdash\npanel and every layout media block leave _shell.html and\n_decision_layer.css for one owner. No visual change.\n')"
git commit -F .git/cm.txt
```

---

### Task 3: Generalise `.pdash` into a reusable `.epanel`

The party panel becomes the first instance of the component every later panel uses.

**Files:**
- Modify: `dashboard/_layout.css` (rename and generalise the panel rules)
- Modify: `dashboard/_shell.html:1709-1716` (party panel markup) and add the two edge rails
- Modify: `dashboard/_app.js:2395-2399` (panel toggle) and `dashboard/_app.js:788-795` (`closePdash`)
- Modify: `tests/test_dashboard_layout.py` (contract L4)

**Interfaces:**
- Consumes: `_layout.css` owning `.pdash*` (Task 2).
- Produces:
  - CSS: `.epanel[data-edge="left"|"right"][data-open="true"|"false"]`, `.epanel-rail[data-edge]`, `.epanel-tab[data-panel]`, `.epanel-body`.
  - Markup: `<aside class="epanel" data-edge="right" data-open="false" id="pdash">` with `<div class="epanel-body" id="pdash-body">`; tabs live in `<div class="epanel-rail" data-edge="right">` as `<button class="epanel-tab" data-panel="pdash">`.
  - JS: `setPanel(id, open)` — sets `data-open`, syncs the tab's `aria-expanded`, persists to `localStorage` under `"epanel:" + id`. `restorePanels()` — called once at startup, reads those keys. Both defined in `_app.js`.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`, before the `if FAILURES:` block:

```python
print("L4 — the edge-panel component")

check(".epanel{" in LAYOUT, "L4a .epanel defined in _layout.css")
check(".epanel-tab{" in LAYOUT, "L4b .epanel-tab defined in _layout.css")
check('data-edge="right"' in LAYOUT, "L4c right edge styled")
check('data-edge="left"' in LAYOUT, "L4d left edge styled")

panels = re.findall(r'<aside class="epanel"[^>]*id="([a-z-]+)"', SHELL)
tabs = set(re.findall(r'class="epanel-tab"[^>]*data-panel="([a-z-]+)"', SHELL))
check(bool(panels), "L4e at least one .epanel exists in the markup")
for p in panels:
    check(p in tabs, "L4f panel %s has a tab" % p)
for m in re.finditer(r'<aside class="epanel"([^>]*)>', SHELL):
    check("data-edge=" in m.group(1), "L4g every .epanel declares data-edge")

check("setPanel" in APP, "L4h _app.js defines setPanel")
check('"epanel:"' in APP, "L4i panel state persists under an epanel: key")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on `L4a` through `L4i` — nothing named `.epanel` exists yet.

- [ ] **Step 3: Generalise the CSS in `_layout.css`**

Replace the `.pdash` / `.pdash-tab` / `.pdash-body` block you moved in Task 2 with the edge-agnostic component. Keep the existing visual values exactly — this is a rename plus a left-edge mirror, not a restyle:

```css
/* ---------- edge panels ----------
   One component for every viewport-edge flyout. Fixed, so a shut panel
   costs ZERO layout: the content grid always gets the full viewport.
   Tabs stack in an .epanel-rail per edge; adding a surface is one <button>
   plus one <aside>. Generalised from .pdash 2026-09-02. */
.epanel{
  position:fixed; top:0; bottom:0; z-index:40;
  width:min(430px, 92vw);
  transition:transform .32s var(--ease);
  background:rgba(13,16,22,.97); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  box-shadow:0 0 44px rgba(0,0,0,.5);
  display:flex; flex-direction:column;
}
.epanel[data-edge="right"]{right:0; transform:translateX(100%); border-left:1px solid var(--rule-2)}
.epanel[data-edge="left"]{left:0; transform:translateX(-100%); border-right:1px solid var(--rule-2)}
.epanel[data-open="true"]{transform:none}
.epanel-body{overflow-y:auto; padding:12px 12px 18px; flex:1}
.epanel-empty{padding:6px 2px}

/* the tab rails: one stacked column of tabs per edge, centred vertically
   and pinned OUTSIDE the panel so they stay reachable when it is shut */
.epanel-rail{
  position:fixed; top:50%; transform:translateY(-50%); z-index:41;
  display:flex; flex-direction:column; gap:8px;
}
.epanel-rail[data-edge="right"]{right:0}
.epanel-rail[data-edge="left"]{left:0}
.epanel-tab{
  writing-mode:vertical-rl; padding:16px 8px;
  font-family:var(--mono); font-size:10px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--brass); background:linear-gradient(90deg, var(--panel-hi), var(--panel-lo));
  border:1px solid var(--rule-2); cursor:pointer;
  transition:color .18s var(--ease), border-color .18s var(--ease);
}
.epanel-rail[data-edge="right"] .epanel-tab{
  border-right:0; border-radius:10px 0 0 10px; box-shadow:-8px 0 18px rgba(0,0,0,.4)}
.epanel-rail[data-edge="left"] .epanel-tab{
  border-left:0; border-radius:0 10px 10px 0; box-shadow:8px 0 18px rgba(0,0,0,.4)}
.epanel-tab b{color:var(--ink); font-weight:600}
.epanel-tab:hover{color:var(--brass-bright); border-color:var(--brass-deep)}
/* phones: panels are bottom sheets, rails a horizontal row above them */
@media (max-width:960px){
  .epanel{left:0; right:0; top:auto; bottom:0; width:auto; max-height:76vh;
    border:1px solid var(--rule-2); border-bottom:0; border-radius:14px 14px 0 0}
  .epanel[data-edge="left"], .epanel[data-edge="right"]{transform:translateY(100%)}
  .epanel[data-open="true"]{transform:none}
  .epanel-rail{top:auto; bottom:0; transform:none; flex-direction:row;
    justify-content:center; width:100%; gap:6px}
  .epanel-rail[data-edge="left"], .epanel-rail[data-edge="right"]{left:0; right:0}
  .epanel-tab{writing-mode:horizontal-tb; padding:7px 12px; border-radius:8px 8px 0 0;
    border:1px solid var(--rule-2); border-bottom:0}
}
```

Then rename the panel-scoped chrome selectors that stayed in `_shell.html` — `.pdash .wf-comp`, `.pdash .wf-col`, `.pdash .wf-mcard`, `.pdash .wf-mnm`, `.pdash .dm-pop`, `.pdash-fly*` — changing the `.pdash` prefix to `.epanel`. `#pdash` keeps its id, so `.pdash-fly` becomes `.epanel-fly` and `#pdash-fly` becomes `#epanel-fly` only if you also update `_app.js`; **simpler and safer: keep the `pdash-fly` id and class as-is** — it is party-specific chrome, not part of the panel component.

- [ ] **Step 4: Update the party panel markup**

In `dashboard/_shell.html`, replace the `<aside class="pdash" id="pdash">` block (lines 1709-1716) with the panel plus its rail. Put both rails immediately before the `.drawer` markup:

```html
<!-- edge panel rails: one stacked tab column per viewport edge -->
<div class="epanel-rail" data-edge="left"></div>
<div class="epanel-rail" data-edge="right">
  <button class="epanel-tab" data-panel="pdash" aria-expanded="false"
    title="show or hide the party board">party <b id="pdash-count">0/0</b></button>
</div>

<aside class="epanel" data-edge="right" data-open="false" id="pdash" aria-label="Party board">
  <div class="epanel-body" id="pdash-body"></div>
  <!-- kit flyout: fills on hover over a member tile (showPdashFly) -->
  <div class="pdash-fly" id="pdash-fly" hidden></div>
</aside>
```

The `#pdash-toggle` button id is gone — the tab is now addressed by `data-panel`.

- [ ] **Step 5: Replace the toggle logic in `_app.js`**

Delete the `#pdash-toggle` branch at lines 2395-2399 and add the generic state machine. Put `setPanel`/`restorePanels` next to the old rail code (around line 2204), replacing nothing yet — `setRail` is deleted in Task 5:

```js
/* Edge panels: one state machine for every viewport-edge flyout. State is
   data-open on the panel, mirrored to its tab's aria-expanded, persisted so
   the layout choice survives reloads. Display only. */
function setPanel(id, open){
  const p = $(id);
  if (!p) return;
  p.dataset.open = open ? "true" : "false";
  const tab = document.querySelector('.epanel-tab[data-panel="' + id + '"]');
  if (tab) tab.setAttribute("aria-expanded", String(!!open));
  try { localStorage.setItem("epanel:" + id, open ? "1" : ""); }
  catch (e) { /* private mode */ }
}
function restorePanels(){
  document.querySelectorAll(".epanel").forEach(p => {
    let v = "";
    try { v = localStorage.getItem("epanel:" + p.id) || ""; }
    catch (e) { /* private mode */ }
    setPanel(p.id, v === "1");
  });
}
```

In the document click handler, replace the deleted `#pdash-toggle` branch with:

```js
  const etab = e.target.closest(".epanel-tab");
  if (etab){
    const id = etab.dataset.panel;
    setPanel(id, $(id).dataset.open !== "true");
    return;
  }
```

In `closePdash()` (lines 788-795), replace the manual `data-open` writes with `setPanel("pdash", false)`, keeping the `hidePdashFly()` call first.

At the end of the file, next to the existing startup restore on line 2631, add:

```js
restorePanels();
```

- [ ] **Step 6: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 7: Rebuild and verify the panel still works**

```
py -3 dashboard/build.py
```

Then with Playwright against `http://localhost:8099/index.html` at 1867x945: click the party tab, confirm the panel slides in from the right and the member tiles render; reload and confirm it reopens (persistence); click again and confirm it closes.

- [ ] **Step 8: Commit**

```bash
git add dashboard/_layout.css dashboard/_shell.html dashboard/_app.js tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Generalise the party panel into a reusable .epanel\n\nOne edge-panel component for both viewport edges, with stacked tab\nrails, a generic setPanel/restorePanels state machine and per-panel\nlocalStorage persistence. The party board is its first instance.\n')"
git commit -F .git/cm.txt
```

---

### Task 4: The status bar

Puts the verdict and the constantly-turned knobs in the masthead, before the rail is deleted, so the selects move once.

**Files:**
- Modify: `dashboard/_shell.html` (masthead at 1561-1575; remove `.ws-fit` from `.ws-right` at ~1690; remove `.foot-chips`)
- Modify: `dashboard/_layout.css` (masthead layout)
- Modify: `dashboard/_decision_layer.js:603` (write the identity into the bar)
- Modify: `dashboard/_app.js:1128-1137` (write the party count into the bar)
- Modify: `tests/test_dashboard_layout.py` (contract L5)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: masthead ids `sb-identity` (identity glyph + label + strength) and `sb-count` (`N/M`). `#fit-num`, `#fit-of`, `#fit-bar`, `#parity-dot`, `#parity-chip`, `#build-stamp`, `#style`, `#size-input`, `#size-minus`, `#size-plus`, `#content` all keep their existing ids and handlers — they are relocated, not rewritten.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`:

```python
print("L5 — status bar")

head = SHELL[SHELL.index("<header class=\"masthead\">"):SHELL.index("</header>")]
for el in ['id="fit-num"', 'id="fit-of"', 'id="fit-bar"', 'id="sb-identity"',
           'id="sb-count"', 'id="style"', 'id="size-input"', 'id="content"',
           'id="parity-chip"', 'id="build-stamp"']:
    check(el in head, "L5a masthead carries %s" % el)
check(SHELL.count('id="fit-num"') == 1, "L5b #fit-num is not duplicated")
check(SHELL.count('id="style"') == 1, "L5c #style is not duplicated")
check(SHELL.count('id="size-input"') == 1, "L5d #size-input is not duplicated")
check("foot-chips" not in SHELL, "L5e .foot-chips retired — its chips moved up")
check('"sb-identity"' in DECISION_JS, "L5f decision layer fills #sb-identity")
check('"sb-count"' in APP, "L5g _app.js fills #sb-count")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on every `L5a` line except `id="parity-chip"`/`id="build-stamp"`, plus `L5e`, `L5f`, `L5g`.

- [ ] **Step 3: Rewrite the masthead markup**

Replace `dashboard/_shell.html` lines 1561-1575 with a two-line masthead. The `.ws-fit` markup is **moved here** (cut it out of the `.ws-right` div), so `_app.js:1179-1187` keeps updating it with no change:

```html
<header class="masthead">
  <div class="mh-top">
    <div class="brandmark">
      <span class="sigil" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#E5B45C" stroke-width="1.8" stroke-linecap="round"><path d="M4 4l10.5 10.5M4 4v3.5M4 4h3.5"/><path d="M20 4L9.5 14.5M20 4v3.5M20 4h-3.5"/><path d="M7 17l-2.4 2.4M17 17l2.4 2.4"/><path d="M5.2 15.2l3.6 3.6M18.8 15.2l-3.6 3.6"/></svg></span>
      <div>
        <h1>Comp Forge</h1>
        <span class="sub">Albion composition engine</span>
      </div>
    </div>
    <div class="ws-fit sb-fit">
      <div class="sec-label">Composition fitness</div>
      <div><span class="num" id="fit-num">0.0</span> <span class="of" id="fit-of">/ 0</span></div>
      <div class="meter-track"><div class="meter-fill" id="fit-bar" style="width:0%"></div></div>
    </div>
    <div class="sb-identity" id="sb-identity"></div>
    <div class="spacer"></div>
    <a class="about-link" href="how-it-works.html">How it works <span aria-hidden="true">→</span></a>
    <button class="share-btn lf-btn" id="companion-connect">connect live party</button>
    <label class="lf-sync" id="companion-sync-wrap" hidden
           title="keep the loaded comp following the live party: weapon swaps update their slot, newly visible weapons fill in, real Q/W picks flow into the loadouts — no re-load needed">
      <input type="checkbox" id="companion-sync"> live sync</label>
  </div>
  <div class="mh-bar">
    <label class="sb-field"><span>style</span><select id="style"></select></label>
    <label class="sb-field"><span>size</span>
      <span class="size-row">
        <button class="size-btn" id="size-minus" aria-label="one fewer">&minus;</button>
        <input class="size-input" id="size-input" type="number" min="2" max="60" inputmode="numeric">
        <button class="size-btn" id="size-plus" aria-label="one more">+</button>
      </span></label>
    <label class="sb-field"><span>content</span><select id="content">
      <option value="castle_outpost">Castle Outpost</option>
    </select></label>
    <span class="sb-count" id="sb-count">0/0</span>
    <div class="spacer"></div>
    <span class="chip"><span class="dot" id="parity-dot"></span><span id="parity-chip">parity — checking</span></span>
    <span class="chip">dataset <span class="mono" id="build-stamp">—</span></span>
  </div>
</header>
```

Then delete from `_shell.html`: the `.ws-fit` block inside `.ws-right` (now moved), the `.foot-chips` div near the end of `.main`, and the `#style` / `#size-input` / `#size-minus` / `#size-plus` / `#content` controls inside the rail's `<section>` — the rail keeps `#style-blurb`, `#size-presets`, `#size-hint`, `#size-notice`, `#forge-rail`, `#share`, `#export`, `#clear`.

- [ ] **Step 4: Add masthead layout to `_layout.css`**

```css
/* ---------- masthead / status bar ----------
   Two lines: identity + verdict on top, the constantly-turned knobs below.
   Style and size change on nearly every interaction; burying them behind a
   panel tab would cost more than the space it saves. */
.masthead{display:flex; flex-direction:column; gap:0}
.mh-top{display:flex; align-items:center; gap:26px; padding:10px 34px 8px}
.mh-bar{display:flex; align-items:center; gap:18px; padding:6px 34px 8px;
  border-top:1px solid var(--rule)}
.mh-top .spacer, .mh-bar .spacer{flex:1}
.sb-fit{margin-bottom:0; display:flex; align-items:baseline; gap:10px}
.sb-fit .sec-label{margin:0}
.sb-fit .num{font-size:26px}
.sb-fit .meter-track{width:120px; margin-top:0; align-self:center}
.sb-identity{display:flex; align-items:center; gap:8px}
.sb-field{display:flex; align-items:center; gap:7px}
.sb-field>span{font-family:var(--mono); font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-3)}
.sb-field select, .sb-field .size-input{margin:0}
@media (max-width:960px){
  .mh-top, .mh-bar{padding-left:16px; padding-right:16px; flex-wrap:wrap; gap:12px}
  .sb-fit .meter-track{width:80px}
}
```

- [ ] **Step 5: Fill `#sb-identity` from the decision layer**

`statusRadar()` already computes the identity — `const id = ...ENG.compIdentity(party, COMBOS_CUR)...` and `const c = identityCenter(id);` at `_decision_layer.js:258-259`. Write the status bar from there, so it reuses that value and adds **no** engine call, and so the bar and the radar's hollow centre can never disagree.

In `dashboard/_decision_layer.js`, immediately after `const c = identityCenter(id);` (line 259), add:

```js
    /* mirror the identity verdict into the status bar — same identityCenter()
       value the hollow center draws, so the two can never disagree */
    const sbi = document.getElementById("sb-identity");
    if (sbi) sbi.innerHTML = `<b class="${c.firm ? "firm" : ""}">${esc(c.name)}</b>`
      + (c.sub ? `<span>${esc(c.sub.toUpperCase())}</span>` : "");
```

`statusRadar()` returns early at `if (!N) return "";` (line 229), and `renderDecisionLayer()`'s empty-comp branch at line 551 never calls it at all. So also clear the bar in `renderDecisionLayer()`, as the first statement of the function:

```js
    const sbi0 = document.getElementById("sb-identity");
    if (sbi0) sbi0.innerHTML = "";
```

- [ ] **Step 6: Fill `#sb-count` from `_app.js`**

In `dashboard/_app.js`, in the block that sets `#pdash-count` (around line 1133), add immediately after it:

```js
    const sbc = $("sb-count");
    if (sbc) sbc.textContent = pc ? pc.textContent : `${party.length}/${PLAN()}`;
```

- [ ] **Step 7: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 8: Rebuild and verify the controls still drive the engine**

```
py -3 dashboard/build.py
py -3 tests/test_js_parity.py
```

Both exit 0. Then with Playwright at 1867x945: change the style select and confirm the radar and pick card re-render; click size `+`/`−` and confirm the target numbers move; confirm the fitness number, identity label and party count all populate.

- [ ] **Step 9: Commit**

```bash
git add dashboard/_shell.html dashboard/_layout.css dashboard/_decision_layer.js dashboard/_app.js tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Status bar: the verdict and the knobs you actually turn\n\nMasthead grows a second line carrying fitness, identity, live style /\nsize / content controls, party count and the parity and dataset chips.\nEvery value already rendered somewhere; nothing new is computed.\n')"
git commit -F .git/cm.txt
```

---

### Task 5: Retire the rail; setup becomes a left-edge panel

**Files:**
- Modify: `dashboard/_shell.html` (delete the whole `<aside class="rail">`, add the setup panel)
- Modify: `dashboard/_layout.css` (delete `.rail*`, `.rs-*`, `.msetup`, `.shell[data-rail]`; collapse `.shell` to one column)
- Modify: `dashboard/_app.js` (delete `setRail`, `RAIL_KEY`, the `#rail-*`/`#msetup` click branches, the `#msetup-sum` writer, the startup rail restore)
- Modify: `tests/test_dashboard_layout.py` (contract L6)

**Interfaces:**
- Consumes: `setPanel`/`restorePanels` (Task 3); the masthead now owning `#style`/`#size-input`/`#content` (Task 4).
- Produces: `#setup-panel`, an `.epanel[data-edge="left"]` holding the remaining setup controls. `.shell` is a single content region.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`:

```python
print("L6 — the in-flow rail is gone")

for dead in ["data-rail", "rail-toggle", "rail-strip", "rail-expand",
             "msetup", "rs-btn", "rs-forge", "RAIL_KEY", "setRail"]:
    check(dead not in SHELL, "L6a %s absent from _shell.html" % dead)
    check(dead not in LAYOUT, "L6b %s absent from _layout.css" % dead)
    check(dead not in APP, "L6c %s absent from _app.js" % dead)
check('id="setup-panel"' in SHELL, "L6d setup panel exists")
check('data-panel="setup-panel"' in SHELL, "L6e setup panel has a tab")
for keep in ['id="forge-rail"', 'id="share"', 'id="export"', 'id="clear"',
             'id="size-presets"', 'id="size-hint"', 'id="style-blurb"',
             'id="size-notice"']:
    check(keep in SHELL, "L6f setup panel keeps %s" % keep)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on the `L6a`/`L6b`/`L6c` lines for every dead identifier, plus `L6d` and `L6e`.

- [ ] **Step 3: Replace the rail markup with a left-edge panel**

Delete the entire `<aside class="rail">...</aside>` block from `dashboard/_shell.html`. Add the tab to the left rail (which Task 3 left empty) and the panel next to `#pdash`:

```html
<div class="epanel-rail" data-edge="left">
  <button class="epanel-tab" data-panel="setup-panel" aria-expanded="false"
    title="show or hide setup">setup</button>
</div>
```

```html
<aside class="epanel" data-edge="left" data-open="false" id="setup-panel" aria-label="Setup">
  <div class="epanel-body">
    <div class="sec-label">Setup</div>
    <div class="field">
      <div class="size-hint" id="style-blurb"></div>
    </div>
    <div class="field">
      <label>Party size presets</label>
      <span id="size-presets"></span>
      <div class="size-hint" id="size-hint"></div>
    </div>
    <div id="size-notice"></div>
    <div class="btn-row">
      <button class="share-btn forge-rail" id="forge-rail"
        title="fill every open slot for the current content, style and size; on a fully forged roster this rebuilds the generated slots">forge full comp</button>
    </div>
    <div class="btn-row">
      <button class="share-btn" id="share">copy share link</button>
      <button class="share-btn" id="export">copy comp text</button>
    </div>
    <div class="btn-row">
      <button class="share-btn clear-btn" id="clear">clear comp</button>
    </div>
  </div>
</aside>
```

- [ ] **Step 4: Delete the rail rules from `_layout.css`**

Remove every rule you moved in Task 2 Step 3 rows 2, 9 (`.rail`, `.rail-body`, `.rail-toggle`, `.rail-strip`, `.rs-btn`, `.rs-forge`, all `.shell[data-rail="min"]` rules and their `@media` block, `.msetup` and its `@media` block) and every `.shell[data-rail="min"]` selector in the `.ws-party` and `.wheelstage` blocks. Collapse `.shell` to:

```css
.shell{display:block; max-width:none; margin:0}
```

The `max-width:1560px` cap goes with it — the page runs full-bleed, which is the ~300px of horizontal room this redesign spends.

Also delete the now-dead `.ws-party` rules: the party dock was retired on `origin/main` (`9c8c946`) and no `.ws-party` element exists in the markup.

- [ ] **Step 5: Delete the rail state machine from `_app.js`**

Remove: `RAIL_KEY` and `setRail` (lines 2204-2211), the `#rail-toggle` and `#rail-expand`/`#rail-expand-setup` click branches (2385-2387), the `#msetup` click branch (2388-2394), the `#msetup-sum` writer (534-539), and the startup restore on line 2631.

Keep the `#forge-rail-mini` reference in the forge click handler at lines 2303 and 2314 only if that button still exists — it does not, so **remove `|| e.target.closest("#forge-rail-mini")` and the `|| forgeBtn.id === "forge-rail-mini"` clause**, leaving the `#forge-rail` cases intact.

- [ ] **Step 6: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 7: Rebuild and verify forge/share/export/clear still work**

```
py -3 dashboard/build.py
node tests/test_loadout_codec.js
```

Both exit 0. Then with Playwright at 1867x945: open the setup tab, click `forge full comp` and confirm a roster fills; click `copy share link` and confirm the button's confirmation text appears; click `clear comp` twice and confirm the two-step arm-then-clear still behaves.

- [ ] **Step 8: Commit**

```bash
git add dashboard/_shell.html dashboard/_layout.css dashboard/_app.js tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Retire the setup rail for a left-edge panel\n\nThe rail and its data-rail state machine are deleted; setup becomes an\n.epanel on the left edge, and the shell drops its 1560px cap to run\nfull-bleed. A shut panel costs no layout.\n')"
git commit -F .git/cm.txt
```

---

### Task 6: Caller tools and live party become panels

Empties `.main` of everything that is not grid content.

**Files:**
- Modify: `dashboard/_shell.html` (tabs + two panels; remove the `.livefeed` section from `.main`)
- Modify: `dashboard/_decision_layer.js:512-539` (mount the tools fold into its panel)
- Modify: `tests/test_dashboard_layout.py` (contract L7)

**Interfaces:**
- Consumes: `.epanel` (Task 3).
- Produces: `#tools-panel` (left edge, hosts `#dl-tools-fold`) and `#live-panel` (right edge, hosts `#companion`). `.main`'s only remaining children are `.decision-layer`, `.wheelstage`, `#warn-slot`, `#groups`, `#meta-sec`, `.footnote`.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`:

```python
print("L7 — deep interactive surfaces live in panels")

check('id="tools-panel"' in SHELL, "L7a caller-tools panel exists")
check('id="live-panel"' in SHELL, "L7b live-party panel exists")
check('data-panel="tools-panel"' in SHELL, "L7c tools panel has a tab")
check('data-panel="live-panel"' in SHELL, "L7d live panel has a tab")
main = SHELL[SHELL.index('<main class="main">'):SHELL.index("</main>")]
check('class="livefeed"' not in main, "L7e livefeed left .main")
check('id="meta-sec"' in main, "L7f killboard stays a deep board in .main")
check("tools-panel" in DECISION_JS, "L7g tools fold mounts into its panel")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on `L7a`-`L7e` and `L7g`.

- [ ] **Step 3: Add the tabs and panels**

In `dashboard/_shell.html`, add to the left rail after the setup tab:

```html
  <button class="epanel-tab" data-panel="tools-panel" aria-expanded="false"
    title="show or hide caller tools — player pool and swap impact">tools</button>
```

and to the right rail after the party tab:

```html
  <button class="epanel-tab" data-panel="live-panel" aria-expanded="false"
    title="show or hide the live party feed">live</button>
```

Add the two panels next to the others:

```html
<aside class="epanel" data-edge="left" data-open="false" id="tools-panel" aria-label="Caller tools">
  <div class="epanel-body" id="tools-panel-body"></div>
</aside>

<aside class="epanel" data-edge="right" data-open="false" id="live-panel" aria-label="Live party">
  <div class="epanel-body">
    <!-- Live party feed: the companion's home, one card per in-game member -->
    <section class="livefeed" id="companion" data-live="false">
      <div class="sec-label">Live party</div>
      <div class="lf-bar">
        <div class="status" id="companion-status" hidden></div>
        <button class="load-btn lf-btn" id="companion-load" hidden>load party into comp</button>
      </div>
      <div class="comp-members" id="companion-members"></div>
    </section>
  </div>
</aside>
```

Delete the original `<section class="livefeed" id="companion">` block from inside `<main class="main">` — it is moved here, not copied. `#companion-connect` and `#companion-sync` stay in the masthead where `origin/main` already put them.

- [ ] **Step 4: Re-anchor the tools fold**

In `dashboard/_decision_layer.js`, replace the anchor logic at the end of `renderPlayerTools` (lines 536-539):

```js
    /* the fold lives in the left-edge tools panel (2026-09-02) — it is an
       interactive workflow, not glance-info, so it costs the grid nothing */
    const panel = document.getElementById("tools-panel-body");
    if (panel) panel.appendChild(fold);
    else host.appendChild(fold);
```

Also update the stale comment above the `document.createElement("details")` call (lines 512-514), which still describes the hero-grid placement.

- [ ] **Step 5: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 6: Rebuild and verify both panels**

```
py -3 dashboard/build.py
```

With Playwright at 1867x945: open the `tools` tab, add a weapon to the player pool via its search box, and confirm the "Best from this player's pool" block renders and the pool survives a re-render (add a weapon to the comp, confirm the pool chip is still there). Open the `live` tab and confirm the companion section renders its connect/status UI.

The companion needs `localhost:53321`. Port 53321 may be held by the RUNNING companion — check `localhost:53321/status` before binding anything there, and do not kill a live companion to test.

- [ ] **Step 7: Commit**

```bash
git add dashboard/_shell.html dashboard/_decision_layer.js tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Caller tools and live party move to edge panels\n\nBoth are interactive workflows rather than glance-info, so they earn a\ntab instead of grid space. .main is now only grid content plus the\nkillboard deep board.\n')"
git commit -F .git/cm.txt
```

---

### Task 7: The four-column grid

**Files:**
- Modify: `dashboard/_layout.css` (replace the `@media (min-width:1251px)` hero grid; add the 1400 and 1700 blocks; set `--wd`)
- Modify: `tests/test_dashboard_layout.py` (contract L8)

**Interfaces:**
- Consumes: `.main` containing only `.decision-layer` (dissolving to `.dl-status` + `.dl-pick`), `.wheelstage` (dissolving to `.ws-center`), `#warn-slot`, `#groups`, `#meta-sec`, `.footnote` (Task 6).
- Produces: the four-column grid. Column 4 is empty until Task 8 fills it — that is expected and correct.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`:

```python
print("L8 — the column grid")

check("@media (min-width:1700px)" in LAYOUT, "L8a four-column breakpoint exists")
check("@media (min-width:1400px) and (max-width:1699px)" in LAYOUT,
      "L8b three-column breakpoint exists")
check("@media (min-width:1251px) and (max-width:1399px)" in LAYOUT,
      "L8c the 1251-1399 hero grid is preserved untouched")
check("min(520px" in LAYOUT or "--wd:min(520px" in LAYOUT,
      "L8d wheel shrinks to 520px in the grid")
check("680px" not in LAYOUT, "L8e the 680px wheel override is gone")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on `L8a`-`L8e`.

- [ ] **Step 3: Rewrite the grid blocks in `_layout.css`**

Replace the `@media (min-width:1251px){...}` hero-grid block (moved in from `_decision_layer.css` in Task 2) with three blocks. The 1251-1399 block is the **old block verbatim**, only its media query narrowed — that is what keeps mid-width viewports untouched:

```css
/* ---------- the card grid ----------
   Four columns at >=1700px (2026-09-02 density redesign): diagnosis left,
   the wheel, the pick card, then pressure/roles/warnings. .wheelstage and
   .decision-layer dissolve with display:contents so their children place
   directly. Below 1251px nothing changed — the stacked stage rules run. */
@media (min-width:1700px){
  .main{
    display:grid; align-items:start; gap:18px 24px;
    grid-template-columns:minmax(320px,.8fr) minmax(540px,1.15fr)
                          minmax(380px,.95fr) minmax(380px,1fr);
  }
  .main>*{grid-column:1/-1; min-width:0}
  .decision-layer{display:contents}
  .wheelstage{display:contents}
  .dl-status{grid-column:1; grid-row:1; padding:0}
  #groups{grid-column:1; grid-row:2; margin-top:0}
  .ws-center{grid-column:2; grid-row:1/3; order:0}
  .dl-pick{grid-column:3; grid-row:1/3; padding:14px 16px}
  .dl-kp{grid-column:4; grid-row:1}
  .dl-roles{grid-column:4; grid-row:2}
  #warn-slot{grid-column:4; grid-row:3}
  .dl-empty{grid-column:1; grid-row:1/3}
  /* the semicircle at one-column scale */
  .wheel{--wd:min(520px,100cqi)}
  /* everything after the hero — the killboard, the footnote — is a
     full-width deep board in DOM order */
  #meta-sec, .footnote{grid-column:1/-1; grid-row:auto}
}
/* three columns: column 4 dissolves into a full-width row under the hero,
   its three cards side by side. Columns 1-3 keep their proportions. */
@media (min-width:1400px) and (max-width:1699px){
  .main{
    display:grid; align-items:start; gap:18px 24px;
    grid-template-columns:minmax(320px,.85fr) minmax(500px,1.2fr) minmax(380px,1fr);
  }
  .main>*{grid-column:1/-1; min-width:0}
  .decision-layer{display:contents}
  .wheelstage{display:contents}
  .dl-status{grid-column:1; grid-row:1; padding:0}
  #groups{grid-column:1; grid-row:2; margin-top:0}
  .ws-center{grid-column:2; grid-row:1/3; order:0}
  .dl-pick{grid-column:3; grid-row:1/3; padding:14px 16px}
  .dl-empty{grid-column:1; grid-row:1/3}
  .dl-kp{grid-column:1; grid-row:3}
  .dl-roles{grid-column:2; grid-row:3}
  #warn-slot{grid-column:3; grid-row:3}
  .wheel{--wd:min(520px,100cqi)}
  #meta-sec, .footnote{grid-column:1/-1; grid-row:auto}
}
```

Then paste the **original** `@media (min-width:1251px){ ... }` block back, changed only to `@media (min-width:1251px) and (max-width:1399px){ ... }`, minus its `.shell[data-rail="min"] .ws-center` line (that selector no longer exists) and minus its `.wheel{--wd:min(680px,100cqi)}` line (replaced by the default in `_shell.html`, which is `min(720px,100cqi)` and correct at that width).

- [ ] **Step 4: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0. `L8e` passes because the only `680px` occurrence was the override you just removed.

- [ ] **Step 5: Rebuild and verify all four widths**

```
py -3 dashboard/build.py
```

With Playwright, forge a full 20-player comp, then screenshot at each width into `.playwright-mcp/`:

| Width | Expect |
|---|---|
| 1867 | four columns; column 4 holds only the warn slot (Task 8 fills the rest) |
| 1500 | three columns; warn slot on the full-width row under the hero |
| 1300 | the pre-existing two-column hero grid, visually unchanged from `origin/main` |
| 900 | single-column stack; panels are bottom sheets |

The 1300px screenshot is the regression check that matters — it must match `origin/main`.

- [ ] **Step 6: Commit**

```bash
git add dashboard/_layout.css tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Four-column card grid above 1700px\n\nDiagnosis, wheel, pick card and a pressure column; three columns from\n1400px; below 1251px nothing changed. The wheel shrinks to a 520px\nsemicircle so it stops owning half the screen.\n')"
git commit -F .git/cm.txt
```

---

### Task 8: Kill pressure and role check as cards

These render today only as lines inside the radar's hover tooltip. Extract them so the tooltip and the cards call the same helpers and can never disagree.

**Files:**
- Modify: `dashboard/_decision_layer.js` (extract from `centerTipHtml` at lines 173-200; render into the grid)
- Modify: `dashboard/_decision_layer.css` (card chrome)
- Modify: `tests/test_dashboard_layout.py` (contract L9)

**Interfaces:**
- Consumes: the grid's column-4 placements `.dl-kp` / `.dl-roles` (Task 7).
- Produces: `killPressureModel()` returning `null` or `{pierce, heal_cut, burst}` each `{ok, have, bar, pct}`; `killPressureCard()` and `roleCard()` returning HTML strings (empty string when there is nothing to show); `killPressureLine()` and `roleLines()` returning the tooltip's existing `<div class="dlt-line">` markup.

- [ ] **Step 1: Write the failing contract**

Append to `tests/test_dashboard_layout.py`:

```python
print("L9 — kill pressure and role check are cards")

check("killPressureCard" in DECISION_JS, "L9a killPressureCard defined")
check("roleCard" in DECISION_JS, "L9b roleCard defined")
check('"dl-kp"' in DECISION_JS or "dl-kp" in DECISION_JS, "L9c .dl-kp rendered")
check("dl-roles" in DECISION_JS, "L9d .dl-roles rendered")
check(".dl-kp{" in DECISION_CSS, "L9e .dl-kp chrome in _decision_layer.css")
check(".dl-roles{" in DECISION_CSS, "L9f .dl-roles chrome in _decision_layer.css")
check(".dl-kp{" not in LAYOUT, "L9g .dl-kp chrome is NOT in _layout.css")
tip = DECISION_JS[DECISION_JS.index("function centerTipHtml"):]
tip = tip[:tip.index("function roleAdvisory")]
check("ENG.killPressure" not in tip,
      "L9h centerTipHtml no longer calls the engine directly",
      "it must go through the shared helper so tooltip and card agree")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: FAIL on `L9a`-`L9f` and `L9h`.

- [ ] **Step 3: Extract the shared model and helpers**

In `dashboard/_decision_layer.js`, add above `centerTipHtml`:

```js
  /* Kill pressure and role check are DESCRIPTIVE — they translate engine
     output and never score. The tooltip and the cards both read these, so
     the two surfaces can never disagree. */
  function killPressureModel(){
    if (typeof ENG.killPressure !== "function") return null;
    const kp = ENG.killPressure(party, COMBOS_CUR);
    if (!kp) return null;
    const lens = k => {
      const l = kp[k];
      return {ok: l.ok, have: l.have, bar: l.bar,
              pct: l.bar > 0 ? Math.round(100 * l.have / l.bar) : 100};
    };
    return {pierce: lens("pierce"), heal_cut: lens("heal_cut"), burst: lens("burst")};
  }
  const KP_LABEL = {pierce: "pierce", heal_cut: "heal-cut", burst: "burst"};
  function killPressureLine(){
    const kp = killPressureModel();
    if (!kp) return "";
    const bit = k => kp[k].ok
      ? `<b class="dlt-ok">✓ ${KP_LABEL[k]}</b>`
      : `<b class="dlt-bad">✗ ${KP_LABEL[k]} ${kp[k].pct}%</b>`;
    return `<div class="dlt-line"><span>kill pressure</span><span>${
      bit("pierce")} ${bit("heal_cut")} ${bit("burst")}</span></div>`;
  }
  function killPressureCard(){
    const kp = killPressureModel();
    if (!kp) return "";
    const light = k => `<div class="dl-kp-row ${kp[k].ok ? "ok" : "bad"}">
      <span class="dl-kp-dot"></span><b>${KP_LABEL[k]}</b>
      <span class="dl-kp-n">${kp[k].ok ? "covered" : kp[k].pct + "%"}</span></div>`;
    return `<div class="dl-kp"><span class="dl-kicker">Kill pressure — can this comp finish a target?</span>
      ${light("pierce")}${light("heal_cut")}${light("burst")}
      <div class="dl-note">descriptive — kill pressure never scores</div></div>`;
  }
  function roleLines(){
    const adv = roleAdvisory();
    if (!adv) return "";
    const label = k => (((ENG.rolesBook || {})[k]) || {}).name || k;
    const short = k => label(k).split(" / ")[0].split(" (")[0];
    let h = "";
    const tally = Object.entries(adv.tally)
      .map(([k, n]) => `${n}× ${esc(short(k))}`).join(" · ");
    if (tally) h += `<div class="dlt-line"><span>roles</span><span>${tally}</span></div>`;
    const fns = {};
    adv.members.forEach(m => (m.functions || []).forEach(c => { fns[c] = (fns[c] || 0) + 1; }));
    const fnTxt = Object.entries(fns).map(([k, n]) => `${n}× ${esc(short(k))}`).join(" · ");
    if (fnTxt) h += `<div class="dlt-line"><span>functions</span><span>${fnTxt}</span></div>`;
    adv.flags.forEach(f2 => {
      h += `<div class="dlt-warn">⚠ ${f2.kind === "no_engage_tank"
        ? "no engage tank — nobody makes a clump"
        : `${esc(nameOf(f2.weapon))}: worn chest fights its ${esc(label(f2.role).toLowerCase())} job`}</div>`;
    });
    return h;
  }
  function roleCard(){
    const adv = roleAdvisory();
    if (!adv) return "";
    const label = k => (((ENG.rolesBook || {})[k]) || {}).name || k;
    const short = k => label(k).split(" / ")[0].split(" (")[0];
    const tally = Object.entries(adv.tally).map(([k, n]) =>
      `<span class="dl-role-chip"><b>${n}</b> ${esc(short(k))}</span>`).join("");
    const flags = adv.flags.map(f2 =>
      `<div class="dl-role-flag">⚠ ${f2.kind === "no_engage_tank"
        ? "no engage tank — nobody makes a clump"
        : `${esc(nameOf(f2.weapon))}: worn chest fights its ${esc(label(f2.role).toLowerCase())} job`}</div>`).join("");
    return `<div class="dl-roles"><span class="dl-kicker">Role check — who is actually in this comp</span>
      <div class="dl-role-tally">${tally}</div>${flags}
      <div class="dl-note">descriptive — roles never score</div></div>`;
  }
```

Then in `centerTipHtml`, delete the `if (typeof ENG.killPressure === "function"){...}` block (lines 173-183) and the `const adv = roleAdvisory(); if (adv){...}` block (lines 184-199), replacing both with:

```js
    h += killPressureLine();
    h += roleLines();
```

- [ ] **Step 4: Render the cards into the grid**

In `renderDecisionLayer()`, append the two cards to the `host.innerHTML` template literal, after the closing `</div>` of `.dl-pick`:

```js
      ${killPressureCard()}
      ${roleCard()}`;
```

Both helpers return `""` when there is nothing to show, so an empty comp renders no card and the grid rows collapse.

- [ ] **Step 5: Add the card chrome to `_decision_layer.css`**

Layout goes in `_layout.css` (Task 7 already placed `.dl-kp`/`.dl-roles`); only chrome goes here:

```css
/* kill pressure + role check as cards (2026-09-02). Both DESCRIPTIVE — they
   translate engine output and never feed scoring. The radar tooltip renders
   the same models through killPressureLine()/roleLines(). */
.dl-kp{background:var(--panel-lo); border:1px solid var(--rule); border-radius:12px; padding:12px 14px}
.dl-kp-row{display:flex; align-items:center; gap:9px; padding:5px 0; font-size:13px}
.dl-kp-dot{width:9px; height:9px; border-radius:50%; flex:none}
.dl-kp-row.ok .dl-kp-dot{background:#3FD68C; box-shadow:0 0 8px rgba(63,214,140,.6)}
.dl-kp-row.bad .dl-kp-dot{background:#E0556B; box-shadow:0 0 8px rgba(224,85,107,.6)}
.dl-kp-row b{font-weight:600; color:var(--ink)}
.dl-kp-n{margin-left:auto; font-family:var(--mono); font-size:11px; color:var(--ink-3)}
.dl-roles{background:var(--panel-lo); border:1px solid var(--rule); border-radius:12px; padding:12px 14px}
.dl-role-tally{display:flex; flex-wrap:wrap; gap:5px; margin:8px 0 4px}
.dl-role-chip{font-family:var(--mono); font-size:11px; color:var(--ink-2);
  background:var(--sunk); border:1px solid var(--rule); border-radius:99px; padding:3px 9px}
.dl-role-chip b{color:var(--brass); font-weight:600}
.dl-role-flag{font-size:12px; color:#F0A63C; margin-top:6px}
.dl-note{font-size:10px; color:var(--ink-3); margin-top:8px}
```

- [ ] **Step 6: Run the contract test**

Run: `py -3 tests/test_dashboard_layout.py`

Expected: PASS, exit 0.

- [ ] **Step 7: Rebuild and verify tooltip and cards agree**

```
py -3 dashboard/build.py
py -3 tests/test_js_parity.py
```

Both exit 0. Then with Playwright at 1867x945: forge a full comp, read the kill-pressure lights and the role tally off the two new cards, then hover the radar's hollow centre and confirm the tooltip reports **the same** values. They share a model, so any disagreement is a bug in the extraction.

- [ ] **Step 8: Commit**

```bash
git add dashboard/_decision_layer.js dashboard/_decision_layer.css tests/test_dashboard_layout.py dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Kill pressure and role check become cards\n\nBoth were buried in the radar tooltip. Extracted into shared models so\nthe tooltip and the new column-4 cards read the same numbers. Still\npurely descriptive: no scoring call site changes.\n')"
git commit -F .git/cm.txt
```

---

### Task 9: Full gate run and docs regeneration

**Files:**
- Modify: `dashboard/index.html`, `dashboard/how-it-works.html`, `docs/index.html`, `docs/how-it-works.html` (regenerated)
- Modify: `dashboard/README.md` (document `_layout.css`)
- Modify: `HANDOFF.md` (record the redesign)

**Interfaces:**
- Consumes: everything.
- Produces: a green branch ready for review.

- [ ] **Step 1: Regenerate every page from clean sources**

Run bare, never piped:

```
py -3 dashboard/build.py
```

Expected: exit 0.

- [ ] **Step 2: Run the full display-layer gate list**

Run each directly; exit 0 = pass. Do not trust historical pass counts in docs — read the current output.

```
py -3 tests/test_dashboard_layout.py
py -3 tests/test_js_parity.py
node tests/test_display_math.js
node tests/test_loadout_codec.js
```

If any fails, fix the cause before continuing — a layout change cannot legitimately move a parity or display-math result.

- [ ] **Step 3: Confirm no CRLF churn**

Windows rebuilds churn the tree with CRLF copies if a writer lost its `newline="\n"`. Check the diff is real:

```
git diff --stat
```

Expected: only files you intended to change. If a generated page shows a whole-file rewrite with no visible content change, a writer lost its LF discipline — fix it in `build.py`.

- [ ] **Step 4: Visual verification at all four widths**

Serve and screenshot into `.playwright-mcp/` (gitignored):

```
py -3 -m http.server --directory dashboard 8099
```

At 1867, 1500, 1300 and 900px with a forged 20-player comp, confirm:

- 1867 — four columns; radar + capability supply left, wheel, pick card, kill pressure + roles + warnings right; no horizontal scrollbar
- 1500 — three columns; the pressure row full-width beneath
- 1300 — matches `origin/main`'s two-column hero grid
- 900 — single-column stack; both tab rails are horizontal at the bottom and panels open as bottom sheets
- At every width: all four panels (setup, tools, party, live) open, close, and persist across reload

- [ ] **Step 5: Update `dashboard/README.md`**

Add `_layout.css` to the sources list and state the boundary:

```markdown
- `_shell.html`, `_layout.css`, `_app.js`, `_loadout.js`,
  `_decision_layer.js/.css`, `_explainer.html` — the **sources** (the `_`
  prefix marks them).
```

And under **Boundary**, add:

```markdown
- **One home per layout rule.** `_layout.css` owns the `.shell`/`.main` grid,
  the wheel stage, the `.epanel` edge-panel system and every layout `@media`
  block; it is inlined LAST so it wins on source order without `!important`.
  `_shell.html` and `_decision_layer.css` keep component chrome only.
  `tests/test_dashboard_layout.py` pins this.
```

- [ ] **Step 6: Record the change in `HANDOFF.md`**

Add an entry describing the redesign: the four-column grid, the `.epanel` system replacing the rail, the status bar, the two new descriptive cards, and the new gate `py -3 tests/test_dashboard_layout.py`. Follow the file's existing entry format — read the most recent entry first and match it.

- [ ] **Step 7: Commit**

```bash
git add dashboard/README.md HANDOFF.md dashboard/index.html dashboard/how-it-works.html docs/index.html docs/how-it-works.html
py -3 -c "import io;io.open('.git/cm.txt','w',encoding='utf-8',newline='\n').write('Document the layout boundary and regenerate the pages\n\nAdds the new dashboard layout gate to the docs and records the density\nredesign in HANDOFF.\n')"
git commit -F .git/cm.txt
```

- [ ] **Step 8: Open the PR**

```bash
git push -u origin dashboard-density-redesign
```

Then open a PR against `main` describing the redesign and listing the gates run. Do not merge — the owner reviews.

---

## Notes for the executor

- **The 1300px screenshot is the regression contract.** Everything below 1251px is meant to be byte-for-byte the behaviour on `origin/main`. If it moved, a rule was dropped in Task 2 or a `[data-rail]` selector removal in Task 5 took a live rule with it.
- **`tests/test_cohort_families.py` is not in this plan's gate list** — it is unrelated to the display layer, and under a Git-Bash-spawned console it dies with a `UnicodeDecodeError` that is an environment artifact, not a contract failure.
- **If a task reveals that a rule cannot move cleanly**, stop and report rather than adding `!important`. The whole point of `_layout.css` is that source order makes `!important` unnecessary; reaching for it means a rule is in the wrong file.
