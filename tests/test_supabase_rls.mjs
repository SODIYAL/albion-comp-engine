/* Row-level security tests for supabase/migrations/.
 *
 * Every migration runs in file order against a real Postgres (PGlite:
 * Postgres compiled to WebAssembly) beside a stand-in for the Supabase
 * platform: the auth schema and auth.uid(), the API roles, and the
 * project's default privileges (pg_default_acl read from the project:
 * every new table and function in public is granted to anon and
 * authenticated). Each case runs the way PostgREST runs a request: one
 * transaction, an API role, the signed-in user's JWT claims.
 *
 * Pinned: a signed-in player reads and writes their own rows only and
 * writes only the columns a form edits; anon reaches nothing; the sign-up
 * trigger still fires with its EXECUTE revoked and stores names trimmed;
 * the weapon list saves in one transaction, bounded, keeping created_at
 * across saves; the migrations apply twice without error.
 *
 * Needs @electric-sql/pglite, installed for the test run only:
 *   npm install --no-save @electric-sql/pglite@0.5.8
 *
 * Run:  node tests/test_supabase_rls.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MIGRATIONS = path.join(HERE, "..", "supabase", "migrations");

let PGlite;
try {
  ({ PGlite } = await import("@electric-sql/pglite"));
} catch (e) {
  console.log("FAIL  @electric-sql/pglite is not installed. Run:\n"
    + "      npm install --no-save @electric-sql/pglite@0.5.8");
  process.exit(1);
}

let pass = 0, fail = 0;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}

/* the parts of the Supabase platform the migrations lean on */
const PLATFORM = `
  create role anon nologin noinherit;
  create role authenticated nologin noinherit;
  create role service_role nologin noinherit bypassrls;
  create role supabase_auth_admin nologin noinherit;
  create schema auth;
  create table auth.users (id uuid primary key, email text, raw_user_meta_data jsonb);
  create function auth.uid() returns uuid language sql stable as $$
    select nullif(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub', '')::uuid
  $$;
  grant usage on schema auth to anon, authenticated, service_role, supabase_auth_admin;
  grant execute on function auth.uid() to anon, authenticated, service_role, supabase_auth_admin;
  grant select, insert, delete on auth.users to supabase_auth_admin;
  grant usage on schema public to anon, authenticated, service_role, supabase_auth_admin;
  alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
  alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
  alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
`;

const A = "00000000-0000-4000-8000-00000000000a";
const B = "00000000-0000-4000-8000-00000000000b";
const C = "00000000-0000-4000-8000-00000000000c";
const D = "00000000-0000-4000-8000-00000000000d";
const E = "00000000-0000-4000-8000-00000000000e";

const db = new PGlite();
await db.exec(PLATFORM);

const files = fs.readdirSync(MIGRATIONS).filter(f => f.endsWith(".sql")).sort();
const applyAll = async () => { for (const f of files) await db.exec(fs.readFileSync(path.join(MIGRATIONS, f), "utf8")); };

/* one request: its own transaction, role and claims */
async function run(role, sub, sql, params = []) {
  return db.transaction(async tx => {
    await tx.exec(`set local role ${role}`);
    await tx.query("select set_config('request.jwt.claims', $1, true)",
                   [sub ? JSON.stringify({ sub, role }) : ""]);
    return tx.query(sql, params);
  });
}
async function code(role, sub, sql, params = []) {
  try { await run(role, sub, sql, params); return "ok"; }
  catch (e) { return e.code || String(e.message); }
}
const rows = async (role, sub, sql, params) => (await run(role, sub, sql, params)).rows;
const affected = async (role, sub, sql, params) => (await run(role, sub, sql, params)).affectedRows;
const signUp = (id, meta) => run("supabase_auth_admin", null,
  "insert into auth.users (id, email, raw_user_meta_data) values ($1, $2, $3)",
  [id, `${id.slice(-1)}@example.com`, JSON.stringify(meta)]);
