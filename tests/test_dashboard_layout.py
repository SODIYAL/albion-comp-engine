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
for el in ['id="fit-num"', 'id="fit-of"', 'id="fit-bar"', 'id="sb-identity"']:
    check(el in head, "L5a masthead carries %s" % el)
# the comp's settings (content, playstyle, planned size), the count, the
# forge actions and the build diagnostics live in the setup panel: one home,
# the masthead a single line
setup = seg(SHELL, 'id="setup-panel"', "</aside>", "L5 setup panel anchors")
for el in ['id="content"', 'id="style"', 'id="size-input"', 'id="size-minus"',
           'id="size-plus"', 'id="sb-count"', 'id="forge-slot"',
           'id="parity-chip"', 'id="build-stamp"']:
    check(el in setup, "L5a2 the setup panel carries %s" % el)
    check(el not in head, "L5a3 the masthead no longer carries %s" % el)
check('class="mh-bar"' not in SHELL and ".mh-bar" not in LAYOUT
      and "sb-field" not in SHELL and "sb-field" not in LAYOUT,
      "L5a4 the masthead's control row is retired, markup and rules both")
check(SHELL.count('id="fit-num"') == 1, "L5b #fit-num is not duplicated")
check(SHELL.count('id="style"') == 1, "L5c #style is not duplicated")
check(SHELL.count('id="size-input"') == 1, "L5d #size-input is not duplicated")
check('class="foot-chips"' not in SHELL and ".foot-chips{" not in SHELL,
      "L5e .foot-chips retired - its chips moved up",
      "markup and rule both gone; a mention in a comment is fine")
check('"sb-identity"' in DECISION_JS, "L5f decision layer fills #sb-identity")
check('"sb-count"' in APP, "L5g _app.js fills #sb-count")
# the size is set inside the setup panel, beside the full notice
# (#size-notice); while the panel is shut its tab names the caveat, and a
# parity mismatch raises an alarm in the masthead no shut panel can hide
_sn = setup.find('id="size-input"'), setup.find('id="size-notice"'), setup.find('id="forge-slot"')
check(0 <= _sn[0] < _sn[1] < _sn[2],
      "L5h the size notice sits between the size controls and the forge actions",
      "setting an unvalidated size must warn where the size is set")
_rs = seg(APP, "function renderSetup(){", "const SWAP_CFG", "L5i renderSetup anchors")
check('.epanel-tab[data-panel="setup-panel"]' in _rs and "tab.dataset.note = note" in _rs
      and "delete tab.dataset.note" in _rs and ".epanel-tab[data-note]::after{" in LAYOUT,
      "L5i the setup tab carries a dot and a tooltip while the panel holds a size notice")
check('id="parity-alarm" hidden' in head and 'alarm.hidden = ok' in APP
      and ".chip[hidden]{display:none}" in SHELL,
      "L5j a parity mismatch shows in the masthead, whatever the setup panel's state")
check('data-open-panel="setup-panel"' in DECISION_JS and 'closest("[data-open-panel]")' in APP,
      "L5k the empty comp names the setup panel and opens it")
check('if (needSize()) setPanel("setup-panel", true, false);' in APP,
      "L5l a link that arrives with the size ask open shows the setup panel, the saved layout untouched")

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
check(SHELL.count('id="forge-slot"') == 1, "L13d forge actions have one home (the setup panel, L5a2)")
check('id="forge-rail"' not in SHELL,
      "L13e no second forge control beside the forge slot")
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
# the identity is a headline over the diagram, never a label inside it, and
# the diagram draws no per-axis target mark: both read as unexplained shapes
check('class="dl-ident' in _sr and "<strong>${esc(c.title)}</strong>" in _sr
      and _sr.find('class="dl-ident') < _sr.find('<svg class="dl-radar"'),
      "L15c2 the comp identity is a headline above the radar")
check("dlr-id" not in DECISION_JS and "dlr-id" not in DECISION_CSS
      and "stroke-dasharray" not in _sr and "brass-deep" not in _sr,
      "L15c3 the radar carries no centre label and no target ticks")
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
# the pick is explained one player ahead: its lead capability can be a
# requirement at the next size and none at the judged one (a portal pool's
# none row), where target(cap) has no row and the render stopped mid-pass
check("lead.target.toFixed(1)" in why and "target(lead.cap)" not in why,
      "L20g2 the why sentence reads the term's own typical, never a row the judged size may lack")
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
check(".masthead .chip{padding:3px 8px; font-size:10px; margin:0}" in LAYOUT
      and "#setup-panel .sb-count{margin-left:6px; line-height:1}" in LAYOUT,
      "L23d the masthead's alarm chip sheds the note box's margin; the count centres with the size controls")

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
check('<label for="size-input">Planned size</label>' in SHELL and "<span>size</span>" not in SHELL,
      "L24g the size field is labelled planned size, never size alone")
check("<label>Suggested size</label>" in SHELL and "Party size presets" not in SHELL,
      "L24h the preset row is labelled as a suggestion")
count = seg(APP, 'const count = `${party.length}/${PLAN()}`;', "$(\"pdash\").style", "L24 count anchors")
check("sbc.title = " in count and "in party" in count and "planned" in count,
      "L24i the count beside the planned size carries a tooltip naming both numbers")

# L25 - a content may ask for its size before it forges (template
# size_prompt: the Dragon Portal pools). The ask is raised on the switch
# into such a content, cleared by every size control, answered by a
# link's n=, and while raised the forge slot shows the pools instead of
# the forge button and the setup tab names it.
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
check('const note = needSize() ? "choose a portal size"' in APP,
      "L25g the setup tab names the open ask")
check('fitStat !== "none" ? "" :' in APP and "No harvested evidence for this content yet" in APP,
      "L25h a content whose fit is none shows the borrowed-evidence notice")
import json as _json
with open(os.path.join(ROOT, "pipeline", "out", "dataset-latest.json"), encoding="utf-8") as _fh:
    tpl25 = (_json.load(_fh).get("templates") or {}).get("ancient_lands") or {}
