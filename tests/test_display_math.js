/* Killboard display-math tests — usageBucket / cohortContext / cohortAffinity
 * in dashboard/_app.js — plus the supply board's ring geometry and what its
 * rows show a customer (renderGroups: names, numbers, chips).
 *
 * These three functions are the one display-layer computation that does NOT
 * "show its own mistakes" on screen (the codec-test rationale): a wrong
 * bucket or a wrong lift renders as a plausible strip, and exactly that
 * shipped once — the strip keyed off the judged roster size, so a 20-man
 * plan quoted small-gank cohorts and the affinity surface stayed invisible
 * for the whole planning phase (fixed: usageBucket -> PLAN()).
 *
 * _app.js is inlined into a page, not a module, so the functions under test
 * are extracted from the source by name and evaluated in a vm context with
 * the globals they read stubbed out. Extraction fails LOUD if a function is
 * renamed or its closing brace moves off column 0.
 *
 * Run:  node tests/test_display_math.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const CompEngine = require(path.join(__dirname, "..", "engine", "app_scoring.js"));

const SRC = fs.readFileSync(
  path.join(__dirname, "..", "dashboard", "_app.js"), "utf8");

function extract(name) {
  const m = SRC.match(new RegExp(
    "function " + name + "\\(\\)\\{\\n[\\s\\S]*?\\n\\}"));
  if (!m) throw new Error(`could not extract function ${name}() from _app.js`);
  return m[0];
}
const label = SRC.match(/const USAGE_BUCKET_LABEL = \{.*\};/);
if (!label) throw new Error("could not extract USAGE_BUCKET_LABEL");
const sizeLabel = SRC.match(/const COHORT_SIZE_LABEL = \{.*\};/);
if (!sizeLabel) throw new Error("could not extract COHORT_SIZE_LABEL");

const ctx = {
  PLANNED: 20,
  party: [],
  PLAN: null,           // assigned below, mirrors _app.js semantics
  USAGE: {},
  FAMILIES: {},
  WEAPONS: {},
  console,
};
vm.createContext(ctx);
vm.runInContext("PLAN = () => Math.max(PLANNED, party.length);", ctx);
vm.runInContext(label[0], ctx);
vm.runInContext(sizeLabel[0], ctx);
vm.runInContext(extract("usageBucket"), ctx);
vm.runInContext(extract("cohortContext"), ctx);
vm.runInContext(extract("cohortAffinity"), ctx);
vm.runInContext(extract("cohortNeighbours"), ctx);
vm.runInContext(extract("familyRows"), ctx);

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail ? "\n      " + detail : ""}`); }
}
const run = (expr) => vm.runInContext(expr, ctx);

/* 1 — bucket thresholds on the participant axis (2 x PLAN, mirrors
   engine sizeBucket: <12 small, <=30 mid, else large) */
{
  const at = (planned) => { ctx.PLANNED = planned; ctx.party = []; return run("usageBucket()"); };
  check("bucket thresholds: plan 3/5 small, 6/15 mid, 16/20 large",
        at(3) === "small" && at(5) === "small"
        && at(6) === "mid" && at(15) === "mid"
        && at(16) === "large" && at(20) === "large",
        `3:${at(3)} 5:${at(5)} 6:${at(6)} 15:${at(15)} 16:${at(16)} 20:${at(20)}`);
}

/* 2 — THE regression: the bucket follows the size the comp is FOR, not the
   roster count so far. A 20-man plan with 3 picks must quote large fights. */
{
  ctx.PLANNED = 20;
  ctx.party = ["A", "B", "C"];
  const early = run("usageBucket()");
  // and a roster grown past the plan drags the bucket up with it
  ctx.PLANNED = 3;
  ctx.party = ["A", "B", "C", "D", "E", "F", "G"];
  const grown = run("usageBucket()");
  check("planned size drives the bucket, not the judged roster count",
        early === "large" && grown === "mid",
        `3-of-20 -> ${early} (want large); 7-of-3 -> ${grown} (want mid)`);
}

