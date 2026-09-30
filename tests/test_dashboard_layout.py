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
# the bar is ONE segmented container that never wraps ON DESKTOP (the
# density redesign); at and below 960px it wraps - it cannot scroll (overflow
# would clip its own popups, see L11m) and its nowrap segments overpainted
# each other
_wfb = SHELL.find(".wf-bar{")
check(_wfb >= 0 and "flex-wrap:nowrap" in SHELL[_wfb:_wfb + 400],
      "L11i the bar never wraps to a second line on desktop")
check(".wf-bar{flex-wrap:wrap}" in SHELL,
      "L11n at and below 960px the bar wraps",
      "phones can neither scroll it nor fit it on one line")
check("<select" not in seg(SHELL, 'class="wf-bar"', "</main>", "L11j bar anchors"),
      "L11j no native select in the bar - the tree menu carries icons")
check('id="tree-menu"' in SHELL and "setTreeMenu" in APP,
      "L11k the tree dropdown is a real listbox")
check("treeIconFor" in APP, "L11l tree options carry a weapon icon")
# The bar hosts three absolutely-positioned popups (chip flyouts, tree menu,
# search). Any overflow other than visible makes it a clipping context and
# silently cuts all three off - which shipped once.
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

print("L19 - the page iterates the rows the ENGINE judges, never the raw template")
# A ramp row (anti_zone, none_until 14) is dropped from ENG.reqs
# at small sizes; REQS() read tpl().requirements and handed the capability
# board a cap with no weight - render() died on the first paint (empty
# party) at castle / blackzone_roam / territory_defense / faction_war and
# the page stayed half-drawn. The display layer reads ENG.reqs, one source.
check("const REQS = () => ENG.reqs;" in APP, "L19a REQS() is ENG.reqs")
check("tpl().requirements" not in APP, "L19b no raw template requirement read in _app.js")
check(".requirements" not in read("_decision_layer.js"), "L19c the decision layer reads no raw template rows")

print("L20 - the board shows the TYPICAL winner in four stages, and says when it cannot")
# Target is the median (standing rule 17): the second number on every row
# was the least any winner fielded, labelled 'target'; every row overshot
# and the reader concluded three healers at 15 was too many. The label now
# says typical; the ring reads red below the bare minimum, amber up to
# typical, green to the soft cap, purple past it (three stages, then purple);
# a row whose target is not a measured median says so on hover, in words the
# ENGINE's provenance picks (targetSource) - never a page-side rule, and
# never a chip on the visible label (a customer cannot act on provenance).
check("capability supply vs. typical winner" in SHELL.lower(),
      "L20a the section label says typical winner")
check("const targetSource = cap => ENG.targetSource(cap);" in APP
      and "const targetMin = cap => ENG.targetMin(cap);" in APP,
      "L20b the page reads provenance and the minimum from the engine")
board = seg(APP, "function renderGroups", "function renderWeaknesses", "L20 board anchors")
check("targetSource(" in board and 'class="tag src' not in board,
      "L20c the board reads content_min / borrowed from targetSource and notes it on hover, not as a chip")
check('have < lo ? "low"' in board and '"part"' in board and '"met"' in board,
      "L20d the ring has the four stages: low < min <= part < typical <= met < soft cap < over")
check("/ typical" in board, "L20e the legend value is labelled typical")
check(".ring.low{" in SHELL and ".cap-sw.low{" in SHELL,
      "L20f the low stage is styled")
check(".tag.src{" not in SHELL, "L20i the retired src chip took its selector with it")
why = seg(APP, "function whySentence", "function loadHash", "L20 why anchors")
check("c !== lead.cap" in why, "L20g the lead gap never appears in 'already covers'")
sync = seg(APP, "function syncEngine", "function gearsFromLoadout", "L20 sync anchors")
check("PLANNED = Math.max(PLANNED, party.length)" in sync,
      "L20h the SIZE stepper follows roster growth on every path")

# L21 - slot controls (F32/F33): lock / replace / refresh-rest
# beside the hover x on every tile and in the popover's action row; the
# replace list is the ENGINE's one-slot forge (the page never ranks);
# refresh walks the next-best comp through the forge's `avoid` list;
# locks survive the permalink and a content switch
tile = seg(APP, "function buildCompBoard", "function renderRoster", "L21 tile anchors")
check(all(x in tile for x in ('data-lock="${i}"', 'data-replace="${i}"',
                              'data-refresh="${i}"', 'data-remove="${i}"')),
      "L21a every tile carries lock / replace / refresh-rest / remove controls")
check('PROV[i] === "l" ? " locked" : ""' in tile,
      "L21b a locked tile is marked at rest, not only on hover")
pop = seg(APP, "function memberPop", "function replaceListHtml", "L21 popover anchors")
check(all(x in pop for x in ("data-lock=", "data-replace=", "data-refresh=", "data-remove=")),
      "L21c the popover action row carries the same four actions (touch)")
rl = seg(APP, "function replaceListHtml", "let BOARD_HTML", "L21 replace anchors")
check("data-replaceto=" in rl and "REPLACE_OPTS" in rl and ".sort(" not in rl,
      "L21d the replace list renders the engine's ranked options and never ranks itself")
handlers = seg(APP, 'const rp = e.target.closest("[data-replace]")',
               'const rm = e.target.closest("[data-remove]")', "L21 handler anchors")
