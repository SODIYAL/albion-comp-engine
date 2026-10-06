/* Dragon Portal page tests — the script inside dashboard/_portal.html.
 *
 * The page is a killboard surface with no engine: its only logic is how it
 * orders, switches and opens what the stats artifact carries. A wrong order
 * renders as a plausible table, so the order, the view switch, the address
 * hash and the shape blocks are pinned here.
 *
 * The page's one <script> is extracted from the source and run in a vm
 * context over a stub document (elements that keep their innerHTML and
 * their listeners) and a synthetic PORTAL_STATS. Extraction fails LOUD if
 * the script moves.
 *
 * Run:  node tests/test_portal_page.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = fs.readFileSync(path.join(__dirname, "..", "dashboard", "_portal.html"), "utf8");
const m = SRC.match(/<!-- PORTAL_STATS -->\s*<script>\n([\s\S]*?)\n<\/script>/);
if (!m) throw new Error("could not extract the page script from _portal.html");
const SCRIPT = m[1];

let passed = 0, failed = 0;
function check(name, ok, detail) {
  console.log((ok ? "PASS  " : "FAIL  ") + name + (!ok && detail ? "\n      " + detail : ""));
  if (ok) passed++; else failed++;
}

const W = (id, parties, kd, dom, extra) => Object.assign({
  id, name: id, icon: "T6_" + id, parties, share: parties / 10, players: parties,
  scored: 9, dominant_share: dom, kd, kills: 1, deaths: 1, median_ip: 1200, build: {},
}, extra || {});
const pool = (label, lo, hi, extra) => Object.assign({
  label, sizes: [lo, hi], parties: 50, scored: 48, dominant_share: 0.9,
  weapons: [], weapons_total: 0, comps: [], comps_total: 0,
}, extra || {});
const comp = (names, n, kd, dom) => ({
  weapons: names.map(x => ({id: x, name: x, icon: "T6_" + x})),
  members: names.map(x => ({id: x, name: x, icon: "T6_" + x, sightings: n, build: {}})),
  n, scored: n, dominant_share: dom, kd,
});
const STATS = {
  battles: 10, parties: 20, generated_at: "2026-10-03T06:40Z",
  window: {first: "2026-09-05T08:09", last: "2026-10-03T06:34"},
  thresholds: {slot_votes: 3, comp_sightings: 2},
  pools: {
    solo: pool("Solo", 1, 1, {weapons: [
      W("ALPHA", 9, 2.0, 0.5, {build: {armor: {id: "ARMOR_A", name: "Armor A", votes: 5, share: 0.5, of: 10,
        others: [{id: "ARMOR_B", name: "Armor B", votes: 3, share: 0.3}]}}}),
      W("BRAVO", 7, 9.0, 0.9), W("CHARLIE", 5, null, null, {scored: 0}), W("DELTA", 3, 4.0, 0.7, {scored: 2})]}),
    trio: pool("3v3", 2, 3),
    five: pool("5v5", 4, 5, {weapons: [W("ALPHA", 9, 2.0, 0.5)],
      comps: [comp(["ALPHA", "BRAVO"], 8, 1.5, 0.4), comp(["CHARLIE", "DELTA"], 3, 7.0, 0.95)]}),
    seven: pool("7v7", 6, 7, {
      comps: [comp(["ALPHA", "BRAVO"], 2, 1.0, 0.5)],
      shapes: [
        {counts: {frontline: 1, healer: 1, support: 0, dps: 5}, size: 7, n: 60, scored: 60, dominant_share: 0.6, kd: 4.0,
         weapons: {dps: [{id: "ALPHA", name: "ALPHA", icon: "T6_ALPHA", parties: 30, share: 0.5, copies: 2}]}},
        {counts: {frontline: 2, healer: 1, support: 0, dps: 4}, size: 7, n: 43, scored: 3, dominant_share: 0.99, kd: 9.0,
         weapons: {frontline: [{id: "BRAVO", name: "BRAVO", icon: "T6_BRAVO", parties: 43, share: 1.0, copies: 1}]}}],
      shapes_total: 2,
      profile: {parties: 390, shapes_distinct: 46,
        roles: {frontline: {p25: 1, p50: 1, p75: 2, min: 0, max: 4}, healer: {p25: 1, p50: 1, p75: 1, min: 0, max: 3},
                support: {p25: 0, p50: 0, p75: 1, min: 0, max: 3}, dps: {p25: 3, p50: 4, p75: 5, min: 1, max: 7}},
        weapons: {healer: [{id: "CHARLIE", name: "CHARLIE", icon: "T6_CHARLIE", parties: 182, share: 0.467, copies: 1}]}}}),
    large: pool("20v20", 15, 20, {comps: [], shapes: [], shapes_total: 0,
      profile: {parties: 95, shapes_distinct: 78,
        roles: {frontline: {p25: 3, p50: 4, p75: 5, min: 0, max: 9}, healer: {p25: 3, p50: 4, p75: 4, min: 1, max: 6},
                support: {p25: 2, p50: 3, p75: 4, min: 0, max: 6}, dps: {p25: 7, p50: 7, p75: 9, min: 3, max: 13}},
        weapons: {healer: [{id: "CHARLIE", name: "CHARLIE", icon: "T6_CHARLIE", parties: 85, share: 0.895, copies: 2}]}}}),
  },
};

/* one page load: a stub document, the script run once */
function boot(hash, stored) {
  const store = Object.assign({}, stored || {});
  const mk = () => {
    const h = {};
    return {innerHTML: "", h, dataset: {}, value: "", hidden: false, addEventListener: (t, f) => { h[t] = f; },
            querySelectorAll: () => [], querySelector: () => null, focus() {}};
  };
  const els = {chips: mk(), tabs: mk(), pool: mk(), wfilter: mk(), "wfilter-in": mk(), "wfilter-clear": mk(), "wfilter-list": mk()};
  const ctx = {
    PORTAL_STATS: STATS, console,
    document: {getElementById: id => els[id]},
    location: {hash: hash || ""},
    localStorage: {getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; }},
  };
  vm.createContext(ctx);
  vm.runInContext(SCRIPT, ctx);
  const target = (sel, dataset) => ({closest: s => (s === sel ? {dataset, querySelector: () => ({hidden: true}),
                                                              classList: {add() {}, remove() {}},
                                                              getAttribute: () => "false", setAttribute() {}} : null)});
  return {
    els, store,
    html: () => els.pool.innerHTML,
    tab: k => els.tabs.h.click({target: target(".tab", {pool: k})}),
    view: v => els.pool.h.click({target: target(".view", {view: v})}),
    sort: (table, key) => els.pool.h.click({target: target("th.sortable", {table, sort: key})}),
    /* the filter box: a typed query, a press on a match, the clear button */
    type: q => { els["wfilter-in"].value = q; els["wfilter-in"].h.input(); },
    pick: id => els["wfilter-list"].h.mousedown({target: target("li[data-id]", {id}), preventDefault() {}}),
    clear: () => els["wfilter-clear"].h.click(),
    list: () => els["wfilter-list"].innerHTML,
  };
}
/* the data rows' first cell text after the rank, in page order */
const order = (html, names) => names.map(n => [n, html.indexOf(">" + n + "<")]).filter(x => x[1] >= 0)
  .sort((a, b) => a[1] - b[1]).map(x => x[0]).join(" ");