_fit25 = tpl25.get("fit") or {}
check(tpl25.get("size_prompt", {}).get("sizes") == [3, 5, 7, 20] and tpl25.get("validated_sizes") == []
      and _fit25.get("stat") == "median" and _fit25.get("source") == "harvest" and _fit25.get("comps", 0) >= 40,
      "L25i the Dragon Portal template prompts for 3 / 5 / 7 / 20, validates no size and carries the portal harvest's median rows")

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
_cdn_attrs = SCRIPTS[i_cdn][0] if i_cdn >= 0 else ""
check(re.search(r"supabase-js@\d+\.\d+\.\d+/dist/umd/supabase\.js", _cdn_attrs) is not None
      and re.search(r'integrity="sha384-[A-Za-z0-9+/]{64}"', _cdn_attrs) is not None
      and 'crossorigin="anonymous"' in _cdn_attrs,
      "L27s the library is pinned: an exact version and file, a sha384 integrity hash, anonymous CORS",
      _cdn_attrs.strip()[:160])

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
check("Runestone Golem Transformation" in (CATALOG.get("2H_SHAPESHIFTER_KEEPER") or {}).get("e", [])
      and all(isinstance(v.get("e", []), list) and all(isinstance(n, str) and n != n.upper() for n in v.get("e", []))
              for v in CATALOG.values()),
      "L28p an entry carries the names of the line's own E spells (the import reads a weapon named by its E)")
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
setup_panel = seg(SHELL, 'id="setup-panel"', "</aside>", "L30r setup panel anchors")
check('id="save-comp-row"' in setup_panel and 'id="save-comp"' in setup_panel and setup_panel.index('id="share"') < setup_panel.index('id="save-comp"') < setup_panel.index('id="clear"')
      and re.search(r'<div class="btn-row" id="save-comp-row" hidden>', SHELL) is not None and ".btn-row[hidden]{display:none}" in SHELL
      and "el.railRow.hidden = !state.user;" in COMPS_JS and 'openComps({ fromPlanner: true })' in COMPS_JS and "if (!el.fromPlanner.hidden) fromPlanner();" in COMPS_JS
      and "save-comp" not in APP and "railSave" not in APP,
      "L30r the setup drawer's save button is the account layer's: hidden until the comps module shows it to a logged-in account, it opens the saved comps dialog on the planner's comp; the planner never references it")
check(".cp-fields{grid-template-columns:repeat(2, minmax(0, 1fr))}" in LAYOUT, "L30n on a phone the comp's fields stack in two columns that shrink to the card (_layout.css)")
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
check('for="ev-zone"' in edlg and 'id="ev-zone"' in edlg and '<option value="utc">' in edlg and '<option value="local">' in edlg
      and edlg.index('value="utc"') < edlg.index('value="local"')
      and 'id="ev-start-echo"' in edlg and 'id="ev-mass-echo"' in edlg,
      "L31r the times are typed in UTC (the default) or the caller's own zone, each field echoing its other reading")
check("toZoneInput(current.starts_at, zone)" in EVENTS_JS and "fromZoneInput(el.start.value, zone)" in EVENTS_JS
      and all(x in read("_signup.js") for x in ("eventCountdown(ev.starts_at)", "eventTimeLabel(ev.starts_at, true)",
                                                "setInterval(paintWhen", "clearInterval(whenTimer)")),
      "L31s the form reads and writes its times through the zone; the sheet shows the reader's zone, UTC and a countdown it keeps current")
check("function massDefault" in EVENTS_JS and "const MASS_LEAD_MINUTES = 30;" in EVENTS_JS and "function followStart" in EVENTS_JS
      and EVENTS_JS.count("el.mass.max = el.start.value") >= 3 and 'el.mass.addEventListener("change"' in EVENTS_JS
      and "if (t === el.mass) massFollows = false;" in EVENTS_JS,
      "L31t the mass field is bounded by the start and follows it, the lead before, until the caller types one; a mass time past the start goes back to the lead")
check('id="ev-source-label"' in edlg and 'id="ev-replace"' not in edlg and "Keep these slots" in EVENTS_JS
      and "el.sourceWrap.hidden = !!current.id && !powers.editSlots;" in EVENTS_JS and "async function replaceRoster" in EVENTS_JS
      and "function renderSlots" in EVENTS_JS and ".gd-btn:disabled{" in AUTH_CSS and "el.open.title = openable" in EVENTS_JS,
      "L31u a saved CTA that may still change its slots replaces its roster from a saved comp or the planner through the one picker; a slot change leaves the typed fields alone; the planner button reads disabled over an empty roster and says why")
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

print("L32 - sign-up: one sheet for guests and accounts, the page a CTA's link opens")
# Sign-up (platform phase 5): the sheet is reached by ?cta=<code> and is
# the page itself (the head script sets the sheet view before the planner
# draws; the CTAs dialog's sheet button goes to the link); the module
# reaches the database through three functions, keeps the guest's claim
# token in localStorage, and meets the planner through the address bar
# alone.
SIGNUP_JS = read("_signup.js")
HEAD = SHELL.split("<body>")[0]
sdlg = seg(SHELL, '<main class="sheet-page" id="signup-page"', "</main>", "L32 page anchors")
check('aria-labelledby="su-title"' in sdlg and 'id="su-title"' in sdlg and "<dialog" not in sdlg and "aria-modal" not in sdlg
      and 'id="su-close"' not in sdlg and "autofocus" not in sdlg,
      "L32a the sheet is a titled page section, no dialog: no modal attributes, no close button, no title focus")
check('document.documentElement.dataset.view = "sheet"' in HEAD and "cta=" in HEAD
      and SHELL.find("</header>") < SHELL.find('id="signup-page"') < SHELL.find('<div class="shell" id="shell">'),
      "L32a2 the head script sets the sheet view from the address before the planner draws; the sheet section stands between the masthead and the planner")
check('html[data-view="sheet"] .shell' in LAYOUT and 'html[data-view="sheet"] .sheet-only{display:inline-block}' in LAYOUT
      and 'class="about-link sheet-only" href="index.html"' in SHELL,
      "L32a3 in the sheet view the planner is not displayed and the masthead links back to it (_layout.css)")
