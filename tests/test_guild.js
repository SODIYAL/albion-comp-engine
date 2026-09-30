/* Guild tests - dashboard/_guild.js.
 *
 * _auth.js, _profile.js and _guild.js run together in a vm context with
 * no document, as the page loads them (the guild module leans on the
 * auth and profile helpers): the helpers and the pure functions load,
 * and each UI block returns before touching the DOM. The helpers run
 * against a stub client that records every query, so what the page sends
 * to Supabase is pinned without a network; tests/test_supabase_rls.mjs
 * pins what the database does with it.
 *
 * Pinned: join codes and guild names validate as the database checks
 * them, the member table sorts admins first and reads each member's
 * lists and roles from the catalog, role coverage counts mains and
 * swaps, the client offers only what the guard would allow (an officer
 * reaches members and callers, the last admin cannot step down), database
 * errors read as sentences, and each helper writes exactly what its
 * policy admits (a role change writes the role column of one row; a
 * refusal that returns no row is reported, never swallowed).
 *
 * Run:  node tests/test_guild.js
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

/* the stub client: PostgREST chains are recorded and answered from REPLY */
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

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

/* a catalog shaped like build.py's */
const CATALOG = {
  MAIN_HOLYSTAFF_AVALON: { name: "Hallowfall", role: "healer", item: "" },
  MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
  "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" },
  "2H_ARCANESTAFF": { name: "Great Arcane Staff", role: "support", item: "" },
};