/* Fixture for the cohort math: 11 large-fight baskets. ZZZ is an unknown
   (renamed/retired) weapon key — it must never surface as a candidate.
   Hand-computed below: count[A]=6 (r1,r2,r3,r5,r8,r11), count[B]=5,
   count[C]=5, count[D]=4, count[E]=2, N=11. */
const BASKETS = [
  ["A", "B"], ["A", "B"], ["A", "C"], ["B", "C"], ["A", "B", "C"],
  ["C", "D"], ["D", "E"], ["A", "D"], ["B", "D"], ["C", "E"], ["A", "ZZZ"],
];
function setUsage(baskets) {
  ctx.USAGE = { cohort_baskets: { large: baskets, mid: [], small: [] } };
  ctx.WEAPONS = { A: {}, B: {}, C: {}, D: {}, E: {} };
}

/* 3 — thin data yields no context: under 8 usable rows, or rows thinned
   below 2 weapons, the strip must fall back (return null) */
{
  ctx.PLANNED = 20; ctx.party = [];
  setUsage(BASKETS.slice(0, 7));
  const thin = run("cohortContext()");
  setUsage(BASKETS.slice(0, 6).concat([["A"], ["B"], ["C"]]));  // 9 rows, 6 usable
  const thinned = run("cohortContext()");
  setUsage(BASKETS);
  const okCtx = run("cohortContext()");
  check("under 8 usable cohorts the context is null; 11 usable rows carry",
        thin === null && thinned === null
        && okCtx && okCtx.key === "large" && okCtx.rows.length === 11
        && okCtx.label === "16+",   // the cohort axis is party size
        `thin=${JSON.stringify(thin)} thinned=${JSON.stringify(thinned)}`);
}

/* 4 — single-weapon party: minOverlap 1, candidates need >=2 cohorts,
   lift is popularity-corrected both*N/(countA*countW), hand-computed */
{
  setUsage(BASKETS);
  ctx.PLANNED = 20; ctx.party = ["A"];
  const a = run("cohortAffinity()");
  const byW = {}; a.candidates.forEach(c => { byW[c.w] = c; });
  check("candidates: B (3 cohorts) then C (2); D at 1 cohort is filtered out",
        a.minOverlap === 1 && a.N === 11
        && a.candidates.map(c => c.w).join(",") === "B,C"
        && byW.B.cohorts === 3 && byW.C.cohorts === 2 && !byW.D,
        JSON.stringify(a.candidates));
  check("pair lift is popularity-corrected (B: 3*11/(6*5)=1.1, C: 2*11/30)",
        Math.abs(byW.B.lift - 1.1) < 1e-12
        && Math.abs(byW.C.lift - 22 / 30) < 1e-12,
        `B=${byW.B.lift} C=${byW.C.lift}`);
  check("selected weapons and unknown keys never appear as candidates",
        !byW.A && !byW.ZZZ, JSON.stringify(Object.keys(byW)));
}

/* 5 — from two unique selected weapons on, a match must echo a PAIR:
   only r1,r2,r5 hold both A and B; their sole co-member C appears in one
   cohort, under the >=2 floor, so the candidate list is rightly empty */
{
  ctx.party = ["A", "B"];
  const a = run("cohortAffinity()");
  check("2-weapon party requires >=2 overlap; lone-cohort candidates drop",
        a.minOverlap === 2 && a.candidates.length === 0,
        JSON.stringify(a.candidates));
}

/* 6 — no party or no context -> null, never a throw */
{
  ctx.party = [];
  const empty = run("cohortAffinity()");
  ctx.party = ["A"];
  ctx.USAGE = {};
  const noData = run("cohortAffinity()");
  check("empty party or missing cohort data yields null",
        empty === null && noData === null,
        `empty=${JSON.stringify(empty)} noData=${JSON.stringify(noData)}`);
}

