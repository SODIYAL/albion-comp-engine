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


def seg(src, start, end, label):
    """Slice src between two anchors. A missing anchor is a RECORDED failure,
    never a traceback - a bare .index() here used to kill the whole report at
    the first renamed anchor, hiding every later contract behind it."""
    i = src.find(start)
    j = src.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        check(False, label, "anchor %r missing" % (start if i < 0 else end))
        return ""
    return src[i:j]


SHELL = read("_shell.html")
DECISION_CSS = read("_decision_layer.css")
DECISION_JS = read("_decision_layer.js")
APP = read("_app.js")
LAYOUT = read("_layout.css")
with open(os.path.join(DASH, "build.py"), encoding="utf-8") as f:
    BUILD = f.read()

print("L1 - layout source exists and is wired into the build")

check(LAYOUT.strip() != "", "L1a _layout.css is non-empty")
check("_layout.css" in BUILD, "L1b build.py reads _layout.css")
_dc, _lc = BUILD.find("_decision_layer.css"), BUILD.find("_layout.css")
check(
    0 <= _dc < _lc,
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
# at <=960px BOTH rails become full-width fixed bottom bars; without
# click-through the later-DOM rail's transparent box eats the other's taps
check("pointer-events:none" in LAYOUT and "pointer-events:auto" in LAYOUT,
      "L4j phone tab bars are click-through outside their tabs",
      "setup/tools tabs sat under the right rail's invisible container")
# phones collapse every panel into ONE bottom-sheet slot; a second open
# panel just hides underneath with its tab still reading expanded
_sp = seg(APP, "function setPanel", "function syncPanelRail", "L4k anchors")
check('matchMedia("(max-width:960px)")' in _sp,
      "L4k phones hold one open panel TOTAL, not one per edge")
check("function setPanel(id, open, persist)" in APP,
      "L4l setPanel can close without persisting")
check('setPanel("pdash", false, false)' in APP,
      "L4l closePdash's transient drawer-overlay close does not persist",
      "opening the evidence drawer used to erase the saved panel choice")
check('.epanel[data-open="true"]{z-index:42}' in LAYOUT,
      "L4m an open panel rises above its rail on desktop",
      "the rail sat on the kit flyout's hover path and mouseleave killed it")
# the desktop/phone split must TILE: a (min-width:961px) media paired with
# the <=960 block left 960.5px (scaled displays) matching neither - the
# rule is unconditional and the phone block lowers it back
check("min-width:961px" not in LAYOUT,
      "L4m2 the z-order split is unconditional + phone reset, not a gapped pair")
check('.epanel[data-open="true"]{z-index:40}' in LAYOUT,
      "L4m3 phones keep the tab bar above the open sheet")
check(LAYOUT.count("--epw:min(") == 1,
      "L4n one --epw declaration - panel and rail must read the SAME width",
      "two copies let the rail translate by a stale width and detach")

print("L5 - status bar")

head = seg(SHELL, '<header class="masthead">', "</header>", "L5 masthead anchors")
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
# the size input lives here now; the extrapolation/over-cap honesty notice
# must be visible where the size is SET, not only inside the shut setup panel
check('id="size-notice-mh"' in head,
      "L5h the size honesty notice is mirrored beside the size controls",
      "setting an unvalidated size used to warn only inside a closed panel")
check('"size-notice-mh"' in APP, "L5i renderSetup fills the masthead notice")

print("L6 - the in-flow rail is gone")

# plain substring checks: do NOT leave explanatory comments naming these
for dead in ["data-rail", "rail-toggle", "rail-strip", "rail-expand",
             "msetup", "rs-btn", "rs-forge", "RAIL_KEY", "setRail"]:
    check(dead not in SHELL, "L6a %s absent from _shell.html" % dead)
    check(dead not in LAYOUT, "L6b %s absent from _layout.css" % dead)
    check(dead not in APP, "L6c %s absent from _app.js" % dead)
check('id="setup-panel"' in SHELL, "L6d setup panel exists")
check('data-panel="setup-panel"' in SHELL, "L6e setup panel has a tab")
for keep in ['id="share"', 'id="export"', 'id="clear"',
             'id="size-presets"', 'id="size-hint"', 'id="style-blurb"',
             'id="size-notice"']:
    check(keep in SHELL, "L6f setup panel keeps %s" % keep)

print("L7 - deep interactive surfaces live in panels")

check('id="tools-panel"' in SHELL, "L7a caller-tools panel exists")
check('id="live-panel"' in SHELL, "L7b live-party panel exists")
check('data-panel="tools-panel"' in SHELL, "L7c tools panel has a tab")
check('data-panel="live-panel"' in SHELL, "L7d live panel has a tab")
main = seg(SHELL, '<main class="main">', "</main>", "L7 main anchors")
check('class="livefeed"' not in main and main != "", "L7e livefeed left .main")
check('id="meta-sec"' in main, "L7f killboard stays a deep board in .main")
check("tools-panel" in DECISION_JS, "L7g tools fold mounts into its panel")
# the connect button stayed in the masthead while its feedback moved into
# the default-closed live panel - connecting must open the panel too
check('setPanel("live-panel", true' in APP,
      "L7h connecting the companion opens the live panel",
      "status, troubleshooting and load-party rendered into a shut panel")

print("L8 - the column grid")

# SHAPE pins, never tuning values (a nudged breakpoint or wheel width must
# not fail the gate - that trains mechanical re-pinning): grid bands are
# the media blocks whose .main declares a track template. One two-, one
# three- and one four-column band, each carrying a wheel-width override.
_bands = [b for b in re.split(r"(?=@media )", LAYOUT)
          if ".main{grid-template-columns:" in b]
_tracks = sorted(b.split(".main{grid-template-columns:")[1].split("}")[0]
                 .count("minmax(") for b in _bands)
check(_tracks == [2, 3, 4],
      "L8a one two-, one three- and one four-column band", str(_tracks))
check(all("--wd:min(" in b for b in _bands),
      "L8b every grid band sets its wheel width")
# 125%/150% display scaling yields fractional viewport widths (1399.5px);
# an integer max-width leaves an open interval matching NO band, and the
# base >=1251 grid has no column template - the page collapsed to one column
check(not re.search(r"max-width:1\d{3}px\)", LAYOUT),
      "L8c no integer band boundary leaves a fractional-width gap")
for _x in re.findall(r"max-width:(\d+)\.98px\)", LAYOUT):
    check(("min-width:%dpx" % (int(_x) + 1)) in LAYOUT,
          "L8d the band above max-width:%s.98px starts at %dpx - bands tile"
          % (_x, int(_x) + 1))
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
tip = seg(DECISION_JS, "function centerTipHtml", "function roleAdvisory",
          "L9h centerTipHtml anchors")
check("ENG.killPressure" not in tip and tip != "",
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
# the bar is ONE segmented container that never wraps ON DESKTOP (owner
# 2026-09-02); below 640px it wraps - it cannot scroll (overflow would clip
# its own popups, see L11m) and its nowrap segments overpainted each other
_wfb = SHELL.find(".wf-bar{")
check(_wfb >= 0 and "flex-wrap:nowrap" in SHELL[_wfb:_wfb + 400],
      "L11i the bar never wraps to a second line on desktop")
check(".wf-bar{flex-wrap:wrap}" in SHELL,
      "L11n below 640px the bar wraps",
      "phones can neither scroll it nor fit it on one line")
check("<select" not in seg(SHELL, 'class="wf-bar"', "</main>", "L11j bar anchors"),
      "L11j no native select in the bar - the tree menu carries icons")
check('id="tree-menu"' in SHELL and "setTreeMenu" in APP,
      "L11k the tree dropdown is a real listbox")
check("treeIconFor" in APP, "L11l tree options carry a weapon icon")
# The bar hosts three absolutely-positioned popups (chip flyouts, tree menu,
# search). Any overflow other than visible makes it a clipping context and
# silently cuts all three off - which shipped once on 2026-09-02.
bar = seg(SHELL, ".wf-bar{", "}", "L11m bar rule anchors")
bar = re.sub(r"/\*.*?\*/", "", bar, flags=re.S)   # a comment may say the word
check(not re.search(r"overflow[-a-z]*\s*:", bar) and bar != "",
      "L11m .wf-bar declares no overflow - it would clip its own popups",
      bar.strip())


print("L12 - the hub gauges do not clip their own glow")

hub = seg(SHELL, ".hub-rings{", "}", "L12 hub rule anchors")
glow = ".hub-rings .ring-fill.done" in SHELL and "drop-shadow(0 0 5px currentColor)" in SHELL
check(not glow or "overflow:visible" in hub,
      "L12a .hub-rings stays overflow:visible while .done carries a glow",
      "an <svg> clips at its viewport, squaring off the outermost ring's glow")

print("L13 - the wheel foot stopped repeating the page")

foot = seg(APP, '$("wheel-foot").innerHTML', "const fslot", "L13 foot anchors")
check("party <b>" not in foot and foot != "",
      "L13a the foot no longer prints party n/n",
      "the ring legend below it already did, and so do the masthead and tab")
check("slotLabel" not in foot, "L13b slot number left to the pick card header")
check("esc(sn)" not in foot, "L13c playstyle left to the masthead and radar")
check('id="forge-slot"' in SHELL, "L13d forge actions have a masthead home")
check('id="forge-rail"' not in SHELL,
      "L13e the setup panel's half of the forge pair is gone")
check("#forge-rail" not in APP, "L13f and its handler with it")
# at the hard cap recs is null; gating BOTH buttons on recs left a 60/60
# roster with no reforge control anywhere (the deleted rail button was the
# only entry point in that state)
check("const reforgeBtn" in APP and 'id="reforge"' in APP,
      "L13g reforge stays reachable at the hard cap",
      "reforge needs no recommendation capacity - it rebuilds forged slots")
wf_head = seg(APP, "function renderWheelFoot", '$("wheel-foot")', "L13h foot head anchors")
check("styleName()" not in wf_head and "slotLabel" not in wf_head,
      "L13h the foot no longer computes labels it never renders")
check(APP.count("${party.length}/${PLAN()}") == 1,
      "L13i the party count string is built once for its two homes",
      "two adjacent copies drift the masthead count from the party tab")

print("L14 - the open slot adds to the party")

check('id="open-slot-add"' in APP, "L14a the open slot is a real control")
check("open-slot-add" in APP and "setPickSearch(" in APP,
      "L14b it opens the shared search rather than a second copy")
check(SHELL.count('id="pick-search-pop"') == 1,
      "L14c there is exactly one search popover to keep in sync",
      "the markup lives in _shell.html - counting _app.js was vacuous")
# it is re-parented into the board, which re-renders its innerHTML on every
# roster change - it MUST be moved back out on close or it is destroyed
sp = seg(APP, "function setPickSearch", "function renderPickHits", "L14d anchors")
check("home.appendChild(pop)" in sp,
      "L14d the popover returns to the toolbar when it closes",
      "the party board would otherwise wipe it on the next render")
# ... and while it is OPEN at the open slot, every renderWheel rebuilds the
# board - the wipe site must park the live popover and re-seat it, or the
# first keystroke in the open-slot search destroys the node for the session
wff = seg(APP, "function renderWheelFoot", "function renderWheel(", "L14e anchors")
check("parkedPickSearch(" in wff and "dash.innerHTML" in wff
      and wff.find("parkedPickSearch(") < wff.find("dash.innerHTML")
      and "reseatPickSearch(" in wff,
      "L14e a live popover survives the board rebuild",
      "park BEFORE dash.innerHTML, re-seat after - typing triggers renders")
_ent = APP.find('$("pick-filter").addEventListener("keydown"')
check(_ent >= 0 and "setPickSearch(false)" in APP[_ent:_ent + 400],
      "L14f Enter-to-add dismisses the popover like the click path does")
check('$("pick-search-pop").hidden' not in APP,
      "L14g popover derefs are null-guarded",
      "a destroyed popover must not throw on every Escape press")

print("L15 - one palette for the group surfaces")

meta = seg(DECISION_JS, "const DL_GROUP_META", "};", "L15 anchors")
check("GROUP_COL." in meta,
      "L15a the radar reads the app's GROUP_COL hues",
      "the comment claims ONE source; the radar kept its own copy")
check('"#' not in meta, "L15b no second hand-stepped hex table to drift")
# statusRadar is a markup function evaluated inside template literals - a
# hidden #sb-identity write mid-evaluation coupled it to a clear two
# functions away; the write is an explicit renderDecisionLayer step now
_sr = seg(DECISION_JS, "function statusRadar", "let CHAIN_OPEN", "L15c anchors")
check("sb-identity" not in _sr and _sr != "",
      "L15c statusRadar builds markup only - no hidden status-bar write")
check("function syncSbIdentity" in DECISION_JS,
      "L15d the status-bar identity write is an explicit named step")
check("function identityModel" in DECISION_JS,
      "L15e compIdentity is memoised like the other per-pass models")

print("L16 - one engine walk per render pass")

check("DL_MEMO" in DECISION_JS,
      "L16a kill-pressure and role models are memoised per pass",
      "killPressure ran 2x and roleAdvisory 3x on every render")
check("function whyNotBlock(rec, shown, rep)" in DECISION_JS,
      "L16b whyNotBlock reuses the pick report already in hand",
      "two pickReport calls per render can silently diverge")

print("L17 - the layout file carries no stale component chrome")

for dead in [".dl-add{margin-top:10px}", ".dl-gains li{padding:6px 7px}",
             "width:68px", "grid-template-columns:1fr 1fr"]:
    check(dead not in LAYOUT, "L17a stale override %s gone from _layout.css" % dead,
          "inlined last, it silently beat the redesigned component chrome")
_wr = LAYOUT.find(".dl-col1, .dl-col3, .dl-pressure{display:flex")
_mq = LAYOUT.find("@media (min-width:1251px)")
check(0 <= _wr < _mq,
      "L17b column wrappers keep their card gap at every width",
      "below 1251px the wrapper divs stacked their cards flush")
check(".dl-tools{display:grid;grid-template-columns:1fr;" in DECISION_CSS,
      "L17c the tools fold is one column - it lives in a 430px panel",
      "a viewport-keyed 2-col grid crushed the pool/swap cards to ~190px")
check("@media(max-width:900px){.dl-tools" not in DECISION_CSS,
      "L17d the dead viewport escape for the tools grid is gone")
# the wheel stage wraps ONE visible child everywhere (.ws-right is
# display:none, no left flank exists in markup) - the multi-column stage
# machinery placed flanks that never render
check(".wheelstage{display:block}" in LAYOUT,
      "L17e the stage is a plain block below the dissolve",
      "its 3-col template would crush the lone .ws-center into column 1")
for dead in ["max-width:1560px", ".ws-center{order:1}", "order:2}", "order:3}",
             ".wheelstage{gap:20px}"]:
    check(dead not in LAYOUT,
          "L17f retired flank geometry %s gone from _layout.css" % dead)

print("L18 - markup rewrites took their selectors with them")

check(".wf-over{" in SHELL, "L18a the over-plan warning is styled",
      "it rendered as default body text amid 10px mono chips")
check(".dl-alt-row" not in DECISION_CSS, "L18b .dl-alt-row orphan gone")
check(".wf-actions{" not in SHELL, "L18c .wf-actions orphan gone")
check(".wheel-foot .eyebrow{" not in SHELL, "L18d .eyebrow orphan gone")

if FAILURES:

    print("\n%d contract(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall dashboard layout contracts pass")
sys.exit(0)
