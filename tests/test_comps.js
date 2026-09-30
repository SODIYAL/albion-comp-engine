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
 * its policy admits.
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
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js"]) {
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

console.log(`\n${pass}/${pass + fail} saved comp tests passed`);
process.exit(fail ? 1 : 0);
})();