/* 7 — partial-roster neighbours (roadmap item 6): baskets sharing >=2 of
   the selected weapons, ranked shared desc then Jaccard desc then basket
   order. Party [A,B]: r1 [A,B] and r2 [A,B] are exact echoes (Jaccard 1),
   r5 [A,B,C] shares both but adds C (Jaccard 2/3) and its `others` names
   the completion. Hand-computed against BASKETS. */
{
  setUsage(BASKETS);
  ctx.PLANNED = 20; ctx.party = ["A", "B"];
  const nb = run("cohortNeighbours()");
  check("neighbours: three >=2-overlap baskets, exact echoes first, then r5",
        nb && nb.matched === 3 && nb.rows.length === 3
        && nb.rows[0].shared === 2 && nb.rows[0].jaccard === 1
        && nb.rows[1].jaccard === 1
        && Math.abs(nb.rows[2].jaccard - 2 / 3) < 1e-12
        && nb.rows[2].others.join(",") === "C",
        JSON.stringify(nb && nb.rows));
}

/* 8 — a single-weapon party has no roster shape to echo; unknown weapon
   keys are stripped BEFORE the overlap count (a basket [A, ZZZ] must not
   match a pair through a retired key) */
{
  ctx.party = ["A"];
  const single = run("cohortNeighbours()");
  ctx.party = ["A", "ZZZ"];
  const ghost = run("cohortNeighbours()");
  check("pairs only: 1 selected weapon -> null; unknown keys never match",
        single === null && ghost === null,
        `single=${JSON.stringify(single)} ghost=${JSON.stringify(ghost)}`);
}

/* 9 — the view caps at 3 rows but reports the full match count, and the
   duplicate-weapon roster dedupes before matching (2x A + B is the pair
   A,B — duplicates must not inflate overlap or the shared denominator) */
{
  setUsage(BASKETS.concat([["A", "B", "D"]]));   // a 4th >=2-overlap basket
  ctx.party = ["A", "A", "B"];
  const nb = run("cohortNeighbours()");
  check("top-3 slice with full matched count; duplicates dedupe",
        nb && nb.matched === 4 && nb.rows.length === 3
        && nb.selected.length === 2
        && nb.rows.every(r => r.shared === 2),
        JSON.stringify(nb && {matched: nb.matched, n: nb.rows.length}));
}

/* 10 — recurring observed families (roadmap item 7): rows key to the
   planned bucket; `anchored` demands BOTH anchor weapons in the roster;
   `mine` marks the family pieces the roster carries (catalog-filtered) */
{
  ctx.FAMILIES = { large: [
    { anchor: ["A", "B"], cohorts: 9, orgs: 5, battles: 6, lift: 2.1,
      cast: [{ weapon: "C", share: 0.6 }, { weapon: "D", share: 0.4 }] },
    { anchor: ["D", "E"], cohorts: 5, orgs: 3, battles: 4, lift: 1.5, cast: [] },
  ], mid: [], small: [] };
  setUsage(BASKETS);   // resets WEAPONS to A..E
  ctx.PLANNED = 20; ctx.party = ["A", "B", "C", "ZZZ"];
  const fr = run("familyRows()");
  check("family match: anchored when both anchors held; mine lists carried "
        + "pieces; unknown roster keys ignored",
        fr && fr.length === 2
        && fr[0].anchored === true && fr[0].mine.join(",") === "A,B,C"
        && fr[1].anchored === false && fr[1].mine.length === 0,
        JSON.stringify(fr));
  ctx.PLANNED = 8;   // mid bucket -> empty family list -> null
  const empty = run("familyRows()");
  ctx.PLANNED = 20; ctx.FAMILIES = undefined;
  const missing = run("typeof FAMILIES === 'undefined' ? familyRows() : 'x'");
  check("empty bucket or missing FAMILIES embed yields null, never a throw",
        empty === null && missing === null,
        `empty=${JSON.stringify(empty)} missing=${JSON.stringify(missing)}`);
}

