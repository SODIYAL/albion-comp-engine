/* Player-profile tests - dashboard/_profile.js.
 *
 * _auth.js and _profile.js run together in a vm context with no document,
 * as the page loads them (the profile module leans on the auth helpers):
 * the helpers and the pure functions load, and each UI block returns
 * before touching the DOM. The helpers run against a stub client that
 * records every query, so what the page sends to Supabase is pinned
 * without a network; tests/test_supabase_rls.mjs pins what the database
 * does with it.
 *
 * Pinned: the weapon lists read and write in one order (mains first), a
 * key the catalog no longer holds is kept, search finds weapons by the
 * words players type and never offers a listed or removed line, roles
 * derive from the catalog, database errors read as sentences, and a save
 * writes exactly the two name columns of the caller's own row.
 *
 * Run:  node tests/test_profile.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");
const DATASET = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "pipeline", "out", "dataset-latest.json"), "utf8"));

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* the stub client: PostgREST chains are recorded and answered from REPLY */
const CALLS = [];
const REPLY = {};
let SESSION = { user: { id: "u-1", email: "p@example.com" } };
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
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: [], error: null });
  },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

/* a catalog shaped like build.py's: names from the dataset, a stand-in
   role (the real one is the engine's role_class, pinned by the layout
   test on the built page) */
const CATALOG = {};
for (const [k, w] of Object.entries(DATASET.weapons)) {
  CATALOG[k] = { name: w.display_name || k, role: "dps", item: "" };
  if (w.removed) CATALOG[k].removed = true;
}
Object.assign(CATALOG.MAIN_HOLYSTAFF_AVALON, { role: "healer" });
Object.assign(CATALOG.MAIN_MACE_HELL, { role: "frontline" });

