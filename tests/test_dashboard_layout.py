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
        print("  FAIL %s%s" % (label, (" - " + detail) if detail else ""))
        FAILURES.append(label)


SHELL = read("_shell.html")
DECISION_CSS = read("_decision_layer.css")
DECISION_JS = read("_decision_layer.js")
APP = read("_app.js")
LAYOUT = read("_layout.css")
BUILD = open(os.path.join(DASH, "build.py"), encoding="utf-8").read()

print("L1 - layout source exists and is wired into the build")

check(LAYOUT.strip() != "", "L1a _layout.css is non-empty")
check("_layout.css" in BUILD, "L1b build.py reads _layout.css")
check(
    BUILD.index("_decision_layer.css") < BUILD.index("_layout.css"),
    "L1c _layout.css is inlined AFTER _decision_layer.css",
    "source order is what lets layout rules win without !important",
)

print("L2 - display-only boundary: no new engine calls")

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

print("L2 (cont.) - roster mutations stay centralised")

for anchor in ["sortPartyByRole", "data-add", "data-swapat"]:
    check(anchor in APP, "L2b %s still routes roster mutation" % anchor,
          "layout work must not introduce a second mutation path")
check(
    APP.count("function sortPartyByRole") == 1,
    "L2c exactly one sortPartyByRole definition",
)

print("L3 - one home per layout rule")

OWNED = [".shell{", ".main{", ".wheelstage{", ".ws-flank{", ".ws-center{",
         ".epanel{", ".epanel-tab{", ".epanel-body{"]
for sel in OWNED:
    check(sel in LAYOUT, "L3a %s defined in _layout.css" % sel)
    check(sel not in SHELL, "L3b %s NOT left in _shell.html" % sel)
    check(sel not in DECISION_CSS, "L3c %s NOT left in _decision_layer.css" % sel)
# Component cards (.dl-gains, .dl-tools, .dl-alt-row) legitimately use their
# own internal grids. What must NOT live here is the PAGE grid: the dissolve
# trick, the stage children it re-parents, and the hero breakpoint.
for marker in ["display:contents", ".ws-right", ".wheelstage", "min-width:1251px"]:
    check(marker not in DECISION_CSS,
          "L3d page-grid marker %s absent from _decision_layer.css" % marker,
          "component grids are fine here; the page grid belongs to _layout.css")

print("L4 - the edge-panel component")

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

print("L5 - status bar")

head = SHELL[SHELL.index('<header class="masthead">'):SHELL.index("</header>")]
for el in ['id="fit-num"', 'id="fit-of"', 'id="fit-bar"', 'id="sb-identity"',
           'id="sb-count"', 'id="style"', 'id="size-input"', 'id="content"',
           'id="parity-chip"', 'id="build-stamp"']:
    check(el in head, "L5a masthead carries %s" % el)
check(SHELL.count('id="fit-num"') == 1, "L5b #fit-num is not duplicated")
check(SHELL.count('id="style"') == 1, "L5c #style is not duplicated")
check(SHELL.count('id="size-input"') == 1, "L5d #size-input is not duplicated")
check('class="foot-chips"' not in SHELL and ".foot-chips{" not in SHELL,
      "L5e .foot-chips retired - its chips moved up",
      "markup and rule both gone; a mention in a comment is fine")
check('"sb-identity"' in DECISION_JS, "L5f decision layer fills #sb-identity")
check('"sb-count"' in APP, "L5g _app.js fills #sb-count")

print("L6 - the in-flow rail is gone")

# plain substring checks: do NOT leave explanatory comments naming these
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

print("L7 - deep interactive surfaces live in panels")

check('id="tools-panel"' in SHELL, "L7a caller-tools panel exists")
check('id="live-panel"' in SHELL, "L7b live-party panel exists")
check('data-panel="tools-panel"' in SHELL, "L7c tools panel has a tab")
check('data-panel="live-panel"' in SHELL, "L7d live panel has a tab")
main = SHELL[SHELL.index('<main class="main">'):SHELL.index("</main>")]
check('class="livefeed"' not in main, "L7e livefeed left .main")
check('id="meta-sec"' in main, "L7f killboard stays a deep board in .main")
check("tools-panel" in DECISION_JS, "L7g tools fold mounts into its panel")

print("L8 - the column grid")

check("@media (min-width:1700px)" in LAYOUT, "L8a four-column breakpoint exists")
check("@media (min-width:1400px) and (max-width:1699px)" in LAYOUT,
      "L8b three-column breakpoint exists")
check("@media (min-width:1251px) and (max-width:1399px)" in LAYOUT,
      "L8c the 1251-1399 hero grid is preserved")