const NAMES = ["ALPHA", "BRAVO", "CHARLIE", "DELTA"];

/* ---- the first paint ---- */
let p = boot();
check("PP1 the page opens on the solo pool, weapons ordered by parties, with no view switch (a solo has no comp)",
      order(p.html(), NAMES) === "ALPHA BRAVO CHARLIE DELTA" && !p.html().includes('class="views"')
      && p.html().includes("Weapons that won"), order(p.html(), NAMES));
check("PP2 the chips state the window and the tabs every pool with its size range",
      p.els.chips.innerHTML.includes("2026-10-03 06:34") && p.els.tabs.innerHTML.includes("15–20 players")
      && (p.els.tabs.innerHTML.match(/class="tab"/g) || []).length === 5);

/* ---- sorting ---- */
p.sort("weapons", "kd");
check("PP3 a heading click orders by that column, highest first; a missing value sorts last",
      order(p.html(), NAMES) === "BRAVO DELTA ALPHA CHARLIE" && /data-sort="kd"[^>]*aria-sort="descending"/.test(p.html()),
      order(p.html(), NAMES));
p.sort("weapons", "kd");
check("PP3b the same heading again flips the order; the missing value stays last",
      order(p.html(), NAMES) === "ALPHA DELTA BRAVO CHARLIE" && /data-sort="kd"[^>]*aria-sort="ascending"/.test(p.html()),
      order(p.html(), NAMES));