check("ENG.replaceOptions(party, ri, COMBOS_CUR, GEARS_CUR, 5)" in handlers,
      "L21e replace options come from the engine's one-slot forge with the roster's own combos and kits")
check('PROV[si] = PROV[si] === "l" ? "l" : "m"' in handlers,
      "L21f applying a replacement keeps a lock and makes a forged slot a manual pick")
rfn = seg(APP, "function refreshUnlocked", "function render()", "L21 refresh anchors")
check('.filter(i => PROV[i] === "l")' in rfn and "AVOID" in rfn
      and "lockedGears, AVOID)" in rfn and "r.exhausted" in rfn,
      "L21g refresh holds only LOCKED slots, forges in the on-screen kits, passes the shown rosters as avoid, and reports exhaustion")
check('PROV[holdIndex] = "l"' in rfn,
      "L21h a refresh from a tile locks that tile's weapon first")
check("AVOID_SIG" in rfn and "lockSignature(locked, forgeSize)" in rfn,
      "L21i the avoid list resets when the locks, content, style or size change")
foot = seg(APP, "function renderWheelFoot", "function renderWheel(", "L21 foot anchors")
check('PROV[i] !== "l")' in foot and "refresh unlocked" in foot,
      "L21j the global button is 'refresh unlocked', shown while any slot is unlocked")
codec = seg(read("_loadout.js"), "function provEncode", "function provDecode", "L21 codec anchors")
check("PROV_STATES" in codec and "l: true" in read("_loadout.js"),
      "L21k the permalink provenance codec carries the lock state")
switch = seg(APP, 'if (e.target.id === "content")', 'if (e.target.id === "style")', "L21 switch anchors")
check('PROV[i] === "l" ? "l" : "m"' in switch,
      "L21l locks survive a content switch")
check(".wf-ctl{" in SHELL and ".wf-dm.locked .wf-mcard{" in SHELL and ".dm-replace{" in SHELL,
      "L21m the controls, the locked tile and the replace list are styled")
# monoline UI icons (the reference set): one inline-SVG
# helper, currentColor, no emoji or text glyphs on the controls
uih = seg(APP, "const UI_ICONS = {", "const ROLE_LABELS", "L21 icon anchors")
check(all(k in uih for k in ("lock:", "unlock:", "replace:", "refresh:", "close:"))
      and 'stroke="currentColor"' in uih and 'stroke-linecap="round"' in uih,
      "L21n the slot controls draw from one monoline SVG helper (lock / unlock / replace / refresh / close, currentColor, round caps)")
check(all(x in tile for x in ('ui(PROV[i] === "l" ? "lock" : "unlock", 12)', 'ui("replace", 12)',
                              'ui("refresh", 12)', 'ui("close", 12)', 'ui("lock", 10)'))
      and not any(g in tile for g in ("&#128274;", "&#128275;", "&#8646;", "&#8635;")),
      "L21o every tile control and the at-rest lock mark are SVG icons, never emoji or text glyphs")
check(all(x in pop for x in ('ui(PROV[i] === "l" ? "unlock" : "lock", 11)', 'ui("replace", 11)',
                             'ui("refresh", 11)', 'ui("close", 11)')),
      "L21p the popover action row carries the same icons in front of the words")
check("1F512" not in SHELL and ".wf-mcard .n .ui{" in SHELL and ".dm-act .ui{" in SHELL,
      "L21q the emoji lock mark is gone; the icon slots are styled")

# L22 - tile labels (R37): PRIMARY · tag · tag composed from
# the detected seat's word and the weapon's dataset `label.tags`; the page
# composes and never derives a tag
lab = seg(APP, "const fine = (id, w) =>", "const CLS = {", "L22 label anchors")
check(".label" in lab and "L.tags" in lab and "det.word" in lab
      and 'det.class !== "healer"' in lab and "capabilities" not in lab,
      "L22a the tile label reads the seat word + dataset label.tags (healers keep their profile word) and never touches capabilities")
check("fine(m.role, party[i])" in tile,
      "L22b every tile composes its label from the member's detected seat and its own weapon")

# L23 - three visual fixes: the picker facet never
# overruns the controls, interaction badges are text pills, the masthead
# size chip does not inherit the note box's margin
check("#picker-chips, .wf-search{flex:none}" in SHELL and "#facet-slot{flex:1 1 0" in SHELL
      and "container-type:inline-size" in SHELL and "@container (min-width:300px)" in SHELL,
      "L23a the picker controls never shrink; the facet takes the leftover width and shows its description only when the slot has room")
fac = seg(APP, 'const nMatch = ', 'const idx = wheelFocusIdx', "L23 facet anchors")
check('class="facet-n"' in fac and 'class="facet-t"' in fac and 'title="showing:' in fac
      and 'class="w"' in fac and "@container (max-width:150px){ .wf-bar .facet .w{display:none} }" in SHELL
      and "@container (max-width:44px){ .wf-bar .facet .facet-n{display:none} }" in SHELL
      and "overflow:hidden" in seg(SHELL, "#facet-slot{", "#facet-slot:empty", "L23 slot anchors"),
      "L23b the facet readout is count-first, compacts by its own width (words, then the count) and clips rather than spills; the full sentence rides the tooltip")
check(".bdg.b-int{" in SHELL and "width:auto; height:auto" in seg(SHELL, ".bdg.b-int{", "}", "L23 pill anchors")
      and ".int-row>div:first-child{display:flex; flex-wrap:wrap" in SHELL,
      "L23c interaction badges are text pills in a wrapping row, never the 22px icon box")
