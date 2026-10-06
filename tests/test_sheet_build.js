/* Sheet build tests - dashboard/_build.js.
 *
 * The pure half of the build module: a share hash's members and
 * loadouts, and the build per slot of a sheet (set, unset, a changed
 * weapon, a slot with no weapon), named from stub tables through the
 * real codec (_loadout.js, loaded with a stub GEAR). No DOM: the UI
 * half returns at once without a document.
 *
 * Run:  node tests/test_sheet_build.js
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");
let failures = 0, passes = 0;
function check(name, cond, detail) {
  if (cond) { passes += 1; console.log("PASS  " + name); }
  else { failures += 1; console.log("FAIL  " + name + (detail !== undefined ? "  " + JSON.stringify(detail) : "")); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const GEAR = {
  HEAD_PLATE_KEEPER: { name: "Judicator Helmet", slot: "head", example_item: "T8_HEAD_PLATE_KEEPER" },
  ARMOR_PLATE_SET2: { name: "Knight Armor", slot: "armor", example_item: "T8_ARMOR_PLATE_SET2" },
  SHOES_LEATHER_MORGANA: { name: "Stalker Shoes", slot: "shoes", example_item: "T8_SHOES_LEATHER_MORGANA" },
  T8_MEAL_SANDWICH: { name: "Beef Sandwich", slot: "food", example_item: "T8_MEAL_SANDWICH" }
};
const SPELLS = {
  "2H_POLEHAMMER": { q: [["Q1", "Heavy Smash"], ["Q2", "Deep Leap"]], w: [["W1", "Giant Steps"]], e: [["E1", "Grasp of the Undead"]], passive: [["P1", "Aggression"], ["P2", "Toughness"]] },
  "2H_LONGBOW": { q: [["Q3", "Multishot"]], w: [["W3", "Ray of Light"]], e: [["E3", "Undead Arrows"]], passive: [["P3", "Aggression"]] }
};
const ctx = { console, URLSearchParams };
vm.createContext(ctx);
ctx.GEAR = GEAR;
ctx.SPELLS = SPELLS;
ctx.ICONS = {};
for (const f of ["_loadout.js", "_build.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);
const tables = { decode: run("loadoutDecode"), gear: GEAR, spells: SPELLS };

/* 1 - the hash's members and loadouts */
{
  const members = run("hashMembers");
  /* two members: the first with helm, armor, food, Q2, W1, passive 2; the second bare */
  const hash = "#c=castle&n=2&p=2H_POLEHAMMER,2H_LONGBOW&g=HEAD_PLATE_KEEPER,ARMOR_PLATE_SET2,T8_MEAL_SANDWICH~0.1.-.-.-.-.2.1.0.1";
  const m = members(hash, tables.decode);
  check("the weapons come in the comp's order", same(m.weapons, ["2H_POLEHAMMER", "2H_LONGBOW"]));
  check("the loadouts decode through the planner's codec, the dictionary's keys kept",
        same(m.loadouts[0], { head: "HEAD_PLATE_KEEPER", armor: "ARMOR_PLATE_SET2", food: "T8_MEAL_SANDWICH", q: 1, w: 0, p: 1 }) && m.loadouts[1] === undefined, m.loadouts);
  check("a hash without a hash mark, a loadout or members reads as empty",
        same(members("c=castle", tables.decode), { weapons: [], loadouts: [] }) && same(members(null, tables.decode), { weapons: [], loadouts: [] }));
}

/* 2 - the build per slot */
{
  const builds = run("sheetBuilds");
  const hash = "#c=castle&n=3&p=2H_POLEHAMMER,2H_LONGBOW,2H_LONGBOW&g=HEAD_PLATE_KEEPER,ARMOR_PLATE_SET2,T8_MEAL_SANDWICH~0.1.-.-.-.-.2.1.0.1";
  const slots = [
    { position: 1, weapon_id: "2H_POLEHAMMER" },
    { position: 2, weapon_id: "2H_LONGBOW" },
    { position: 3, weapon_id: "2H_POLEHAMMER" },   /* the caller changed slot 3's weapon */
    { position: 4, weapon_id: null }                /* a slot past the comp, any weapon */
  ];
  const b = builds(hash, slots, tables);
  check("a saved build names its gear in the codec's order with the item to draw",
        b[1].state === "set" && same(b[1].gear.map(g => `${g.label}:${g.name}:${g.item}`),
          ["Helm:Judicator Helmet:T8_HEAD_PLATE_KEEPER", "Armor:Knight Armor:T8_ARMOR_PLATE_SET2", "Food:Beef Sandwich:T8_MEAL_SANDWICH"]), b[1]);
  check("and its spells by name, with the weapon's E",
        same(b[1].spells.map(s => `${s.label}:${s.name}`), ["Q:Deep Leap", "W:Giant Steps", "Passive:Toughness"]) && same(b[1].e, ["Grasp of the Undead"]), b[1]);
  check("a member saved without a loadout is unset", same(b[2], { state: "unset", weapon: "2H_LONGBOW" }), b[2]);
  check("a slot whose weapon no longer matches the member is changed", same(b[3], { state: "changed", weapon: "2H_POLEHAMMER" }), b[3]);
  check("a slot with no weapon has none", same(b[4], { state: "none" }), b[4]);
  check("a comp saved without the loadout parameter is unset on every slot",
        same(builds("#c=castle&p=2H_POLEHAMMER", [{ position: 1, weapon_id: "2H_POLEHAMMER" }], tables)[1], { state: "unset", weapon: "2H_POLEHAMMER" }));
  check("a gear key the page does not know is left out, never shown by key",
        same(builds("#p=2H_LONGBOW&g=MYSTERY_HELM~0.-.-.-.-.-.-.0.-.-", [{ position: 1, weapon_id: "2H_LONGBOW" }], tables)[1].gear, [])
        && builds("#p=2H_LONGBOW&g=MYSTERY_HELM~0.-.-.-.-.-.-.0.-.-", [{ position: 1, weapon_id: "2H_LONGBOW" }], tables)[1].state === "set");
  check("a spell index past the pool is left out", same(builds("#p=2H_LONGBOW&g=~-.-.-.-.-.-.-.9.-.-", [{ position: 1, weapon_id: "2H_LONGBOW" }], tables)[1].state, "unset"));
  const M = run("BUILD_MSG");
  check("every state without a build has a sentence", !!M.none && !!M.changed && !!M.unset);
}

/* 3 - the boundary */
{
  const src = fs.readFileSync(path.join(DASH, "_build.js"), "utf8");
  check("the module reads the planner's tables and codec alone: no engine, no planner state, no table of the database",
        !/\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine|PLANNED|LOADOUT\b|window\.DB|\.from\(|\.rpc\(/.test(src));
  check("the module paints into the build places alone and listens for the sheet's event",
        /addEventListener\("sheet-read"/.test(src) && /\[data-su-build\]/.test(src) && !/su-board|su-slot\b|su-form/.test(src));
}

console.log(`\n${passes}/${passes + failures} sheet build tests passed`);
process.exit(failures ? 1 : 0);