check(".sheet-page > .auth-card{max-height:none; overflow:visible}" in AUTH_CSS and ".sheet-page[hidden]{display:none}" in AUTH_CSS
      and ".auth-dialog [hidden], .sheet-page [hidden], .acct-menu [hidden]{display:none !important}" in AUTH_CSS,
      "L32a4 the page is the scroller (no card cap), hidden keeps its meaning on the page, and the account layer's tones apply to it")
check("function sheetView()" in APP and "if (sheetView()) return;" in seg(APP, "function saveHash()", "}", "L32a5 save anchors")
      and "if (sheetView()) return false;" in seg(APP, "function loadStored()", "}", "L32a5 load anchors"),
      "L32a5 while the page shows a sheet the hidden planner writes neither the address nor storage, and loads nothing from storage")
for fid in ("su-name", "su-slot", "su-weapon-add", "su-ip", "su-swap", "su-note"):
    check(('id="%s"' % fid) in sdlg and ('for="%s"' % fid) in sdlg, "L32b field %s has its label" % fid)
check('role="alert"' in sdlg and 'aria-live="polite"' in sdlg, "L32c errors and changes are announced, on the page")
check('class="su-bands" id="su-board" aria-labelledby="su-board-label"' in sdlg and "<table" not in sdlg and "<th" not in sdlg,
      "L32d the roster is a set of role bands, labelled, no table")
check('role="combobox"' in sdlg and 'aria-controls="su-weapon-results"' in sdlg and 'id="su-weapon-results"' in sdlg and 'role="listbox"' in sdlg,
      "L32e the weapon picker is a combobox bound to its listbox (the profile's pattern)")
check('id="ev-sheet"' in SHELL and 'id="ev-link"' in SHELL, "L32f the CTAs dialog offers the sheet and its link")
check("location.assign(signupLink(current.share_code, location.href))" in read("_events.js") and "cta-sheet" not in SIGNUP_JS
      and "cta-sheet" not in read("_events.js"),
      "L32g the CTAs dialog goes to the sheet's link (the address is the one handover; no call between modules)")
check("codeFromSearch(" in SIGNUP_JS and "location.search" in SIGNUP_JS and "state.ready" in SIGNUP_JS,
      "L32h the link opens the sheet once the stored session has been read")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT", SIGNUP_JS),
      "L32i _signup.js reads and writes no planner or engine state")
check("const hash = templateHash(sheet.event, sheet.slots);" in SIGNUP_JS and "location.assign(plannerLink(location.href, hash));" in SIGNUP_JS and "location.hash" not in SIGNUP_JS,
      "L32j the sheet opens a CTA in the planner through the share hash, as a page load of the planner's address")
check('sessionStorage.setItem(SHEET_WHO_KEY, JSON.stringify(sheetWho(hash, sheetBoard(sheet.slots, sheet.signups))))' in SIGNUP_JS
      and 'const SHEET_WHO_KEY = "compforge-who";' in SIGNUP_JS and 'const WHO_KEY = "compforge-who";' in APP
      and "function whoFromSession" in APP and "rec.hash !== h" in APP and "function whoAt" in APP and "r.w === party[i]" in APP
      and "WHO = order.map(i => WHO[i]);" in APP and "WHO.splice(ri, 1);" in APP
      and not re.search(r"\bWHO\b|whoAt", seg(APP, "function syncEngine(", "\n}", "L32j2 sync anchors") + seg(APP, "function partyCalc(", "\n}", "L32j2 calc anchors"))
      and SIGNUP_JS.count("sessionStorage.") == 1 and "&who=" not in SIGNUP_JS and "who" not in seg(APP, "function saveHash()", "\n}", "L32j2 save anchors"),
      "L32j2 who holds each slot rides to the planner in this tab alone (sessionStorage keyed to the hash, never the address or storage), shows on the board tile while the slot keeps that weapon, follows the roster's order and removals, and is read by no scoring path")
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
check(all(s in AUTH_CSS for s in (".sheet-page{", ".su-grid{", ".su-mine{", ".su-free{")) and ".signup-dialog" not in AUTH_CSS,
      "L32p the sheet page, its grid and its marks are styled in _auth.css")
check('id="su-roles"' in sdlg and 'id="su-next-list"' in sdlg and sdlg.find('id="su-roles"') < sdlg.find('class="su-grid"')
      and "function sheetTally" in SIGNUP_JS and "renderRoles(board)" in SIGNUP_JS and "weaponArt(" in SIGNUP_JS
      and "slotWeaponPick(row)" in SIGNUP_JS and "repaintPick(t)" in SIGNUP_JS
      and all(s in AUTH_CSS for s in (".su-roles{", ".su-next{", ".su-next-slot{", ".su-weapon-pick{")),
      "L32t the role bar (held of planned per role, the open slots to fill next with their icons) sits above the roster; the caller's weapon list carries the chosen weapon's icon")
check("function sheetBands" in SIGNUP_JS and "sheetBands(board, CATALOG).map(band =>" in SIGNUP_JS and "slotCell(row, board, mineId)" in SIGNUP_JS
      and 'BAND_NAMES = { frontline: "Tanks", support: "Supports", dps: "DPS", healer: "Healers", any: "Any weapon" }' in SIGNUP_JS
      and "<optgroup" not in SIGNUP_JS and 'document.createElement("optgroup")' in SIGNUP_JS
      and all(s in AUTH_CSS for s in (".su-bands{", ".su-band-hd{", ".su-band-grid{display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr))", ".su-slot{", ".su-band.frontline .su-band-name, .su-band.frontline .su-pos{color:var(--role-tank)}"))
      and ".su-band-grid{grid-template-columns:1fr}" in LAYOUT,
      "L32u the roster is grouped into role bands, Tanks, Supports, DPS, Healers, then Any weapon, as many slots across as 300px columns fit (one on a phone), the role's colour on the band's name and its slot numbers; the form's slot list is grouped the same way")