check(".mh-bar .chip{margin:0}" in LAYOUT and ".mh-bar .sb-count{line-height:1}" in LAYOUT,
      "L23d the masthead size chip and count centre with the controls")

# L24 - content and planned size are separate settings: the content
# label carries no number, the plan sticks once set (PLAN_TOUCHED), a
# content switch resets the plan only while it is untouched, and the
# masthead reads the two numbers as two numbers
opt = seg(APP, "content.innerHTML = Object.entries(DATASET.templates)", "content.dataset.built", "L24 option anchors")
check(opt and "base" not in opt,
      "L24a the content option label is the template name alone, never a base size")
cswitch = seg(APP, 'if (e.target.id === "content"){', "render();", "L24 content-switch anchors")
check("if (!PLAN_TOUCHED) PLANNED = baseSize();" in cswitch,
      "L24b a content switch resets the plan only while the plan is untouched")
check("let PLAN_TOUCHED = false;" in APP,
      "L24c the touched flag starts false on a fresh page")
sz = seg(APP, 'const sz = e.target.closest("[data-size]");', 'const cap = e.target.closest("[data-cap]");', "L24 size-control anchors")
check(sz.count("PLAN_TOUCHED = true") == 3,
      "L24d preset, minus and plus each mark the plan touched")
inp = seg(APP, 'if (e.target.id === "size-input"){', "else {", "L24 size-input anchors")
check("PLAN_TOUCHED = true" in inp,
      "L24e the typed size marks the plan touched")
restore = seg(APP, "PLANNED = (n >= 2 && n <= HARD_CAP) ? n : baseSize();", "STYLE = ", "L24 restore anchors")
check("PLAN_TOUCHED = PLANNED !== baseSize();" in restore,
      "L24f a restored link or session counts as touched when its size is not the template's suggestion")
check("<span>planned</span>" in SHELL and "<span>size</span>" not in SHELL,
      "L24g the masthead field is labelled planned, not size")
check("<label>Suggested size</label>" in SHELL and "Party size presets" not in SHELL,
      "L24h the preset row is labelled as a suggestion")
count = seg(APP, 'const count = `${party.length}/${PLAN()}`;', "$(\"pdash\").style", "L24 count anchors")
check("sbc.title = " in count and "in party" in count and "planned" in count,
      "L24i the masthead count chip carries a tooltip naming both numbers")

# L25 - a content may ask for its size before it forges (template
# size_prompt: the Dragon Portal pools). The ask is raised on the switch
# into such a content, cleared by every size control, answered by a
# link's n=, and while raised the forge slot shows the pools instead of
# the forge button and the masthead chip names it.
check("let ASK_SIZE = false;" in APP and "const needSize = () => !!sizePrompt() && ASK_SIZE;" in APP,
      "L25a the ask flag and its predicate exist")
cswitch25 = seg(APP, 'if (e.target.id === "content"){', "render();", "L25 content-switch anchors")
check("ASK_SIZE = !!sizePrompt();" in cswitch25,
      "L25b the switch into a content raises the ask when the template prompts")
sz25 = seg(APP, 'const sz = e.target.closest("[data-size]");', 'const cap = e.target.closest("[data-cap]");', "L25 size-control anchors")
check(sz25.count("ASK_SIZE = false") == 3,
      "L25c preset, minus and plus each answer the ask")
inp25 = seg(APP, 'if (e.target.id === "size-input"){', "else {", "L25 size-input anchors")
check("ASK_SIZE = false" in inp25, "L25d the typed size answers the ask")
restore25 = seg(APP, "PLANNED = (n >= 2 && n <= HARD_CAP) ? n : baseSize();", "STYLE = ", "L25 restore anchors")
check("ASK_SIZE = !!sizePrompt() && !(n >= 2 && n <= HARD_CAP);" in restore25,
      "L25e a link's size answers the ask, a link without one asks")
foot = seg(APP, "function renderWheelFoot(", "const board = BOARD_HTML;", "L25 forge-slot anchors")
check("needSize()" in foot and 'data-size="${n}"' in foot and "const forge = ask ||" in foot,
      "L25f while the ask is open the forge slot shows the pools as data-size controls instead of the forge button")
check('mh.textContent = "choose a portal size";' in APP,
      "L25g the masthead chip names the open ask")
check('fitStat !== "none" ? "" :' in APP and "No harvested evidence for this content yet" in APP,
      "L25h a content whose fit is none shows the borrowed-evidence notice")
import json as _json
with open(os.path.join(ROOT, "pipeline", "out", "dataset-latest.json"), encoding="utf-8") as _fh:
    tpl25 = (_json.load(_fh).get("templates") or {}).get("ancient_lands") or {}
check(tpl25.get("size_prompt", {}).get("sizes") == [3, 5, 7, 20] and tpl25.get("validated_sizes") == []
      and (tpl25.get("fit") or {}).get("stat") == "none",
      "L25i the Dragon Portal template prompts for 3 / 5 / 7 / 20, validates no size and declares no evidence")

