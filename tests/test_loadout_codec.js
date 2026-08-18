/* Loadout permalink codec — round-trip tests for dashboard/_loadout.js.
 *
 * The codec is the one part of the loadout layer that OUTLIVES a session: a
 * shared link decoded wrongly silently hands someone a different comp than
 * the one that was sent. Everything else in that file is redrawn from state
 * every render and shows its own mistakes.
 *
 * _loadout.js is inlined into a page, not a module, so it is evaluated here
 * in a vm context with the page globals it reads stubbed out.
 *
 * Run:  node tests/test_loadout_codec.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");
const SRC = path.join(ROOT, "dashboard", "_loadout.js");
const GEAR_LINES = path.join(ROOT, "pipeline", "out", "gear_lines.json");

/* Real catalogue when it is built, a small stub otherwise, so the test runs
   on a fresh checkout. Keys deliberately include underscores — the record
   separator must not collide with them. */
let GEAR;
if (fs.existsSync(GEAR_LINES)) {
  GEAR = JSON.parse(fs.readFileSync(GEAR_LINES, "utf8"));
} else {
  GEAR = {
    HEAD_PLATE_SET2: {slot: "head", name: "Knight Helmet"},
    ARMOR_PLATE_KEEPER: {slot: "armor", name: "Judicator Armor"},
    SHOES_LEATHER_MORGANA: {slot: "shoes", name: "Stalker Shoes"},
    CAPEITEM_SMUGGLER: {slot: "cape", name: "Smuggler Cape"},
    OFF_SHIELD: {slot: "offhand", name: "Shield"},
    T5_POTION_REVIVE: {slot: "potion", name: "Gigantify Potion"},
    T7_MEAL_OMELETTE_AVALON: {slot: "food", name: "Avalonian Pork Omelette"},
  };
}