/* 14 — observed effect quotas (increment 3b, R18):
   carried counts come from the LOADOUT chests only, quotas scale to
   PLAN, unknown gear blocks any shortfall claim, and the panel arms at
   15+ only. */
{
  vm.runInContext(extract("effectQuotaRows"), ctx);
  ctx.FAMILIES = {};
  ctx.PLANNED = 20;
  ctx.party = ["W1", "W2", "W3"];
  ctx.EFFECT_QUOTAS = { min_size: 15, rosters: 8, effects: {
    reflect_shell: { name: "Reflect area", items: ["ARMOR_PLATE_HELL"],
                     typical: 3.0, fielded: 0.88 } } };
  ctx.LOADOUT = [{ armor: "ARMOR_PLATE_HELL" }, { armor: "ARMOR_PLATE_SET2" },
                 { armor: "ARMOR_PLATE_HELL" }];
  let rows = run("effectQuotaRows()");
  const counted = rows && rows.length === 1 && rows[0].have === 2
    && rows[0].want === 3 && rows[0].unset === 0 && rows[0].short === true;
  ctx.LOADOUT = [{ armor: "ARMOR_PLATE_HELL" }, {}, undefined];
  rows = run("effectQuotaRows()");
  const unknownSafe = rows && rows[0].have === 1 && rows[0].unset === 2
    && rows[0].short === false;   // unknown chests never claim a shortfall
  ctx.PLANNED = 10; ctx.party = [];
  const below = run("effectQuotaRows()");
  ctx.PLANNED = 30; ctx.party = []; ctx.LOADOUT = [];
  rows = run("effectQuotaRows()");
  const scaled = rows && rows[0].want === 4.5;   // 3.0 * 30/20
  ctx.EFFECT_QUOTAS = undefined; ctx.PLANNED = 20;
  const missing = run(
    "typeof EFFECT_QUOTAS === 'undefined' ? effectQuotaRows() : 'x'");
  check("effect quotas: chest-counted, PLAN-scaled, unknown-gear-honest, "
        + "armed at 15+, missing embed yields null",
        counted && unknownSafe && below === null && scaled
        && missing === null,
        `counted=${counted} unknownSafe=${unknownSafe} `
        + `below=${JSON.stringify(below)} scaled=${scaled}`);
}

/* 9 — gearsFromLoadout (dressed forge Task 1): LOADOUT entry -> engine
   gears list. Curated pieces only, fixed LO_SLOTS order, null when
   nothing curated is equipped — the page's scoring truth depends on
   this mapping being stable (the fitness cache key embeds it). */
{
  const mg = SRC.match(
    /function gearsFromLoadout\(lo, gearDb\)\{\n[\s\S]*?\n\}/);
  if (!mg) throw new Error("could not extract gearsFromLoadout from _app.js");
  vm.runInContext(mg[0], ctx);
  const GEAR_FIX = JSON.stringify({ HEAD_CLOTH_SET2: 1, ARMOR_PLATE_SET2: 1 });
  const mapped = run(
    `JSON.stringify(gearsFromLoadout({ head: "HEAD_CLOTH_SET2",
       armor: "ARMOR_PLATE_SET2", shoes: "SHOES_NOT_CURATED", q: 1 },
       ${GEAR_FIX}))`);
  check("gearsFromLoadout maps curated slots in fixed order",
        mapped === JSON.stringify(["HEAD_CLOTH_SET2", "ARMOR_PLATE_SET2"]),
        mapped);
  const empties = run(
    `[gearsFromLoadout(undefined, ${GEAR_FIX}),
      gearsFromLoadout({ q: 2 }, ${GEAR_FIX}),
      gearsFromLoadout({ shoes: "SHOES_NOT_CURATED" }, ${GEAR_FIX})]`);
  check("gearsFromLoadout: empty/uncurated -> null",
        empties.every(v => v === null), JSON.stringify(empties));
}