print("L26 - the supply board carries a visible key for its colours and ticks")
# The four ring stages and the two ticks were explained only in source
# comments, and a full ring is the comp-fitted ceiling, not the typical
# winner: a nearly full amber ring read as healthy. The key sits inside the
# section and reuses the rows' own swatch classes, so its colours cannot
# drift from the rows'.
supply_sec = seg(SHELL, '<section id="supply-sec">', "</section>", "L26 supply section anchors")
ring_key = seg(supply_sec, 'class="ring-key"', "</div>", "L26 key anchors")
for stage in ("low", "part", "met", "over"):
    check('class="cap-sw %s"' % stage in ring_key, "L26a the key shows the %s swatch" % stage)
check('class="k-tick"' in ring_key and 'class="k-tick min"' in ring_key,
      "L26b the key draws the typical tick and the minimum tick")
check("typical" in ring_key.lower() and "minimum" in ring_key.lower() and "full ring" in ring_key.lower(),
      "L26c the key names the typical winner, the minimum and what a full ring means")
check(".ring-key{" in SHELL and ".k-tick{" in SHELL and ".k-tick.min{" in SHELL,
      "L26d the key and its ticks are styled")

print("L27 - accounts: the sign-in layer stands apart from the planner")
# The account scripts rode inside the planner's <script>, and _supabase.js
# throws when the Supabase library fails to load (a blocked CDN, a strict-CSP
# host, offline): that one throw stopped the whole planner. The library tag
# sat in <head>, where it held the first paint on the CDN. Now the library,
# the client and the account UI load after the planner, each in its own
# <script>, and the account UI reads and writes no planner state.
AUTH_JS = read("_auth.js")
AUTH_CSS = read("_auth.css")
head = seg(SHELL, "<head>", "</head>", "L27 head anchors")
check("supabase-js" not in head,
      "L27a the Supabase library does not hold the first paint from <head>")
check("window.AUTH_LINK" in head and "access_token" in head and "replaceState" in head,
      "L27b <head> sets an email link's return aside before the planner rewrites the hash")
mast = seg(SHELL, '<header class="masthead">', "</header>", "L27 masthead anchors")
check('id="acct-btn"' in mast and ">Log in<" in mast,
      "L27c the masthead carries the account button, reading Log in when logged out")
dlg = seg(SHELL, '<dialog class="auth-dialog"', "</dialog>", "L27 dialog anchors")
check('aria-modal="true"' in dlg and 'aria-labelledby="auth-title"' in dlg and 'id="auth-title"' in dlg,
      "L27d the sign-in dialog is modal and titled")
for fid in ("login-email", "login-password", "signup-email", "signup-password",
            "signup-albion", "signup-server", "signup-display"):
    check(('id="%s"' % fid) in dlg and ('for="%s"' % fid) in dlg,
          "L27e field %s has its label" % fid)
check('data-auth-view="signup"' in dlg and 'data-auth-view="login"' in dlg,
      "L27f log in and create account switch to each other")
check('role="alert"' in dlg, "L27g the dialog's errors are announced, inside the dialog")
acct_menu = seg(SHELL, 'id="acct-menu"', 'id="acct-menu-err"', "L27 menu anchors")
check('id="acct-profile"' in acct_menu and 'id="acct-logout"' in acct_menu,
      "L27h the account menu offers Profile and Log out")
check(SHELL.find('id="acct-menu"') > SHELL.find("</header>"),
      "L27i the account menu sits outside the masthead (its backdrop-filter would contain a fixed menu)")
ui = AUTH_JS[AUTH_JS.find("(function accountUI()"):]
check(ui != "" and "window.DB" not in ui,
      "L27j the account UI calls the helpers, never the Supabase client directly")
check("createClient" not in AUTH_JS, "L27k one Supabase client: _auth.js never creates another")
check(not re.search(r"\bENG\b|CompEngine|DATASET|\bparty\b|\brender\(|saveHash|loadHash", AUTH_JS),
      "L27l _auth.js reads and writes no planner or engine state")
check(not re.search(r"signInUser|signUpUser|signOutUser|getCurrentProfile|window\.DB", APP + DECISION_JS),
      "L27m the planner never calls the account layer")
check(all(s in AUTH_CSS for s in (".acct-btn{", ".acct-menu{", ".auth-dialog{", ".auth-dialog::backdrop{")),
      "L27n the button, the menu and the dialog are styled in _auth.css")
check('decision_css + "\\n" + auth_css + "\\n"' in BUILD and "+ layout_css" in BUILD,
      "L27o _auth.css is inlined before _layout.css, so layout rules still win on order")
PAGE = read("index.html")
SCRIPTS = re.findall(r"<script\b([^>]*)>(.*?)</script>", PAGE, re.S)


def script_at(pred):
    return next((i for i, (attrs, body) in enumerate(SCRIPTS) if pred(attrs, body)), -1)


i_app = script_at(lambda a, b: "const DATASET" in b)
i_cdn = script_at(lambda a, b: "supabase-js" in a)
i_client = script_at(lambda a, b: "window.supabase.createClient" in b)
i_auth = script_at(lambda a, b: "function signInUser" in b)
check(min(i_app, i_cdn, i_client, i_auth) >= 0,
      "L27p the built page carries the planner, the library, the client and the account UI",
      "script indices app=%d cdn=%d client=%d auth=%d" % (i_app, i_cdn, i_client, i_auth))
check(0 <= i_app < i_cdn < i_client < i_auth,
      "L27q each loads after the planner, in its own <script>: a failure there stops only itself",
      "script indices app=%d cdn=%d client=%d auth=%d" % (i_app, i_cdn, i_client, i_auth))