check('id="su-count"' in sdlg and 'id="su-ics"' in sdlg and 'download="cta.ics"' in sdlg and "function eventIcs" in SIGNUP_JS and 'el.ics.href = ics ? `data:text/calendar;charset=utf-8,${encodeURIComponent(ics)}`' in SIGNUP_JS
      and "el.countBig.textContent = until;" in SIGNUP_JS and ".su-count{" in AUTH_CSS and ".su-count-big{font-size:var(--fs-title)" in AUTH_CSS and ".su-count{align-items:flex-start" in LAYOUT,
      "L32x the start counts down beside the title at the title step and the reader can add it to a calendar (an .ics the page writes); on a phone the countdown drops under the title")
check(all(('id="%s"' % i) in sdlg for i in ("su-copy", "su-link-top", "su-builds")) and "function sheetText" in SIGNUP_JS and "function toClipboard" in SIGNUP_JS
      and 'toClipboard(sheetText(sheet.event, lastBoard, CATALOG, signupLink(code, location.href)), "Roster copied.")' in SIGNUP_JS and "function paintBuilds" in SIGNUP_JS,
      "L32y the status row copies the roster as text and the link, and opens or folds every build at once")
check('id="su-record"' in sdlg and 'id="su-record-actions"' in sdlg and 'id="su-mark-all"' in seg(sdlg, 'id="su-record-actions"', "</div>", "L32z record anchors") and 'id="su-history-link"' in sdlg
      and 'el.formTitle.textContent = ended ? "Record" : "Sign up";' in SIGNUP_JS and 'el.next.hidden = !tally.next.length || sheet.event.status === "completed";' in SIGNUP_JS
      and 'free.textContent = ended ? "unfilled" : "free";' in SIGNUP_JS and 'window.Account.open("history")' in SIGNUP_JS and "open(name) {" in read("_auth.js")
      and '.su-status-row[data-status="completed"] .su-live-state{display:none}' in AUTH_CSS and '.su-bands:not([data-status="completed"]) .su-slot .su-controls{position:absolute' in AUTH_CSS
      and ".su-free.ended{" in AUTH_CSS and ".su-record{" in AUTH_CSS,
      "L32z once completed the panel is the record (counts, mark everyone, the guild's history through the account store), fill-next and the live mark go, a slot nobody took reads unfilled, and the marks stay in view; before that the caller's line waits for the pointer over the cell's corner")
check('${att.confirmed} of ${board.counts.claimed} confirmed`' in SIGNUP_JS and '(status === "confirmed" ? "✓ " : "")' in SIGNUP_JS
      and 'cell.className = "gd-cov reserve";' in SIGNUP_JS and "playerBlock(s, s.id === mineId, true)" in SIGNUP_JS and ".su-declared-chips{" in AUTH_CSS,
      "L32aa confirmed reads at a glance (a tick on the name, confirmed of claimed in the status row), the reserves count in the role bar, and a reserve's weapons are chips with their icons")
check("function takeSlot" in SIGNUP_JS and "dataset.suTake = String(row.position)" in SIGNUP_JS and "function paintPick" in SIGNUP_JS
      and 'id="su-taking"' in sdlg and '<h3 class="su-form-title" id="su-form-label">Sign up</h3>' in sdlg
      and "takeSlot(take.dataset.suTake)" in SIGNUP_JS and 'el.slot.addEventListener("change", paintPick)' in SIGNUP_JS
      and all(s in AUTH_CSS for s in (".su-take{", ".su-slot.su-pick{", ".su-form-wrap{position:sticky", ".su-taking{", ".su-form-title{"))
      and ".su-form-wrap{position:static; margin-top:14px}" in LAYOUT,
      "L32v a free slot's button and the fill-next chips name the slot in the form; the panel is the page's brass, pinned beside the roster (unpinned under it on a phone), and says which slot is being taken")
check('head.value = MOVE_PLACEHOLDER' in SIGNUP_JS and 'head.textContent = "Move to…"' in SIGNUP_JS and "(here)" not in signup_ui
      and "if (t.value === MOVE_PLACEHOLDER) return;" in SIGNUP_JS and ".su-controls .su-move, .su-controls .su-mark{" in AUTH_CSS,
      "L32w the caller's line reads Move to…, the mark and the removal, small and under the player; a move list never names the slot the player already holds")
check(".su-grid{grid-template-columns:1fr}" in LAYOUT, "L32q on a phone the form drops under the roster (_layout.css)")
i_signup = script_at(lambda a, b: "function loadSheet" in b)
check(0 <= i_events < i_signup, "L32r the sign-up module loads after the CTAs module, in its own <script>",
      "script indices events=%d signup=%d" % (i_events, i_signup))
check("localStorage" in SIGNUP_JS and "crypto.getRandomValues" in SIGNUP_JS,
      "L32s the guest's claim token is random and kept in this browser alone")

print("L33 - caller management: the caller runs the sheet from the same page")
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

print("L34 - live updates: the sheet listens on the CTA's channel and re-reads itself")
# Phase 7: one Realtime broadcast per write, on cta:<code>; the sheet
# joins when it opens, leaves when it closes, and re-reads through the
# same function it always read through.
check('id="su-live-state"' in sdlg and 'aria-live="polite"' in sdlg, "L34a the sheet shows whether it is live, and says so to a screen reader")
check("function watchSheet" in SIGNUP_JS and 'window.DB.channel(sheetTopic(code))' in SIGNUP_JS and "window.DB.removeChannel(channel)" in SIGNUP_JS,
      "L34b the channel is joined and left through one helper")
check("startWatching()" in SIGNUP_JS and "stopWatching()" in SIGNUP_JS and 'window.addEventListener("pagehide", stopWatching)' in SIGNUP_JS,
      "L34c the sheet joins once read and leaves when the page goes")
check("LIVE_SETTLE_MS" in SIGNUP_JS and "reload(true, true)" in SIGNUP_JS,
      "L34d a change settles, then the sheet re-reads through event_by_code, the player's typing kept")
check('.on("postgres_changes"' not in SIGNUP_JS, "L34e no row data crosses the channel: broadcasts only, the policies still decide what is read")
check(all(s in AUTH_CSS for s in (".su-live-state{", '.su-live-state[data-live="yes"]')), "L34f the live mark is styled in _auth.css")