check("--wd:min(520px,100cqi)" in LAYOUT, "L8d wheel shrinks to 520px in the four-col grid")
check('id="supply-sec"' in SHELL, "L8e capability supply section is placeable")
# every selector the grid places must be a real .main child (or a child of a
# display:contents wrapper), else the rule silently does nothing
for sel in ["#supply-sec", "#warn-slot", "#meta-sec"]:
    check(sel.lstrip("#.") in SHELL, "L8f grid target %s exists in markup" % sel)

print("L9 - kill pressure and role check are cards")

check("killPressureCard" in DECISION_JS, "L9a killPressureCard defined")
check("roleCard" in DECISION_JS, "L9b roleCard defined")
check("dl-kp" in DECISION_JS, "L9c .dl-kp rendered")
check("dl-roles" in DECISION_JS, "L9d .dl-roles rendered")
check(".dl-kp" in DECISION_CSS, "L9e .dl-kp chrome in _decision_layer.css")
check(".dl-roles" in DECISION_CSS, "L9f .dl-roles chrome in _decision_layer.css")
check(".dl-kp{" not in LAYOUT, "L9g .dl-kp chrome is NOT in _layout.css")
tip = DECISION_JS[DECISION_JS.index("function centerTipHtml"):]
tip = tip[:tip.index("function roleAdvisory")]
check("ENG.killPressure" not in tip,
      "L9h centerTipHtml no longer calls the engine directly",
      "it must go through the shared helper so tooltip and card agree")

print("L10 - the pick card is split into three")

check("dl-col3" in DECISION_JS, "L10a column wrapper emitted")
for cls in ["dl-need", "dl-chain-card", "dl-pick"]:
    check('"%s"' % cls in DECISION_JS or 'class="%s"' % cls in DECISION_JS,
          "L10b %s card emitted" % cls)
check(".dl-col3{" in LAYOUT or ".dl-col3," in LAYOUT,
      "L10c .dl-col3 placed by _layout.css")

print("L11 - the add-weapon bar is one row")

check('class="wf-bar"' in SHELL, "L11a single-row bar exists")
check("wheel-filters" not in SHELL, "L11b the stacked filter wrapper is gone")
check("wf-filter-row" not in SHELL, "L11c its row wrapper is gone too")
check('id="pick-filter"' in SHELL, "L11d the live filter input survives")
check(SHELL.count('id="pick-filter"') == 1, "L11e and is not duplicated")
check("setPickSearch" in APP, "L11f search popover has a state machine")
# an active query must stay visible - a silently narrowed wheel was the risk
check("syncPickSearch" in APP, "L11g an active query is mirrored onto the button")
check('id="pick-search-q"' in SHELL, "L11h the button carries the query text")
# the bar is ONE segmented container that never wraps (owner 2026-09-02)
check("flex-wrap:nowrap" in SHELL[SHELL.index(".wf-bar{"):SHELL.index(".wf-bar{") + 400],
      "L11i the bar never wraps to a second line")
check("<select" not in SHELL[SHELL.index('class="wf-bar"'):SHELL.index("</main>")],
      "L11j no native select in the bar - the tree menu carries icons")
check('id="tree-menu"' in SHELL and "setTreeMenu" in APP,
      "L11k the tree dropdown is a real listbox")
check("treeIconFor" in APP, "L11l tree options carry a weapon icon")
# The bar hosts three absolutely-positioned popups (chip flyouts, tree menu,
# search). Any overflow other than visible makes it a clipping context and
# silently cuts all three off - which shipped once on 2026-09-02.
bar = SHELL[SHELL.index(".wf-bar{"):SHELL.index("}", SHELL.index(".wf-bar{"))]
bar = re.sub(r"/\*.*?\*/", "", bar, flags=re.S)   # a comment may say the word
check(not re.search(r"overflow[-a-z]*\s*:", bar),
      "L11m .wf-bar declares no overflow - it would clip its own popups",
      bar.strip())


print("L12 - the hub gauges do not clip their own glow")

hub = SHELL[SHELL.index(".hub-rings{"):SHELL.index("}", SHELL.index(".hub-rings{"))]
glow = ".hub-rings .ring-fill.done" in SHELL and "drop-shadow(0 0 5px currentColor)" in SHELL
check(not glow or "overflow:visible" in hub,
      "L12a .hub-rings stays overflow:visible while .done carries a glow",
      "an <svg> clips at its viewport, squaring off the outermost ring's glow")

if FAILURES:
    print("\n%d contract(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall dashboard layout contracts pass")
sys.exit(0)