const W = list => JSON.stringify(list.map(([weapon_id, preference]) => ({ weapon_id, preference })));
const saveWeapons = (sub, list) => rows("authenticated", sub,
  "select weapon_id, preference, sort_order, id, created_at from public.set_my_weapons($1::jsonb)", [W(list)]);

try {

/* 1 - the migrations */
{
  let err = null;
  try { await applyAll(); } catch (e) { err = e.message; }
  check(`the ${files.length} migrations apply in file order`, err === null, err);
  err = null;
  try { await applyAll(); } catch (e) { err = e.message; }
  check("the migrations apply a second time without error (idempotent)", err === null, err);
}

/* 2 - sign-up: the trigger fires with its EXECUTE revoked, names stored clean */
{
  await signUp(A, { albion_name: "  ZaddyAO ", display_name: "" });
  await signUp(B, { albion_name: "Bob", display_name: "Bobby" });
  await signUp(C, { albion_name: "x".repeat(70) });
  const a = (await db.query("select * from public.profiles where id = $1", [A])).rows[0];
  check("sign-up creates the profile row (the trigger runs with its definer's rights, EXECUTE revoked)", !!a);
  check("sign-up stores the Albion name trimmed and an empty display name as null",
        a && a.albion_name === "ZaddyAO" && a.display_name === null, a);
  const c = (await db.query("select albion_name from public.profiles where id = $1", [C])).rows[0];
  check("sign-up cuts an oversized name to the 64-character bound instead of failing",
        c && c.albion_name.length === 64, c && c.albion_name.length);
  await signUp(D, { albion_name: "Dee", albion_server: "europe" });
  await signUp(E, { albion_name: "Eve", albion_server: "narnia" });
  const server = async id => (await db.query("select albion_server from public.profiles where id = $1", [id])).rows[0];
  check("sign-up stores the character's server", (await server(D)).albion_server === "europe");
  check("sign-up stores a server off the list as null instead of failing",
        (await server(E)).albion_server === null);
  check("a profile from before the server, or without one, reads null", (await server(A)).albion_server === null);
}

/* 3 - profiles: own row only, the two name columns only */
{
  const mine = await rows("authenticated", A, "select id from public.profiles");
  check("a player reads only their own profile", mine.length === 1 && mine[0].id === A, mine);
  const before = (await db.query("select updated_at from public.profiles where id = $1", [A])).rows[0].updated_at;
  const n = await affected("authenticated", A,
    "update public.profiles set albion_name = $1, display_name = $2 where id = $3", ["ZaddyAO", "Zaddy", A]);
  const after = (await db.query("select * from public.profiles where id = $1", [A])).rows[0];
  check("a player updates their own two names", n === 1 && after.display_name === "Zaddy", { n, after });
  check("updated_at follows the change (the trigger runs with its EXECUTE revoked)",
        after.updated_at > before, { before, after: after.updated_at });
  check("a player cannot update another player's profile",
        await affected("authenticated", A, "update public.profiles set display_name = 'x' where id = $1", [B]) === 0);
  check("a player records their server",
        await affected("authenticated", A, "update public.profiles set albion_server = 'asia' where id = $1", [A]) === 1
        && (await db.query("select albion_server from public.profiles where id = $1", [A])).rows[0].albion_server === "asia");
  check("the database refuses a server off the game's three",
        await code("authenticated", A, "update public.profiles set albion_server = 'narnia' where id = $1", [A]) === "23514");
  check("a player cannot set another player's server",
        await affected("authenticated", A, "update public.profiles set albion_server = 'asia' where id = $1", [B]) === 0);
  for (const col of ["avatar_url = 'x'", "created_at = now()", "updated_at = now()", `id = '${C}'`]) {
    check(`a player cannot write ${col.split(" ")[0]} (column grants)`,
          await code("authenticated", A, `update public.profiles set ${col} where id = $1`, [A]) === "42501");
  }
  for (const [label, value] of [["an untrimmed", " Zaddy "], ["an empty", ""], ["a 65-character", "y".repeat(65)]]) {
    check(`the database refuses ${label} Albion name`,
          await code("authenticated", A, "update public.profiles set albion_name = $1 where id = $2", [value, A]) === "23514");
    check(`the database refuses ${label} display name`,
          await code("authenticated", A, "update public.profiles set display_name = $1 where id = $2", [value, A]) === "23514");
  }
  check("a player cannot insert a profile for someone else",
        await code("authenticated", A, "insert into public.profiles (id) values ($1)", [C]) === "42501");
  check("a player cannot set timestamps on an inserted profile",
        await code("authenticated", A, "insert into public.profiles (id, created_at) values ($1, now())", [A]) === "42501");
  check("anon reads no profile", await code("anon", null, "select * from public.profiles") === "42501");
  check("anon writes no profile",
        await code("anon", null, "update public.profiles set display_name = 'x'") === "42501");
  check("no API role calls the sign-up trigger function",
        await code("authenticated", A, "select public.handle_new_user()") === "42501"
        && await code("anon", null, "select public.handle_new_user()") === "42501");
}

/* 4 - player_weapons through set_my_weapons */
{
  const first = await saveWeapons(A, [["MAIN_HOLYSTAFF_AVALON", "main"], ["2H_ICECRYSTAL_UNDEAD", "main"],
                                      ["MAIN_MACE_HELL", "secondary"]]);
  check("set_my_weapons saves the list in order, mains first",
        first.map(r => `${r.weapon_id}:${r.preference}:${r.sort_order}`).join(",")
        === "MAIN_HOLYSTAFF_AVALON:main:0,2H_ICECRYSTAL_UNDEAD:main:1,MAIN_MACE_HELL:secondary:2", first);
  const kept = first.find(r => r.weapon_id === "2H_ICECRYSTAL_UNDEAD");
  const second = await saveWeapons(A, [["2H_ICECRYSTAL_UNDEAD", "main"], ["2H_HAMMER_UNDEAD", "secondary"],
                                       ["MAIN_MACE_HELL", "secondary"]]);
  check("a re-save drops unlisted weapons, adds new ones, re-orders the rest",
        second.map(r => `${r.weapon_id}:${r.preference}:${r.sort_order}`).join(",")
        === "2H_ICECRYSTAL_UNDEAD:main:0,2H_HAMMER_UNDEAD:secondary:1,MAIN_MACE_HELL:secondary:2", second);
  const again = second.find(r => r.weapon_id === "2H_ICECRYSTAL_UNDEAD");
  check("a weapon kept across saves keeps its id and created_at",
        again && again.id === kept.id && +again.created_at === +kept.created_at);

  await saveWeapons(B, [["2H_LONGBOW", "main"]]);
  const bSees = await rows("authenticated", B, "select weapon_id from public.player_weapons");
  check("a player reads only their own weapons", bSees.length === 1 && bSees[0].weapon_id === "2H_LONGBOW", bSees);
  const aAfterB = await rows("authenticated", A, "select weapon_id from public.player_weapons");
  check("another player's save leaves this player's list alone", aAfterB.length === 3, aAfterB);

  check("a direct insert takes its user_id from auth.uid()",
        await code("authenticated", A, "insert into public.player_weapons (weapon_id) values ('2H_BOW')") === "ok"
        && (await db.query("select user_id from public.player_weapons where weapon_id = '2H_BOW'")).rows[0].user_id === A);
  check("a player cannot write the user_id column",
        await code("authenticated", A, "insert into public.player_weapons (user_id, weapon_id) values ($1, '2H_AXE')", [B]) === "42501");
  check("a player cannot rename a listed weapon (weapon_id is not updatable)",
        await code("authenticated", A, "update public.player_weapons set weapon_id = '2H_AXE' where weapon_id = '2H_BOW'") === "42501");
  const before = (await db.query("select updated_at from public.player_weapons where weapon_id = '2H_BOW'")).rows[0].updated_at;
  await run("authenticated", A, "update public.player_weapons set preference = 'secondary' where weapon_id = '2H_BOW'");
  const after = (await db.query("select updated_at, preference from public.player_weapons where weapon_id = '2H_BOW'")).rows[0];
  check("a player changes a weapon's preference; updated_at follows",
        after.preference === "secondary" && after.updated_at > before, after);
  check("a player cannot change or remove another player's weapons",
        await affected("authenticated", A, "update public.player_weapons set sort_order = 9 where user_id = $1", [B]) === 0
        && await affected("authenticated", A, "delete from public.player_weapons where user_id = $1", [B]) === 0);
  check("a player removes their own weapon directly",
        await affected("authenticated", A, "delete from public.player_weapons where weapon_id = '2H_BOW'") === 1);

  const bad = [
    ["a weapon key off the catalog's form", W([["perma", "main"]]), "23514"],
    ["an unknown preference", W([["2H_AXE", "tank"]]), "23514"],
    ["the same weapon twice", W([["2H_AXE", "main"], ["2H_AXE", "secondary"]]), "21000"],
    ["a payload that is not a list", JSON.stringify({ weapon_id: "2H_AXE" }), "22023"],
    ["an entry without a weapon", JSON.stringify([{ preference: "main" }]), "23502"],
  ];
  for (const [label, payload, want] of bad) {
    const got = await code("authenticated", A, "select * from public.set_my_weapons($1::jsonb)", [payload]);
    check(`set_my_weapons refuses ${label} (${want})`, got === want, got);
  }
  const unchanged = await rows("authenticated", A, "select weapon_id from public.player_weapons order by sort_order");
  check("a refused save changes nothing (one transaction)", unchanged.length === 3, unchanged);
}

/* 5 - the 50-row storage bound */
{
  const fifty = Array.from({ length: 50 }, (_, i) => [`W_${String(i).padStart(2, "0")}`, "secondary"]);
  check("fifty weapons save", (await saveWeapons(A, fifty)).length === 50);
  check("re-saving the same fifty passes the bound (rows that exist pass)", (await saveWeapons(A, fifty)).length === 50);
  check("set_my_weapons refuses a fifty-first",
        await code("authenticated", A, "select * from public.set_my_weapons($1::jsonb)", [W([...fifty, ["W_50", "main"]])]) === "23514");
  check("a direct fifty-first insert is refused too (the trigger, not only the function)",
        await code("authenticated", A, "insert into public.player_weapons (weapon_id) values ('W_50')") === "23514");
}

/* 6 - anon and sessionless callers */
{
  check("anon cannot call set_my_weapons",
        await code("anon", null, "select * from public.set_my_weapons('[]'::jsonb)") === "42501");
  check("anon reads no weapons", await code("anon", null, "select * from public.player_weapons") === "42501");
  check("the authenticated role without a user id saves nothing",
        await code("authenticated", null, "select * from public.set_my_weapons('[]'::jsonb)") === "42501");
  check("no API role calls a trigger function",
        await code("authenticated", A, "select public.player_weapons_bound()") === "42501"
        && await code("authenticated", A, "select public.set_updated_at()") === "42501");
}

/* 7 - deleting an account removes its data */
{
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [B]);
  const left = (await db.query(
    "select (select count(*) from public.profiles where id = $1) as p, (select count(*) from public.player_weapons where user_id = $1) as w", [B])).rows[0];
  check("deleting an auth user removes their profile and weapons (cascade)",
        Number(left.p) === 0 && Number(left.w) === 0, left);
}