print("L35 - history: the sheet carries the record, the player confirms, the caller marks")
# Phase 8: attendance on the sheet, apart from the sign-up. The player's
# confirmation and the caller's marks are helpers the policies bound;
# the record's rows with no claim behind them are listed as history.
check('id="su-confirm"' in sdlg and 'id="su-history"' in sdlg and 'id="su-mark-all"' in sdlg,
      "L35a the sheet carries the confirm button, the record list and mark-everyone")
check("attendanceTag(" in SIGNUP_JS and "markSelect(" in SIGNUP_JS and "dataset.suMark" in SIGNUP_JS,
      "L35b each sign-up shows its mark; the caller gets a mark list per record")
check("markPowers(myRole, ev.status, sheet.mine)" in SIGNUP_JS and "historyRows(sheet.attendance)" in SIGNUP_JS and "attendanceSummary(sheet.attendance)" in SIGNUP_JS,
      "L35c what the sheet offers follows the role, the status and the player's own sign-up; the counts and the history come from the record")
check("ATTENDANCE_NAMES[" in SIGNUP_JS and "<option" not in SIGNUP_JS and "<select" not in SIGNUP_JS,
      "L35d the marks are named through one map and built without markup strings")
check(all(s in AUTH_CSS for s in (".su-att{", '.su-att[data-status="no_show"]', ".su-mark{", ".su-confirm{")), "L35e the record's marks are styled in _auth.css")

print("L36 - history: the facts over a guild's completed CTAs, read through one function, shown with their definitions")
# Phase 9: the seventh feature module follows the profile's pattern and
# never touches the planner, the engine or the sheet's channel.
HISTORY_JS = read("_history.js")
hdlg = seg(SHELL, '<dialog class="auth-dialog guild-dialog comp-dialog history-dialog"', "</dialog>", "L36 dialog anchors")
check('aria-modal="true"' in hdlg and 'aria-labelledby="hs-title"' in hdlg and 'id="hs-title"' in hdlg,
      "L36a the history dialog is modal and titled")
for fid in ("hs-guild", "hs-search"):
    check(('id="%s"' % fid) in hdlg and ('for="%s"' % fid) in hdlg, "L36b field %s has its label" % fid)
check('role="alert"' in hdlg and 'aria-live="polite"' in hdlg, "L36c errors and changes are announced, inside the dialog")
check('id="hs-players"' in hdlg and 'id="hs-ctas"' in hdlg and hdlg.count("<th scope=\"col\"") == 13,
      "L36d the players table has its seven headers and the CTAs table its six")
check('id="hs-definitions"' in hdlg and "None of this is a skill rating" in HISTORY_JS,
      "L36e the measures are defined beside the facts, and no skill rating is offered")
check('id="acct-history"' in SHELL[SHELL.find('id="acct-events"'):SHELL.find('id="acct-logout"')],
      "L36f the account menu offers History between CTAs and Log out")
check("el.historyItem" in AUTH_JS and "views.history" in AUTH_JS, "L36g the account UI shows the item once the module registered its view")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT|location\.hash", HISTORY_JS),
      "L36h _history.js reads and writes no planner or engine state and never touches the address bar")
history_ui = HISTORY_JS[HISTORY_JS.find("(function historyUI()"):]
check(history_ui != "" and "window.DB" not in history_ui and "createClient" not in HISTORY_JS and ".from(" not in HISTORY_JS and ".channel(" not in HISTORY_JS,
      "L36i the history UI calls its one helper, never the Supabase client, no table and no channel")
check('window.Account.registerView("history"' in HISTORY_JS and "window.Account.subscribe(" in HISTORY_JS,
      "L36j the history module reaches identity through window.Account")
check("weaponInfo(" in HISTORY_JS and "ROLE_ORDER" in HISTORY_JS and "role_class" not in HISTORY_JS,
      "L36k roles are read through the catalog: one role read, no engine")
check(not re.search(r"loadGuildHistory|playerRows|weaponRows|ctaRows|historyTotals|isRegular", APP + DECISION_JS),
      "L36l the planner never calls the history module")
check(all(s in AUTH_CSS for s in (".history-dialog{", ".hs-head{", ".hs-table td{", ".hs-regular .gd-name{")),
      "L36m the history dialog, its head, tables and the regular's mark are styled in _auth.css")
check(".hs-guild{flex-basis:100%}" in LAYOUT and ".hs-table{display:block; overflow-x:auto}" in LAYOUT,
      "L36n on a phone the guild pick takes the row and the tables scroll sideways (_layout.css)")
i_history = script_at(lambda a, b: "function loadGuildHistory" in b)
check(0 <= i_signup < i_history, "L36o the history module loads after the sheet, in its own <script>",
      "script indices signup=%d history=%d" % (i_signup, i_history))

print("L37 - import and export: a spreadsheet as a saved comp, read on the client with uncertain names reviewed; CSV out of the comps and history dialogs")
# Phase 10: the eighth feature module reads a sheet in the browser, reads
# every name through the catalog and the guild's alias table, and saves
# the comp through the comps module's helper; the comps dialog opens it
# through a DOM event and gets the comp back the same way. The export is
# the shared kit: each dialog shapes its own rows.
IMPORT_JS = read("_import.js")
idlg = seg(SHELL, '<dialog class="auth-dialog guild-dialog comp-dialog import-dialog"', "</dialog>", "L37 dialog anchors")
check('aria-modal="true"' in idlg and 'aria-labelledby="im-title"' in idlg and 'id="im-title"' in idlg,
      "L37a the import dialog is modal and titled")
for fid in ("im-guild", "im-text", "im-file", "im-name", "im-content", "im-style", "im-size", "im-remember", "im-players", "im-parties"):
    check(('id="%s"' % fid) in idlg and ('for="%s"' % fid) in idlg, "L37b field %s has its label" % fid)
check('role="alert"' in idlg and 'aria-live="polite"' in idlg, "L37c errors and changes are announced, inside the dialog")
check('id="im-columns"' in idlg and 'id="im-rows"' in idlg and idlg.count("<th scope=\"col\">") == 8,
      "L37d the column map and the review table with its eight headers")
check('accept=".csv,.tsv,.txt' in idlg and "xlsx" in IMPORT_JS and "readAsText" in IMPORT_JS,
      "L37e a CSV, TSV or text file is read in the browser; a workbook is refused with the way round")
