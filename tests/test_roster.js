/* Roster read tests - dashboard/_roster.js.
 *
 * The account modules run together in a vm context with no document, as
 * the page loads them: the pure functions load, and each UI block
 * returns before touching the DOM. The read runs twice: over a stub
 * engine that records every call, so what the module asks the engine
 * and what it hands it are pinned (weapon keys and the build each seat
 * is read in, the CTA's content and style, the held size and one
 * ahead); and over the real engine (engine/app_scoring.js on
 * pipeline/out/dataset-latest.json, the code and data the parity gate
 * runs), so the read's shape holds on the planner's own rules and a
 * forged comp's saved link reads what the planner reads.
 *
 * Pinned: the held party (the slot's weapon, else the claimant's first
 * declared weapon; free slots never), the plan, the context (an unknown
 * content or style falls back), the builds (the saved link's build for a
 * slot still naming its weapon, read as the planner reads it, else the
 * engine's default kit), the needs (floor and needed cuts, a floor on
 * the weapon and spell supply alone), the overstack, the picks one
 * ahead, the replacements, the open slots with the engine's rank, the
 * pool (reserves and members not on the sheet, matched by name whatever
 * its case), the fillers in order, the headline, and that nothing about
 * a player reaches the engine.
 *
 * Run:  node tests/test_roster.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");
const DATASET_PATH = path.join(__dirname, "..", "pipeline", "out", "dataset-latest.json");
const ENGINE_PATH = path.join(__dirname, "..", "engine", "app_scoring.js");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from() { throw new Error("the roster module reaches no table"); },
  rpc() { throw new Error("the roster module calls no function"); },
  channel() { throw new Error("the roster module is not live"); },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js", "_history.js", "_import.js", "_roster.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

const CATALOG = {
  MAIN_HOLYSTAFF_AVALON: { name: "Hallowfall", role: "healer", item: "" },
  MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
  "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" },
  "2H_ARCANESTAFF": { name: "Great Arcane Staff", role: "support", item: "" },
  "2H_HAMMER": { name: "Great Hammer", role: "frontline", item: "" },
};

/* the sheet as event_by_code answers it */
const EVENT = { content: "castle", style: "clap", planned_size: 8, status: "open" };
const SLOTS = [
  { position: 1, weapon_id: "MAIN_MACE_HELL", role: "tank" }, { position: 2, weapon_id: "MAIN_HOLYSTAFF_AVALON", role: "healer" },
  { position: 3, weapon_id: null, role: "flex" }, { position: 4, weapon_id: "2H_LONGBOW" }, { position: 5, weapon_id: "2H_ARCANESTAFF" },
  { position: 6, weapon_id: "2H_LONGBOW" },
];
const SIGNUPS = [
  { id: "a", position: 1, player_name: "Disc", weapons: ["MAIN_MACE_HELL"], can_swap: false, account: true, created_at: "1" },
  { id: "b", position: 3, player_name: "Gus", weapons: ["2H_HAMMER", "2H_LONGBOW"], can_swap: true, account: false, created_at: "2" },
  { id: "c", position: 4, player_name: "Eff", weapons: [], can_swap: false, account: true, created_at: "3" },
  { id: "d", position: null, player_name: "Res", weapons: ["MAIN_HOLYSTAFF_AVALON"], can_swap: false, account: true, created_at: "4" },
  { id: "e", position: null, player_name: "Wye", weapons: [], can_swap: true, account: false, created_at: "5" },
];
const board = run("sheetBoard")(SLOTS, SIGNUPS);

/* a stub engine recording what it is asked: each call's party, combos
   and gears (a list per seat); the default kit of a weapon is
   KIT_<weapon>, and the supply read without gears is half the dressed
   supply, so the floor basis shows */