(async () => {

/* 1 - validation */
{
  const cleanCode = run("cleanJoinCode"), vCode = run("validateJoinCode"), vGuild = run("validateGuild");
  check("a join code is compared trimmed and upper case", cleanCode("  ab12cd34ef ") === "AB12CD34EF");
  check("a join code of ten letters and digits passes", same(vCode("AB12CD34EF"), {}));
  check("an empty join code is asked for", !!vCode("   ").code);
  check("a short or off-form join code is refused", !!vCode("AB12").code && !!vCode("AB12CD34E!").code);
  check("the client's code form is the constant the schema test pins", run("JOIN_CODE_RE").test("AB12CD34EF"));
  check("a guild needs a name and a server",
        !!vGuild({ name: "  ", albionServer: "europe" }).name
        && !!vGuild({ name: "Zaddy", albionServer: "narnia" }).albionServer
        && same(vGuild({ name: " Zaddy Guild ", albionServer: "asia" }), {}));
  check("a guild name is bounded like an account name (ACCOUNT_NAME_MAX)",
        !!vGuild({ name: "x".repeat(run("ACCOUNT_NAME_MAX") + 1), albionServer: "asia" }).name
        && same(vGuild({ name: "x".repeat(run("ACCOUNT_NAME_MAX")), albionServer: "asia" }), {}));
  check("the roles, in rank order", same(run("GUILD_ROLES"), ["member", "caller", "officer", "admin"]));
}

/* 2 - the member table */
{
  const rows = run("memberRows");
  const members = [
    { user_id: "u-c", role: "member", created_at: "2026-09-02", profile: { albion_name: "Cee", display_name: null, albion_server: "asia" } },
    { user_id: "u-a", role: "admin", created_at: "2026-09-01", profile: { albion_name: "AyAO", display_name: "Ay", albion_server: "asia" } },
    { user_id: "u-b", role: "member", created_at: "2026-09-03", profile: { albion_name: "Bee", display_name: "", albion_server: null } },
    { user_id: "u-o", role: "officer", created_at: "2026-09-04", profile: null },
    { user_id: "u-x", role: "warlord", created_at: "2026-09-05", profile: { albion_name: "Ex" } },
  ];
  const weapons = [
    { user_id: "u-c", weapon_id: "MAIN_MACE_HELL", preference: "secondary", sort_order: 1 },
    { user_id: "u-c", weapon_id: "MAIN_HOLYSTAFF_AVALON", preference: "main", sort_order: 0 },
    { user_id: "u-a", weapon_id: "2H_LONGBOW", preference: "main", sort_order: 0 },
    { user_id: "u-a", weapon_id: "2H_RENAMED", preference: "main", sort_order: 1 },
  ];
  const table = rows(members, weapons, CATALOG);
  check("admins first, then officers, then members by name; a profile-less member reads Unnamed",
        same(table.map(r => `${r.role}:${r.name}`), ["admin:Ay", "officer:Unnamed", "member:Bee", "member:Cee", "member:Ex"]),
        table.map(r => `${r.role}:${r.name}`));
  const c = table.find(r => r.userId === "u-c");
  check("a member's lists read mains first in saved order, and the roles they cover from the catalog",
        same(c.lists, { main: ["MAIN_HOLYSTAFF_AVALON"], secondary: ["MAIN_MACE_HELL"] })
        && same(c.roles, { main: ["healer"], secondary: ["frontline"] }), c);
  check("the display name names the row and the Albion name rides beside it",
        table[0].name === "Ay" && table[0].albion === "AyAO" && table[0].server === "asia");
  check("a role the client does not know reads as member, the weakest",
        table.find(r => r.userId === "u-x").role === "member");
  const cov = run("roleCoverage")(table);
  check("coverage counts members per role by their mains, and swaps beside",
        cov.healer.main === 1 && cov.frontline.main === 0 && cov.frontline.also === 1 && cov.dps.main === 1
        && cov.support.main === 0, cov);
  check("no members, no coverage", same(run("roleCoverage")([]), { frontline: { main: 0, also: 0 }, support: { main: 0, also: 0 }, dps: { main: 0, also: 0 }, healer: { main: 0, also: 0 } }));
}

/* 3 - what the client offers: the guard's rules, never more */
{
  const powers = run("memberPowers");
  const member = { role: "member" }, caller = { role: "caller" }, officer = { role: "officer" }, admin = { role: "admin" };
  check("a member only leaves", same(powers("member", true, member, 2), { roles: [], remove: true, removeLabel: "Leave" })
        && powers("member", false, admin, 2).remove === false && powers("member", false, member, 2).roles.length === 0);
  check("an officer sets members and callers between those two roles, and removes them",
        same(powers("officer", false, member, 1).roles, ["member", "caller"])
        && same(powers("officer", false, caller, 1).roles, ["member", "caller"])
        && powers("officer", false, caller, 1).remove === true);
  check("an officer never reaches an officer or an admin",
        powers("officer", false, officer, 1).roles.length === 0 && powers("officer", false, officer, 1).remove === false
        && powers("officer", false, admin, 1).roles.length === 0 && powers("officer", false, admin, 1).remove === false);
  check("an admin sets any role and removes anyone",
        same(powers("admin", false, member, 1).roles, ["member", "caller", "officer", "admin"])
        && powers("admin", false, officer, 1).remove === true);
  check("the last admin can neither be changed nor removed, nor leave",
        powers("admin", false, admin, 1).roles.length === 0 && powers("admin", false, admin, 1).remove === false
        && powers("admin", true, admin, 1).remove === false);
  check("with a second admin, an admin may step down or leave",
        powers("admin", false, admin, 2).roles.length === 4 && powers("admin", true, admin, 2).remove === true);
}

/* 4 - error wording */
{
  const msg = run("guildErrorMessage"), M = run("GUILD_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["not signed in (client)", { code: "not_signed_in", message: "not signed in" }, M.signedOut],
    ["not signed in (create_guild)", { code: "42501", message: "sign in to create a guild" }, M.signedOut],
    ["expired session", { code: "PGRST301", message: "JWT expired" }, M.session],
    ["table missing (migration not applied)", { code: "PGRST205", message: "Could not find the table" }, M.missing],
    ["function missing (migration not applied)", { code: "PGRST202", message: "Could not find the function" }, M.missing],
    ["no guild has the code", { code: "P0002", message: "no guild has this join code" }, M.noCode],
    ["the name exists on the server", { code: "23505", message: "duplicate key value violates unique constraint" }, M.taken],
    ["the last admin", { code: "23514", message: "a guild keeps at least one admin" }, M.lastAdmin],
    ["too many guilds", { code: "23514", message: "an account belongs to at most 20 guilds" }, M.tooManyGuilds],
    ["a full guild", { code: "23514", message: "a guild holds at most 500 members" }, M.guildFull],
    ["an officer's reach", { code: "42501", message: "an officer manages members and callers only" }, M.officerReach],
    ["a policy refusal", { code: "42501", message: "permission denied for table guilds" }, M.refused],
    ["no row came back", { code: "refused", message: "the server refused the change" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: the bounds in the sentences are the bounds in force",
        M.tooManyGuilds.includes(String(run("GUILDS_MAX"))) && M.guildFull.includes(String(run("GUILD_MEMBERS_MAX"))));
}

/* 5 - what the helpers send */
{
  const find = (table) => CALLS.find(c => c.table === table);
  const has = (ops, ...want) => ops.some(o => want.every((w, i) => same(o[i], w)));

  CALLS.length = 0;
  REPLY.guild_members = { data: [{ role: "admin", created_at: "x", guild: { id: "g1", name: "Z", albion_server: "asia" } },
                                 { role: "member", created_at: "y", guild: null }], error: null };
  const mine = await run("loadMyGuilds")();
  let q = find("guild_members");
  check("loadMyGuilds reads the caller's memberships with their guilds, oldest first",
        has(q.ops, "eq", "user_id", "u-me") && q.ops.some(o => o[0] === "select" && /guild:guilds\(/.test(o[1]))
        && has(q.ops, "order", "created_at"), q.ops);
  check("loadMyGuilds drops a membership whose guild is unreadable", mine.length === 1 && mine[0].guild.id === "g1");

  CALLS.length = 0;
  REPLY.guild_members = { data: [], error: null };
  await run("loadGuildMembers")("g1");
  q = find("guild_members");
  check("loadGuildMembers reads one guild's members with their profiles",
        has(q.ops, "eq", "guild_id", "g1") && q.ops.some(o => o[0] === "select" && /profile:profiles\(/.test(o[1])), q.ops);

  CALLS.length = 0;
  REPLY.player_weapons = { data: [], error: null };
  await run("loadMembersWeapons")(["u-a", "u-c"]);
  q = find("player_weapons");
  check("loadMembersWeapons reads those players' lists in saved order",
        has(q.ops, "in", "user_id", ["u-a", "u-c"]) && has(q.ops, "order", "sort_order"), q.ops);
  CALLS.length = 0;
  check("loadMembersWeapons asks nothing for no players", same(await run("loadMembersWeapons")([]), []) && CALLS.length === 0);

  CALLS.length = 0;
  REPLY.guild_join_codes = { data: null, error: null };
  const none = await run("loadJoinCode")("g1");
  q = find("guild_join_codes");
  check("loadJoinCode reads the code through the view, one row or none",
        has(q.ops, "eq", "guild_id", "g1") && q.ops.some(o => o[0] === "maybeSingle") && none === null, q.ops);

  CALLS.length = 0;
  REPLY["rpc:create_guild"] = { data: { id: "g2", name: "New" }, error: null };
  await run("createGuild")({ name: "  New ", albionServer: "europe" });
  let r = CALLS.find(c => c.rpc);
  check("createGuild calls create_guild with the trimmed name and the server",
        r.rpc === "create_guild" && same(r.args, { name: "New", albion_server: "europe" }), r);

  CALLS.length = 0;
  REPLY["rpc:join_guild"] = { data: { id: "g1" }, error: null };
  await run("joinGuild")(" ab12cd34ef ");
  r = CALLS.find(c => c.rpc);
  check("joinGuild calls join_guild with the cleaned code", r.rpc === "join_guild" && same(r.args, { code: "AB12CD34EF" }), r);

  CALLS.length = 0;
  REPLY.guild_members = { data: { user_id: "u-c", role: "caller" }, error: null };
  await run("setMemberRole")("g1", "u-c", "caller");
  q = find("guild_members");
  const upd = q.ops.find(o => o[0] === "update");
  check("setMemberRole writes exactly the role column of one member's row",
        upd && same(Object.keys(upd[1]), ["role"]) && upd[1].role === "caller"
        && has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "eq", "user_id", "u-c"), q.ops);

  CALLS.length = 0;
  REPLY.guild_members = { data: null, error: null };
  let refused = null;
  try { await run("setMemberRole")("g1", "u-a", "member"); } catch (e) { refused = e; }
  check("a change the policy or guard refused (no row back) is reported, never swallowed",
        refused && refused.code === "refused");

  CALLS.length = 0;
  REPLY.guild_members = { data: [{ user_id: "u-c" }], error: null };
  await run("removeMember")("g1", "u-c");
  q = find("guild_members");
  check("removeMember deletes one member's row and reads it back",
        q.ops.some(o => o[0] === "delete") && has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "eq", "user_id", "u-c")
        && q.ops.some(o => o[0] === "select"), q.ops);
  CALLS.length = 0;
  await run("leaveGuild")("g1");
  q = find("guild_members");
  check("leaveGuild removes the caller's own row", has(q.ops, "eq", "user_id", "u-me"), q.ops);
  CALLS.length = 0;
  REPLY.guild_members = { data: [], error: null };
  refused = null;
  try { await run("removeMember")("g1", "u-a"); } catch (e) { refused = e; }
  check("a removal the policy refused (no row back) is reported", refused && refused.code === "refused");

  CALLS.length = 0;
  REPLY.guilds = { data: { id: "g1", name: "Renamed" }, error: null };
  await run("renameGuild")("g1", " Renamed ");
  q = find("guilds");
  const ren = q.ops.find(o => o[0] === "update");
  check("renameGuild writes exactly the trimmed name of one guild",
        ren && same(ren[1], { name: "Renamed" }) && has(q.ops, "eq", "id", "g1"), q.ops);

  CALLS.length = 0;
  REPLY.guilds = { data: [{ id: "g1" }], error: null };
  REPLY.guild_join_codes = { data: { join_code: "NEW0000000" }, error: null };
  const code = await run("renewJoinCode")("g1");
  q = find("guilds");
  const renew = q.ops.find(o => o[0] === "update");
  check("renewJoinCode writes any value to join_code (the guard replaces it) and reads the new code through the view",
        renew && same(Object.keys(renew[1]), ["join_code"]) && has(q.ops, "eq", "id", "g1")
        && !!find("guild_join_codes") && code === "NEW0000000", q.ops);

  CALLS.length = 0;
  REPLY.guilds = { data: [{ id: "g1" }], error: null };
  await run("deleteGuild")("g1");
  q = find("guilds");
  check("deleteGuild deletes one guild and reads the row back",
        q.ops.some(o => o[0] === "delete") && has(q.ops, "eq", "id", "g1") && q.ops.some(o => o[0] === "select"), q.ops);

  check("no helper writes user_id, guild ids or timestamps",
        !/user_id:\s|created_by|created_at:\s|updated_at/.test(fs.readFileSync(path.join(DASH, "_guild.js"), "utf8")
          .split("/* --------------------------------------------------------------- pure */")[0]
          .replace(/\.eq\("user_id"|\.in\("user_id"|select\([^)]*\)/g, "")));
}

console.log(`\n${pass}/${pass + fail} guild tests passed`);
process.exit(fail ? 1 : 0);
})();