check(i_app >= 0 and "signInUser" not in SCRIPTS[i_app][1] and "createClient" not in SCRIPTS[i_app][1],
      "L27r the planner's <script> carries no account code")

print("L28 - the profile: names and weapon lists, the account layer's first data")
# The profile is the first user-owned data (supabase/migrations) and the
# pattern later modules follow: its own script after _auth.js, identity
# from window.Account, the client only in its helpers, and a weapon catalog
# derived at build - the engine's role_class, never a second role read.
PROFILE_JS = read("_profile.js")
pdlg = seg(SHELL, '<dialog class="auth-dialog profile-dialog"', "</dialog>", "L28 dialog anchors")
check('aria-modal="true"' in pdlg and 'aria-labelledby="profile-title"' in pdlg and 'id="profile-title"' in pdlg,
      "L28a the profile dialog is modal and titled")
for fid in ("profile-albion", "profile-server", "profile-display", "pw-add-main", "pw-add-secondary"):
    check(('id="%s"' % fid) in pdlg and ('for="%s"' % fid) in pdlg, "L28b field %s has its label" % fid)
for where in ("main", "secondary"):
    tag = re.search(r'<input[^>]*\bid="pw-add-%s"[^>]*>' % where, pdlg)
    tag = tag.group(0) if tag else ""
    check('role="combobox"' in tag and ('aria-controls="pw-results-%s"' % where) in tag
          and 'aria-expanded="false"' in tag,
          "L28c the %s picker is a combobox bound to its listbox" % where)
    check(re.search(r'id="pw-results-%s" role="listbox"' % where, pdlg) is not None,
          "L28d the %s picker's results are a listbox" % where)
check('aria-live="polite"' in pdlg and 'role="alert"' in pdlg,
      "L28e list changes and errors are announced")
check(not re.search(r"\bENG\b|CompEngine|DATASET|\bparty\b|\brender\(|saveHash|loadHash", PROFILE_JS),
      "L28f _profile.js reads and writes no planner or engine state")
profile_ui = PROFILE_JS[PROFILE_JS.find("(function profileUI()"):]
check(profile_ui != "" and "window.DB" not in profile_ui and "createClient" not in PROFILE_JS,
      "L28g the profile UI calls its helpers, never the Supabase client")
check('window.Account.registerView("profile"' in PROFILE_JS and "window.Account.subscribe(" in PROFILE_JS,
      "L28h the profile reaches identity through window.Account")
check(not re.search(r"saveMyProfile|loadMyWeapons|saveMyWeapons|ACCOUNT_CATALOG|window\.Account", APP + DECISION_JS),
      "L28i the planner never calls the account layer's modules")
check(all(s in AUTH_CSS for s in (".profile-dialog{", ".pw-chip{", ".pw-results{", ".pw-role.frontline{")),
      "L28j the profile dialog, its chips and its picker are styled in _auth.css")
check(".profile-names{grid-template-columns:1fr}" in LAYOUT, "L28k on a phone the two names stack (_layout.css)")
i_profile = script_at(lambda a, b: "const ACCOUNT_CATALOG" in b)
check(0 <= i_auth < i_profile, "L28l the profile loads after the account UI, in its own <script>",
      "script indices auth=%d profile=%d" % (i_auth, i_profile))
m = re.search(r"const ACCOUNT_CATALOG = (\{.*?\});\n", SCRIPTS[i_profile][1]) if i_profile >= 0 else None
CATALOG = _json.loads(m.group(1)) if m else {}
with open(os.path.join(ROOT, "pipeline", "out", "dataset-latest.json"), encoding="utf-8") as f:
    WEAPONS = _json.load(f)["weapons"]
check(sorted(CATALOG) == sorted(WEAPONS), "L28m the catalog carries every dataset weapon line",
      "missing %s" % sorted(set(WEAPONS) - set(CATALOG))[:5])
check(all(CATALOG[k]["name"] == (WEAPONS[k].get("display_name") or k)
          and bool(CATALOG[k].get("removed")) == bool(WEAPONS[k].get("removed")) for k in CATALOG),
      "L28n each entry's name and removed flag are the dataset's")
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402
_eng = Engine()
drift = [k for k in CATALOG if CATALOG[k]["role"] != _eng.role_of(k)]
check(not drift, "L28o each entry's role is the engine's role_class (one role read)", str(drift[:5]))

print("L29 - guilds: the second feature module follows the profile's pattern")
# Guilds (platform phase 2): its own script after the profile, identity
# through window.Account, the client only in its helpers, weapons read
# through the catalog and the profile module's pure functions, and the
# planner never calling any of it.
GUILD_JS = read("_guild.js")
gdlg = seg(SHELL, '<dialog class="auth-dialog guild-dialog"', "</dialog>", "L29 dialog anchors")
check('aria-modal="true"' in gdlg and 'aria-labelledby="guild-title"' in gdlg and 'id="guild-title"' in gdlg,
      "L29a the guilds dialog is modal and titled")
for fid in ("guild-join-code", "guild-new-name", "guild-new-server", "guild-rename-name"):
    check(('id="%s"' % fid) in gdlg and ('for="%s"' % fid) in gdlg, "L29b field %s has its label" % fid)
check('role="alert"' in gdlg and 'aria-live="polite"' in gdlg, "L29c errors and changes are announced, inside the dialog")
check('id="guild-members"' in gdlg and "<table" in gdlg and gdlg.count("<th scope=\"col\">") == 4,
      "L29d the member table has its four column headers")