function stubEngine() {
  const calls = [];
  const copy = a => (a ? a.map(x => (Array.isArray(x) ? x.slice() : x)) : a);
  const eng = {
    data: { templates: { castle: {}, territory_defense: {} }, styles: { balanced: {}, clap: {} } },
    reqs: { tankiness: { weight: 6 }, heal_sustain: { weight: 7 }, burst_aoe: { weight: 5 }, mobility: { weight: 2 } },
    gear: { HEAD_PLATE_SET2: {}, ARMOR_CLOTH_SET1: {}, OFF_SHIELD: {} },
    size: 0, content: null, style: null,
    setContent(content, size, style) { calls.push(["setContent", content, size, style]); this.content = content; this.size = size; this.style = style; },
    kitVariants(w) { return [["v0", ["KIT_" + w]]]; },
    comboFromPicks(w, picks) { calls.push(["comboFromPicks", w, Object.assign({}, picks)]); return 7; },
    fitness(party, combos, gears) { calls.push(["fitness", party.slice(), copy(combos), copy(gears)]); return party.length * 2; },
    maxFitness(party, combos, gears) { calls.push(["maxFitness", party.slice(), copy(combos), copy(gears)]); return 10; },
    effectiveSupply(party, combos, gears) {
      calls.push(["effectiveSupply", party.slice(), copy(combos), copy(gears)]);
      const k = gears ? 1 : 0.5;
      return { tankiness: 1.5 * k, heal_sustain: 0.5 * k, burst_aoe: 9 * k, mobility: 3 * k };
    },
    weaknesses(party, n, combos, gears) { calls.push(["weaknesses", party.slice(), copy(combos), copy(gears), n]); return [{ cap: "heal_sustain", gap: 5.2, have: 0.5, target: 4 }, { cap: "tankiness", gap: 2.1, have: 1.5, target: 3.3 }, { cap: "mobility", gap: 0.2, have: 3, target: 3.1 }]; },
    floorArmed(cap, have) { calls.push(["floorArmed", cap, have]); return cap === "heal_sustain"; },
    weight(cap) { return this.reqs[cap].weight; },
    softCap(cap) { return { tankiness: 7, heal_sustain: 6, burst_aoe: 8, mobility: 5 }[cap]; },
    duplicateConflicts(party, combos) { calls.push(["duplicateConflicts", party.slice(), copy(combos)]); return [{ severity: "warning", reason: "Sunder: counts once", weapons: ["2H_LONGBOW", "2H_LONGBOW"], confidence: "verified" }]; },
    swapReview(party, n, pool, combos, gears) { calls.push(["swapReview", party.slice(), copy(combos), copy(gears), n, pool]); return party.map((w, i) => ({ index: i, weapon: w, rank: i === 2 ? 3 : 1, redundant: i === 2, verdict: i === 2 ? "redundant" : "ok", off_comp: false, off_style: false, options: i === 2 ? [{ weapon: "MAIN_HOLYSTAFF_AVALON", gain: 1.25 }, { weapon: "2H_ARCANESTAFF", gain: 0.4 }] : [] })); },
    recommend(party, n, pool, combos, gears) { calls.push(["recommend", party.slice(), copy(combos), copy(gears), n, this.size, pool]); return [{ weapon: "MAIN_HOLYSTAFF_AVALON", score: 3.1, verdict: "ok", caps_gain: 2 }, { weapon: "2H_ARCANESTAFF", score: 1.2, verdict: "redundant", caps_gain: 0 }]; },
  };
  return { eng, calls };
}

