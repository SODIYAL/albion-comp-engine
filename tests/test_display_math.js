/* Killboard display-math tests — usageBucket / cohortContext / cohortAffinity
 * in dashboard/_app.js.
 *
 * These three functions are the one display-layer computation that does NOT
 * "show its own mistakes" on screen (the codec-test rationale): a wrong
 * bucket or a wrong lift renders as a plausible strip, and exactly that
 * shipped once — the strip keyed off the judged roster size, so a 20-man
 * plan quoted small-gank cohorts and the affinity surface stayed invisible
 * for the whole planning phase (fixed 2026-08-22, usageBucket -> PLAN()).
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
        && okCtx && okCtx.key === "large" && okCtx.rows.length === 11,
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

/* 14 — observed effect quotas (increment 3b, owner-ruled 2026-08-26):
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

console.log(`\n${pass}/${pass + fail} display-math tests passed`);
process.exit(fail ? 1 : 0);
