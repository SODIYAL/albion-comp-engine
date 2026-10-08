/* Saved comp tests - dashboard/_comps.js.
 *
 * _auth.js, _profile.js, _guild.js and _comps.js run together in a vm
 * context with no document, as the page loads them: the helpers and the
 * pure functions load, and each UI block returns before touching the
 * DOM. The helpers run against a stub client that records every query,
 * so what the page sends to Supabase is pinned without a network;
 * tests/test_supabase_rls.mjs pins what the database does with it.
 *
 * Pinned: the planner's share hash reads into a template and a template
 * writes back the hash the planner opens (the saved hash while the roster
 * still matches, a plain link otherwise), slots normalize to one per
 * position in order, the summary counts roles through the catalog,
 * validation follows the database's bounds, only caller roles write,
 * database errors read as sentences, and each helper writes exactly what
 * its policy admits. The kits: each slot reads the kit its saved link
 * holds at its position through the planner's codec (_loadout.js, loaded
 * here with a stub GEAR), a slot's weapon picked in the dialog drops its
 * kit while the others keep theirs, a removed slot takes its own along,
 * and the link rebuilt from the slots decodes back to the same kits; the
 * picker lists the profile's search and the open slot.
 *
 * Run:  node tests/test_comps.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const CALLS = [];
const REPLY = {};
const SESSION = { user: { id: "u-me", email: "me@example.com" } };
function chain(record, answer) {
  const proxy = new Proxy(function () {}, {
    get(_t, prop) {
      if (prop === "then") return (res, rej) => Promise.resolve(answer()).then(res, rej);
      return (...args) => { record.push([prop, ...args]); return proxy; };
    },
  });
  return proxy;
}
const DB = {
  auth: {
    getSession: async () => ({ data: { session: SESSION }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from(table) {
    const ops = [];
    CALLS.push({ table, ops });
    return chain(ops, () => REPLY[table] || { data: null, error: null });
  },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
/* the planner's gear catalog the codec reads (a key it does not hold is dropped) */
ctx.GEAR = {
  HEAD_PLATE_KEEPER: { name: "Judicator Helmet", slot: "head", example_item: "T8_HEAD_PLATE_KEEPER" },
  ARMOR_PLATE_SET2: { name: "Knight Armor", slot: "armor", example_item: "T8_ARMOR_PLATE_SET2" },
  T8_MEAL_SANDWICH: { name: "Beef Sandwich", slot: "food", example_item: "T8_MEAL_SANDWICH" }
};
vm.createContext(ctx);
for (const f of ["_loadout.js", "_auth.js", "_profile.js", "_guild.js", "_comps.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

const CATALOG = {
  MAIN_HOLYSTAFF_AVALON: { name: "Hallowfall", role: "healer", item: "" },
  MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
  "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" },
  "2H_ARCANESTAFF": { name: "Great Arcane Staff", role: "support", item: "" },
};
const CONTENTS = { territory_defense: "Territory Defense", ancient_lands: "Dragon Portal" };
const STYLES = { brawl: "Brawl", clap: "Clap" };

(async () => {

/* 1 - the share hash */
{
  const parse = run("parseShareHash");
  const p = parse("#c=ancient_lands&n=7&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc&f=fff&k=0.1");
  check("a share hash reads its content, size, style and weapons in order; the loadout codec's parts are left alone",
        p && p.content === "ancient_lands" && p.size === 7 && p.style === "clap"
        && same(p.weapons, ["2H_LONGBOW", "MAIN_MACE_HELL"]) && p.hash.startsWith("c=ancient_lands"), p);
  check("a hash without a size or style reads null and balanced",
        (() => { const q = parse("c=castle&p=2H_LONGBOW"); return q.size === null && q.style === "" && q.weapons.length === 1; })());
  check("a junk hash or none is no comp", parse("#foo") === null && parse("") === null && parse(null) === null);
  check("a hash with a content but no weapons is a comp with none",
        (() => { const q = parse("c=castle&n=20"); return q && q.weapons.length === 0 && q.size === 20; })());
  const zerg = parse("#c=castle&n=20&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc&t=2&n1=20&p1=2H_MACE&g1=x&f1=f&k1=0&n3=20&p3=2H_BOW");
  check("a zerg's address keeps the open party alone: no t=, no other party's fields",
        zerg && same(zerg.weapons, ["2H_LONGBOW", "MAIN_MACE_HELL"])
        && zerg.hash === "c=castle&n=20&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc", zerg && zerg.hash);

  const slotsFrom = run("slotsFromWeapons");
  check("weapons become slots from position 1",
        same(slotsFrom(["A", "B"]), [{ position: 1, weapon_id: "A", role: null, note: null }, { position: 2, weapon_id: "B", role: null, note: null }]));
  check("slots stop at the roster cap", slotsFrom(Array(70).fill("A")).length === run("COMP_SLOTS_MAX"));

  const hashOf = run("templateHash");
  const t = { content: "ancient_lands", style: "clap", planned_size: 7, share_hash: "c=ancient_lands&n=7&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc" };
  check("the saved hash opens while the roster still matches (kits ride along)",
        hashOf(t, slotsFrom(["2H_LONGBOW", "MAIN_MACE_HELL"])) === t.share_hash);
  check("a changed roster opens as a plain link built from the slots",
        hashOf(t, slotsFrom(["2H_LONGBOW"])) === "c=ancient_lands&n=7&st=clap&p=2H_LONGBOW");
  check("a template without a saved hash opens as a plain link; balanced carries no st=",
        hashOf({ content: "castle", style: "", planned_size: 20 }, slotsFrom(["A", null, "B"])) === "c=castle&n=20&p=A,B");
  check("a changed content, style or size drops the saved hash",
        hashOf(Object.assign({}, t, { style: "" }), slotsFrom(["2H_LONGBOW", "MAIN_MACE_HELL"])) === "c=ancient_lands&n=7&p=2H_LONGBOW,MAIN_MACE_HELL"
        && hashOf(Object.assign({}, t, { planned_size: 5 }), slotsFrom(["2H_LONGBOW", "MAIN_MACE_HELL"])).includes("n=5"));
}

/* 2 - slots and the summary */
{
  const norm = run("normalizeSlots");
  const rows = norm([
    { position: 3, weapon_id: "2H_LONGBOW", role: " ranged ", note: "" },
    { position: "1", weapon_id: "MAIN_MACE_HELL", role: null, note: " engage first " },
    { position: 1, weapon_id: "DUPLICATE" },
    { position: 0, weapon_id: "OFF" },
    { position: 61, weapon_id: "OFF" },
    { position: 2, weapon_id: null, role: "x".repeat(50) },
  ]);
  check("slots normalize to one per position, in order, texts trimmed and cut at the bounds, off-range positions dropped",
        same(rows.map(r => `${r.position}:${r.weapon_id}:${r.role}:${r.note}`),
             ["1:MAIN_MACE_HELL:null:engage first", `2:null:${"x".repeat(40)}:null`, "3:2H_LONGBOW:ranged:null"]), rows);
  const summary = run("templateSummary")(rows.concat([{ position: 4, weapon_id: "2H_UNKNOWN" }]), CATALOG);
  check("the summary counts slots per role through the catalog, plus open and unknown",
        summary.frontline === 1 && summary.dps === 1 && summary.healer === 0 && summary.support === 0
        && summary.open === 1 && summary.unknown === 1 && summary.total === 4, summary);
}

/* 3 - validation and powers */
{
  const v = run("validateTemplate");
  check("a comp needs a name, a listed content and a size within the roster cap",
        !!v({ name: " ", content: "castle_outpost", plannedSize: 20 }, CONTENTS, STYLES).name
        && !!v({ name: "A", content: "narnia", plannedSize: 20 }, CONTENTS, STYLES).content
        && !!v({ name: "A", content: "territory_defense", plannedSize: 1 }, CONTENTS, STYLES).plannedSize
        && !!v({ name: "A", content: "territory_defense", plannedSize: 61 }, CONTENTS, STYLES).plannedSize
        && same(v({ name: "A", content: "territory_defense", style: "", plannedSize: 20 }, CONTENTS, STYLES), {}));
  check("a style off the list is refused; balanced (empty) passes",
        !!v({ name: "A", content: "territory_defense", style: "yolo", plannedSize: 20 }, CONTENTS, STYLES).style
        && same(v({ name: "A", content: "territory_defense", style: "clap", plannedSize: 20 }, CONTENTS, STYLES), {}));
  check("the name shares the account name bound",
        !!v({ name: "x".repeat(run("ACCOUNT_NAME_MAX") + 1), content: "territory_defense", plannedSize: 20 }, CONTENTS, STYLES).name);
  const powers = run("compPowers");
  check("callers, officers and admins write; members read",
        powers("caller").write && powers("officer").write && powers("admin").write && !powers("member").write && !powers(null).write);
}

/* 4 - error wording */
{
  const msg = run("compErrorMessage"), M = run("COMP_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["not signed in", { code: "42501", message: "sign in to save a comp" }, M.signedOut],
    ["table missing", { code: "PGRST205", message: "Could not find the table" }, M.missing],
    ["a name in use", { code: "23505", message: "duplicate key value" }, M.taken],
    ["too many comps", { code: "23514", message: "a guild keeps at most 100 templates" }, M.tooManyTemplates],
    ["too many slots", { code: "23514", message: "a comp holds at most 60 slots" }, M.tooManySlots],
    ["a position twice", { code: "21000", message: "ON CONFLICT DO UPDATE command cannot affect row a second time" }, M.duplicate],
    ["refused by the policy", { code: "42501", message: "the template was not found, or your role does not edit it" }, M.refused],
    ["no row came back", { code: "refused", message: "the server refused the change" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
    ["a bad number", { code: "22P02", message: "invalid input syntax for type smallint" }, M.invalid],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: the bounds in the sentences are the bounds in force",
        M.tooManyTemplates.includes(String(run("COMP_TEMPLATES_MAX"))) && M.tooManySlots.includes(String(run("COMP_SLOTS_MAX"))));
}

/* 5 - what the helpers send */
{
  const find = table => CALLS.find(c => c.table === table);
  const has = (ops, ...want) => ops.some(o => want.every((w, i) => same(o[i], w)));

  CALLS.length = 0;
  REPLY.comp_templates = { data: [], error: null };
  await run("loadGuildTemplates")("g1");
  let q = find("comp_templates");
  check("loadGuildTemplates reads one guild's comps, newest change first, with the editor and the slot count",
        has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "order", "updated_at", { ascending: false })
        && q.ops.some(o => o[0] === "select" && /editor:profiles!comp_templates_updated_by_fkey/.test(o[1]) && /slots:comp_template_slots\(count\)/.test(o[1])), q.ops);

  CALLS.length = 0;
  REPLY.comp_templates = { data: { id: "t1", slots: [{ position: 2, weapon_id: "B" }, { position: 1, weapon_id: "A" }] }, error: null };
  const t = await run("loadTemplate")("t1");
  q = find("comp_templates");
  check("loadTemplate reads one comp with its slots, and orders the slots",
        has(q.ops, "eq", "id", "t1") && q.ops.some(o => o[0] === "maybeSingle")
        && same(t.slots.map(s => s.position), [1, 2]), q.ops);

  CALLS.length = 0;
  REPLY["rpc:save_comp_template"] = { data: { id: "t1" }, error: null };
  await run("saveTemplate")({ id: null, guild_id: "g1", name: " Castle A ", content: "castle", style: "", planned_size: "20", notes: " n ",
                              share_hash: "c=castle&p=A", slots: [{ position: 2, weapon_id: "B" }, { position: 1, weapon_id: "A", role: " r " }] });
  const r = CALLS.find(c => c.rpc);
  check("saveTemplate sends one save_comp_template payload: trimmed texts, a numeric size, normalized slots",
        r.rpc === "save_comp_template" && same(r.args.template, {
          id: null, guild_id: "g1", name: "Castle A", content: "castle", style: "", planned_size: 20, notes: "n",
          share_hash: "c=castle&p=A",
          slots: [{ position: 1, weapon_id: "A", role: "r", note: null }, { position: 2, weapon_id: "B", role: null, note: null }]
        }), r.args);

  CALLS.length = 0;
  REPLY.comp_templates = { data: [{ id: "t1" }], error: null };
  await run("deleteTemplate")("t1");
  q = find("comp_templates");
  check("deleteTemplate deletes one comp and reads the row back",
        q.ops.some(o => o[0] === "delete") && has(q.ops, "eq", "id", "t1") && q.ops.some(o => o[0] === "select"), q.ops);
  CALLS.length = 0;
  REPLY.comp_templates = { data: [], error: null };
  let refused = null;
  try { await run("deleteTemplate")("t1"); } catch (e) { refused = e; }
  check("a deletion the policy refused (no row back) is reported", refused && refused.code === "refused");

  const src = fs.readFileSync(path.join(DASH, "_comps.js"), "utf8");
  check("the module touches the planner through the address bar alone",
        /location\.hash/.test(src) && !/\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine/.test(src));
}

/* 6 - the export: the comp as a sheet and as lines */
{
  const slots = [{ position: 2, weapon_id: "2H_LONGBOW", role: "dps", note: "kite" }, { position: 1, weapon_id: "MAIN_MACE_HELL", role: "tank", note: null }, { position: 3, weapon_id: null, role: null, note: "flex" }];
  const rows = run("compSheetRows")(slots, CATALOG);
  check("the sheet: a header, then one row per slot in order with the catalog name, the role and the note; an open slot has no weapon",
        same(rows, [["#", "Weapon", "Role", "Note"], [1, "Incubus Mace", "tank", ""], [2, "Longbow", "dps", "kite"], [3, "", "", "flex"]]), rows);
  const text = run("compText")({ name: "Castle A", content: "territory_defense", planned_size: 20, style: "clap" }, slots, CATALOG, CONTENTS, STYLES);
  check("the lines: a title with the content, the size and the style, then numbered slots with the role after a dash and the note in brackets",
        text === "Castle A · Territory Defense · 20 planned · Clap\n1. Incubus Mace - tank\n2. Longbow - dps (kite)\n3. open slot (flex)", text);
  check("an unknown key keeps its key; a comp with no name is Comp", run("compText")({}, [{ position: 1, weapon_id: "MYSTERY" }], CATALOG, CONTENTS, STYLES) === "Comp\n1. MYSTERY");
}

/* 7 - the kit each slot carries, the slots edited in the dialog, the
   link rebuilt through the planner's codec */
{
  const DICT = "HEAD_PLATE_KEEPER,ARMOR_PLATE_SET2,T8_MEAL_SANDWICH";
  /* three members: the first locked in helm, armor, food and Q2/W1/passive 2;
     the second forged on combo 3 with Q1; the third the engine's helm */
  const planner = `c=castle&n=20&st=clap&p=2H_POLEHAMMER,2H_LONGBOW,MAIN_HOLYSTAFF_AVALON`
    + `&g=${DICT}~0.1.-.-.-.-.2.1.0.1!-.-.-.-.-.-.-.0.-.-!0.-.-.-.-.-.-.-.-.-.e&f=lf&k=-.3`;
  const t = { content: "castle", style: "clap", planned_size: 20, share_hash: planner };
  const slots = run("slotsFromWeapons")(["2H_POLEHAMMER", "2H_LONGBOW", "MAIN_HOLYSTAFF_AVALON"]);
  const parsed = run("parseShareHash")(planner);
  check("the share hash keeps its members by position and every field",
        same(parsed.members, ["2H_POLEHAMMER", "2H_LONGBOW", "MAIN_HOLYSTAFF_AVALON"]) && parsed.params.f === "lf" && parsed.params.k === "-.3"
        && same(run("parseShareHash")("c=castle&p=A,,B,,").members, ["A", "", "B"]) && same(run("parseShareHash")("c=castle&p=A,,B,,").weapons, ["A", "B"]));
  const kits = run("slotKits")(planner, slots);
  check("each slot reads the kit its saved link holds at its position, through the planner's codec",
        same(kits[1], { loadout: { head: "HEAD_PLATE_KEEPER", armor: "ARMOR_PLATE_SET2", food: "T8_MEAL_SANDWICH", q: 1, w: 0, p: 1 }, prov: "l" })
        && same(kits[2], { loadout: { q: 0 }, prov: "f", combo: 3 }) && same(kits[3], { loadout: { head: "HEAD_PLATE_KEEPER", _eng: 1 } }), kits);
  check("a slot whose weapon is not the member at its position reads no kit (the sheet's rule)",
        Object.keys(run("slotKits")(planner, run("slotsFromWeapons")(["2H_POLEHAMMER", "2H_BOW", "MAIN_HOLYSTAFF_AVALON"]))).join(",") === "1,3"
        && Object.keys(run("slotKits")("", slots)).length === 0 && Object.keys(run("slotKits")("c=castle&p=2H_POLEHAMMER", slots)).length === 0);
  const held = run("slotsWithKits")(slots, planner);
  check("the slots carry their kits; an unedited comp opens as saved and keeps its stored link",
        held.every(s => s.kit) && run("templateHash")(t, held) === planner && run("keptHash")(t, held) === planner);

  const picked = run("withSlotWeapon")(held, 2, "2H_BOW");
  check("a weapon picked for a slot drops that slot's kit; the others keep theirs; the same weapon changes nothing",
        picked[1].weapon_id === "2H_BOW" && !picked[1].kit && picked[0].kit === held[0].kit && picked[2].kit === held[2].kit
        && run("withSlotWeapon")(held, 2, "2H_LONGBOW")[1] === held[1] && run("withSlotWeapon")(held, 3, "")[2].weapon_id === null);
  const rebuilt = run("templateHash")(t, picked);
  check("the comp opens through a link built from its slots: the changed slot without a kit, the others in theirs",
        rebuilt === `c=castle&n=20&st=clap&p=2H_POLEHAMMER,2H_BOW,MAIN_HOLYSTAFF_AVALON&g=${DICT}~0.1.-.-.-.-.2.1.0.1!-.-.-.-.-.-.-.-.-.-!0.-.-.-.-.-.-.-.-.-.e&f=l`,
        rebuilt);
  check("a save keeps that link, so the stored link matches the stored slots again",
        run("keptHash")(t, picked) === rebuilt && run("templateHash")(Object.assign({}, t, { share_hash: rebuilt }), picked) === rebuilt);
  const back = run("slotKits")(rebuilt, picked);
  check("the rebuilt link reads back to the same kits", same(back[1], kits[1]) && !back[2] && same(back[3], kits[3]), back);

  const dropped = run("dropSlot")(held, 1);
  const afterDrop = run("templateHash")(t, dropped);
  check("a removed slot takes its kit along; the others move up with theirs",
        same(dropped.map(s => `${s.position}:${s.weapon_id}`), ["1:2H_LONGBOW", "2:MAIN_HOLYSTAFF_AVALON"])
        && afterDrop === "c=castle&n=20&st=clap&p=2H_LONGBOW,MAIN_HOLYSTAFF_AVALON&g=HEAD_PLATE_KEEPER~-.-.-.-.-.-.-.0.-.-!0.-.-.-.-.-.-.-.-.-.e&f=f&k=3",
        afterDrop);
  const opened = run("withSlotWeapon")(held, 2, null);
  check("an open slot is an empty entry, every later slot at its position",
        run("templateHash")(t, opened).includes("p=2H_POLEHAMMER,,MAIN_HOLYSTAFF_AVALON&")
        && same(run("slotMembers")(opened), ["2H_POLEHAMMER", "", "MAIN_HOLYSTAFF_AVALON"])
        && same(run("slotMembers")(run("slotsFromWeapons")(["A", null, null])), ["A"]));
  check("with kits on the slots a changed content keeps every kit; without them the plain link stands",
        run("templateHash")(Object.assign({}, t, { content: "ancient_lands" }), held).startsWith(`c=ancient_lands&n=20&st=clap&p=2H_POLEHAMMER,2H_LONGBOW,MAIN_HOLYSTAFF_AVALON&g=${DICT}~`)
        && run("templateHash")(Object.assign({}, t, { content: "ancient_lands" }), slots) === "c=ancient_lands&n=20&st=clap&p=2H_POLEHAMMER,2H_LONGBOW,MAIN_HOLYSTAFF_AVALON");
  check("a changed roster without any kit keeps the stored link as it was (the plain link is built on open)",
        run("keptHash")(t, run("slotsFromWeapons")(["2H_BOW"])) === planner);
  const zerg = run("slotKits")("c=castle&n=20&p=2H_POLEHAMMER&g=HEAD_PLATE_KEEPER~0&t=1&n2=20&p2=2H_LONGBOW&g2=ARMOR_PLATE_SET2~1", slots.slice(0, 1));
  check("a zerg's link gives the open party's kits alone", same(zerg[1], { loadout: { head: "HEAD_PLATE_KEEPER" } }), zerg);
  check("a link is on the database's form and past COMP_HASH_MAX none is built",
        /^[A-Za-z0-9_.,=&%:~!*()-]+$/.test(rebuilt) && run("COMP_HASH_MAX") === 8000
        && run("kitHash")(t, Array.from({ length: 60 }, (_, i) => ({ position: i + 1, weapon_id: `W${"X".repeat(150)}${i}`, kit: { loadout: { head: "HEAD_PLATE_KEEPER" } } }))) === "");
  const options = run("slotPickOptions")("long", CATALOG, "2H_LONGBOW");
  check("a slot's picker lists the profile's search, then the open slot while the slot holds a weapon, an extra Enter never picks unasked",
        options[0].key === "2H_LONGBOW" && !options[0].extra && options[options.length - 1].key === "" && options[options.length - 1].role === "any"
        && options[options.length - 1].extra === true && run("slotPickOptions")("long", CATALOG, null).every(o => o.key)
        && same(run("slotPickOptions")("zzz", CATALOG, "2H_LONGBOW").map(o => o.extra), [true]));
}

/* 8 - the boundary: the planner is the address bar and its codec's functions */
{
  const src = fs.readFileSync(path.join(DASH, "_comps.js"), "utf8");
  const calls = (src.match(/\b(loadoutEncode|loadoutDecode|provEncode|provDecode|comboEncode|comboDecode|partyDecode|partyEncode|loGear|loSlotOpen)\(/g) || [])
    .map(c => c.slice(0, -1));
  const tables = src.match(/\b(ICONS|GEAR|SPELLS|WEAPONS|LOADOUTS)\b/g) || [];
  const globals = new Set(calls.concat(tables));
  check("the comps module calls the codec's functions and reads the icons, never the planner's tables or state",
        same([...globals].sort(), ["ICONS", "comboDecode", "comboEncode", "loadoutDecode", "loadoutEncode", "provDecode", "provEncode"]), [...globals]);
  check("the dialog's weapon picker is the profile's combobox", /weaponCombo\(/.test(src) && /slotPickOptions\(/.test(src));
}

console.log(`\n${pass}/${pass + fail} saved comp tests passed`);
process.exit(fail ? 1 : 0);
})();
