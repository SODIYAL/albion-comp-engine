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

/* 7 — provenance codec: forged-slot flags survive the permalink;
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
  /* locks: 'l' = a hand-locked slot — the only state a
     refresh holds; survives the permalink beside m / f */
  const encL = vm.runInContext('provEncode(["l","f","m","l","m"], 5)', ctx);
  check("locked slots encode as 'l' (trailing manuals still trimmed)",
        encL === "lfml", `got ${JSON.stringify(encL)}`);
  const decL = vm.runInContext('provDecode("lfml", 5)', ctx);
  check("locked slots decode and pad to party size",
        JSON.stringify(decL) === JSON.stringify(["l","f","m","l","m"]),
        `got ${JSON.stringify(decL)}`);
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

/* 10 — combo permalink codec: explicit forge combos (E-slot use
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

/* 11 — neither caller-reference fill (loadoutPrefillGear, loadoutPrefill)
   puts an off-hand on a two-hander, the engine kit's rule (L40f). A swap
   or replace landing and a forge result land the engine's kit first and
   take the reference only in slots it leaves unset, so they score the kit
   the engine priced; an add starts from the caller reference */
{
  const off = someKey("offhand"), head = someKey("head");
  const ref = [{ canonical: true, gear: { head, offhand: off } }];
  ctx.LOADOUTS = { blackzone_roam: { "2H_DUALMACE_AVALON": ref, MAIN_MACE: ref } };
  ctx.ENG = undefined;
  ctx.party = ["2H_DUALMACE_AVALON", "MAIN_MACE"];
  for (const fill of ["loadoutPrefillGear", "loadoutPrefill"]) {
    vm.runInContext(`LOADOUT = [{}, {}]; ${fill}(0); ${fill}(1);`, ctx);
    const L = vm.runInContext("LOADOUT", ctx);
    check(`${fill}: a two-hander takes the reference's head but no off-hand; a one-hander takes both`,
          L[0].head === head && !("offhand" in L[0])
          && L[1].head === head && L[1].offhand === off, JSON.stringify(L));
  }
}

/* a zerg in the address: the open party rides the plain fields and every
   other party its suffixed fields (partyEncode); partyDecode reads one
   party back, dropping an unknown weapon from every array together */
{
  ctx.WEAPONS = {"2H_HAMMER_AVALON": {}, "2H_MACE": {}, "2H_LONGBOW": {}};
  const head = someKey("head");
  const parse = s => {
    const p = {};
    s.replace(/^[#&]/, "").split("&").forEach(kv => { const i = kv.indexOf("="); if (i > 0) p[kv.slice(0, i)] = kv.slice(i + 1); });
    return p;
  };
  ctx.__s = {party: ["2H_HAMMER_AVALON", "2H_MACE", "2H_LONGBOW"], PROV: ["l", "f", "m"],
             COMBO: [2, null, 1], LOADOUT: [{head}, {}, {q: 0}], PLANNED: 18};
  const enc = vm.runInContext("partyEncode(2, __s)", ctx);
  ctx.__p = parse(enc);
  const d = vm.runInContext('partyDecode(__p, "2")', ctx);
  check("a party's suffixed fields round-trip: roster, locks, combos, kits, planned size",
        d.party.join(",") === "2H_HAMMER_AVALON,2H_MACE,2H_LONGBOW" && d.PROV.join("") === "lfm"
        && JSON.stringify(d.COMBO) === "[2,null,1]" && d.LOADOUT[0].head === head
        && d.LOADOUT[2].q === 0 && d.PLANNED === 18 && !("p" in ctx.__p) && !("n" in ctx.__p), enc);
  ctx.__q = Object.assign({}, ctx.__p, {p2: "2H_HAMMER_AVALON,NOT_A_WEAPON,2H_LONGBOW"});
  const u = vm.runInContext('partyDecode(__q, "2")', ctx);
  check("an unknown weapon drops from every array together: no lock, combo or kit shifts",
        u.party.join(",") === "2H_HAMMER_AVALON,2H_LONGBOW" && u.PROV.join("") === "lm"
        && JSON.stringify(u.COMBO) === "[2,1]" && u.LOADOUT[1].q === 0
        && JSON.stringify(u.index) === "[0,2]", JSON.stringify(u));
  ctx.__e = {party: [], PROV: [], COMBO: [], LOADOUT: [], PLANNED: 20};
  const empty = vm.runInContext("partyEncode(3, __e)", ctx);
  ctx.__z = Object.assign(parse(empty), ctx.__p, {p: "2H_MACE", n: "7", t: "1", p11: "2H_MACE", k12: "1"});
  const nums = vm.runInContext("partyNumbers(__z)", ctx);
  const e = vm.runInContext('partyDecode(__z, "3")', ctx);
  check("an empty party still exists (its n alone); only parties 1 to PARTIES_MAX count, the plain fields never",
        empty === "&n3=20" && JSON.stringify(nums) === "[2,3]" && e.party.length === 0 && e.PLANNED === 20,
        `${empty} ${JSON.stringify(nums)}`);
}

/* the engine mark: an engine kit still reads as the engine's after a reload
   (it used to come back as a fielded build); a plain kit's record is the
   ten fields it always was, and a mark alone carries nothing */
{
  const head = someKey("head"), armor = someKey("armor");
  const engine = {head, armor, q: 1, _eng: 1};
  const fielded = {head, armor, q: 1};
  const {enc, dec} = roundTrip(["2H_MACE", "2H_HOLYSTAFF"], [engine, fielded]);
  const recs = enc.slice(enc.indexOf("~") + 1).split("!");
  check("an engine kit keeps its mark through the link; a fielded build never gains one",
        !!dec[0] && dec[0]._eng === 1 && !!dec[1] && !("_eng" in dec[1]) && dec[0].head === head && dec[1].q === 1, enc);
  check("the mark is an eleventh field on the marked member alone: an older link reads the same ten",
        recs[0].split(".").length === 11 && recs[0].endsWith(".e") && recs[1].split(".").length === 10, enc);
  const {enc: bare} = roundTrip(["2H_MACE"], [{_eng: 1}]);
  check("a mark with no piece and no spell writes nothing", bare === "", bare);
  ctx.__old = enc.replace(/\.e(?=!|$)/g, "");
  const old = vm.runInContext("loadoutDecode(__old)", ctx);
  check("a link written before the mark decodes as it did, unmarked", !!old[0] && !("_eng" in old[0]) && old[0].head === head);
}

console.log(`\n${pass}/${pass + fail} loadout codec tests passed`);
process.exit(fail ? 1 : 0);