check('id="acct-guilds"' in acct_menu and 'id="acct-guilds"' in SHELL[SHELL.find('id="acct-profile"'):SHELL.find('id="acct-logout"')],
      "L29e the account menu offers Guilds between Profile and Log out")
check("el.guildsItem" in AUTH_JS and "views.guilds" in AUTH_JS, "L29f the account UI shows the item once the module registered its view")
check(not re.search(r"\bENG\b|CompEngine|DATASET|\bparty\b|\brender\(|saveHash|loadHash", GUILD_JS),
      "L29g _guild.js reads and writes no planner or engine state")
guild_ui = GUILD_JS[GUILD_JS.find("(function guildUI()"):]
check(guild_ui != "" and "window.DB" not in guild_ui and "createClient" not in GUILD_JS,
      "L29h the guilds UI calls its helpers, never the Supabase client")
check('window.Account.registerView("guilds"' in GUILD_JS and "window.Account.subscribe(" in GUILD_JS,
      "L29i the guilds module reaches identity through window.Account")
check("rolesCovered(" in GUILD_JS and "weaponInfo(" in GUILD_JS and "role_class" not in GUILD_JS,
      "L29j member roles are read through the profile module's catalog functions: one role read, no engine")
check(not re.search(r"loadMyGuilds|loadGuildMembers|createGuild|joinGuild|setMemberRole|GUILD_ROLES", APP + DECISION_JS),
      "L29k the planner never calls the guild module")
check(all(s in AUTH_CSS for s in (".guild-dialog{", ".gd-grid{", ".gd-table{", ".gd-code-value{")),
      "L29l the guilds dialog, its grid, table and code are styled in _auth.css")
check(".gd-grid{grid-template-columns:1fr}" in LAYOUT, "L29m on a phone the guild list stacks above the guild (_layout.css)")
i_guild = script_at(lambda a, b: "function loadMyGuilds" in b)
check(0 <= i_profile < i_guild, "L29n the guilds module loads after the profile, in its own <script>",
      "script indices profile=%d guild=%d" % (i_profile, i_guild))

print("L30 - saved comps: the planner is reached through the address bar alone")
# A comp template is saved from the planner's share hash and opened by
# setting it: the account layer reads no planner state, the planner never
# calls the account layer, and the one bridge is the link the planner
# already publishes (the loadout codec, tests/test_loadout_codec.js).
COMPS_JS = read("_comps.js")
cdlg = seg(SHELL, '<dialog class="auth-dialog guild-dialog comp-dialog"', "</dialog>", "L30 dialog anchors")
check('aria-modal="true"' in cdlg and 'aria-labelledby="comp-title"' in cdlg and 'id="comp-title"' in cdlg,
      "L30a the saved comps dialog is modal and titled")
for fid in ("comp-guild", "comp-name", "comp-content", "comp-style", "comp-size", "comp-notes"):
    check(('id="%s"' % fid) in cdlg and ('for="%s"' % fid) in cdlg, "L30b field %s has its label" % fid)
check('role="alert"' in cdlg and 'aria-live="polite"' in cdlg, "L30c errors and changes are announced, inside the dialog")
check('id="comp-slots"' in cdlg and cdlg.count("<th scope=\"col\">") == 5, "L30d the slot table has its five column headers")
check('id="acct-comps"' in SHELL[SHELL.find('id="acct-guilds"'):SHELL.find('id="acct-logout"')],
      "L30e the account menu offers Saved comps between Guilds and Log out")
check("el.compsItem" in AUTH_JS and "views.comps" in AUTH_JS, "L30f the account UI shows the item once the module registered its view")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT", COMPS_JS),
      "L30g _comps.js reads and writes no planner or engine state")
check("location.hash" in COMPS_JS and "hashchange" in APP and "loadHash()" in APP[APP.find('addEventListener("hashchange"'):],
      "L30h the bridge is the share hash: the module reads and sets location.hash, the planner applies a hash change")
comps_ui = COMPS_JS[COMPS_JS.find("(function compsUI()"):]
check(comps_ui != "" and "window.DB" not in comps_ui and "createClient" not in COMPS_JS,
      "L30i the comps UI calls its helpers, never the Supabase client")
check('window.Account.registerView("comps"' in COMPS_JS and "window.Account.subscribe(" in COMPS_JS,
      "L30j the comps module reaches identity through window.Account")
check("weaponInfo(" in COMPS_JS and "role_class" not in COMPS_JS,
      "L30k slot roles are read through the catalog: one role read, no engine")
check(not re.search(r"loadGuildTemplates|loadTemplate|saveTemplate|deleteTemplate|parseShareHash|templateHash", APP + DECISION_JS),
      "L30l the planner never calls the comps module")
check(all(s in AUTH_CSS for s in (".comp-dialog{", ".cp-fields{", ".cp-table td{")),
      "L30m the comps dialog is styled in _auth.css")
check(".cp-fields{grid-template-columns:repeat(2, 1fr)}" in LAYOUT, "L30n on a phone the comp's fields stack in two columns (_layout.css)")
i_comps = script_at(lambda a, b: "const ACCOUNT_CONTENTS" in b)
check(0 <= i_guild < i_comps, "L30o the comps module loads after the guilds module, in its own <script>",
      "script indices guild=%d comps=%d" % (i_guild, i_comps))