const ctx = {
  GEAR, ICONS: {}, SPELLS: {}, LOADOUTS: {}, CONTENT: "blackzone_roam",
  party: [], esc: s => String(s), console,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(SRC, "utf8"), ctx, {filename: "_loadout.js"});

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail ? "\n      " + detail : ""}`); }
}

/* Encode/decode against a given party size. `party` is read by loadoutEncode
   to know how many records to emit. */
function roundTrip(partyArr, loadout) {
  ctx.party = partyArr;
  /* LOADOUT is a `let` in the script, so it lives in the context's LEXICAL
     scope — assigning ctx.LOADOUT would create an unrelated global the script
     never reads. Assign it from inside instead. */
  ctx.__lo = loadout;
  vm.runInContext("LOADOUT = __lo;", ctx);
  const enc = vm.runInContext("loadoutEncode()", ctx);
  const dec = vm.runInContext(`loadoutDecode(${JSON.stringify(enc)})`, ctx);
  return {enc, dec};
}

/* Compare only the fields the codec claims to carry, treating an absent
   member and an empty object as the same thing. */
function sameLoadout(a, b, n) {
  for (let i = 0; i < n; i++) {
    const x = a[i] || {}, y = b[i] || {};
    const keys = new Set(Object.keys(x).concat(Object.keys(y)));
    for (const k of keys) if (x[k] !== y[k]) return `slot ${i} field ${k}: ${x[k]} vs ${y[k]}`;
  }
  return null;
}

const someKey = slot => Object.keys(GEAR).find(k => GEAR[k].slot === slot);

/* 1 — nothing set encodes to nothing, so a plain comp's link is unchanged */
{
  const {enc, dec} = roundTrip(["2H_MACE", "2H_HOLYSTAFF"], []);
  check("empty loadouts encode to an empty string", enc === "", `got ${JSON.stringify(enc)}`);
  check("empty string decodes to an empty array", dec.length === 0);
}

/* 2 — a full loadout survives intact */
{
  const full = {
    head: someKey("head"), armor: someKey("armor"), shoes: someKey("shoes"),
    cape: someKey("cape"), offhand: someKey("offhand"),
    potion: someKey("potion"), food: someKey("food"),
    q: 2, w: 0, p: 3,
  };
  const {enc, dec} = roundTrip(["2H_MACE"], [full]);
  check("full loadout round-trips", sameLoadout([full], dec, 1) === null,
        sameLoadout([full], dec, 1));
  check("keys with underscores survive the separators",
        !!dec[0] && dec[0].head === full.head && dec[0].armor === full.armor,
        `enc=${enc}`);
  check("spell index 0 is preserved, not dropped as falsy",
        !!dec[0] && dec[0].w === 0, `w decoded as ${dec[0] && dec[0].w}`);
}

/* 3 — gaps and trailing empties */
{
  const lo = [];
  lo[0] = {head: someKey("head"), q: 1};
  lo[2] = {food: someKey("food")};
  const {enc, dec} = roundTrip(["a", "b", "c", "d", "e"], lo);
  check("sparse loadouts round-trip", sameLoadout(lo, dec, 5) === null,
        sameLoadout(lo, dec, 5));
  check("trailing empty members are not encoded", !enc.endsWith("!"), `enc=${enc}`);
}

/* 4 — the dictionary holds real keys, so a stale link degrades safely rather
   than silently resolving to whatever now sits at that index */
{
  const dec = vm.runInContext(
    'loadoutDecode("NOT_A_REAL_ITEM,' + someKey("head") + '~0.-.-.-.-.-.-.-.-.-!1.-.-.-.-.-.-.-.-.-")', ctx);
  check("unknown catalogue key is dropped, not rendered",
        !(dec[0] && dec[0].head), `got ${JSON.stringify(dec[0])}`);
  check("a known key alongside it still decodes",
        dec[1] && dec[1].head === someKey("head"), `got ${JSON.stringify(dec[1])}`);
}

/* 5 — junk must never throw; a bad link should lose gear, not break the page */
{
  let threw = null;
  for (const junk of ["", "~", "abc", "~!!!", "A,B~zz.zz", "x~0.0.0.0.0.0.0.0.0.0"]) {
    try { vm.runInContext(`loadoutDecode(${JSON.stringify(junk)})`, ctx); }
    catch (e) { threw = `${junk}: ${e.message}`; break; }
  }
  check("malformed input decodes without throwing", threw === null, threw);
}

/* 6 — a 20-man sharing a few gear sets stays a sane URL length */
{
  const set = {
    head: someKey("head"), armor: someKey("armor"), shoes: someKey("shoes"),
    cape: someKey("cape"), potion: someKey("potion"), food: someKey("food"),
    q: 1, w: 2, p: 0,
  };
  const lo = Array.from({length: 20}, () => Object.assign({}, set));
  const {enc, dec} = roundTrip(Array(20).fill("2H_MACE"), lo);
  check("20-man round-trips", sameLoadout(lo, dec, 20) === null, sameLoadout(lo, dec, 20));
  check(`20-man encodes compactly (${enc.length} chars)`, enc.length < 700,
        `${enc.length} chars`);
}

/* 7 — provenance codec (2026-08-18): forged-slot flags survive the permalink;
   pre-provenance links decode to all-manual */
{
  const enc = vm.runInContext('provEncode(["m","f","f","m","m"], 5)', ctx);
  check("provenance encodes with trailing manuals trimmed", enc === "mff", `got ${JSON.stringify(enc)}`);
  const dec = vm.runInContext('provDecode("mff", 5)', ctx);
  check("provenance decodes and pads to party size",
        JSON.stringify(dec) === JSON.stringify(["m", "f", "f", "m", "m"]),
        JSON.stringify(dec));
  const legacy = vm.runInContext('provDecode("", 3)', ctx);
  check("a pre-provenance link decodes to all-manual",
        JSON.stringify(legacy) === JSON.stringify(["m", "m", "m"]), JSON.stringify(legacy));
  const junk = vm.runInContext('provDecode("zzz!@#", 4)', ctx);
  check("junk provenance degrades to manual, never throws",
        JSON.stringify(junk) === JSON.stringify(["m", "m", "m", "m"]), JSON.stringify(junk));
}

/* 8 — spell picks -> engine picks map (the scoring bridge) */
{
  ctx.__spells = { CURSED: { q: [["QA", "Q first"], ["QB", "Q second"]],
                             w: [["WA", "W first"]],
                             passive: [["PA", "P first"], ["PB", "P second"]] } };
  vm.runInContext("SPELLS = __spells;", ctx);
  ctx.party = ["CURSED"];
  ctx.__lo = [{q: 1, p: 0}];
  vm.runInContext("LOADOUT = __lo;", ctx);
  const picks = vm.runInContext("loadoutPicks(0)", ctx);
  check("picks map slot indices to spell ids for the engine",
        picks && picks.q === "QB" && picks.passive === "PA" && !("w" in picks),
        JSON.stringify(picks));
  vm.runInContext("LOADOUT = [{}];", ctx);
  const none = vm.runInContext("loadoutPicks(0)", ctx);
  check("a member with no picks yields null (engine default combo)", none === null,
        JSON.stringify(none));
  const oob = (vm.runInContext("LOADOUT = [{q: 99}];", ctx),
               vm.runInContext("loadoutPicks(0)", ctx));
  check("an out-of-pool pick is ignored, not sent as garbage", oob === null,
        JSON.stringify(oob));
}

/* 9 — forged combo -> picker state (what the forge scored is what shows) */
{
  ctx.ENG = { comboSpells: () => [["q", "QB"], ["w", "WA"], ["passive", "PB"], ["e", "EE"]] };
  vm.runInContext("LOADOUT = [{}];", ctx);
  vm.runInContext("loadoutApplySpells(0, 3)", ctx);
  const L = vm.runInContext("LOADOUT[0]", ctx);
  check("forged combo writes q/w/p picker indices; fixed E is skipped",
        L.q === 1 && L.w === 0 && L.p === 1 && !("e" in L), JSON.stringify(L));
}

/* 10 — combo permalink codec (2026-08-18): explicit forge combos (E-slot use
   variants no picker can express) survive the k= param */
{
  const enc = vm.runInContext("comboEncode([null, 3, 0, null, null], 5)", ctx);
  check("combo indexes encode with trailing nulls trimmed", enc === "-.3.0",
        `got ${JSON.stringify(enc)}`);
  const dec = vm.runInContext('comboDecode("-.3.0", 5)', ctx);
  check("combo indexes decode and pad to party size",
        JSON.stringify(dec) === JSON.stringify([null, 3, 0, null, null]),
        JSON.stringify(dec));
  const none = vm.runInContext('comboEncode([null, null], 2)', ctx);
  check("all-default combos encode to nothing (plain links unchanged)",
        none === "", JSON.stringify(none));
  const junk = vm.runInContext('comboDecode("zz.!!.-1", 3)', ctx);
  check("junk combo fields degrade to default, never throw",
        JSON.stringify(junk) === JSON.stringify([1295, null, null]) ||
        JSON.stringify(junk) === JSON.stringify([null, null, null]),
        JSON.stringify(junk));
}

console.log(`\n${pass}/${pass + fail} loadout codec tests passed`);
process.exit(fail ? 1 : 0);
