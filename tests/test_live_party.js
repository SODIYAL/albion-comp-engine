/* Live-party kit mapping — liveGearKey / liveGearPicks / liveLoadout in
 * dashboard/_app.js.
 *
 * The companion reports full game item ids; the curated catalogue keys
 * armor pieces tier-stripped but potions/food tiered. A wrong mapping does
 * not show its own mistake: the member simply scores that slot naked (or
 * in the wrong item) while the panel reads "connected". So the mapping is
 * pinned here, the way the codec and the killboard math are.
 *
 * _app.js is inlined into a page, not a module, so the functions under
 * test are extracted from the source by name and evaluated in a vm context
 * with the globals they read stubbed out. Extraction fails LOUD if a
 * function is renamed or its closing brace moves off column 0.
 *
 * Run:  node tests/test_live_party.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = fs.readFileSync(
  path.join(__dirname, "..", "dashboard", "_app.js"), "utf8");

function extract(name) {
  const m = SRC.match(new RegExp(
    "function " + name + "\\([^)]*\\)\\{\\n[\\s\\S]*?\\n\\}"));
  if (!m) throw new Error(`could not extract function ${name}() from _app.js`);
  return m[0];
}
function extractConst(name) {
  const m = SRC.match(new RegExp("const " + name + " = [\\s\\S]*?;\\n"));
  if (!m) throw new Error(`could not extract const ${name} from _app.js`);
  return m[0];
}

/* a small catalogue shaped like the real one: armor keys tier-stripped,
   potions/food tiered (see pipeline/out/dataset-latest.json gear) */
const GEAR = {
  HEAD_CLOTH_SET1: { slot: "head" },
  ARMOR_LEATHER_HELL: { slot: "armor" },
  SHOES_PLATE_AVALON: { slot: "shoes" },
  CAPEITEM_DEMON: { slot: "cape" },
  OFF_BOOK: { slot: "offhand" },
  T6_POTION_HEAL: { slot: "potion" },
  T7_MEAL_OMELETTE: { slot: "food" },
};
/* the Q/W pools the picker indexes into: [id, ...] entries per slot */
const SPELLS = {
  "2H_HOLYSTAFF": { q: [["HOLYFLASH"], ["HOLY_GENERIC_HEAL"]], w: [["SACRED_PULSE"]] },
};
const ctx = { GEAR, SPELLS, console };
vm.createContext(ctx);
vm.runInContext([
  extractConst("LIVE_SLOT"), "let LIVE_BASE_MAP = null;",
  extract("liveGearKey"), extract("liveGearPicks"),
  extract("liveSpellPicks"), extract("liveLoadout"),
  extractConst("liveSig"),
].join("\n"), ctx);

let fails = 0;
function eq(got, want, what) {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { console.log("PASS " + what); return; }
  fails++; console.log(`FAIL ${what}\n  got  ${g}\n  want ${w}`);
}

/* key mapping */
eq(ctx.liveGearKey("T6_HEAD_CLOTH_SET1@1"), "HEAD_CLOTH_SET1", "armor: tier + enchant stripped");
eq(ctx.liveGearKey("T8_ARMOR_LEATHER_HELL@3"), "ARMOR_LEATHER_HELL", "armor: high tier, high enchant");
eq(ctx.liveGearKey("T6_POTION_HEAL"), "T6_POTION_HEAL", "potion: exact tiered key");
eq(ctx.liveGearKey("T8_POTION_HEAL@1"), "T6_POTION_HEAL", "potion: other tier wears the curated record by base");
eq(ctx.liveGearKey("T7_MEAL_OMELETTE@2"), "T7_MEAL_OMELETTE", "food: enchant stripped, tier kept");
eq(ctx.liveGearKey("T4_CAPE"), null, "uncurated item (plain cape) -> null, never a stand-in");
eq(ctx.liveGearKey("ITEM_12345"), null, "companion offline placeholder -> null");
eq(ctx.liveGearKey(undefined), null, "missing -> null");

/* slot mapping: chest -> armor; mainhand/bag/mount ignored; slot mismatch dropped */
eq(ctx.liveGearPicks({
  mainhand: "T8_2H_HOLYSTAFF@3", chest: "T8_ARMOR_LEATHER_HELL@3", head: "T6_HEAD_CLOTH_SET1",
  shoes: "T7_SHOES_PLATE_AVALON", cape: "T4_CAPEITEM_DEMON", offhand: "T5_OFF_BOOK",
  potion: "T8_POTION_HEAL", food: "T7_MEAL_OMELETTE", bag: "T8_BAG", mount: "T8_MOUNT_HORSE",
}), { head: "HEAD_CLOTH_SET1", armor: "ARMOR_LEATHER_HELL", shoes: "SHOES_PLATE_AVALON",
      cape: "CAPEITEM_DEMON", offhand: "OFF_BOOK", potion: "T6_POTION_HEAL", food: "T7_MEAL_OMELETTE" },
   "full kit maps every loadout slot, chest -> armor, non-loadout slots ignored");
eq(ctx.liveGearPicks({ chest: "T6_HEAD_CLOTH_SET1" }), null, "item in the wrong slot is dropped");
eq(ctx.liveGearPicks({ head: "T4_CAPE" }), null, "kit of only uncurated pieces -> null");
eq(ctx.liveGearPicks(null), null, "no equipment -> null");

/* the whole LOADOUT entry: picks + kit, no engine mark */
const m = { weapon: "2H_HOLYSTAFF", spells: { q: "HOLY_GENERIC_HEAL", w: "SACRED_PULSE", e: "X" },
            equipment: { chest: "T8_ARMOR_LEATHER_HELL", potion: "T8_POTION_HEAL" } };
eq(ctx.liveLoadout(m), { q: 1, w: 0, armor: "ARMOR_LEATHER_HELL", potion: "T6_POTION_HEAL" },
   "liveLoadout = real q/w indices + worn kit");
eq(ctx.liveLoadout({ weapon: "2H_HOLYSTAFF", equipment: { chest: "T8_ARMOR_LEATHER_HELL" } }),
   { armor: "ARMOR_LEATHER_HELL" }, "kit without spells still dresses the member");
eq(ctx.liveLoadout({ weapon: "2H_HOLYSTAFF" }), undefined, "nothing known -> undefined (engine default)");
eq("_eng" in (ctx.liveLoadout(m) || {}), false, "a fielded build never wears the engine mark");

/* the sync signature changes when the worn kit changes */
const liveSig = vm.runInContext("liveSig", ctx);
const s1 = liveSig(m);
const s2 = liveSig({ ...m, equipment: { chest: "T6_ARMOR_LEATHER_HELL", potion: "T6_POTION_HEAL" } });
const s3 = liveSig({ ...m, equipment: { chest: "T8_ARMOR_LEATHER_HELL", potion: "T8_POTION_HEAL", head: "T6_HEAD_CLOTH_SET1" } });
eq(s1.g === s2.g, true, "same curated kit at another tier -> same signature (no re-render churn)");
eq(s1.g !== s3.g, true, "a new worn piece -> new signature (live sync re-dresses)");

console.log(fails ? `${fails} FAILED` : "ALL PASS");
process.exit(fails ? 1 : 0);