m_c = re.search(r"const ACCOUNT_CONTENTS = (\{.*?\});\n", SCRIPTS[i_comps][1]) if i_comps >= 0 else None
m_s = re.search(r"const ACCOUNT_STYLES = (\{.*?\});\n", SCRIPTS[i_comps][1]) if i_comps >= 0 else None
with open(os.path.join(ROOT, "pipeline", "out", "dataset-latest.json"), encoding="utf-8") as f:
    _ds = _json.load(f)
CONTENTS = _json.loads(m_c.group(1)) if m_c else {}
STYLES = _json.loads(m_s.group(1)) if m_s else {}
check(sorted(CONTENTS) == sorted(_ds["templates"]) and all(CONTENTS[k] == (_ds["templates"][k].get("name") or k) for k in CONTENTS),
      "L30p the contents on offer are the dataset's templates, by name")
check(sorted(STYLES) == sorted(k for k in _ds.get("styles", {}) if k != "balanced"),
      "L30q the styles on offer are the dataset's, balanced being the absence of one")

print("L31 - CTAs: an event is a copy of a comp, met through the address bar alone")
# CTAs (platform phase 4): the fourth feature module. Its roster is
# copied from a saved comp or the planner's hash and is the event's own
# from then on; the module never writes a template, never reads planner
# state, and opens an event in the planner by setting the share hash.
EVENTS_JS = read("_events.js")
edlg = seg(SHELL, '<dialog class="auth-dialog guild-dialog comp-dialog event-dialog"', "</dialog>", "L31 dialog anchors")
check('aria-modal="true"' in edlg and 'aria-labelledby="ev-title"' in edlg and 'id="ev-title"' in edlg,
      "L31a the CTAs dialog is modal and titled")
for fid in ("ev-guild", "ev-source", "ev-name", "ev-start", "ev-mass", "ev-size", "ev-content", "ev-style", "ev-notes"):
    check(('id="%s"' % fid) in edlg and ('for="%s"' % fid) in edlg, "L31b field %s has its label" % fid)
check('role="alert"' in edlg and 'aria-live="polite"' in edlg, "L31c errors and changes are announced, inside the dialog")
check('id="ev-slots"' in edlg and edlg.count("<th scope=\"col\">") == 5, "L31d the slot table has its five column headers")
check(edlg.count('type="datetime-local"') == 2, "L31e the start and the mass time are date-time fields")
check('id="acct-events"' in SHELL[SHELL.find('id="acct-comps"'):SHELL.find('id="acct-logout"')],
      "L31f the account menu offers CTAs between Saved comps and Log out")
check("el.eventsItem" in AUTH_JS and "views.events" in AUTH_JS, "L31g the account UI shows the item once the module registered its view")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT", EVENTS_JS),
      "L31h _events.js reads and writes no planner or engine state")
check("location.hash" in EVENTS_JS, "L31i the bridge is the share hash: the module reads and sets location.hash")
events_ui = EVENTS_JS[EVENTS_JS.find("(function eventsUI()"):]
check(events_ui != "" and "window.DB" not in events_ui and "createClient" not in EVENTS_JS,
      "L31j the CTAs UI calls its helpers, never the Supabase client")
check('window.Account.registerView("events"' in EVENTS_JS and "window.Account.subscribe(" in EVENTS_JS,
      "L31k the CTAs module reaches identity through window.Account")
check("weaponInfo(" in EVENTS_JS and "role_class" not in EVENTS_JS,
      "L31l slot roles are read through the catalog: one role read, no engine")
check(not re.search(r"from\(\"comp_template|save_comp_template|saveTemplate\(|deleteTemplate\(", EVENTS_JS),
      "L31m the module never writes a template: an event is a copy")
check(not re.search(r"loadGuildEvents|loadEvent|saveEvent|deleteEvent|setEventStatus|eventGroups|EVENT_STATUSES", APP + DECISION_JS),
      "L31n the planner never calls the CTAs module")
check(all(s in AUTH_CSS for s in (".event-dialog{", ".ev-status-row{", ".ev-group{", ".ev-status[data-status=")),
      "L31o the CTAs dialog, its status row and its calendar are styled in _auth.css")
check(".ev-share-wrap{margin-left:0; flex-basis:100%}" in LAYOUT, "L31p on a phone the share code drops under the status (_layout.css)")
i_events = script_at(lambda a, b: "function loadGuildEvents" in b)
check(0 <= i_comps < i_events, "L31q the CTAs module loads after the comps module, in its own <script>",
      "script indices comps=%d events=%d" % (i_comps, i_events))

print("L32 - sign-up: one sheet for guests and accounts, opened by a link or from the CTAs dialog")
# Sign-up (platform phase 5): the sheet is reached by ?cta=<code> or by a
# DOM event the CTAs dialog dispatches (never a call between modules);
# the module reaches the database through three functions, keeps the
# guest's claim token in localStorage, and meets the planner through the
# address bar alone.
SIGNUP_JS = read("_signup.js")
sdlg = seg(SHELL, '<dialog class="auth-dialog signup-dialog"', "</dialog>", "L32 dialog anchors")
check('aria-modal="true"' in sdlg and 'aria-labelledby="su-title"' in sdlg and 'id="su-title"' in sdlg,
      "L32a the sheet dialog is modal and titled")