/* ---- capability-ring geometry -------------------------------------------
 * The supply board's arcs are the other display computation that does not
 * show its own mistakes usefully: a ring drawn outside its viewBox still
 * PAINTS (SVG overflow), so a wrong origin renders as arcs sitting on top
 * of the legend text rather than as a blank chart. That shipped once
 * (cy was set to the bottom of the box instead of the top, so
 * every arc ran 92px past it and covered the labels).
 */
{
  const geo = SRC.match(/function ringPath\([\s\S]*?\n\}\nfunction ringTick\([\s\S]*?\n\}/);
  if (!geo) throw new Error("could not extract ringPath/ringTick from _app.js");
  const ctx = { Math };
  vm.createContext(ctx);
  vm.runInContext(geo[0], ctx);

  /* renderGroups' geometry is EXTRACTED from the source, never copied - a
     hand copy drifted once (the sw formula lost its || 30 fallback) and a
     stale copy makes this guard validate itself instead of the page */
  const constM = SRC.match(/const W = ([\d.]+), R = ([\d.]+), cx = ([\d.]+), cy = ([\d.]+), H = ([\d.]+), r0 = ([\d.]+);/);
  if (!constM) throw new Error("could not extract renderGroups' geometry constants from _app.js");
  const [W, R, cx, cy, H, r0] = constM.slice(1).map(Number);
  const swM = SRC.match(/const sw = (Math\.max\([^\n]+\));/);
  if (!swM) throw new Error("could not extract renderGroups' stroke formula from _app.js");
  const halfM = SRC.match(/ringTick\(cx, cy, r, x\.tickPct \/ 100, (.+)\);/);
  if (!halfM) throw new Error("could not extract renderGroups' tick half-length from _app.js");
  /* a path is "M x0 y0 A r r 0 0 0 x1 y1" - take the FIRST and LAST pairs,
     never every number pair (the radii and flags are not coordinates) */
  const nums = d => (d.match(/-?[\d.]+/g) || []).map(Number);
  const ends = d => { const n = nums(d); return [[n[0], n[1]], [n[n.length - 2], n[n.length - 1]]]; };

  check("ringPath: zero coverage draws nothing",
        vm.runInContext(`ringPath(${cx},${cy},${R},0)`, ctx) === "");

  const full = ends(vm.runInContext(`ringPath(${cx},${cy},${R},1)`, ctx));
  check("ringPath: full sweep ends level with its start",
        full[0][1] === cy && full[1][1] === cy, JSON.stringify(full));
  check("ringPath: full sweep spans the diameter",
        Math.abs((full[1][0] - full[0][0]) - 2 * R) < 0.01, JSON.stringify(full));

  const half = ends(vm.runInContext(`ringPath(${cx},${cy},${R},0.5)`, ctx));
  check("ringPath: half sweep reaches the deepest point",
        Math.abs(half[1][0] - cx) < 0.01 && Math.abs(half[1][1] - (cy + R)) < 0.01,
        JSON.stringify(half));

  /* THE REGRESSION GUARD. An arc's extreme is NOT its endpoints - a full
     sweep ends level with its start while dipping r below it. The reachable
     extremes are cy + r (any sweep past halfway) and cx +/- r. Sweep EVERY
     group size 1..8: the stroke (and with it the tick half-length) GROWS as
     n shrinks, so the widest ring count is the LEAST clipping-prone case -
     testing only n=8 passed while every 2-6 cap group drew its tick past
     the box. The outermost ring is r=R for all n>1; ticks get 1px of slack
     for their own round line cap. */
  for (let n = 1; n <= 8; n++){
    const step = n > 1 ? (R - r0) / (n - 1) : 0;
    const sw = vm.runInContext(
      `(() => { const step = ${step}; return ${swM[1]}; })()`, ctx);
    const rOut = n > 1 ? r0 + (n - 1) * step : (r0 + R) / 2;
    const half = vm.runInContext(
      `(() => { const sw = ${sw}, H = ${H}, cy = ${cy}, r = ${rOut}; return ${halfM[1]}; })()`, ctx);
    const deepestArc = cy + rOut + sw / 2;
    let tickY = 0, tickXmax = 0, tickXmin = Infinity;
    for (let f = 0; f <= 100; f++){
      const t = vm.runInContext(`ringTick(${cx},${cy},${rOut},${f / 100},${half})`, ctx).map(Number);
      tickY = Math.max(tickY, t[1], t[3]);
      tickXmax = Math.max(tickXmax, t[0], t[2]);
      tickXmin = Math.min(tickXmin, t[0], t[2]);
    }
    check(`ring geometry fits the viewBox at n=${n} (arc ${deepestArc.toFixed(1)} <= ${H}, tick y ${tickY.toFixed(1)} <= ${H - 1})`,
          deepestArc <= H && tickY <= H - 1 && tickXmax <= W && tickXmin >= 0,
          `n=${n} sw=${sw.toFixed(2)} half=${half.toFixed(2)} tick y ${tickY.toFixed(2)} x ${tickXmin.toFixed(1)}..${tickXmax.toFixed(1)}`);
  }

}