(async () => {

/* 1 - the weapon lists */
{
  const lists = run("weaponLists");
  const rows = [
    { weapon_id: "MAIN_MACE_HELL", preference: "secondary", sort_order: 2 },
    { weapon_id: "MAIN_HOLYSTAFF_AVALON", preference: "main", sort_order: 0 },
    { weapon_id: "2H_ICECRYSTAL_UNDEAD", preference: "main", sort_order: 1 },
  ];
  check("saved rows read back as two lists in saved order",
        same(lists(rows), { main: ["MAIN_HOLYSTAFF_AVALON", "2H_ICECRYSTAL_UNDEAD"], secondary: ["MAIN_MACE_HELL"] }),
        lists(rows));
  check("a repeated key keeps its first place",
        same(lists([...rows, { weapon_id: "MAIN_HOLYSTAFF_AVALON", preference: "secondary", sort_order: 9 }]).secondary,
             ["MAIN_MACE_HELL"]));
  check("an unknown preference reads as secondary, the weaker claim",
        same(lists([{ weapon_id: "2H_AXE", preference: "tank", sort_order: 0 }]), { main: [], secondary: ["2H_AXE"] }));
  check("no rows read as two empty lists",
        same(lists(null), { main: [], secondary: [] }) && same(lists([]), { main: [], secondary: [] }));

  const payload = run("weaponPayload");
  const L = { main: ["A1", "A2"], secondary: ["B1"] };
  check("the save payload lists mains first, each list in its order",
        same(payload(L), [{ weapon_id: "A1", preference: "main" }, { weapon_id: "A2", preference: "main" },
                          { weapon_id: "B1", preference: "secondary" }]));
  const saved = payload(L).map((r, i) => ({ ...r, sort_order: i }));
  check("what a save writes reads back as the same lists", same(lists(saved), L));
  const sameLists = run("sameWeaponLists");
  check("list equality sees order and preference",
        sameLists(L, { main: ["A1", "A2"], secondary: ["B1"] })
        && !sameLists(L, { main: ["A2", "A1"], secondary: ["B1"] })
        && !sameLists(L, { main: ["A1"], secondary: ["A2", "B1"] }));

  const info = run("weaponInfo");
  const unknown = info(CATALOG, "2H_RENAMED_LINE");
  check("a key the catalog no longer holds is kept and shown as unknown",
        unknown.known === false && unknown.name === "2H_RENAMED_LINE" && unknown.role === null, unknown);
  check("a known key carries its name and role",
        same(info(CATALOG, "MAIN_HOLYSTAFF_AVALON"),
             { key: "MAIN_HOLYSTAFF_AVALON", name: "Hallowfall", role: "healer", item: "", known: true, removed: false }));
}

/* 2 - search */
{
  const search = (q, exclude) => vm.runInContext("weaponSearch", ctx)(q, CATALOG, new Set(exclude || []));
  const names = hits => hits.map(h => h.name);
  check("an exact name ranks first", names(search("Hallowfall"))[0] === "Hallowfall", names(search("Hallowfall")));
  check("a prefix finds the weapon (perma -> Permafrost Prism)",
        names(search("perma"))[0] === "Permafrost Prism", names(search("perma")));
  check("the words of a name can each be started (great arc -> Great Arcane Staff)",
        names(search("great arc")).includes("Great Arcane Staff"), names(search("great arc")));
  check("a fragment inside a name finds it (fall -> Hallowfall)",
        names(search("fall")).includes("Hallowfall"), names(search("fall")));
  check("search ignores case and surrounding spaces",
        same(names(search("  HALLOWFALL ")), names(search("hallowfall"))));
  check("a weapon already listed is never offered",
        !search("hallow", ["MAIN_HOLYSTAFF_AVALON"]).some(h => h.key === "MAIN_HOLYSTAFF_AVALON"));
  const removedKey = Object.keys(CATALOG).find(k => CATALOG[k].removed);
  check("a line that left the game is never offered",
        !!removedKey && !search(CATALOG[removedKey].name).some(h => h.key === removedKey), removedKey);
  check("at most eight results", search("a").length === run("WEAPON_SEARCH_LIMIT") && run("WEAPON_SEARCH_LIMIT") === 8);
  check("an empty query offers nothing", search("").length === 0 && search("   ").length === 0);
  check("nothing matching offers nothing", search("zzzzqqq").length === 0);
  check("every result is a catalog key of the database's form",
        search("staff").every(h => /^[A-Z0-9_]{1,64}$/.test(h.key) && CATALOG[h.key]));
}

/* 3 - roles derive from the catalog */
{
  const roles = run("rolesCovered");
  check("roles come from the catalog's role class, in roster order",
        same(roles({ main: ["2H_ICECRYSTAL_UNDEAD", "MAIN_HOLYSTAFF_AVALON"], secondary: ["MAIN_MACE_HELL"] }, CATALOG),
             { main: ["dps", "healer"], secondary: ["frontline"] }));
  check("a role both lists cover counts as main",
        same(roles({ main: ["MAIN_HOLYSTAFF_AVALON"], secondary: ["MAIN_HOLYSTAFF_AVALON"] }, CATALOG).secondary, []));
  check("an unknown key adds no role", same(roles({ main: ["2H_GONE"], secondary: [] }, CATALOG), { main: [], secondary: [] }));
  check("every role class has a caller's word",
        same(Object.keys(run("ROLE_NAMES")).sort(), ["dps", "frontline", "healer", "support"]));
}

/* 4 - names */
{
  const clean = run("cleanName");
  check("a name is stored trimmed, and empty as null",
        clean("  Zaddy ") === "Zaddy" && clean("") === null && clean("   ") === null && clean(null) === null);
}

/* 5 - error wording */
{
  const msg = run("profileErrorMessage"), M = run("PROFILE_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["not signed in (client)", { code: "not_signed_in", message: "not signed in" }, M.signedOut],
    ["not signed in (set_my_weapons)", { code: "42501", message: "sign in to save weapons" }, M.signedOut],
    ["expired session", { code: "PGRST301", message: "JWT expired" }, M.session],
    ["table missing (migration not applied)", { code: "PGRST205", message: "Could not find the table" }, M.missing],
    ["function missing (migration not applied)", { code: "PGRST202", message: "Could not find the function" }, M.missing],
    ["no profile row", { code: "PGRST116", message: "0 rows" }, M.noRow],
    ["refused by a policy or grant", { code: "42501", message: "permission denied for table profiles" }, M.denied],
    ["over the weapon bound", { code: "23514", message: "a player lists at most 50 weapons" }, M.tooMany],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
    ["a weapon listed twice", { code: "21000", message: "ON CONFLICT DO UPDATE command cannot affect row a second time" }, M.duplicate],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: an unknown failure carries the server's message",
        /Something went wrong: .*boom/.test(msg({ code: "XX000", message: "boom" })));
  check("error wording: the bound in the sentence is the bound in force",
        M.tooMany.includes(String(run("WEAPONS_MAX"))));
}

/* 6 - what the helpers send */
{
  CALLS.length = 0;
  REPLY.profiles = { data: { id: "u-1", albion_name: "ZaddyAO", albion_server: "europe", display_name: null }, error: null };
  const row = await run("saveMyProfile")({ albionName: "ZaddyAO", albionServer: "europe", displayName: null });
  const q = CALLS.find(c => c.table === "profiles");
  const update = q && q.ops.find(o => o[0] === "update");
  check("saveMyProfile writes exactly the name, server and display name columns",
        !!update && same(Object.keys(update[1]).sort(), ["albion_name", "albion_server", "display_name"])
        && update[1].albion_name === "ZaddyAO" && update[1].albion_server === "europe"
        && update[1].display_name === null, q && q.ops);
  check("saveMyProfile targets the caller's own row and reads it back",
        q.ops.some(o => o[0] === "eq" && o[1] === "id" && o[2] === "u-1")
        && q.ops.some(o => o[0] === "select") && q.ops.some(o => o[0] === "single"), q.ops);
  check("saveMyProfile returns the saved row", row && row.albion_name === "ZaddyAO");

  /* the dialog's baseline is the row as the database holds it, read on
     every opening, never the sign-up metadata */
  CALLS.length = 0;
  const fresh = await run("loadMyProfile")();
  const pr = CALLS.find(c => c.table === "profiles");
  check("loadMyProfile reads the caller's own row, one row, writing nothing",
        !!pr && pr.ops.some(o => o[0] === "select") && pr.ops.some(o => o[0] === "eq" && o[1] === "id" && o[2] === "u-1")
        && pr.ops.some(o => o[0] === "single") && !pr.ops.some(o => ["update", "insert", "upsert", "delete"].includes(o[0])), pr && pr.ops);
  check("loadMyProfile returns the row", fresh && fresh.albion_name === "ZaddyAO");
  REPLY.profiles = { data: null, error: { code: "PGRST301", message: "JWT expired" } };
  let lost = null;
  try { await run("loadMyProfile")(); } catch (e) { lost = e; }
  check("a failed profile read throws (the dialog then locks the names), never answers with nothing",
        !!lost && lost.code === "PGRST301");
  REPLY.profiles = { data: { id: "u-1", albion_name: "ZaddyAO", albion_server: "europe", display_name: null }, error: null };

  CALLS.length = 0;
  REPLY.player_weapons = { data: [{ weapon_id: "2H_AXE", preference: "main", sort_order: 0 }], error: null };
  const got = await run("loadMyWeapons")();
  const w = CALLS.find(c => c.table === "player_weapons");
  check("loadMyWeapons reads the caller's rows in saved order",
        w.ops.some(o => o[0] === "select" && /weapon_id/.test(o[1]) && /preference/.test(o[1]) && /sort_order/.test(o[1]))
        && w.ops.some(o => o[0] === "eq" && o[1] === "user_id" && o[2] === "u-1")
        && w.ops.some(o => o[0] === "order" && o[1] === "sort_order"), w.ops);
  check("loadMyWeapons returns the rows", got.length === 1 && got[0].weapon_id === "2H_AXE");

  CALLS.length = 0;
  await run("saveMyWeapons")({ main: ["A1"], secondary: ["B1"] });
  const r = CALLS.find(c => c.rpc);
  check("saveMyWeapons saves the whole list through set_my_weapons, mains first",
        r && r.rpc === "set_my_weapons"
        && same(r.args, { weapons: [{ weapon_id: "A1", preference: "main" }, { weapon_id: "B1", preference: "secondary" }] }),
        r);

  REPLY["rpc:set_my_weapons"] = { data: null, error: { code: "23514", message: "a player lists at most 50 weapons" } };
  let thrown = null;
  try { await run("saveMyWeapons")({ main: ["A1"], secondary: [] }); } catch (e) { thrown = e; }
  check("saveMyWeapons throws the server's error (the dialog words it)", thrown && thrown.code === "23514");
  delete REPLY["rpc:set_my_weapons"];

  SESSION = null;
  thrown = null;
  const sent = CALLS.length;
  try { await run("saveMyProfile")({ albionName: "Z", displayName: null }); } catch (e) { thrown = e; }
  check("a helper without a session refuses before sending",
        thrown && thrown.code === "not_signed_in" && CALLS.length === sent);
  SESSION = { user: { id: "u-1", email: "p@example.com" } };
}

console.log(`\n${pass}/${pass + fail} profile tests passed`);
process.exit(fail ? 1 : 0);

})().catch(e => { console.error(e); process.exit(1); });