check('id="comp-import"' in cdlg and 'dispatchEvent(new CustomEvent("comp-import"' in COMPS_JS and 'addEventListener("comp-import"' in IMPORT_JS,
      "L37f the comps dialog opens the import through a DOM event carrying the guild, no call between modules")
check('dispatchEvent(new CustomEvent("comp-imported"' in IMPORT_JS and 'addEventListener("comp-imported"' in COMPS_JS,
      "L37g the imported comp goes back the same way and the comps dialog opens it")
check("saveTemplate(" in IMPORT_JS and "validateTemplate(" in IMPORT_JS and "save_comp_template" not in IMPORT_JS and 'from("comp_template' not in IMPORT_JS,
      "L37h the comp is saved through the comps module's helper under its rules; the import module writes no template itself")
check(not re.search(r"ENG|CompEngine|DATASET|render\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT|location\.hash", IMPORT_JS),
      "L37i _import.js reads and writes no planner or engine state and never touches the address bar")
import_ui = IMPORT_JS[IMPORT_JS.find("(function importUI()"):]
check(import_ui != "" and "window.DB" not in import_ui and "createClient" not in IMPORT_JS and ".channel(" not in IMPORT_JS
      and sorted(set(re.findall(r'\.from\("(\w+)"', IMPORT_JS))) == ["weapon_aliases"],
      "L37j the import UI calls its helpers; the module's one table is weapon_aliases, no channel")
check("weaponInfo(" in IMPORT_JS and "weaponOptions(" in IMPORT_JS and "role_class" not in IMPORT_JS
      and "<option" not in IMPORT_JS and "<select" not in IMPORT_JS and "<optgroup" not in IMPORT_JS,
      "L37k weapons and roles are read through the catalog, the lists built without markup strings")
check("function matchWeapon" in IMPORT_JS and '"uncertain"' in IMPORT_JS and '"likely"' in IMPORT_JS and "function learnedAliases" in IMPORT_JS
      and "function detectColumns" in IMPORT_JS and "data-im-column" in IMPORT_JS.replace("dataset.imColumn", "data-im-column"),
      "L37l columns are detected and the caller may reset them; a name is read through the catalog and the alias table, an uncertain one chosen, a chosen one remembered")
check(not re.search(r"parseSheet|matchWeapon|detectColumns|sheetRows|importSlots|learnedAliases|loadGuildAliases", APP + DECISION_JS),
      "L37m the planner never calls the import module")
check('id="comp-export"' in cdlg and 'id="comp-copy"' in cdlg and 'id="hs-export-players"' in hdlg and 'id="hs-export-ctas"' in hdlg,
      "L37n a comp exports as CSV and as text; the history's players and CTAs export as CSV")
check("function acctCsvText" in AUTH_JS and "function acctDownloadText" in AUTH_JS and "function acctFilename" in AUTH_JS
      and "compSheetRows(" in COMPS_JS and "compText(" in COMPS_JS and "historySheetRows(" in HISTORY_JS
      and "acctDownloadText(" in COMPS_JS and "acctDownloadText(" in HISTORY_JS,
      "L37o the CSV writer, the file name and the download are the shared kit (_auth.js); each dialog shapes its own rows")
check(all(s in AUTH_CSS for s in (".import-dialog{", ".im-columns{", ".im-table td{", '.im-table tr[data-status="uncertain"] .im-status{')),
      "L37p the import dialog, its column map, its table and the uncertain mark are styled in _auth.css")
check(".im-source{grid-template-columns:1fr}" in LAYOUT and ".im-table{display:block; overflow-x:auto}" in LAYOUT,
      "L37q on a phone the source stacks and the review table scrolls sideways (_layout.css)")
i_import = script_at(lambda a, b: "function loadGuildAliases" in b)
check(0 <= i_history < i_import, "L37r the import module loads after the history module, in its own <script>",
      "script indices history=%d import=%d" % (i_history, i_import))

print("L38 - the engine's read on the sheet: the planner's engine on the roster's weapon keys, display only, people beside it never scored")
# Phase 11: the one account surface that reads the engine. The roster
# module makes its own CompEngine over DATASET (never the planner's
# instance or state), the sheet hands its roster over as a DOM event,
# the read is painted into elements the sign-up module never touches,
# and sign-ups and members are shown beside the engine's needs, never
# handed to it.
ROSTER_JS = read("_roster.js")
rr = seg(sdlg, '<details class="rr" id="rr-wrap"', "</details>", "L38 read anchors")
for rid in ("rr-headline", "rr-note", "rr-needs", "rr-picks", "rr-free", "rr-swaps", "rr-over", "rr-definitions"):
    check(('id="%s"' % rid) in rr, "L38a the read carries %s" % rid)
check(rr.count('aria-labelledby="rr-') == 5 and rr.count('class="pw-label" id="rr-') == 5, "L38b each of the five blocks is a labelled section")
check(sdlg.find('id="rr-wrap"') > sdlg.find('id="su-history-wrap"') and sdlg.find('id="rr-wrap"') < sdlg.find('class="auth-hint su-link-row"'),
      "L38c the read sits in the roster column after the record and before the link")
check('dispatchEvent(new CustomEvent("sheet-read"' in SIGNUP_JS and 'addEventListener("sheet-read"' in ROSTER_JS,
      "L38d the sheet hands its roster over as a DOM event; the roster module listens (no call between modules)")
check("rr-" not in SIGNUP_JS and "rosterRead" not in SIGNUP_JS, "L38e the sign-up module never touches the read's elements or functions")
check("function handOver" in SIGNUP_JS and SIGNUP_JS.count("handOver();") >= 2
      and "sheet = null;" in seg(SIGNUP_JS, "function showNoEvent()", "handOver();", "L38f no-event anchors"),
      "L38f the roster is handed over after every render and cleared when the sheet names no CTA")
check("new CompEngine(DATASET" in ROSTER_JS and "engine.setContent(" in ROSTER_JS,
      "L38g the roster module makes its own engine over the dataset and sets the CTA's content, size and style on it")