(async () => {

/* 1 - the held party and the plan */
{
  const held = run("heldParty")(board);
  check("the held party is the slot's weapon for each held slot, the claimant's first declared weapon for a slot naming none; free slots never",
        same(held.party, ["MAIN_MACE_HELL", "2H_HAMMER", "2H_LONGBOW"])
        && same(held.seats.map(s => `${s.position}:${s.source}:${s.player}`), ["1:slot:Disc", "3:declared:Gus", "4:slot:Eff"]), held);
  check("the plan is every slot's weapon", same(run("plannedParty")(board), ["MAIN_MACE_HELL", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW", "2H_ARCANESTAFF", "2H_LONGBOW"]));
  const emptyHeld = run("heldParty")(run("sheetBoard")([{ position: 1, weapon_id: null }], [{ id: "x", position: 1, player_name: "Nil", weapons: [] }]));
  check("a held slot with no weapon either way is not in the party", emptyHeld.party.length === 0);
  const ctxOf = run("rosterContext");
  const data = { templates: { castle: {}, roads: {} }, styles: { balanced: {}, clap: {} } };
  check("the context is the CTA's content and style when the dataset has them, else the first template and balanced",
        same(ctxOf({ content: "castle", style: "clap" }, data), { content: "castle", style: "clap", known: true })
        && same(ctxOf({ content: "narnia", style: "yolo" }, data), { content: "castle", style: "balanced", known: false })
        && same(ctxOf(null, data), { content: "castle", style: "balanced", known: false }));
}

/* 2 - the read over the stub engine: what the engine is asked, and what it is handed */
{
  const { eng, calls } = stubEngine();
  const read = run("rosterRead")(EVENT, board, eng);
  const setCalls = calls.filter(c => c[0] === "setContent").map(c => c.slice(1).join("/"));
  check("the engine is set to the CTA's content and style at the held size, one ahead for the picks, the plan's size for the plan, and left at the held size",
        same(setCalls, ["castle/3/clap", "castle/4/clap", "castle/5/clap", "castle/3/clap"]), setCalls);
  const handed = calls.filter(c => Array.isArray(c[1])).map(c => c[1]);
  check("every party the engine is handed is weapon keys: no player, no declaration beyond a weapon key, no attendance",
        handed.length > 0 && handed.every(p => p.every(k => typeof k === "string" && /^[A-Z0-9_]+$/.test(k))), handed);
  /* no saved link: every seat in the engine's default kit, on the default spells */
  const heldKits = ["MAIN_MACE_HELL", "2H_HAMMER", "2H_LONGBOW"].map(w => ["KIT_" + w]);
  const heldCalls = calls.filter(c => ["fitness", "maxFitness", "weaknesses", "swapReview", "recommend"].includes(c[0]) && c[1].length === 3);
  check("every held read and the picks one ahead hand the engine the seats' builds: the default kit per weapon with no link saved",
        heldCalls.length === 5 && heldCalls.every(c => same(c[3], heldKits) && same(c[2], [null, null, null])), heldCalls.map(c => c[0] + ":" + JSON.stringify(c[3])));
  const dup = calls.find(c => c[0] === "duplicateConflicts");
  check("the duplicate checks read the seats' spells", dup && same(dup[2], [null, null, null]), dup);
  const planCall = calls.find(c => c[0] === "fitness" && c[1].length === 5);
  check("the plan is read in its own seats' builds",
        planCall && same(planCall[3], ["MAIN_MACE_HELL", "MAIN_HOLYSTAFF_AVALON", "2H_LONGBOW", "2H_ARCANESTAFF", "2H_LONGBOW"].map(w => ["KIT_" + w])), planCall);
  const floors = calls.filter(c => c[0] === "floorArmed" && c[1] === "heal_sustain").map(c => c[2]);
  check("a hard floor reads the weapon and spell supply alone (worn gear never buys floor relief); the need shows the dressed supply",
        floors.length > 0 && floors.every(v => v === 0.25) && read.needs[0].have === 0.5, { floors, have: read.needs[0].have });
  check("the read says every held slot reads the engine's default kit",
        read.held.saved === 0 && /default kit/.test(run("rosterBuildsNote")(read)), run("rosterBuildsNote")(read));
  check("the held read: three held of six, coverage fitness over its ceiling",
        read.held.count === 3 && read.held.fitness === 6 && read.held.max === 10 && read.held.coverage === 0.6 && read.size === 3);
  check("the needs: the planner's gap cut, a hard floor unmet marked, a heavy capability under half marked needed",
        same(read.needs.map(n => `${n.cap}:${n.floor}:${n.needed}`), ["heal_sustain:true:true", "tankiness:false:true"]), read.needs);
  check("the overstack: what sits past its soft cap, most over first", same(read.over.map(o => `${o.cap}:${o.have}:${o.soft}`), ["burst_aoe:9:8"]));
  check("the picks come one ahead with their verdict", same(read.picks.map(p => `${p.rank}:${p.weapon}:${p.verdict}`), ["1:MAIN_HOLYSTAFF_AVALON:ok", "2:2H_ARCANESTAFF:redundant"])
        && calls.find(c => c[0] === "recommend")[5] === 4);
  check("the replacements are the held seats a swap improves, with the seat and the options",
        read.replacements.length === 1 && read.replacements[0].seat.position === 4 && read.replacements[0].weapon === "2H_LONGBOW"
        && same(read.replacements[0].options.map(o => `${o.weapon}:${o.gain}`), ["MAIN_HOLYSTAFF_AVALON:1.25", "2H_ARCANESTAFF:0.4"]), read.replacements);
  check("the duplicate checks ride along", read.duplicates.length === 1 && read.duplicates[0].severity === "warning");
  check("the plan is read beside the held roster when it is bigger", read.plan && read.plan.count === 5 && read.plan.coverage === 1 && read.plan.needs.length === 2);
  check("the labels are the planner's words when the page has them, else the key spelled out",
        run("rosterCapLabel")("heal_sustain") === "Heal sustain" && read.needs[0].label === "Heal sustain");
  ctx.CAP_LABEL = { heal_sustain: "Sustain healing" };
  check("with the planner's table the label is its short title", run("rosterCapLabel")("heal_sustain") === "Sustain healing" && run("rosterCapLabel")("burst_aoe") === "Burst aoe");
  delete ctx.CAP_LABEL;

  const empty = run("rosterRead")(EVENT, run("sheetBoard")(SLOTS, []), eng);
  check("nothing held: coverage zero, the picks still one ahead of an empty party, the plan beside it",
        empty.held.count === 0 && empty.held.coverage === 0 && empty.picks.length === 2 && empty.plan.count === 5 && empty.replacements.length === 0 && empty.duplicates.length === 0);
  check("a dataset without templates gives no read", run("rosterRead")(EVENT, board, Object.assign({}, eng, { data: { templates: {} } })) === null);
}

/* 2b - the saved link's builds, through a codec standing in for the planner's */
{
  const { eng, calls } = stubEngine();
  const slots = [
    { position: 1, weapon_id: "MAIN_MACE_HELL" }, { position: 2, weapon_id: "2H_HAMMER" }, { position: 3, weapon_id: "2H_LONGBOW" },
    { position: 4, weapon_id: null }, { position: 5, weapon_id: "2H_ARCANESTAFF" },
  ];
  const signups = [1, 2, 3, 4, 5].map(p => ({ id: `b${p}`, position: p, player_name: `B${p}`, weapons: p === 4 ? ["MAIN_HOLYSTAFF_AVALON"] : [],
                                               can_swap: false, account: true, created_at: String(p) }));
  const saved = [
    { head: "HEAD_PLATE_SET2", armor: "ARMOR_CLOTH_SET1", cape: "CAPE_NOT_CURATED", offhand: "OFF_SHIELD", q: 1 },
    { armor: "ARMOR_CLOTH_SET1", offhand: "OFF_SHIELD" },
    { head: "HEAD_PLATE_SET2" },
    { head: "HEAD_PLATE_SET2" },
  ];
  const tables = {
    loadout: s => (s === "G" ? saved.slice() : []),
    combo: (s, n) => (s === "K" ? [null, 3, null, null, null] : []).slice(0, n),
    spells: { MAIN_MACE_HELL: { q: [["SPELL_A", "A"], ["SPELL_B", "B"]], w: [], passive: [] } },
  };
  const event = { content: "castle", style: "clap", share_hash: "c=castle&n=5&p=MAIN_MACE_HELL,2H_HAMMER,2H_ARCANESTAFF,MAIN_HOLYSTAFF_AVALON,2H_ARCANESTAFF&g=G&k=K" };
  const read = run("rosterRead")(event, run("sheetBoard")(slots, signups), eng, tables);
  const fit = calls.find(c => c[0] === "fitness" && c[1].length === 5);
  check("a slot still naming the saved member's weapon reads its saved build: curated pieces in the codec's order, the picked spells",
        fit && same(fit[3][0], ["HEAD_PLATE_SET2", "ARMOR_CLOTH_SET1", "OFF_SHIELD"]) && fit[2][0] === 7
        && same(calls.find(c => c[0] === "comboFromPicks"), ["comboFromPicks", "MAIN_MACE_HELL", { q: "SPELL_B" }]), fit && { combos: fit[2], gears: fit[3] });
  check("a saved combo wins over the picks, and a two-handed weapon's saved off-hand is left out, as the planner reads the link",
        fit && same(fit[3][1], ["ARMOR_CLOTH_SET1"]) && fit[2][1] === 3);
  check("a slot whose weapon changed, a slot naming none (its player's declared weapon) and a slot with no build saved read the default kit",
        fit && same(fit[3].slice(2), [["KIT_2H_LONGBOW"], ["KIT_MAIN_HOLYSTAFF_AVALON"], ["KIT_2H_ARCANESTAFF"]]) && same(fit[2].slice(2), [null, null, null]));
  check("the read counts the slots read in a saved build, and says so",
        read.held.saved === 2 && /^2 held slots are read in the build the CTA's comp saved, 3 in the engine's default kit/.test(run("rosterBuildsNote")(read)),
        run("rosterBuildsNote")(read));
  const none = stubEngine();
  run("rosterRead")(event, run("sheetBoard")(slots, signups), none.eng);
  const bare = none.calls.find(c => c[0] === "fitness" && c[1].length === 5);
  check("without the codec every seat reads the default kit", bare && bare[3].every((g, i) => g && /^KIT_/.test(g[0])), bare && bare[3]);
  const note = run("rosterBuildsNote");
  check("the builds line: every held slot saved, one held slot, nothing held",
        note({ held: { count: 3, saved: 3 } }) === "Every held slot is read in the build the CTA's comp saved for it."
        && note({ held: { count: 1, saved: 0 } }) === "The held slot is read in the engine's default kit for its weapon (no build saved for it, or its weapon changed)."
        && note({ held: { count: 0, saved: 0 } }) === "");
}

/* 3 - the open slots, the pool and the fillers */
{
  const picks = [{ rank: 1, weapon: "MAIN_HOLYSTAFF_AVALON" }, { rank: 2, weapon: "2H_ARCANESTAFF" }];
  const free = run("openSlots")(board, picks);
  check("the open slots are the free ones of the plan, each with the engine's rank when its weapon is a pick",
        same(free.map(f => `${f.position}:${f.weapon}:${f.pickRank}`), ["2:MAIN_HOLYSTAFF_AVALON:1", "5:2H_ARCANESTAFF:2", "6:2H_LONGBOW:null"]), free);
  const members = [
    { name: "Disc", albion: "Disc", lists: { main: ["MAIN_MACE_HELL"], secondary: [] } },
    { name: "Healer Hal", albion: "hal", lists: { main: ["MAIN_HOLYSTAFF_AVALON"], secondary: ["2H_ARCANESTAFF"] } },
    { name: "Arc", albion: "ARC", lists: { main: ["2H_ARCANESTAFF"], secondary: ["MAIN_HOLYSTAFF_AVALON"] } },
    { name: "res", albion: "RES", lists: { main: ["2H_LONGBOW"], secondary: [] } },
  ];
  const pool = run("rosterPool")(board, members);
  check("the pool: the reserves with their declarations, and the members not on the sheet by name whatever its case",
        same(pool.reserves.map(r => `${r.name}:${r.declared.join("+")}:${r.swap}`), ["Res:MAIN_HOLYSTAFF_AVALON:false", "Wye::true"])
        && same(pool.others.map(m => m.name), ["Healer Hal", "Arc"]), pool);
  const fillers = run("fillersFor");
  check("who can bring a weapon: declared reserves, members by main, then can-also-play, then reserves who can swap",
        same(fillers("MAIN_HOLYSTAFF_AVALON", pool).map(f => `${f.name}:${f.how}`), ["Res:declared", "Healer Hal:main", "Arc:secondary", "Wye:swap"])
        && same(fillers("2H_ARCANESTAFF", pool).map(f => `${f.name}:${f.how}`), ["Arc:main", "Healer Hal:secondary", "Wye:swap"])
        && fillers(null, pool).length === 0 && fillers("2H_HAMMER", { reserves: [], others: [] }).length === 0);
  const many = { reserves: [], others: Array.from({ length: 9 }, (_, i) => ({ name: `M${i}`, main: ["2H_LONGBOW"], secondary: [] })) };
  check("the fillers are bounded", fillers("2H_LONGBOW", many).length === run("ROSTER_FILLERS"));
}

/* 3b - what a read is of */
{
  const key = run("rosterKey");
  const a = key(EVENT, board);
  const moved = run("sheetBoard")(SLOTS, SIGNUPS.map(s => Object.assign({}, s, { attendance: "confirmed", note: "moved" })));
  check("a mark or a note changes the sheet, not the key: the read is reused", key(EVENT, moved) === a);
  const other = run("sheetBoard")(SLOTS, SIGNUPS.filter(s => s.id !== "c"));
  check("a claim gone changes the held party and the key", key(EVENT, other) !== a);
  check("another content or style is another key", key(Object.assign({}, EVENT, { style: "balanced" }), board) !== a);
  check("a CTA saved again with other builds is another key", key(Object.assign({}, EVENT, { share_hash: "c=castle&p=2H_LONGBOW&g=x" }), board) !== a);
}

/* 4 - the headline */
{
  const headline = run("rosterHeadline");
  const read = { held: { count: 3, coverage: 0.61 }, needs: [{ cap: "mobility", label: "Mobility", needed: false }, { cap: "heal_sustain", label: "Sustain healing", needed: true }],
                 picks: [{ weapon: "MAIN_HOLYSTAFF_AVALON" }], plan: null };
  check("the headline: held of slots, coverage, the first needed gap, the first pick",
        headline(read, board, CATALOG) === "3 of 6 slots held · coverage 61% · biggest need Sustain healing · next pick Hallowfall");
  check("nothing held: the plan's coverage and the first pick",
        headline({ held: { count: 0, coverage: 0 }, needs: [], picks: [{ weapon: "2H_LONGBOW" }], plan: { coverage: 0.8 } }, board, CATALOG) === "no one in a slot yet · the plan covers 80% · first pick Longbow");
  check("a percent reads whole and bounded", run("rosterPct")(0.615) === "62%" && run("rosterPct")(1.4) === "100%" && run("rosterPct")(null) === "0%");
  check("the verdicts and the filler words are named through one map each", run("ROSTER_VERDICTS").ok === "closes a gap" && run("ROSTER_FILLER_HOW").secondary === "can also play");
  check("the definitions say the sheet's people are never scored, and which build a slot is read in",
        /never scored/.test(run("ROSTER_DEFINITIONS")) && /saved for its slot, else in the engine's default kit/.test(run("ROSTER_DEFINITIONS")));
}

/* 5 - the real engine on the dataset: the read's shape on the planner's rules */
{
  const CompEngine = require(ENGINE_PATH);
  const dataset = JSON.parse(fs.readFileSync(DATASET_PATH, "utf8"));
  const eng = new CompEngine(dataset, Object.keys(dataset.templates)[0]);
  const realSlots = [
    { position: 1, weapon_id: "2H_HAMMER_AVALON" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: "2H_LONGBOW" },
    { position: 4, weapon_id: "MAIN_HOLYSTAFF_AVALON" }, { position: 5, weapon_id: "2H_ARCANESTAFF" }, { position: 6, weapon_id: "2H_LONGBOW" },
    { position: 7, weapon_id: "2H_LONGBOW" }, { position: 8, weapon_id: "MAIN_HOLYSTAFF_AVALON" },
  ];
  const realSignups = [1, 2, 3, 4].map(p => ({ id: `s${p}`, position: p, player_name: `P${p}`, weapons: [], can_swap: false, account: true, created_at: String(p) }));
  const realBoard = run("sheetBoard")(realSlots, realSignups);
  const t0 = Date.now();
  const read = run("rosterRead")({ content: "castle", style: "clap", planned_size: 8, status: "open" }, realBoard, eng);
  const ms = Date.now() - t0;
  const known = key => !!dataset.weapons[key];
  check("the real read: four held at castle clap, coverage between 0 and 1, the engine left at the held size",
        read && read.held.count === 4 && read.held.coverage > 0 && read.held.coverage < 1 && eng.size === 4 && eng.content === "castle" && eng.style === "clap", read && read.held);
  check("the needs are template capabilities with have below target, the labels spelled", read.needs.length > 0 && read.needs.every(n => eng.reqs[n.cap] && n.have < n.target && /^[A-Z]/.test(n.label)), read.needs);
  check("the picks are catalog weapons, at most ROSTER_PICKS, with a listed verdict", read.picks.length > 0 && read.picks.length <= run("ROSTER_PICKS") && read.picks.every(p => known(p.weapon) && ["ok", "redundant", "negative"].includes(p.verdict)), read.picks);
  check("the plan of eight is read beside the four held", read.plan && read.plan.count === 8 && read.plan.coverage > read.held.coverage - 1e-9, read.plan);
  check("the replacements name held seats and catalog weapons", read.replacements.every(r => r.seat && known(r.weapon) && r.options.every(o => known(o.weapon))), read.replacements);
  check("the overstack rows are template capabilities past their soft cap", read.over.every(o => eng.reqs[o.cap] && o.have > o.soft), read.over);
  check("a read takes well under a second", ms < 1000, ms);
  const bare = run("rosterRead")({ content: "castle", style: "balanced" }, run("sheetBoard")(realSlots, []), eng);
  check("nothing held on the real engine: a first pick, the plan's read, no replacement", bare.held.count === 0 && bare.picks.length > 0 && bare.plan.count === 8 && bare.replacements.length === 0);
  /* a key the dataset does not hold, on a slot or as a player's own
     declaration, is left out and named: one such key used to throw inside
     the engine and hide the whole read */
  const oddSlots = realSlots.map(s => s.position === 3 ? { position: 3, weapon_id: "2H_RETIRED_STAFF" } : s)
    .concat([{ position: 9, weapon_id: null }]);
  const oddSignups = realSignups.concat([{ id: "s9", position: 9, player_name: "Guest", weapons: ["NOT_A_WEAPON"], can_swap: false, account: false, created_at: "9" }]);
  let odd = null, oddErr = null;
  try { odd = run("rosterRead")({ content: "castle", style: "clap", planned_size: 9, status: "open" }, run("sheetBoard")(oddSlots, oddSignups), eng); }
  catch (e) { oddErr = e; }
  check("unknown weapon keys are left out of the read and named, never stopping it",
        !oddErr && odd && odd.held.count === 3 && same(odd.unknown, ["2H_RETIRED_STAFF", "NOT_A_WEAPON"])
        && odd.held.seats.every(s => known(s.weapon)) && odd.plan && odd.plan.count === 7, oddErr ? String(oddErr) : odd && { held: odd.held.count, unknown: odd.unknown, plan: odd.plan && odd.plan.count });
  check("a read with every key known names none", same(read.unknown, []));

  /* a forged comp of 20: read naked it fell short of the person-unit
     targets (Tankiness "needed" at a sixth of its target on a comp the
     planner reads as covered); read in its builds it reads what the
     planner reads. The saved link is written by the planner's own codec. */
  const codecCtx = { GEAR: JSON.parse(fs.readFileSync(path.join(__dirname, "..", "pipeline", "out", "gear_lines.json"), "utf8")),
                     ICONS: {}, SPELLS: {}, LOADOUTS: {}, CONTENT: "blackzone_roam", party: [], esc: s => String(s), console };
  vm.createContext(codecCtx);
  vm.runInContext(fs.readFileSync(path.join(DASH, "_loadout.js"), "utf8"), codecCtx, { filename: "_loadout.js" });
  const codec = { loadout: codecCtx.loadoutDecode, combo: codecCtx.comboDecode, spells: {} };
  const fe = new CompEngine(dataset, "blackzone_roam");
  fe.setContent("blackzone_roam", 20, "clap");
  const forged = fe.forge(20, []);
  const fEvent = { content: "blackzone_roam", style: "clap", planned_size: 20, status: "open" };
  const fSlots = forged.party.map((w, i) => ({ position: i + 1, weapon_id: w }));
  const fSignups = forged.party.map((w, i) => ({ id: `f${i}`, position: i + 1, player_name: `F${i}`, weapons: [], can_swap: false, account: true, created_at: String(i) }));
  const fBoard = run("sheetBoard")(fSlots, fSignups);
  const neededOf = r => r.needs.filter(n => n.needed).map(n => n.cap);
  const naked = run("rosterNeeds")(fe, forged.party, 8).filter(n => n.needed).map(n => n.cap);
  check("read naked, the forged Blackzone Roam 20 clap lacks tankiness (the person-unit gap the builds close)",
        forged.party.length === 20 && naked.includes("tankiness"), naked);
  const plain = run("rosterRead")(fEvent, fBoard, eng, codec);
  const kits = forged.party.map(w => { const v = eng.kitVariants(w)[0]; return v && v[1] ? v[1].slice() : null; });
  check("with no link saved every slot reads the engine's default kit: no tankiness need, the fitness of those kits",
        plain.held.saved === 0 && !neededOf(plain).includes("tankiness")
        && Math.abs(plain.held.fitness - eng.fitness(forged.party, forged.party.map(() => null), kits)) < 1e-9,
        { needed: neededOf(plain), fitness: plain.held.fitness });
  const kitsAsSaved = (forged.gears || []).map(g => {
    const L = {};
    for (const key of g || []) if (codecCtx.GEAR[key]) L[codecCtx.GEAR[key].slot] = key;
    return L;
  });
  const share = `c=blackzone_roam&n=20&st=clap&p=${forged.party.join(",")}`
    + `&g=${codecCtx.loadoutEncode(forged.party, kitsAsSaved)}&k=${codecCtx.comboEncode(forged.combos, forged.party.length)}`;
  const savedRead = run("rosterRead")(Object.assign({}, fEvent, { share_hash: share }), fBoard, eng, codec);
  const plannerFit = eng.fitness(forged.party, forged.combos, forged.gears);
  check("the forge's saved link reads what the planner reads: every slot in its saved build, the planner's fitness, no tankiness need",
        savedRead.held.saved === 20 && Math.abs(savedRead.held.fitness - plannerFit) < 1e-9 && !neededOf(savedRead).includes("tankiness"),
        { saved: savedRead.held.saved, fitness: savedRead.held.fitness, plannerFit, needed: neededOf(savedRead) });
  const swapped = forged.party.find(w => w !== forged.party[0]);
  const changed = run("rosterRead")(Object.assign({}, fEvent, { share_hash: share }),
                                    run("sheetBoard")(fSlots.map(s => s.position === 1 ? { position: 1, weapon_id: swapped } : s), fSignups), eng, codec);
  check("a slot whose weapon changed after the save reads the default kit; the others keep their saved builds",
        changed.held.saved === 19, changed.held.saved);

  const src = fs.readFileSync(path.join(DASH, "_roster.js"), "utf8");
  check("the module makes its own engine over DATASET and never reads the planner's instance or state",
        /new CompEngine\(DATASET/.test(src) && !/\bENG\b|\brender\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT|location\.hash|COMBOS_CUR|GEARS_CUR/.test(src));
  check("the module reaches no table and no channel: members come through the guild module's helpers",
        !/window\.DB|\.from\(|\.rpc\(|\.channel\(/.test(src) && /loadGuildMembers\(/.test(src) && /loadMembersWeapons\(/.test(src) && /memberRows\(/.test(src));
  check("the sheet hands the roster over as a DOM event and never touches the read's elements",
        /addEventListener\("sheet-read"/.test(src) && /dispatchEvent\(new CustomEvent\("sheet-read"/.test(fs.readFileSync(path.join(DASH, "_signup.js"), "utf8"))
        && !/rr-/.test(fs.readFileSync(path.join(DASH, "_signup.js"), "utf8")));
}

console.log(`\n${pass}/${pass + fail} roster read tests passed`);
process.exit(fail ? 1 : 0);
})();