/* 7 — the supply board as a customer reads it. renderGroups() runs whole in
   a vm with the engine reads stubbed; its HTML is read for what is VISIBLE
   (tags stripped, attributes gone) and what is one hover away (title
   attributes). Every requirement key the shipped templates use is rendered,
   so a new capability without a player name or a group fails here. */
{
  const DATASET = JSON.parse(fs.readFileSync(
    path.join(__dirname, "..", "pipeline", "out", "dataset-latest.json"), "utf8"));
  const KEYS = [...new Set(Object.values(DATASET.templates)
    .flatMap(t => Object.keys(t.requirements || {})))].sort();
  const DL = fs.readFileSync(
    path.join(__dirname, "..", "dashboard", "_decision_layer.js"), "utf8");

  const grab = (re, what) => {
    const m = SRC.match(re);
    if (!m) throw new Error(`could not extract ${what} from _app.js`);
    return m[0];
  };
  const ctx = { Math, String, Object, Set, CASE: null };
  vm.createContext(ctx);
  for (const [re, what] of [
    [/const esc = [\s\S]*?\}\[c\]\)\);/, "esc"],
    [/const GROUP_COL = \{[\s\S]*?\n\};/, "GROUP_COL"],
    [/const GROUPS = \{[\s\S]*?\n\};/, "GROUPS"],
    [/const CAP_PROSE = \{[\s\S]*?\n\};/, "CAP_PROSE"],
    [/const prose = .*;/, "prose"],
    [/const CAP_LABEL = \{[\s\S]*?\n\};/, "CAP_LABEL"],
    [/const capLabel = [\s\S]*?;\n/, "capLabel"],
    [/function ringPath\([\s\S]*?\n\}\nfunction ringTick\([\s\S]*?\n\}/, "ringPath/ringTick"],
    [/function renderGroups\(\)\{\n[\s\S]*?\n\}/, "renderGroups"],
  ]) vm.runInContext(grab(re, what), ctx);
  /* Engine reads come from CASE. Most display-only cases use compact stubs:
     reqs {cap: {target, soft_cap, min, weight}}, have {cap: n},
     mult {cap: style multiplier}, src {cap: source}. Integration cases pass
     a real CompEngine plus party/combo inputs so this same extracted renderer
     crosses the production scoring-to-dashboard boundary. */
  vm.runInContext(`
    var party = [];
    var DOM = {};
    function $(id){ return DOM[id] || (DOM[id] = {innerHTML: ""}); }
    function REQS(){ return CASE.engine ? CASE.engine.reqs : CASE.reqs; }
    function supply(){
      return CASE.engine
        ? CASE.engine.effectiveSupply(CASE.party, CASE.combos, CASE.gears)
        : CASE.have;
    }
    function supplyFloor(){
      return CASE.engine
        ? CASE.engine.effectiveSupply(CASE.party, CASE.combos)
        : CASE.have;
    }
    function target(c){ return CASE.engine ? CASE.engine.target(c) : CASE.reqs[c].target; }
    function softCap(c){ return CASE.engine ? CASE.engine.softCap(c) : CASE.reqs[c].soft_cap; }
    function targetMin(c){ return CASE.engine ? CASE.engine.targetMin(c) : CASE.reqs[c].min; }
    function floorHit(c, have){ return CASE.engine ? CASE.engine.floorArmed(c, have) : false; }
    function targetSource(c){
      return CASE.engine
        ? CASE.engine.targetSource(c)
        : (CASE.src && CASE.src[c]) || "harvest";
    }
    var ENG = {weight: c => CASE.engine
      ? CASE.engine.weight(c)
      : CASE.reqs[c].weight * ((CASE.mult && CASE.mult[c]) || 1)};
  `, ctx);
  const render = c => {
    ctx.CASE = c;
    vm.runInContext("renderGroups()", ctx);
    return vm.runInContext('$("groups").innerHTML', ctx);
  };
  const visible = html => html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
  const rowsOf = html => [...html.matchAll(/<li class="cap[^"]*">([\s\S]*?)<\/li>/g)].map(m => {
    const li = m[1];
    const btn = li.match(/<button class="cap-name" data-cap="([^"]+)"[^>]*>([\s\S]*?)<\/button>/);
    const val = li.match(/<span class="cap-val" title="([^"]*)">([\s\S]*?)<\/span>/);
    const sw = li.match(/<span class="cap-sw (\w+)">/);
    return {cap: btn && btn[1], name: btn ? visible(btn[2]) : "", nameHtml: btn ? btn[2] : "",
            valTitle: val ? val[1] : "", val: val ? visible(val[2]) : "", cls: sw ? sw[1] : ""};
  });
  const groupsOf = html => [...html.matchAll(/<div class="grp"[^>]*>\s*<h3>([^<]*)<\/h3>([\s\S]*?)<\/ul>\s*<\/div>/g)]
    .map(m => ({heading: m[1], rows: rowsOf(m[2]), titles: [...m[2].matchAll(/<title>([^<]*)<\/title>/g)].map(t => t[1])}));
  const std = {target: 2, soft_cap: 4, min: 1, weight: 3};
  const every = {reqs: Object.fromEntries(KEYS.map(k => [k, {...std}])),
                 have: Object.fromEntries(KEYS.map(k => [k, 2.5]))};
  const groups = groupsOf(render(every));
  const allRows = groups.flatMap(g => g.rows);

  check(`supply board renders every shipped requirement (${KEYS.length})`,
        allRows.length === KEYS.length, `rendered ${allRows.length}: ${allRows.map(r => r.cap).join(",")}`);
  const keyed = allRows.filter(r => /_/.test(r.name) || r.name === r.cap);
  check("supply board: every row shows a player name, never an engine key",
        keyed.length === 0, keyed.map(r => `${r.cap} -> "${r.name}"`).join(", "));
  const keyedTitles = groups.flatMap(g => g.titles).filter(t => /\b[a-z]+_[a-z_]+\b/.test(t));
  check("supply board: ring hover text names capabilities, never engine keys",
        keyedTitles.length === 0, keyedTitles.slice(0, 3).join(" | "));
  check("supply board: every shipped requirement sits in a named group (no Other fallback)",
        !groups.some(g => g.heading === "Other"),
        `Other holds: ${(groups.find(g => g.heading === "Other") || {rows: []}).rows.map(r => r.cap).join(",")}`);
  const echo = groups.flatMap(g => g.rows.filter(r => r.name.toLowerCase() === g.heading.toLowerCase())
    .map(r => `${r.cap} "${r.name}" under ${g.heading}`));
  check("supply board: no row repeats its group heading", echo.length === 0, echo.join(", "));

  /* End-to-end supply regression: the SAME party and explicit spell combos
     cross the real JS engine and the real dashboard renderer. Clap expects a
     larger AoE clump than brawl, which changes both effective burst-AoE
     supply and the style-fitted typical shown to the player. Pin the visible
     values: unit-only engine tests or stub-only renderer tests cannot catch a
     broken handoff between these layers. */
  const fixedParty = [
    "2H_HAMMER_AVALON", "2H_LONGBOW", "2H_ICECRYSTAL_UNDEAD",
  ];
  const fixedCombos = [0, 0, 0];
  const styleRow = style => {
    const engine = new CompEngine(DATASET, "castle_outpost", 20, style);
    const html = render({engine, party: fixedParty, combos: fixedCombos});
    return rowsOf(html).find(r => r.cap === "burst_aoe");
  };
  const brawlAoe = styleRow("brawl");
  const clapAoe = styleRow("clap");
  check("supply board: fixed roster renders style-specific brawl/clap AoE supply and typical",
        brawlAoe && clapAoe
        && brawlAoe.val === "5.3 / 20.4"
        && clapAoe.val === "6.3 / 26.4",
        `brawl=${JSON.stringify(brawlAoe)} clap=${JSON.stringify(clapAoe)}`);

  const kpM = DL.match(/const KP_LABEL = \{pierce: "([^"]+)"/);
  if (!kpM) throw new Error("could not extract KP_LABEL.pierce from _decision_layer.js");
  const shred = allRows.find(r => r.cap === "resist_shred") || {name: ""};
  check(`supply board: resist_shred reads "${kpM[1]}", the kill-pressure card's word`,
        shred.name.toLowerCase() === kpM[1].toLowerCase(), `shows "${shred.name}"`);

  /* THE REGRESSION GUARD for the cleanse row that read "6 / 5.6" in amber:
     the shown pair must never contradict the colour. Under typical (red,
     amber) the shown have is never above the shown typical; at or over it
     (green, purple) never below. */
  let bad = null, n = 0;
  for (const t of [0.3, 0.8, 1.2, 1.9, 5.6, 9.9, 15.1, 53.2]){
    for (let h = 0; h <= 2.5 * t + 0.05 && !bad; h += Math.max(0.01, t / 97)){
      const r = rowsOf(render({reqs: {cleanse: {target: t, soft_cap: 2 * t, min: t / 2, weight: 3}},
                               have: {cleanse: h}}))[0];
      const m = r.val.match(/^([\d.]+) \/ ([\d.]+)$/);
      n++;
      if (!m){ bad = `have ${h.toFixed(3)} typical ${t}: value "${r.val}" is not "have / typical"`; break; }
      const [a, b] = [Number(m[1]), Number(m[2])];
      const under = r.cls === "low" || r.cls === "part";
      if ((under && a > b) || (!under && a < b))
        bad = `have ${h.toFixed(3)} typical ${t}: shows "${r.val}" coloured ${r.cls}`;
    }
  }
  check(`supply board: the shown numbers never contradict the colour (${n} cases)`, !bad, bad || "");

  const chips = {reqs: {burst_st: {...std}, engage: {...std}, anti_zone: {...std}, execute: {...std}, peel: {...std}},
                 have: {burst_st: 3, engage: 3, anti_zone: 3, execute: 3, peel: 3},
                 mult: {burst_st: 0.35, engage: 1.4},
                 src: {anti_zone: "content_min", execute: "harvest_borrowed"}};
  const cr = Object.fromEntries(rowsOf(render(chips)).map(r => [r.cap, r]));
  const leaked = Object.values(cr).filter(r => /×\s*\d|\bmin\b|~/.test(r.name));
  check("supply board: style weights and target provenance stay off the visible label",
        leaked.length === 0, leaked.map(r => `${r.cap} "${r.name}"`).join(", "));
  check("supply board: a style that leans on a capability shows an up mark with the weight on hover",
        /▲/.test(cr.engage.name) && /×1\.4|1\.4×|3 → 4\.2/.test(cr.engage.nameHtml),
        `"${cr.engage.name}"`);
  check("supply board: a style that cares less shows a down mark with the weight on hover",
        /▼/.test(cr.burst_st.name) && /0\.35|3 → 1\.1/.test(cr.burst_st.nameHtml),
        `"${cr.burst_st.name}"`);
  check("supply board: an unmarked row shows its name alone", cr.peel.name === "Peel", `"${cr.peel.name}"`);
  /* a narrow column wraps a row's tags below its name instead of pushing
     the value past the panel edge: "Silences" + "overstacked" + "14.8 / 6.0"
     overflowed a 203px column. Wrapping needs a break opportunity (white
     space) before every tag. */
  const tagged = rowsOf(render({reqs: {silence: {...std}, engage: {...std}},
                                have: {silence: 9, engage: 9}, mult: {engage: 1.4}}));
  const glued = tagged.filter(r => /[^\s]<span class="tag/.test(r.nameHtml));
  check("supply board: every tag on a row name can wrap below the name",
        tagged.length === 2 && tagged.every(r => /class="tag/.test(r.nameHtml)) && glued.length === 0,
        glued.map(r => `${r.cap}: ${r.nameHtml}`).join(" | "));
  check("supply board: a floor-only typical says so on hover",
        /floor/i.test(cr.anti_zone.valTitle), `title "${cr.anti_zone.valTitle}"`);
  check("supply board: a borrowed typical says so on hover",
        /borrowed/i.test(cr.execute.valTitle), `title "${cr.execute.valTitle}"`);
}

console.log(`\n${pass}/${pass + fail} display-math tests passed`);
process.exit(fail ? 1 : 0);