check(not re.search(r"\bENG\b|\brender\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT|location\.hash|COMBOS_CUR|GEARS_CUR", ROSTER_JS),
      "L38h the roster module reads and writes no planner state: never the planner's engine, roster, kits or address bar")
planner_globals = set(re.findall(r"\b(CAP_LABEL|CAP_PROSE|ICONS|DATASET|CompEngine|SEMANTIC_ICONS|WEAPONS|TREES|ITEMS|SPELLS|GEAR|USAGE|FAMILIES)\b", ROSTER_JS))
check(planner_globals == {"CAP_LABEL", "CAP_PROSE", "ICONS", "DATASET", "CompEngine"},
      "L38i the planner's globals it reads are the engine, the dataset, the icons and the capability words, no other", str(sorted(planner_globals)))
check("window.DB" not in ROSTER_JS and ".from(" not in ROSTER_JS and ".rpc(" not in ROSTER_JS and ".channel(" not in ROSTER_JS
      and "loadGuildMembers(" in ROSTER_JS and "loadMembersWeapons(" in ROSTER_JS and "memberRows(" in ROSTER_JS,
      "L38j the roster module reaches no table: members and their lists come through the guild module's helpers")
check("weaponInfo(" in ROSTER_JS and "sheetBoard(" in ROSTER_JS and "role_class" not in ROSTER_JS and "<li" not in ROSTER_JS and "<span" not in ROSTER_JS,
      "L38k weapons are read through the catalog and the board through the sheet's own function; the read is built without markup strings")
check("never scored" in ROSTER_JS and "rosterHeadline" in ROSTER_JS and "fillersFor(" in ROSTER_JS,
      "L38l the definitions say who signed up and what members play are shown beside the needs, never scored")
check(not re.search(r"rosterRead|heldParty|fillersFor|sheet-read|rosterPool", APP + DECISION_JS), "L38m the planner never calls the roster module")
check(all(s in AUTH_CSS for s in (".rr{", ".rr-grid{", ".rr-list li{", ".rr-needed .gd-name{")), "L38n the read, its grid, its rows and the needed mark are styled in _auth.css")
check(".rr-grid{grid-template-columns:1fr}" in LAYOUT, "L38o on a phone the read's blocks stack (_layout.css)")
i_roster = script_at(lambda a, b: "function rosterRead" in b)
check(0 <= i_import < i_roster, "L38p the roster module loads after the import module, in its own <script>",
      "script indices import=%d roster=%d" % (i_import, i_roster))
check(i_roster >= 0 and SCRIPTS[i_roster][1].count("new CompEngine(") == 1 and "const ENG = new CompEngine(DATASET" in SCRIPTS[i_app][1],
      "L38q the roster module's engine is its own one instance; the planner's is made in the planner's script alone")

print("L38r - the build on the sheet: the planner's saved loadout per slot, named from the page's tables, display only")
# Phase 12: the build module reads the CTA's share hash (p= and g=, the
# planner's own codec) and names gear and spells from GEAR and SPELLS;
# it paints into the build place each slot cell leaves empty, after the
# sheet's own event, and never scores, writes or reaches a table.
BUILD_JS = read("_build.js")
check("function sheetBuilds" in BUILD_JS and "function hashMembers" in BUILD_JS and 'params.get("g")' in BUILD_JS and 'params.get("p")' in BUILD_JS,
      "L38r1 the build module reads the share hash's members and loadouts through the planner's codec")
check(not re.search(r"\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine|PLANNED|\bLOADOUT\b|location\.hash|window\.DB|\.from\(|\.rpc\(|\.channel\(", BUILD_JS),
      "L38r2 the build module reads and writes no planner state and reaches no table or channel")
build_globals = set(re.findall(r"\b(CAP_LABEL|CAP_PROSE|ICONS|DATASET|CompEngine|SEMANTIC_ICONS|WEAPONS|TREES|ITEMS|SPELLS|GEAR|USAGE|FAMILIES|loadoutDecode|loArtRetry)\b", BUILD_JS))
check(build_globals == {"ICONS", "SPELLS", "GEAR", "loadoutDecode", "loArtRetry"},
      "L38r3 the planner's globals it reads are the gear and spell tables, the icons, the codec and the art retry, no other", str(sorted(build_globals)))
check('addEventListener("sheet-read"' in BUILD_JS and "[data-su-build]" in BUILD_JS and "su-board" not in BUILD_JS and "su-form" not in BUILD_JS
      and 'build.dataset.suBuild = String(row.position)' in SIGNUP_JS and "replaceChildren" not in seg(SIGNUP_JS, "function toggleBuild", "\n  }", "L38r4 toggle anchors")
      and "sheetBuilds" not in SIGNUP_JS and "GEAR" not in SIGNUP_JS and "SPELLS" not in SIGNUP_JS,
      "L38r4 the sheet leaves a build place in every slot cell and never fills it; the build module fills every place after each sheet-read")
check("<li" not in BUILD_JS and "<span" not in BUILD_JS and "<img" not in BUILD_JS and "innerHTML" not in BUILD_JS,
      "L38r5 the build is built without markup strings")
check("BUILD_MSG" in BUILD_JS and all(k in BUILD_JS for k in ("none:", "changed:", "unset:")),
      "L38r6 a slot with no weapon, a changed weapon and a comp saved without loadouts each have a sentence")
check(all(s in AUTH_CSS for s in (".su-build{", ".su-build-gear{", ".su-gear{", ".su-build-spells{", ".su-build-toggle{", '.su-build-toggle[aria-expanded="true"]')),
      "L38r7 the build toggle and the build's rows are styled in _auth.css")
check("function toggleBuild" in SIGNUP_JS and "openBuilds" in SIGNUP_JS and 'setAttribute("aria-expanded"' in SIGNUP_JS,
      "L38r8 the toggle says whether the build is open and the open builds survive a redraw")
i_build = script_at(lambda a, b: "function sheetBuilds" in b)
check(0 <= i_roster < i_build, "L38r9 the build module loads after the roster module, in its own <script>",
      "script indices roster=%d build=%d" % (i_roster, i_build))
check(not re.search(r"sheetBuilds|hashMembers|BUILD_MSG", APP + DECISION_JS), "L38r10 the planner never calls the build module")