p.sort("weapons", "dominant_share");
check("PP3c another heading starts at highest first",
      order(p.html(), NAMES) === "BRAVO DELTA ALPHA CHARLIE", order(p.html(), NAMES));
check("PP4 a weapon under five scored parties is marked thin; a slot card carries its whole field",
      (p.html().match(/\(thin\)/g) || []).length === 2 && p.html().includes('data-alts="1"')
      && p.html().includes("Armor B") && p.html().includes("and 2 more across rarer items"));

/* ---- the view switch ---- */
p.tab("five");
check("PP5 a pool of two and more offers the view switch and remembers the pool",
      p.html().includes('data-view="comps"') && p.html().includes("Weapons that won") && p.store["portal-pool"] === "five");
p.view("comps");
check("PP5b the comps view replaces the weapons table, ordered by sightings, and is remembered",
      p.html().includes('id="comps"') && !p.html().includes("click a row for the build")
      && p.html().indexOf(">ALPHA<") < p.html().indexOf(">CHARLIE<") && p.store["portal-view"] === "comps");
p.sort("comps", "kd");
check("PP5c comps sort by their own headings", p.html().indexOf(">CHARLIE<") < p.html().indexOf(">ALPHA<"));
check("PP5d a pool under six shows no shapes and calls its comps plain comps",
      !p.html().includes('id="shapes"') && !p.html().includes('id="profile"') && p.html().includes("<h3>Comps that won"));
p.tab("solo");
check("PP5e the solo pool falls back to weapons whatever view was open",
      p.html().includes("Weapons that won") && !p.html().includes('id="comps"'));

/* ---- shapes and the roster profile ---- */
p = boot("#seven/comps");
const h7 = p.html();
check("PP6 the address opens a pool and a view (#seven/comps)",
      h7.includes('id="profile"') && h7.includes('id="shapes"') && h7.includes('id="comps"'));
check("PP6b the profile states each role's middle range with its median and extremes, and the weapons that fill it",
      /<b>1–2<\/b><span>Frontline<\/span>/.test(h7) && /<b>1<\/b><span>Healer<\/span>/.test(h7)
      && h7.includes("median 4 · 1 to 7") && h7.includes("CHARLIE <small>47%</small>") && h7.includes("390 parties"));
check("PP6c a shape row reads members per role, most seen first; its detail lists the weapons per role with copies",
      h7.indexOf("<b>5</b> damage") < h7.indexOf("<b>2</b> frontline") && h7.includes("<b>1</b> healer")
      && h7.includes("ALPHA <small>50% ×2</small>") && !h7.includes("<b>0</b> support"));
check("PP6d the profile, the shapes and the exact comps come in that order; the comps are called exact",
      h7.indexOf('id="profile"') < h7.indexOf('id="shapes"') && h7.indexOf('id="shapes"') < h7.indexOf('id="comps"')
      && h7.includes("Exact comps that won"));
p.sort("shapes", "dominant_share");
check("PP6e shapes sort by their own headings; a shape under five scored parties is marked thin",
      p.html().indexOf("<b>2</b> frontline") < p.html().indexOf("<b>5</b> damage") && p.html().includes("(thin)"));
p = boot("#large/comps");
check("PP7 where no shape recurs the page says so and the profile carries the read: ranges, the note that "
      + "exact comps rarely repeat",
      p.html().includes("No role shape has been seen 2 times yet") && /<b>3–5<\/b><span>Frontline<\/span>/.test(p.html())
      && p.html().includes("no single shape dominates") && p.html().includes("An exact comp rarely repeats at this size")
      && p.html().includes("CHARLIE <small>90% ×2</small>"));
p = boot("", {"portal-pool": "five", "portal-view": "comps"});
check("PP8 a return visit opens the remembered pool and view; the address wins over memory",
      p.html().includes('id="comps"') && boot("#solo", {"portal-pool": "five"}).html().includes(">DELTA<"));