for fid in ("su-name", "su-slot", "su-weapon-add", "su-ip", "su-swap", "su-note"):
    check(('id="%s"' % fid) in sdlg and ('for="%s"' % fid) in sdlg, "L32b field %s has its label" % fid)
check('role="alert"' in sdlg and 'aria-live="polite"' in sdlg, "L32c errors and changes are announced, inside the dialog")
check('id="su-board"' in sdlg and sdlg.count("<th scope=\"col\">") == 4, "L32d the roster has its four column headers")
check('role="combobox"' in sdlg and 'aria-controls="su-weapon-results"' in sdlg and 'id="su-weapon-results"' in sdlg and 'role="listbox"' in sdlg,
      "L32e the weapon picker is a combobox bound to its listbox (the profile's pattern)")
check('id="ev-sheet"' in SHELL and 'id="ev-link"' in SHELL, "L32f the CTAs dialog offers the sheet and its link")
check('dispatchEvent(new CustomEvent("cta-sheet"' in read("_events.js") and 'addEventListener("cta-sheet"' in SIGNUP_JS,
      "L32g the CTAs dialog hands the code over as a DOM event; the sheet listens (no call between modules)")
check("codeFromSearch(" in SIGNUP_JS and "location.search" in SIGNUP_JS and "state.ready" in SIGNUP_JS,
      "L32h the link opens the sheet once the stored session has been read")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT", SIGNUP_JS),
      "L32i _signup.js reads and writes no planner or engine state")
check("location.hash" in SIGNUP_JS and "templateHash(" in SIGNUP_JS, "L32j the sheet opens a CTA in the planner through the share hash")
signup_ui = SIGNUP_JS[SIGNUP_JS.find("(function signupUI()"):]
check(signup_ui != "" and "window.DB" not in signup_ui and "createClient" not in SIGNUP_JS,
      "L32k the sheet UI calls its helpers, never the Supabase client")
check(sorted(set(re.findall(r'\.from\("(\w+)"', SIGNUP_JS))) == ["event_slots", "signups"],
      "L32l the player's helpers reach the database through functions alone (the code rides each statement); the caller's touch sign-ups and slots")
check("window.Account.subscribe(" in SIGNUP_JS and 'registerView(' not in SIGNUP_JS,
      "L32m the sheet reads identity through window.Account and is no account-menu view: a guest has no menu")
check("weaponInfo(" in SIGNUP_JS and "weaponSearch(" in SIGNUP_JS and "role_class" not in SIGNUP_JS,
      "L32n weapons are read through the catalog and the profile's search: one role read, no engine")
check(not re.search(r"loadSheet|submitSignUp|cancelSignUp|sheetBoard|codeFromSearch|CLAIM_TOKEN_RE", APP + DECISION_JS),
      "L32o the planner never calls the sign-up module")
check(all(s in AUTH_CSS for s in (".signup-dialog{", ".su-grid{", ".su-mine{", ".su-free{")),
      "L32p the sheet, its grid and its marks are styled in _auth.css")
check(".su-grid{grid-template-columns:1fr}" in LAYOUT, "L32q on a phone the form drops under the roster (_layout.css)")
i_signup = script_at(lambda a, b: "function loadSheet" in b)
check(0 <= i_events < i_signup, "L32r the sign-up module loads after the CTAs module, in its own <script>",
      "script indices events=%d signup=%d" % (i_events, i_signup))
check("localStorage" in SIGNUP_JS and "crypto.getRandomValues" in SIGNUP_JS,
      "L32s the guest's claim token is random and kept in this browser alone")

print("L33 - caller management: the caller runs the sheet from the same dialog")
# Phase 6: the caller's controls live on the sheet, offered by role and
# status (callerPowers), and every action is a helper the policies bound.
check('id="su-caller"' in sdlg and 'id="su-caller-moves"' in sdlg and 'id="su-add-form"' in sdlg,
      "L33a the sheet carries the caller's section: the status moves and add-a-player")
for fid in ("su-add-name", "su-add-slot"):
    check(('id="%s"' % fid) in sdlg and ('for="%s"' % fid) in sdlg, "L33b field %s has its label" % fid)
check("data-su-move" in SIGNUP_JS.replace("dataset.suMove", "data-su-move") and "dataset.suSlotWeapon" in SIGNUP_JS and "dataset.suDrop" in SIGNUP_JS,
      "L33c each sign-up gets a move list and a removal, each slot a weapon list, for the caller alone")
check("callerPowers(myRole, ev.status)" in SIGNUP_JS and "loadMyGuilds()" in SIGNUP_JS,
      "L33d the caller's role is read through the guild module's helper and decides what the sheet offers")
check("setEventStatus(" in SIGNUP_JS and "EVENT_MOVE_LABELS" in SIGNUP_JS,
      "L33e the status moves on the sheet are the CTAs module's helper and labels")
check("weaponOptions(" in SIGNUP_JS and "role_class" not in SIGNUP_JS and "<optgroup" not in SIGNUP_JS and "optgroup" in SIGNUP_JS,
      "L33f the slot's weapon list is the catalog grouped by role, built without markup strings")
check(all(s in AUTH_CSS for s in (".su-caller{", ".su-manage{", ".su-add{")), "L33g the caller's controls are styled in _auth.css")
check(".su-add{flex-wrap:wrap}" in LAYOUT, "L33h on a phone the add-a-player row wraps (_layout.css)")

if FAILURES:

    print("\n%d contract(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall dashboard layout contracts pass")
sys.exit(0)