# ---------------------------------------------------------------------------
print("L39 - the design check of the account dialogs and the portal page: hidden honoured, one line per slot, one primary per dialog, the title takes focus")
PORTAL = read("_portal.html")
check(".auth-dialog [hidden], .sheet-page [hidden], .acct-menu [hidden]{display:none !important}" in AUTH_CSS,
      "L39a every part of the account layer gives the hidden attribute its meaning, whatever display its class sets")
check(".cp-weapon .gd-name{display:inline}" in AUTH_CSS, "L39b a comp or CTA slot is one line: icon, name and role tag inline")
check('.cp-fields .text-input, .cp-fields select{min-width:0}' in LAYOUT and '.cp-fields .auth-field:has(input[type="datetime-local"]){grid-column:1/-1}' in LAYOUT,
      "L39c on a phone the comp and CTA fields shrink to their columns and a date field takes the row (_layout.css)")
check(".cp-foot-r{margin:0 0 0 auto}" in AUTH_CSS, "L39d the footer's primary action sits at the right in every dialog")
hist = seg(SHELL, '<dialog class="auth-dialog guild-dialog comp-dialog history-dialog"', "</dialog>", "L39e history anchors")
check(hist.count('<th scope="col" class="hs-num">') == 8 and ".hs-table th.hs-num{text-align:right}" in AUTH_CSS and "th:nth-child" not in AUTH_CSS,
      "L39e the history tables align a numeric header over its numbers by class, never by position")
check(SHELL.count('tabindex="-1" autofocus') == 5
      and all(('id="%s" tabindex="-1" autofocus' % t) in SHELL for t in ("guild-title", "comp-title", "ev-title", "hs-title", "im-title"))
      and 'id="auth-title" tabindex' not in SHELL and 'id="profile-title" tabindex' not in SHELL and ".auth-hd h2:focus-visible{outline:none}" in AUTH_CSS,
      "L39f the five list dialogs open with focus on their title; the sign-in and profile dialogs focus their first field; the sheet is a page")
check(".su-grid:has(> .su-form-wrap > #su-form[hidden]){grid-template-columns:1fr}" in AUTH_CSS,
      "L39g a sheet that takes no sign-up keeps no column for the form")
check('.im-table tr[data-status="none"] .im-status{color:var(--gap)' in AUTH_CSS, "L39h the import marks a name with no match as plainly as an uncertain one")
check(".auth-dialog, .sheet-page, .acct-menu{--ink-3:#8A8FA8; --role-melee:#FF5C9A}" in AUTH_CSS and "--ink-3:#757A92" in SHELL and "--role-melee:#E00063" in SHELL,
      "L39i the account layer's small-text tones clear 4.5:1 on its surfaces; the planner's tokens stand")
secondary = ("guild-join-submit", "guild-new-submit", "guild-rename-submit", "comp-from-planner", "ev-new", "im-read")
check(all(re.search(r'class="auth-secondary[^"]*" id="%s"' % i, SHELL) for i in secondary) and '.auth-secondary[aria-busy="true"]::before' in AUTH_CSS,
      "L39j one primary per dialog: the side column's creators, the rename and the sheet read are secondary, and show busy like a primary")
rr_css = seg(AUTH_CSS, ".rr{", ".su-status-row[hidden]", "L39k read css anchors")
check('<section class="rr-block rr-block-wide" aria-labelledby="rr-free-label">' in SHELL and '<ul class="rr-list rr-cols" id="rr-free">' in SHELL
      and ".rr-cols{columns:2" in AUTH_CSS and ".rr-list .gd-sub{display:inline}" in AUTH_CSS and "flex-basis:100%" not in rr_css,
      "L39k the read's open slots take the row in two columns and every item is one line")
check(".gd-table{display:block; overflow-x:auto}" in LAYOUT
      and ".gd-table:not(.im-table) td, .gd-table:not(.im-table) th{white-space:nowrap}" in LAYOUT and "su-table" not in LAYOUT and "su-table" not in AUTH_CSS
      and "position:relative}" in seg(AUTH_CSS, ".gd-table th{", "\n.gd-table td", "L39l header anchors") and ".gd-role-select{padding:3px 6px; font-size:var(--fs-dense); width:auto}" in AUTH_CSS,
      "L39l on a phone the member and slot tables scroll sideways at their own widths and a hidden header label never widens the card; the sheet has no table")
check(".gd-weapons{display:inline-flex" in AUTH_CSS and ".gd-covers{display:inline-flex" in AUTH_CSS, "L39m a member's weapons and role tags share one line")
_fs = re.findall(r"font-size:\s*([^;}\s]+)", AUTH_CSS)
check(":root{--fs-label:10px; --fs-meta:11px; --fs-dense:12px; --fs-body:13px; --fs-lead:16px; --fs-title:21px}" in AUTH_CSS
      and _fs and all(re.fullmatch(r"var\(--fs-(label|meta|dense|body|lead|title)\)", v) for v in _fs),
      "L39o the account layer's type is one six-step scale: every font-size is a step, none a literal",
      str(sorted(set(v for v in _fs if not v.startswith("var(--fs-")))[:6]))
check("--serif:" in PORTAL and "h1,h2,h3{font-family:var(--serif)" in PORTAL
      and "white-space:nowrap" in seg(PORTAL, ".brand{", "}", "L39n brand anchors") and "flex-wrap:wrap" in seg(PORTAL, ".top{", "}", "L39n top anchors")
      and "th:nth-child(2),td:nth-child(2){position:sticky;left:0" in PORTAL,
      "L39n the portal page shares the planner's headings and labels, its header wraps on a phone and the weapon column stays put while the table scrolls")
check(".gd-main .cp-foot{position:sticky; bottom:0; z-index:1; background:var(--surface); box-shadow:0 20px 0 var(--surface)}" in AUTH_CSS
      and "max-height:calc(100dvh - 32px); overflow:auto;" in seg(AUTH_CSS, ".auth-card{", "}", "L39p card anchors"),
      "L39p the card is the scroller and a comp's and a CTA's action bar stays in view while the slots scroll under it")

if FAILURES:

    print("\n%d contract(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall dashboard layout contracts pass")
sys.exit(0)