/* 8 - guilds: creation, the join code, roles, the guard, guild-scoped reads */
{
  const roleOf = (sub, gid) => rows("authenticated", sub, "select private.guild_role_of($1) as r", [gid]).then(r => r[0].r);
  const members = (sub) => rows("authenticated", sub, "select user_id, role from public.guild_members order by role, user_id");
  const codeOf = (sub, gid) => rows("authenticated", sub, "select join_code from public.guild_join_codes where guild_id = $1", [gid]);

  const g = (await rows("authenticated", A, "select * from public.create_guild($1, $2)", ["  Zaddy Guild ", "asia"]))[0];
  check("create_guild makes the guild, trimmed, with a ten-character code, and seats its creator as admin",
        g && g.name === "Zaddy Guild" && g.albion_server === "asia" && /^[A-Z0-9]{10}$/.test(g.join_code)
        && g.created_by === A && await roleOf(A, g.id) === "admin", g);
  check("a guild name is unique on its server, whatever its case",
        await code("authenticated", D, "select * from public.create_guild($1, $2)", ["zaddy guild", "asia"]) === "23505");
  const gd = (await rows("authenticated", D, "select * from public.create_guild($1, $2)", ["Zaddy Guild", "europe"]))[0];
  check("the same name on another server is another guild", gd && gd.id !== g.id);
  check("create_guild refuses a blank name and a server off the list",
        await code("authenticated", D, "select * from public.create_guild($1, $2)", ["   ", "asia"]) === "23514"
        && await code("authenticated", D, "select * from public.create_guild($1, $2)", ["Narnians", "narnia"]) === "23514");
  check("anon and a sessionless caller create nothing",
        await code("anon", null, "select * from public.create_guild('X', 'asia')") === "42501"
        && await code("authenticated", null, "select * from public.create_guild('X', 'asia')") === "42501");

  /* joining by code */
  const joined = (await rows("authenticated", C, "select * from public.join_guild($1)", [` ${g.join_code.toLowerCase()} `]))[0];
  check("join_guild seats the code holder as a member (the code compared trimmed, upper case)",
        joined && joined.id === g.id && await roleOf(C, g.id) === "member", joined);
  check("a wrong code joins nothing",
        await code("authenticated", C, "select * from public.join_guild('NOPE000000')") === "P0002");
  await run("authenticated", C, "select * from public.join_guild($1)", [g.join_code]);
  check("joining again is answered with the guild, and one row stays",
        (await members(C)).filter(m => m.user_id === C).length === 1);
  check("anon and a sessionless caller join nothing",
        await code("anon", null, "select * from public.join_guild($1)", [g.join_code]) === "42501"
        && await code("authenticated", null, "select * from public.join_guild($1)", [g.join_code]) === "42501");
  check("a member cannot seat themself directly (the creator's insert policy alone)",
        await code("authenticated", E, "insert into public.guild_members (guild_id, role) values ($1, 'member')", [g.id]) === "42501"
        && await code("authenticated", E, "insert into public.guild_members (guild_id, role) values ($1, 'admin')", [g.id]) === "42501");
  check("a member cannot write the user_id column",
        await code("authenticated", A, "insert into public.guild_members (guild_id, user_id, role) values ($1, $2, 'member')", [g.id, E]) === "42501");

  /* what a member reads */
  const cSees = await rows("authenticated", C, "select id, name from public.guilds order by name");
  check("a member reads their guild and no other", cSees.length === 1 && cSees[0].id === g.id, cSees);
  check("a member reads the guild's members", same((await members(C)).map(m => m.role), ["admin", "member"]));
  const cProfiles = await rows("authenticated", C, "select id, albion_name from public.profiles order by albion_name");
  check("a member reads co-members' profiles (the guild-scoped policy) and no one else's",
        same(cProfiles.map(p => p.id).sort(), [A, C].sort()), cProfiles);
  const cWeapons = await rows("authenticated", C, "select count(*)::int as n from public.player_weapons where user_id = $1", [A]);
  check("a member reads co-members' weapon lists", cWeapons[0].n === 50, cWeapons);
  const eSees = await rows("authenticated", E, "select id from public.guilds");
  const eProfiles = await rows("authenticated", E, "select id from public.profiles");
  check("an outsider reads neither the guild nor its members' profiles",
        eSees.length === 0 && eProfiles.length === 1 && eProfiles[0].id === E);
  check("a member cannot read the join code; an admin can",
        (await codeOf(C, g.id)).length === 0 && (await codeOf(A, g.id))[0].join_code === g.join_code);
  check("a member cannot rename the guild, change roles or remove others",
        await affected("authenticated", C, "update public.guilds set name = 'Mine' where id = $1", [g.id]) === 0
        && await affected("authenticated", C, "update public.guild_members set role = 'admin' where user_id = $1", [C]) === 0
        && await affected("authenticated", C, "delete from public.guild_members where user_id = $1", [A]) === 0);
  check("anon reads no guild, member or code",
        await code("anon", null, "select * from public.guilds") === "42501"
        && await code("anon", null, "select * from public.guild_members") === "42501"
        && await code("anon", null, "select * from public.guild_join_codes") === "42501");

  /* roles and the guard */
  check("the last admin can neither step down nor leave",
        await code("authenticated", A, "update public.guild_members set role = 'member' where guild_id = $1 and user_id = $2", [g.id, A]) === "23514"
        && await code("authenticated", A, "delete from public.guild_members where guild_id = $1 and user_id = $2", [g.id, A]) === "23514");
  check("an admin promotes a member to officer",
        await affected("authenticated", A, "update public.guild_members set role = 'officer' where guild_id = $1 and user_id = $2", [g.id, C]) === 1
        && await roleOf(C, g.id) === "officer");
  await run("authenticated", D, "select * from public.join_guild($1)", [g.join_code]);
  await run("authenticated", E, "select * from public.join_guild($1)", [g.join_code]);
  check("an officer sets a member to caller",
        await affected("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, D]) === 1);
  check("an officer cannot make an officer or an admin, nor touch one",
        await code("authenticated", C, "update public.guild_members set role = 'admin' where guild_id = $1 and user_id = $2", [g.id, D]) === "42501"
        && await code("authenticated", C, "update public.guild_members set role = 'member' where guild_id = $1 and user_id = $2", [g.id, A]) === "42501"
        && await code("authenticated", C, "delete from public.guild_members where guild_id = $1 and user_id = $2", [g.id, A]) === "42501");
  check("an officer removes a member",
        await affected("authenticated", C, "delete from public.guild_members where guild_id = $1 and user_id = $2", [g.id, E]) === 1);
  check("the role column takes the four roles only",
        await code("authenticated", A, "update public.guild_members set role = 'warlord' where guild_id = $1 and user_id = $2", [g.id, D]) === "23514");
  check("a member leaves",
        await affected("authenticated", D, "delete from public.guild_members where guild_id = $1 and user_id = $2", [g.id, D]) === 1
        && await roleOf(D, g.id) === null);
  const before = (await db.query("select updated_at from public.guild_members where guild_id = $1 and user_id = $2", [g.id, C])).rows[0].updated_at;
  await run("authenticated", A, "update public.guild_members set role = 'admin' where guild_id = $1 and user_id = $2", [g.id, C]);
  const after = (await db.query("select updated_at, role from public.guild_members where guild_id = $1 and user_id = $2", [g.id, C])).rows[0];
  check("an admin makes a second admin; updated_at follows", after.role === "admin" && after.updated_at > before);
  check("with a second admin the first steps down",
        await affected("authenticated", A, "update public.guild_members set role = 'officer' where guild_id = $1 and user_id = $2", [g.id, A]) === 1);
  check("an officer cannot delete the guild; an admin renames it",
        await affected("authenticated", A, "delete from public.guilds where id = $1", [g.id]) === 0
        && await affected("authenticated", C, "update public.guilds set name = 'Zaddy Guild II' where id = $1", [g.id]) === 1);
  for (const col of ["albion_server = 'europe'", "created_by = null", "created_at = now()", "updated_at = now()"]) {
    check(`no member writes ${col.split(" ")[0]} on a guild (column grants)`,
          await code("authenticated", C, `update public.guilds set ${col} where id = $1`, [g.id]) === "42501");
  }
  check("a guild name is trimmed, 1-64 characters",
        await code("authenticated", C, "update public.guilds set name = ' x' where id = $1", [g.id]) === "23514"
        && await code("authenticated", C, "update public.guilds set name = $2 where id = $1", [g.id, "y".repeat(65)]) === "23514");

  /* the join code */
  const renewed = (await rows("authenticated", C, "update public.guilds set join_code = 'CHOSEN0000' where id = $1 returning join_code", [g.id]))[0];
  check("an admin renews the code by writing any value; the guard replaces it with a fresh one",
        renewed && renewed.join_code !== "CHOSEN0000" && renewed.join_code !== g.join_code && /^[A-Z0-9]{10}$/.test(renewed.join_code), renewed);
  check("the old code no longer joins; the new one does",
        await code("authenticated", D, "select * from public.join_guild($1)", [g.join_code]) === "P0002"
        && await code("authenticated", D, "select * from public.join_guild($1)", [renewed.join_code]) === "ok");
  check("an officer reads the code but cannot renew it",
        (await codeOf(A, g.id))[0].join_code === renewed.join_code
        && await affected("authenticated", A, "update public.guilds set join_code = 'X' where id = $1", [g.id]) === 0);

  /* bounds */
  {
    let made = 0, err = "ok";
    for (let i = 0; i < 25 && err === "ok"; i++) {
      err = await code("authenticated", E, "select * from public.create_guild($1, 'asia')", [`E guild ${i}`]);
      if (err === "ok") made++;
    }
    check("an account belongs to at most 20 guilds (the guard)", made === 20 && err === "23514", { made, err });
  }

  /* deletion and cascades */
  check("an admin deletes the guild; its memberships go with it (the cascade passes the guard)",
        await affected("authenticated", C, "delete from public.guilds where id = $1", [g.id]) === 1
        && Number((await db.query("select count(*) from public.guild_members where guild_id = $1", [g.id])).rows[0].count) === 0);

  /* succession: the last admin's account is deleted */
  const gdCode = (await db.query("select join_code from public.guilds where id = $1", [gd.id])).rows[0].join_code;
  await run("authenticated", C, "select * from public.join_guild($1)", [gdCode]);
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [D]);
  const dGuild = (await db.query("select created_by from public.guilds where id = $1", [gd.id])).rows[0];
  check("deleting the creator's account keeps the guild, its created_by null",
        dGuild && dGuild.created_by === null, dGuild);
  check("the longest-standing remaining member becomes admin (succession under the cascade)",
        await roleOf(C, gd.id) === "admin");
  const solo = (await rows("authenticated", A, "select * from public.create_guild($1, $2)", ["Solo", "asia"]))[0];
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [A]);
  check("a guild left with no member goes with its last admin's account",
        Number((await db.query("select count(*) from public.guilds where id = $1", [solo.id])).rows[0].count) === 0);
  check("no API role calls the guard or succession trigger functions",
        await code("authenticated", C, "select public.guild_members_guard()") === "42501"
        && await code("authenticated", C, "select public.guilds_guard()") === "42501"
        && await code("authenticated", C, "select public.guild_members_succession()") === "42501");
  const definers = (await db.query(
    "select n.nspname || '.' || p.proname as f from pg_proc p join pg_namespace n on n.oid = p.pronamespace where p.prosecdef and n.nspname in ('public', 'private') order by 1")).rows.map(r => r.f);
  check("the API schema holds one definer, the sign-up trigger; the helpers live in private",
        same(definers, ["private.guild_id_for_code", "private.guild_member_count", "private.guild_role_of", "public.handle_new_user"]), definers);
  check("anon reaches nothing in the private schema",
        await code("anon", null, "select private.guild_role_of(gen_random_uuid())") === "42501");
  const perm = (await db.query(
    "select tablename, cmd, count(*)::int as n from pg_policies where schemaname = 'public' and permissive = 'PERMISSIVE' group by 1, 2 having count(*) > 1")).rows;
  check("one permissive policy per table and action (lint 0006)", perm.length === 0, perm);
}

} catch (e) {
  fail++;
  console.log("FAIL  the run stopped: " + (e.stack || e.message));
}

await db.close();
console.log(`\n${pass}/${pass + fail} row-level security tests passed`);
process.exit(fail ? 1 : 0);