/* ---- the weapon filter ---- */
p = boot("#solo");
p.type("alp");
check("PP9 typing lists the matching weapons with the pools that carry them; the first is selected",
      p.list().includes('data-id="ALPHA"') && !p.list().includes('data-id="BRAVO"') && /data-id="ALPHA" aria-selected="true"/.test(p.list())
      && p.list().includes("Solo · 5v5 · 7v7") && !p.els["wfilter-list"].hidden, p.list());
p.type("zzz");
check("PP9b a query no weapon matches says so", p.list().includes("No weapon on this page matches"));
p.pick("ALPHA");
check("PP9c a chosen weapon narrows the weapons table to its row at its rank, the build open, the read stating where it stands; it is remembered and in the address",
      (p.html().match(/<tr class="row/g) || []).length === 1 && p.html().includes('class="row hit"') && p.html().includes('aria-expanded="true"')
      && p.html().includes("<b>ALPHA</b> is <b>#1</b> of 4 weapons in Solo by parties") && !p.html().includes('data-for="0" hidden')
      && p.store["portal-weapon"] === "ALPHA" && p.els["wfilter-in"].value === "ALPHA" && p.els.wfilter.dataset.on === "1" && !p.els["wfilter-clear"].hidden,
      p.html());
p.sort("weapons", "kd");
check("PP9d the rank follows the order: by K/D ALPHA is third",
      p.html().includes("<b>ALPHA</b> is <b>#3</b> of 4 weapons in Solo by k/d"), p.html());
check("PP9e every tab says how many of its winning parties fielded the weapon, or that it is not seen",
      p.els.tabs.innerHTML.includes("ALPHA: 9 parties") && p.els.tabs.innerHTML.includes('class="tw none">ALPHA: not seen')
      && p.els.tabs.innerHTML.includes("ALPHA: fielded"), p.els.tabs.innerHTML);
p.tab("trio");
check("PP9f a pool without the weapon says so instead of an empty table", p.html().includes("No portal killer parties of this size"));
p.tab("five");
check("PP9g a pool whose table lacks the weapon but whose comps field it points to the comps",
      boot("#five/weapons/BRAVO").html().includes("BRAVO is not among the 1 weapons listed for 5v5") && boot("#five/weapons/BRAVO").html().includes("fielded in 1 winning comp:"));
p.view("comps");
check("PP9h the comps view narrows to the comps that fielded the weapon, its chip marked, the switch counting them",
      (p.html().match(/<tr class="row"/g) || []).length === 1 && p.html().includes('class="w hit"') && p.html().includes(">ALPHA<") && !p.html().includes(">DELTA<")
      && p.html().includes("Comps that won with ALPHA") && p.html().includes("<small>1 of 2</small>"), p.html());
p = boot("#seven/comps/CHARLIE");
check("PP9i the address opens a pool, a view and a weapon: the profile reads the weapon's seat and share; shapes without it are gone",
      p.html().includes("<b>CHARLIE</b> fills the healer seat in <b>47%</b> of the 390 winning parties") && p.html().includes("None of the 2 shapes seen 2+ times fielded CHARLIE")
      && p.html().includes("None of the 1 comps seen 2+ times in 7v7 fielded CHARLIE") && p.els["wfilter-in"].value === "CHARLIE", p.html());
p = boot("#seven/comps/ALPHA");
check("PP9j a shape that fields the weapon stays, the switch counting shapes",
      p.html().includes("<b>5</b> damage") && !p.html().includes("<b>2</b> frontline") && p.html().includes("<small>1 of 2 shapes</small>")
      && p.html().includes("<b>ALPHA</b> is not among the weapons that most often fill a seat in 7v7"), p.html());
p.clear();
check("PP9k clearing the filter restores the whole page and forgets the weapon",
      p.html().includes("<b>2</b> frontline") && !("portal-weapon" in p.store) && p.els["wfilter-in"].value === "" && p.els["wfilter-clear"].hidden);
check("PP9l a remembered weapon returns with the page; an unknown one in the address is ignored",
      boot("#solo", {"portal-weapon": "BRAVO"}).html().includes("<b>BRAVO</b> is <b>#2</b>") && !boot("#solo/weapons/NOPE").html().includes("wf-read"));

console.log(failed ? `\n${failed} portal-page test(s) failed` : `\nall ${passed} portal-page tests pass`);
process.exit(failed ? 1 : 0);
