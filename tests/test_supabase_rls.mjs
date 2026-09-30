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
  -- the Realtime stand-in: realtime.send writes realtime.messages, which
  -- row-level security keeps from every API role (no policy), as on the
  -- project; the trigger that broadcasts must run with its definer's rights
  create schema realtime;
  create table realtime.messages (id bigserial primary key, topic text, event text, payload jsonb, private boolean, extension text,
                                  inserted_at timestamptz default now());
  alter table realtime.messages enable row level security;
  create function realtime.send(payload jsonb, event text, topic text, private boolean default true) returns void
    language plpgsql as $$
    begin
      begin
        insert into realtime.messages (payload, event, topic, private, extension) values (payload, event, topic, private, 'broadcast');
      exception when others then
        raise warning 'ErrorSendingBroadcastMessage: %', sqlerrm;
      end;
    end $$;
  grant usage on schema realtime to anon, authenticated, service_role;
  grant execute on function realtime.send(jsonb, text, text, boolean) to anon, authenticated, service_role;
  grant insert on realtime.messages to anon, authenticated, service_role;
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
  check("the API schema holds three definers, the sign-up, broadcast and record triggers; the helpers live in private",
        same(definers, ["private.guild_id_for_code", "private.guild_member_count", "private.guild_role_of", "public.attendance_record", "public.handle_new_user", "public.sheet_changed"]), definers);
  check("anon reaches nothing in the private schema",
        await code("anon", null, "select private.guild_role_of(gen_random_uuid())") === "42501");
  const perm = (await db.query(
    "select tablename, cmd, roles::text as roles, count(*)::int as n from pg_policies where schemaname = 'public' and permissive = 'PERMISSIVE' group by 1, 2, 3 having count(*) > 1")).rows;
  check("one permissive policy per table, action and role (lint 0006)", perm.length === 0, perm);
}


/* 9 - saved comps: a guild's templates and slots, written by caller roles */
{
  /* the cast: C is admin of gd (succession); fresh accounts F (a member
     of gd), H (a caller of gd), X (an outsider) */
  const F = "00000000-0000-4000-8000-00000000000f";
  const H = "00000000-0000-4000-8000-000000000010";
  const X = "00000000-0000-4000-8000-000000000011";
  const gd = (await db.query("select id from public.guilds where albion_server = 'europe' and lower(name) = 'zaddy guild'")).rows[0];
  for (const [id, n] of [[F, "Eff"], [H, "Aitch"], [X, "Ex"]]) await signUp(id, { albion_name: n });
  const gdCode2 = (await db.query("select join_code from public.guilds where id = $1", [gd.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gdCode2]);
  await run("authenticated", H, "select * from public.join_guild($1)", [gdCode2]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [gd.id, H]);

  const T = (over = {}) => JSON.stringify(Object.assign({
    guild_id: gd.id, name: " Castle A ", content: "castle", style: "clap", planned_size: 20, notes: "  ",
    share_hash: "c=castle&n=20&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL",
    slots: [{ position: 1, weapon_id: "2H_LONGBOW", role: " ranged ", note: "" },
            { position: 2, weapon_id: "MAIN_MACE_HELL", role: null, note: " engage first " }]
  }, over));
  const save = (sub, payload) => rows("authenticated", sub, "select * from public.save_comp_template($1::jsonb)", [payload]);
  const saveCode = (sub, payload) => code("authenticated", sub, "select * from public.save_comp_template($1::jsonb)", [payload]);
  const slotsOf = (sub, id) => rows("authenticated", sub, "select position, weapon_id, role, note from public.comp_template_slots where template_id = $1 order by position", [id]);

  const t = (await save(H, T()))[0];
  check("a caller saves a comp: the template trimmed, empty notes null, its slots written with it",
        t && t.name === "Castle A" && t.notes === null && t.style === "clap" && t.created_by === H && t.updated_by === H
        && same(await slotsOf(H, t.id), [{ position: 1, weapon_id: "2H_LONGBOW", role: "ranged", note: null },
                                         { position: 2, weapon_id: "MAIN_MACE_HELL", role: null, note: "engage first" }]), t);
  check("a member cannot save a comp; an outsider cannot either",
        await saveCode(F, T({ name: "Mine" })) === "42501" && await saveCode(X, T({ name: "Theirs" })) === "42501");
  check("a comp name is unique in its guild, whatever its case", await saveCode(C, T({ name: "castle a" })) === "23505");
  check("the checks refuse a bad content key, a size off the range, a slot off the roster and a long role",
        await saveCode(H, T({ name: "B", content: "Castle Fight" })) === "23514"
        && await saveCode(H, T({ name: "B", planned_size: 61 })) === "23514"
        && await saveCode(H, T({ name: "B", slots: [{ position: 61, weapon_id: "A" }] })) === "23514"
        && await saveCode(H, T({ name: "B", slots: [{ position: 1, role: "r".repeat(41) }] })) === "23514");
  check("a position listed twice or a payload that is not a list is refused",
        await saveCode(H, T({ name: "B", slots: [{ position: 1 }, { position: 1 }] })) === "21000"
        && await saveCode(H, T({ name: "B", slots: { position: 1 } })) === "22023");
  const unchanged = await rows("authenticated", H, "select count(*)::int as n from public.comp_templates where guild_id = $1", [gd.id]);
  check("a refused save changes nothing (one transaction)", unchanged[0].n === 1, unchanged);

  /* reading */
  const fSees = await rows("authenticated", F, "select id, name from public.comp_templates");
  check("a member reads the guild's comps and their slots",
        fSees.length === 1 && fSees[0].id === t.id && (await slotsOf(F, t.id)).length === 2, fSees);
  check("an outsider reads no comp and no slot; anon reads nothing",
        (await rows("authenticated", X, "select id from public.comp_templates")).length === 0
        && (await rows("authenticated", X, "select * from public.comp_template_slots")).length === 0
        && await code("anon", null, "select * from public.comp_templates") === "42501"
        && await code("anon", null, "select * from public.comp_template_slots") === "42501");
  check("a member cannot edit, add slots to or delete a comp",
        await affected("authenticated", F, "update public.comp_templates set name = 'Mine' where id = $1", [t.id]) === 0
        && await code("authenticated", F, "insert into public.comp_template_slots (template_id, position, weapon_id) values ($1, 3, 'A')", [t.id]) === "42501"
        && await affected("authenticated", F, "delete from public.comp_template_slots where template_id = $1", [t.id]) === 0
        && await affected("authenticated", F, "delete from public.comp_templates where id = $1", [t.id]) === 0);

  /* editing */
  const t2 = (await save(C, T({ id: t.id, name: "Castle A v2", notes: "hold the gate", style: "",
                                 slots: [{ position: 1, weapon_id: "2H_LONGBOW", role: "kite", note: null },
                                         { position: 3, weapon_id: null, role: "open", note: "anyone" }] })))[0];
  check("an admin edits a comp: renamed, notes set, the style cleared, updated_by follows; unlisted slots go, listed ones are added or changed",
        t2 && t2.id === t.id && t2.name === "Castle A v2" && t2.notes === "hold the gate" && t2.style === null && t2.updated_by === C
        && t2.updated_at > t.updated_at
        && same(await slotsOf(C, t.id), [{ position: 1, weapon_id: "2H_LONGBOW", role: "kite", note: null },
                                         { position: 3, weapon_id: null, role: "open", note: "anyone" }]), t2);
  check("an edit that names a comp the caller cannot edit is refused", await saveCode(F, T({ id: t.id, name: "Hijack" })) === "42501");
  for (const col of ["guild_id = gen_random_uuid()", "created_by = null", "updated_by = null", "created_at = now()", "updated_at = now()"]) {
    check(`no caller writes ${col.split(" ")[0]} on a comp (column grants)`,
          await code("authenticated", C, `update public.comp_templates set ${col} where id = $1`, [t.id]) === "42501");
  }
  check("a caller edits a slot's role directly; nobody moves a slot's position",
        await affected("authenticated", H, "update public.comp_template_slots set role = 'stopper' where template_id = $1 and position = 1", [t.id]) === 1
        && await code("authenticated", H, "update public.comp_template_slots set position = 9 where template_id = $1 and position = 1", [t.id]) === "42501");

  /* bounds and deletion */
  {
    let made = 1, err = "ok";
    for (let i = 0; i < 105 && err === "ok"; i++) {
      err = await saveCode(H, T({ name: `Comp ${i}`, slots: [] }));
      if (err === "ok") made++;
    }
    check("a guild keeps at most 100 comps (the guard)", made === 100 && err === "23514", { made, err });
    check("a comp holds at most 60 slots (the function)",
          await saveCode(H, T({ id: t.id, slots: Array.from({ length: 61 }, (_, i) => ({ position: i + 1 })) })) === "23514");
  }
  check("a caller deletes a comp; its slots go with it",
        await affected("authenticated", H, "delete from public.comp_templates where id = $1", [t.id]) === 1
        && Number((await db.query("select count(*) from public.comp_template_slots where template_id = $1", [t.id])).rows[0].count) === 0);
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [H]);
  const orphan = (await db.query("select count(*)::int as n, count(created_by)::int as by from public.comp_templates where guild_id = $1", [gd.id])).rows[0];
  check("deleting a caller's account keeps the comps, their created_by null", orphan.n === 99 && orphan.by === 0, orphan);
  check("deleting the guild removes its comps",
        await affected("authenticated", C, "delete from public.guilds where id = $1", [gd.id]) === 1
        && Number((await db.query("select count(*) from public.comp_templates where guild_id = $1", [gd.id])).rows[0].count) === 0);
  check("no API role calls the comp guard", await code("authenticated", C, "select public.comp_templates_guard()") === "42501");
}

/* 10 - CTAs: a guild's events and their slots, copied from a comp, written by caller roles */
{
  /* the cast: C makes a fresh guild (the last one went with section 9);
     F (a member) and X (an outsider) from section 9; K, a new caller */
  const F = "00000000-0000-4000-8000-00000000000f";
  const X = "00000000-0000-4000-8000-000000000011";
  const K = "00000000-0000-4000-8000-000000000012";
  await signUp(K, { albion_name: "Kay" });
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy CTA", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K]);

  const TPL_SLOTS = [{ position: 1, weapon_id: "2H_LONGBOW", role: "ranged", note: null },
                     { position: 2, weapon_id: "MAIN_MACE_HELL", role: null, note: "engage first" }];
  const tpl = (await rows("authenticated", C, "select * from public.save_comp_template($1::jsonb)", [JSON.stringify({
    guild_id: g.id, name: "Castle A", content: "castle", style: "clap", planned_size: 20,
    share_hash: "c=castle&n=20&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL", slots: TPL_SLOTS })]))[0];

  const EV = (over = {}) => JSON.stringify(Object.assign({
    guild_id: g.id, template_id: tpl.id, name: " Friday CTA ", starts_at: "2026-10-03T18:00:00Z",
    mass_at: "2026-10-03T17:30:00Z", notes: "  "
  }, over));
  const save = (sub, payload) => rows("authenticated", sub, "select * from public.save_event($1::jsonb)", [payload]);
  const saveCode = (sub, payload) => code("authenticated", sub, "select * from public.save_event($1::jsonb)", [payload]);
  const slotsOf = (sub, id) => rows("authenticated", sub, "select position, weapon_id, role, note from public.event_slots where event_id = $1 order by position", [id]);
  const tplSlots = () => rows("authenticated", C, "select position, weapon_id, role, note from public.comp_template_slots where template_id = $1 order by position", [tpl.id]);
  const move = (sub, id, to) => code("authenticated", sub, "update public.events set status = $2 where id = $1", [id, to]);

  const e = (await save(K, EV()))[0];
  check("a caller makes a CTA from a comp: the name trimmed, empty notes null, a draft with a 10-character share code; content, style, size, share hash and slots copied from the comp",
        e && e.name === "Friday CTA" && e.notes === null && e.status === "draft" && /^[A-Z0-9]{10}$/.test(e.share_code)
        && e.template_id === tpl.id && e.content === "castle" && e.style === "clap" && e.planned_size === 20
        && e.share_hash === tpl.share_hash && e.created_by === K && e.updated_by === K
        && same(await slotsOf(K, e.id), TPL_SLOTS), e);
  const eb = (await save(K, EV({ name: "B", content: "ancient_lands", planned_size: 7, style: "" })))[0];
  check("a field the payload names wins over the comp's",
        eb && eb.content === "ancient_lands" && eb.planned_size === 7 && eb.style === null && eb.template_id === tpl.id
        && (await slotsOf(K, eb.id)).length === 2, eb);
  const ec = (await save(K, EV({ name: "C", slots: [{ position: 1, weapon_id: "MAIN_HOLYSTAFF_AVALON" }] })))[0];
  check("a payload with its own slots writes those instead of the comp's",
        ec && same(await slotsOf(K, ec.id), [{ position: 1, weapon_id: "MAIN_HOLYSTAFF_AVALON", role: null, note: null }]));
  const ed = (await save(K, EV({ name: "D", template_id: null })))[0];
  check("a CTA without a comp or slots is an empty roster with the defaults",
        ed && ed.template_id === null && ed.content === "territory_defense" && ed.planned_size === 20 && ed.share_hash === null
        && (await slotsOf(K, ed.id)).length === 0, ed);
  check("a comp the caller cannot read is not found",
        await saveCode(K, EV({ name: "E", template_id: "00000000-0000-4000-8000-0000000000ee" })) === "P0002");
  check("a member cannot make a CTA; an outsider cannot either, and cannot see the comp it names",
        await saveCode(F, EV({ name: "Mine" })) === "42501" && await saveCode(X, EV({ name: "Theirs", template_id: null })) === "42501"
        && await saveCode(X, EV({ name: "Theirs" })) === "P0002");
  check("the checks refuse a status off the list, a mass time after the start, a size off the range, a slot off the roster and an empty name",
        await saveCode(K, EV({ name: "E", status: "live" })) === "23514"
        && await saveCode(K, EV({ name: "E", mass_at: "2026-10-03T18:00:01Z" })) === "23514"
        && await saveCode(K, EV({ name: "E", planned_size: 61 })) === "23514"
        && await saveCode(K, EV({ name: "E", slots: [{ position: 61, weapon_id: "A" }] })) === "23514"
        && await saveCode(K, EV({ name: "  " })) === "23514");
  check("a start is required", await saveCode(K, EV({ name: "E", starts_at: null })) === "23502");
  check("a position listed twice or a payload that is not a list is refused",
        await saveCode(K, EV({ name: "E", slots: [{ position: 1 }, { position: 1 }] })) === "21000"
        && await saveCode(K, EV({ name: "E", slots: { position: 1 } })) === "22023");
  const made = await rows("authenticated", K, "select count(*)::int as n from public.events where guild_id = $1", [g.id]);
  check("a refused save changes nothing (one transaction)", made[0].n === 4, made);

  /* editing */
  const e2 = (await save(C, EV({ id: e.id, name: "Friday CTA v2", notes: "hold the gate", mass_at: "",
                                  slots: [{ position: 1, weapon_id: "2H_LONGBOW", role: "kite", note: null },
                                          { position: 3, weapon_id: null, role: "open", note: "anyone" }] })))[0];
  check("an admin edits a CTA: renamed, notes set, the mass time cleared, updated_by follows; unlisted slots go, listed ones are added or changed",
        e2 && e2.id === e.id && e2.name === "Friday CTA v2" && e2.notes === "hold the gate" && e2.mass_at === null
        && e2.updated_by === C && e2.updated_at > e.updated_at
        && same(await slotsOf(C, e.id), [{ position: 1, weapon_id: "2H_LONGBOW", role: "kite", note: null },
                                         { position: 3, weapon_id: null, role: "open", note: "anyone" }]), e2);
  check("editing a CTA's slots leaves the comp as it was", same(await tplSlots(), TPL_SLOTS));
  const e3 = (await save(C, EV({ id: e.id, notes: "n2" })))[0];
  check("an edit that names no slots leaves them alone", e3 && e3.notes === "n2" && (await slotsOf(C, e.id)).length === 2);
  check("an edit that names a CTA the caller cannot edit is refused", await saveCode(F, EV({ id: e.id, name: "Hijack" })) === "42501");
  check("a member cannot edit, add slots to or delete a CTA",
        await affected("authenticated", F, "update public.events set name = 'Mine' where id = $1", [e.id]) === 0
        && await code("authenticated", F, "insert into public.event_slots (event_id, position, weapon_id) values ($1, 9, 'A')", [e.id]) === "42501"
        && await affected("authenticated", F, "delete from public.event_slots where event_id = $1", [e.id]) === 0
        && await affected("authenticated", F, "delete from public.events where id = $1", [e.id]) === 0);
  for (const col of ["guild_id = gen_random_uuid()", "template_id = null", "share_code = 'ABCDEFGHIJ'", "created_by = null",
                     "updated_by = null", "created_at = now()", "updated_at = now()"]) {
    check(`no caller writes ${col.split(" ")[0]} on a CTA (column grants)`,
          await code("authenticated", C, `update public.events set ${col} where id = $1`, [e.id]) === "42501");
  }
  check("a caller edits a slot's role directly; nobody moves a slot's position",
        await affected("authenticated", K, "update public.event_slots set role = 'stopper' where event_id = $1 and position = 1", [e.id]) === 1
        && await code("authenticated", K, "update public.event_slots set position = 9 where event_id = $1 and position = 1", [e.id]) === "42501");

  /* the status */
  check("the status moves one step at a time: draft to locked is refused; draft to open, open to locked, back to open, locked to completed",
        await move(K, e.id, "locked") === "23514" && await move(K, e.id, "open") === "ok" && await move(K, e.id, "locked") === "ok"
        && await move(K, e.id, "open") === "ok" && await move(K, e.id, "locked") === "ok" && await move(K, e.id, "completed") === "ok");
  check("completed is final",
        await move(K, e.id, "open") === "23514" && await move(K, e.id, "locked") === "23514" && await move(K, e.id, "draft") === "23514");
  check("open goes back to draft; a status off the list is refused by the check",
        await move(K, eb.id, "open") === "ok" && await move(K, eb.id, "draft") === "ok" && await move(K, eb.id, "live") === "23514");
  check("a completed CTA keeps its slots: none added, changed or removed, by statement or by save",
        await code("authenticated", K, "insert into public.event_slots (event_id, position, weapon_id) values ($1, 9, 'A')", [e.id]) === "23514"
        && await code("authenticated", K, "update public.event_slots set role = 'x' where event_id = $1 and position = 1", [e.id]) === "23514"
        && await code("authenticated", K, "delete from public.event_slots where event_id = $1 and position = 1", [e.id]) === "23514"
        && await saveCode(K, EV({ id: e.id, slots: [] })) === "23514"
        && (await slotsOf(K, e.id)).length === 2);
  check("a completed CTA's notes still change; a save that names no slots goes through",
        await affected("authenticated", K, "update public.events set notes = 'we won' where id = $1", [e.id]) === 1
        && await saveCode(K, EV({ id: e.id, notes: "we won, barely" })) === "ok");

  /* reading */
  const fSees = await rows("authenticated", F, "select id, share_code from public.events where guild_id = $1", [g.id]);
  check("a member reads the guild's CTAs, their share codes and their slots",
        fSees.length === 4 && fSees.every(r => /^[A-Z0-9]{10}$/.test(r.share_code)) && (await slotsOf(F, e.id)).length === 2, fSees);
  check("an outsider reads no CTA and no slot; anon without a code reads none either, and never the caller column",
        (await rows("authenticated", X, "select id from public.events")).length === 0
        && (await rows("authenticated", X, "select * from public.event_slots")).length === 0
        && await code("anon", null, "select * from public.events") === "42501"
        && (await rows("anon", null, "select id from public.events")).length === 0
        && (await rows("anon", null, "select * from public.event_slots")).length === 0);

  /* the comp goes; the CTA stays */
  check("deleting the comp keeps the CTA, its template_id null and its slots whole",
        await affected("authenticated", C, "delete from public.comp_templates where id = $1", [tpl.id]) === 1
        && (await rows("authenticated", C, "select template_id from public.events where id = $1", [e.id]))[0].template_id === null
        && (await slotsOf(C, e.id)).length === 2);

  /* bounds and deletion */
  {
    let err = "ok";
    for (let i = 0; i < 205 && err === "ok"; i++) {
      err = await code("authenticated", K, "insert into public.events (guild_id, name, starts_at) values ($1, $2, now())", [g.id, `Bound ${i}`]);
    }
    const n = (await db.query("select count(*)::int as n from public.events where guild_id = $1", [g.id])).rows[0].n;
    check("a guild keeps at most 200 CTAs (the guard)", n === 200 && err === "23514", { n, err });
    check("a CTA holds at most 60 slots (the function)",
          await saveCode(K, EV({ id: eb.id, slots: Array.from({ length: 61 }, (_, i) => ({ position: i + 1 })) })) === "23514");
  }
  check("a caller deletes a CTA; its slots go with it",
        await affected("authenticated", K, "delete from public.events where id = $1", [eb.id]) === 1
        && Number((await db.query("select count(*) from public.event_slots where event_id = $1", [eb.id])).rows[0].count) === 0);
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [K]);
  const orphan = (await db.query("select count(*)::int as n, count(created_by)::int as by from public.events where guild_id = $1", [g.id])).rows[0];
  check("deleting a caller's account keeps the CTAs, their created_by null", orphan.n === 199 && orphan.by === 0, orphan);
  check("deleting the guild removes its CTAs, the completed one's frozen slots with them",
        await affected("authenticated", C, "delete from public.guilds where id = $1", [g.id]) === 1
        && Number((await db.query("select count(*) from public.events where guild_id = $1", [g.id])).rows[0].count) === 0
        && Number((await db.query("select count(*) from public.event_slots where event_id = $1", [e.id])).rows[0].count) === 0);
  check("no API role calls the CTA guards",
        await code("authenticated", C, "select public.events_guard()") === "42501"
        && await code("authenticated", C, "select public.event_slots_guard()") === "42501");
}

const code_ = code;
/* 11 - sign-up: guests through the share code and a claim token, accounts under their id */
{
  /* the cast: C makes a guild and a CTA; F (a member) and X (an outsider,
     signed in) from before; two guests known by their tokens */
  const F = "00000000-0000-4000-8000-00000000000f";
  const X = "00000000-0000-4000-8000-000000000011";
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy Sheet", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  const ev = (await rows("authenticated", C, "select * from public.save_event($1::jsonb)", [JSON.stringify({
    guild_id: g.id, name: "Sheet CTA", starts_at: "2026-10-03T18:00:00Z", content: "castle",
    slots: [{ position: 1, weapon_id: "2H_LONGBOW", role: "ranged" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: null }]
  })]))[0];
  const CODE = ev.share_code;
  const T1 = "a".repeat(32), T2 = "b".repeat(32);
  const sheet = (role, sub, code, token) => rows(role, sub, "select public.event_by_code($1, $2) as s", [code, token]).then(r => r[0].s);
  const sheetCode = (role, sub, code, token) => code_(role, sub, "select public.event_by_code($1, $2)", [code, token]);
  const up = (role, sub, token, payload) => rows(role, sub, "select public.sign_up($1, $2, $3::jsonb) as s", [CODE, token, JSON.stringify(payload)]).then(r => r[0].s);
  const upCode = (role, sub, token, payload) => code_(role, sub, "select public.sign_up($1, $2, $3::jsonb)", [CODE, token, JSON.stringify(payload)]);
  const cancel = (role, sub, token) => rows(role, sub, "select public.cancel_sign_up($1, $2) as ok", [CODE, token]).then(r => r[0].ok);
  const claimants = async () => (await db.query("select position, player_name, user_id is not null as account from public.signups where event_id = $1 order by position nulls last, player_name", [ev.id])).rows;

  /* the sheet through the code */
  check("a guest with the code reads the CTA: its guild, slots and an empty sheet, and nothing names them",
        await (async () => { const s = await sheet("anon", null, CODE, null);
          return s.event.id === ev.id && s.event.name === "Sheet CTA" && s.event.share_code === CODE && s.guild.name === "Zaddy Sheet"
            && s.slots.length === 3 && s.slots[0].weapon_id === "2H_LONGBOW" && same(s.signups, []) && s.mine === null
            && !("created_by" in s.event) && !("updated_by" in s.event); })());
  check("a wrong code, a malformed code or an empty one names nothing",
        await sheetCode("anon", null, "ZZZZZZZZZZ", null) === "P0002" && await sheetCode("anon", null, "short", null) === "P0002"
        && await sheetCode("anon", null, "", null) === "P0002");
  check("without the code anon reads no CTA, slot, guild or sign-up",
        (await rows("anon", null, "select id from public.events")).length === 0
        && (await rows("anon", null, "select event_id from public.event_slots")).length === 0
        && (await rows("anon", null, "select id from public.guilds")).length === 0
        && (await rows("anon", null, "select id from public.signups")).length === 0);
  check("anon never reads the caller column or the guild's join code; the code column answers only the CTA the code opened",
        (await rows("anon", null, "select share_code from public.events")).length === 0
        && await code_("anon", null, "select created_by from public.events") === "42501"
        && await code_("anon", null, "select join_code from public.guilds") === "42501");
  check("a signed-in outsider with the code reads the sheet too; without it, nothing",
        (await sheet("authenticated", X, CODE, null)).event.id === ev.id
        && (await rows("authenticated", X, "select id from public.events")).length === 0);

  /* not yet open */
  check("nobody signs up on a draft: not a guest, not a member",
        await upCode("anon", null, T1, { player_name: "Gus", position: 1 }) === "55000"
        && await upCode("authenticated", F, null, { position: 1 }) === "55000");
  await run("authenticated", C, "update public.events set status = 'open' where id = $1", [ev.id]);

  /* guests */
  const g1 = await up("anon", null, T1, { player_name: " Gus ", position: 1, item_power: 1450, can_swap: true, weapons: ["2H_LONGBOW", "2H_BOW"], note: " late 5 min " });
  check("a guest signs up with a token: the name trimmed, the slot claimed, weapons and note kept; the token's hash keys the row and the token is not stored",
        g1 && g1.position === 1 && g1.player_name === "Gus" && g1.item_power === 1450 && g1.can_swap === true
        && same(g1.weapons, ["2H_LONGBOW", "2H_BOW"]) && g1.note === "late 5 min"
        && (await db.query("select guest_token_hash, user_id from public.signups where id = $1", [g1.id])).rows[0].guest_token_hash.length === 64
        && (await db.query("select count(*)::int as n from public.signups where guest_token_hash = $1", [T1])).rows[0].n === 0, g1);
  check("the guest's own row comes back as mine with the token, and not without it",
        (await sheet("anon", null, CODE, T1)).mine.id === g1.id && (await sheet("anon", null, CODE, null)).mine === null
        && (await sheet("anon", null, CODE, T2)).mine === null);
  check("a guest needs a token and a name",
        await upCode("anon", null, null, { player_name: "Nobody", position: 2 }) === "42501"
        && await upCode("anon", null, "short", { player_name: "Nobody", position: 2 }) === "42501"
        && await upCode("anon", null, T2, { position: 2 }) === "23502");
  check("a slot already claimed cannot be claimed again (one conditional statement, the unique index)",
        await upCode("anon", null, T2, { player_name: "Gil", position: 1 }) === "23505");
  const g2 = await up("anon", null, T2, { player_name: "Gil" });
  check("a guest without a slot is a reserve", g2 && g2.position === null && g2.player_name === "Gil");
  const g1b = await up("anon", null, T1, { player_name: "Gus", position: 2, weapons: ["MAIN_MACE_HELL"] });
  check("a second call with the same token updates the sign-up (the slot moves, the weapons change), one row per guest",
        g1b && g1b.id === g1.id && g1b.position === 2 && same(g1b.weapons, ["MAIN_MACE_HELL"])
        && (await db.query("select count(*)::int as n from public.signups where event_id = $1", [ev.id])).rows[0].n === 2);
  check("a guest cannot touch another guest's row: the token decides",
        await affected("anon", null, "update public.signups set player_name = 'Hacked' where id = $1", [g2.id]) === 0
        && await affected("anon", null, "delete from public.signups where id = $1", [g2.id]) === 0
        && await code_("anon", null, "insert into public.signups (event_id, position, guest_token_hash, player_name) values ($1, 3, repeat('c', 64), 'Direct')", [ev.id]) === "42501");
  check("the checks refuse a bad weapon key, a weapon twice, too many weapons, an item power off the range and a long note",
        await upCode("anon", null, T2, { player_name: "Gil", weapons: ["not a key"] }) === "23514"
        && await upCode("anon", null, T2, { player_name: "Gil", weapons: ["2H_BOW", "2H_BOW"] }) === "23514"
        && await upCode("anon", null, T2, { player_name: "Gil", weapons: Array.from({ length: 11 }, (_, i) => `W${i}`) }) === "23514"
        && await upCode("anon", null, T2, { player_name: "Gil", item_power: 3001 }) === "23514"
        && await upCode("anon", null, T2, { player_name: "Gil", note: "n".repeat(201) }) === "23514");
  check("a slot the CTA does not have cannot be claimed", await upCode("anon", null, T2, { player_name: "Gil", position: 9 }) === "23503");

  /* accounts */
  const f1 = await up("authenticated", F, null, { position: 3, item_power: 1300 });
  check("a member signs up under their id, named after their character, without a token",
        f1 && f1.position === 3 && f1.player_name === "Eff"
        && (await db.query("select user_id, guest_token_hash from public.signups where id = $1", [f1.id])).rows[0].user_id === F
        && (await sheet("authenticated", F, CODE, null)).mine.id === f1.id);
  check("a payload name overrides the character's (an alt)", (await up("authenticated", F, null, { position: 3, player_name: "EffAlt" })).player_name === "EffAlt");
  check("an account has one sign-up per CTA: a second call updates it",
        (await db.query("select count(*)::int as n from public.signups where event_id = $1 and user_id = $2", [ev.id, F])).rows[0].n === 1);
  check("a signed-in outsider with the code signs up as an account, as a reserve",
        (await up("authenticated", X, null, { item_power: 1200 })).position === null
        && (await db.query("select user_id from public.signups where event_id = $1 and user_id = $2", [ev.id, X])).rows.length === 1);
  check("an account cannot write another player's row or claim a taken slot",
        await affected("authenticated", X, "update public.signups set player_name = 'Hacked' where id = $1", [f1.id]) === 0
        && await upCode("authenticated", X, null, { position: 3 }) === "23505");
  check("a member reads the whole sheet; the guest hash never joins the sheet's JSON",
        await (async () => { const s = await sheet("authenticated", C, CODE, null);
          return s.signups.length === 4 && s.signups.every(r => !("guest_token_hash" in r) && !("user_id" in r))
            && s.signups.filter(r => r.account).length === 2; })());

  /* adoption: the account made in the guest's browser takes the guest's sign-up */
  const Y = "00000000-0000-4000-8000-000000000013";
  await signUp(Y, { albion_name: "Gil" });
  const adopted = await up("authenticated", Y, T2, { item_power: 1500 });
  check("an account signing up with its browser's guest token adopts that guest sign-up: same row, now the account's, the hash gone",
        adopted && adopted.id === g2.id && adopted.item_power === 1500
        && (await db.query("select user_id, guest_token_hash from public.signups where id = $1", [g2.id])).rows[0].user_id === Y
        && (await db.query("select guest_token_hash from public.signups where id = $1", [g2.id])).rows[0].guest_token_hash === null
        && (await sheet("anon", null, CODE, T2)).mine === null);
  check("a token that names nobody adopts nothing; the account signs up fresh",
        (await up("authenticated", Y, "d".repeat(32), { item_power: 1501 })).id === g2.id
        && (await db.query("select count(*)::int as n from public.signups where event_id = $1", [ev.id])).rows[0].n === 4);

  /* a removed slot, the bound */
  await run("authenticated", C, "delete from public.event_slots where event_id = $1 and position = 2", [ev.id]);
  check("removing a slot leaves its claimant as a reserve",
        (await db.query("select position from public.signups where id = $1", [g1.id])).rows[0].position === null);
  {
    let err = "ok", i = 0;
    for (; i < 125 && err === "ok"; i++) {
      err = await code_("anon", null, "select public.sign_up($1, $2, $3::jsonb)", [CODE, `t${String(i).padStart(31, "0")}`, JSON.stringify({ player_name: `Guest ${i}` })]);
    }
    const n = (await db.query("select count(*)::int as n from public.signups where event_id = $1", [ev.id])).rows[0].n;
    check("a CTA takes at most 120 sign-ups (the guard)", n === 120 && err === "23514", { n, err });
  }

  /* locking, cancelling, completing */
  await run("authenticated", C, "update public.events set status = 'locked' where id = $1", [ev.id]);
  check("once locked, nobody signs up or changes a sign-up, but a player still cancels",
        await upCode("anon", null, T1, { player_name: "Gus", position: 1 }) === "55000"
        && await upCode("authenticated", F, null, { position: 1 }) === "55000"
        && await affected("anon", null, "update public.signups set note = 'x' where id = $1", [g1.id]) === 0
        && await cancel("anon", null, T1) === true
        && await cancel("anon", null, T1) === false
        && await cancel("authenticated", X, null) === true);
  await run("authenticated", C, "update public.events set status = 'completed' where id = $1", [ev.id]);
  check("a completed CTA keeps its sheet: no sign-up, change or cancellation",
        await code_("authenticated", F, "select public.cancel_sign_up($1)", [CODE]) === "55000"
        && await affected("authenticated", F, "delete from public.signups where user_id = $1", [F]) === 0
        && (await db.query("select count(*)::int as n from public.signups where event_id = $1 and user_id = $2", [ev.id, F])).rows[0].n === 1);
  check("the completed sheet still reads through the code", (await sheet("anon", null, CODE, null)).signups.length === 118);

  /* grants and deletion */
  check("no caller writes a sign-up's identity: user_id and the hash are the statement's",
        await code_("anon", null, "update public.signups set guest_token_hash = repeat('e', 64) where id = $1", [g1.id]) === "42501"
        && await code_("authenticated", F, "update public.signups set event_id = gen_random_uuid() where user_id = $1", [F]) === "42501");
  check("no API role calls the sign-up guard", await code_("authenticated", C, "select public.signups_guard()") === "42501");
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [Y]);
  check("deleting an account deletes its sign-ups",
        (await db.query("select count(*)::int as n from public.signups where id = $1", [g2.id])).rows[0].n === 0);
  check("deleting the CTA deletes its sheet",
        await affected("authenticated", C, "delete from public.events where id = $1", [ev.id]) === 1
        && (await db.query("select count(*)::int as n from public.signups where event_id = $1", [ev.id])).rows[0].n === 0);
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
}

/* 12 - caller management: moves, swaps, removals and added players, by the caller roles until completed */
{
  const code_ = code;
  const F = "00000000-0000-4000-8000-00000000000f";
  const K2 = "00000000-0000-4000-8000-000000000014";
  const Y2 = "00000000-0000-4000-8000-000000000015";
  await signUp(K2, { albion_name: "Kay Two" });
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy Callers", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K2, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K2]);
  const ev = (await rows("authenticated", C, "select * from public.save_event($1::jsonb)", [JSON.stringify({
    guild_id: g.id, name: "Managed CTA", starts_at: "2026-10-04T18:00:00Z", content: "castle", status: "draft",
    slots: [{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: null }]
  })]))[0];
  await run("authenticated", C, "update public.events set status = 'open' where id = $1", [ev.id]);
  const CODE = ev.share_code;
  const T1 = "1".repeat(32);
  const up = (role, sub, token, payload) => rows(role, sub, "select public.sign_up($1, $2, $3::jsonb) as s", [CODE, token, JSON.stringify(payload)]).then(r => r[0].s);
  const move = (sub, id, target) => rows("authenticated", sub, "select public.move_signup($1, $2) as m", [id, target]).then(r => r[0].m);
  const moveCode = (sub, id, target) => code_("authenticated", sub, "select public.move_signup($1, $2)", [id, target]);
  const add = (sub, payload) => rows("authenticated", sub, "select public.add_player($1, $2::jsonb) as a", [ev.id, JSON.stringify(payload)]).then(r => r[0].a);
  const addCode = (sub, payload) => code_("authenticated", sub, "select public.add_player($1, $2::jsonb)", [ev.id, JSON.stringify(payload)]);
  const posOf = async id => (await db.query("select position from public.signups where id = $1", [id])).rows[0].position;

  const g1 = await up("anon", null, T1, { player_name: "Gus", position: 1 });
  const f1 = await up("authenticated", F, null, { position: 2 });
  const disc = await add(K2, { player_name: " Disc ", position: 3, weapons: ["2H_HOLYSTAFF"], item_power: 1100 });
  check("a caller adds a player by name: a guest row nobody holds a token for, on the slot named",
        disc && disc.player_name === "Disc" && disc.position === 3 && same(disc.weapons, ["2H_HOLYSTAFF"])
        && (await db.query("select user_id, guest_token_hash from public.signups where id = $1", [disc.id])).rows[0].user_id === null
        && (await db.query("select guest_token_hash from public.signups where id = $1", [disc.id])).rows[0].guest_token_hash.length === 64, disc);
  check("a player needs a name; a taken slot is refused; a member adds nobody",
        await addCode(K2, { position: null }) === "23502" && await addCode(K2, { player_name: "Dup", position: 1 }) === "23505"
        && await addCode(F, { player_name: "Mine" }) === "42501");
  check("a member moves and removes nobody else's sign-up",
        await moveCode(F, g1.id, null) === "42501" && await posOf(g1.id) === 1
        && await affected("authenticated", F, "delete from public.signups where id = $1", [g1.id]) === 0
        && await affected("authenticated", F, "update public.signups set item_power = 1 where id = $1", [g1.id]) === 0);
  check("a caller moves a player to the reserves and back",
        (await move(K2, g1.id, null)).position === null && await posOf(g1.id) === null
        && (await move(K2, g1.id, 1)).position === 1 && await posOf(g1.id) === 1);
  const swapped = await move(K2, g1.id, 2);
  check("a caller moves a player onto a held slot: the two swap in one transaction",
        swapped.position === 2 && swapped.swapped === f1.id && await posOf(g1.id) === 2 && await posOf(f1.id) === 1, swapped);
  check("a move to the slot already held is a no-op", (await move(K2, g1.id, 2)).position === 2 && await posOf(f1.id) === 1);
  check("a player moves their own row while open, but cannot swap another player out",
        await moveCode(F, f1.id, 3) === "42501" && await posOf(f1.id) === 1 && await posOf(disc.id) === 3
        && (await move(F, f1.id, null)).position === null && await posOf(f1.id) === null);
  check("a move to a slot the roster lacks is refused; an unknown sign-up is not found",
        await moveCode(K2, g1.id, 9) === "23503" && await moveCode(K2, "00000000-0000-4000-8000-0000000000ff", 1) === "P0002");
  check("a caller edits a player's fields and cannot rewrite the player (the guard)",
        await affected("authenticated", K2, "update public.signups set item_power = 1234, note = 'late' where id = $1", [disc.id]) === 1
        && await code_("authenticated", K2, "update public.signups set user_id = $2 where id = $1", [g1.id, K2]) === "42501"
        && await code_("authenticated", K2, "update public.signups set guest_token_hash = repeat('9', 64) where id = $1", [g1.id]) === "42501"
        && await code_("authenticated", K2, "update public.signups set user_id = null, guest_token_hash = repeat('9', 64) where id = $1", [f1.id]) === "42501");
  await signUp(Y2, { albion_name: "Gus" });
  check("the adoption still passes the guard: the guest row becomes the account's",
        (await up("authenticated", Y2, T1, {})).id === g1.id
        && (await db.query("select user_id from public.signups where id = $1", [g1.id])).rows[0].user_id === Y2);
  check("a caller changes a slot's weapon; a member does not",
        await affected("authenticated", K2, "update public.event_slots set weapon_id = 'MAIN_HOLYSTAFF_AVALON' where event_id = $1 and position = 3", [ev.id]) === 1
        && await affected("authenticated", F, "update public.event_slots set weapon_id = '2H_BOW' where event_id = $1 and position = 3", [ev.id]) === 0);

  /* locked: the caller still manages, players stop */
  await run("authenticated", C, "update public.events set status = 'locked' where id = $1", [ev.id]);
  const late = await add(K2, { player_name: "Late" });
  check("once locked, a caller still adds a player", late && late.position === null, late);
  const lateMove = await move(K2, late.id, 3);
  check("once locked, a caller still moves a player onto a held slot (a swap)", lateMove.swapped === disc.id && await posOf(disc.id) === null, lateMove);
  check("once locked, a caller still removes a player", await affected("authenticated", K2, "delete from public.signups where id = $1", [late.id]) === 1);
  check("once locked, a player signs up no more and moves their own row no more; a non-member without the code sees no sign-up to move",
        await code_("authenticated", F, "select public.sign_up($1, null, '{}'::jsonb)", [CODE]) === "55000"
        && await moveCode(F, f1.id, 1) === "42501" && await posOf(f1.id) === null
        && await moveCode(Y2, g1.id, 1) === "P0002");
  check("a caller removes a player", await affected("authenticated", K2, "delete from public.signups where id = $1", [disc.id]) === 1);

  /* completed: history */
  await run("authenticated", C, "update public.events set status = 'completed' where id = $1", [ev.id]);
  check("a completed sheet is history: no move, no added player, no removal, not by the caller either",
        await moveCode(K2, g1.id, 1) === "55000" && await addCode(K2, { player_name: "Post" }) === "42501"
        && await affected("authenticated", K2, "delete from public.signups where id = $1", [g1.id]) === 0
        && await affected("authenticated", K2, "update public.signups set note = 'x' where id = $1", [g1.id]) === 0);
  check("no API role calls the caller functions as anon",
        await code_("anon", null, "select public.move_signup($1, 1::smallint)", [g1.id]) === "42501"
        && await code_("anon", null, "select public.add_player($1, '{}'::jsonb)", [ev.id]) === "42501");
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
}

/* 13 - live updates: every write to a sheet sends one broadcast on the CTA's topic, naming the table and the operation alone */
{
  const code_ = code;
  const F = "00000000-0000-4000-8000-00000000000f";
  const K2 = "00000000-0000-4000-8000-000000000014";
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy Live", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K2, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K2]);
  const ev = (await rows("authenticated", C, "select * from public.save_event($1::jsonb)", [JSON.stringify({
    guild_id: g.id, name: "Live CTA", starts_at: "2026-10-05T18:00:00Z", content: "castle", status: "draft",
    slots: [{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }]
  })]))[0];
  const CODE = ev.share_code;
  const TOPIC = `cta:${CODE}`;
  const sent = async () => (await db.query("select topic, event, payload, private from realtime.messages order by id")).rows;
  const clear = () => db.query("delete from realtime.messages");
  const up = (role, sub, token, payload) => rows(role, sub, "select public.sign_up($1, $2, $3::jsonb) as s", [CODE, token, JSON.stringify(payload)]).then(r => r[0].s);
  const says = (m, table, op) => m.topic === TOPIC && m.event === "changed" && m.private === false
    && Object.keys(m.payload).length === 2 && m.payload.table === table && m.payload.op === op;

  await clear();
  check("a send as an API role lands nothing: the message table's row-level security keeps it (why the trigger runs with its definer's rights)",
        await code_("anon", null, "select realtime.send('{}'::jsonb, 'x', 'cta:TEST', false)") === "ok"
        && (await sent()).length === 0);

  await clear();
  await run("authenticated", C, "update public.events set status = 'open' where id = $1", [ev.id]);
  let m = await sent();
  check("opening the CTA sends one message on the CTA's topic: the event 'changed', the table and the operation, public",
        m.length === 1 && says(m[0], "events", "UPDATE"), m);

  await clear();
  const g1 = await up("anon", null, "7".repeat(32), { player_name: "Gus", position: 1, item_power: 1400 });
  m = await sent();
  check("a guest's sign-up (as anon) sends a message for the sign-up and one for its record (the record's trigger fires first, by name); the payloads carry no name, no hash, no id",
        same(m.map(x => `${x.payload.table}:${x.payload.op}`).sort(), ["attendance:INSERT", "signups:INSERT"]) && m.every(x => says(x, x.payload.table, "INSERT"))
        && !JSON.stringify(m).includes("Gus") && !JSON.stringify(m).includes(g1.id), m);

  const f1 = await up("authenticated", F, null, { position: 2 });
  await clear();
  const swapped = (await rows("authenticated", K2, "select public.move_signup($1, $2) as m", [g1.id, 2]))[0].m;
  m = await sent();
  check("a swap sends a message per row changed (the sign-ups and their records), all on the CTA's topic, none naming a player",
        swapped.swapped === f1.id && m.length >= 3 && m.every(x => says(x, x.payload.table, "UPDATE") && ["signups", "attendance"].includes(x.payload.table))
        && !JSON.stringify(m).includes("Gus") && !JSON.stringify(m).includes("Eff"), m);

  await clear();
  await run("authenticated", K2, "update public.event_slots set weapon_id = 'MAIN_HOLYSTAFF_AVALON' where event_id = $1 and position = 1", [ev.id]);
  await run("authenticated", K2, "delete from public.signups where id = $1", [f1.id]);
  m = await sent();
  check("a slot's weapon sends one message; a removal sends one for the sign-up and two for its record (the link nulled by the constraint, then the status)",
        same(m.map(x => `${x.payload.table}:${x.payload.op}`).sort(), ["attendance:UPDATE", "attendance:UPDATE", "event_slots:UPDATE", "signups:DELETE"]), m);

  await clear();
  await run("authenticated", C, "update public.events set name = 'Live CTA renamed' where id = $1", [ev.id]);
  check("any change to the CTA itself sends one message", (await sent()).length === 1);

  await clear();
  await run("authenticated", C, "delete from public.events where id = $1", [ev.id]);
  m = await sent();
  check("deleting the CTA sends the CTA's own message and none for the rows the cascade removes (the CTA is gone before they go)",
        m.length === 1 && says(m[0], "events", "DELETE"), m);

  check("no API role calls the broadcast trigger", await code_("authenticated", C, "select public.sheet_changed()") === "42501"
        && await code_("anon", null, "select public.sheet_changed()") === "42501");
  const definers = (await db.query(
    "select n.nspname || '.' || p.proname as f from pg_proc p join pg_namespace n on n.oid = p.pronamespace where p.prosecdef and n.nspname = 'public' order by 1")).rows.map(r => r.f);
  check("the API schema holds three definers: the sign-up trigger, the broadcast trigger and the record's trigger, triggers no role can call",
        same(definers, ["public.attendance_record", "public.handle_new_user", "public.sheet_changed"]), definers);
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
  await clear();
}

/* 14 - history: the attendance record, kept apart from the sign-up */
{
  const code_ = code;
  const F = "00000000-0000-4000-8000-00000000000f";
  const K2 = "00000000-0000-4000-8000-000000000014";
  const Y3 = "00000000-0000-4000-8000-000000000016";
  await signUp(Y3, { albion_name: "Wye" });
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy History", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K2, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K2]);
  const ev = (await rows("authenticated", C, "select * from public.save_event($1::jsonb)", [JSON.stringify({
    guild_id: g.id, name: "History CTA", starts_at: "2026-10-06T18:00:00Z", content: "castle", status: "draft",
    slots: [{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: "MAIN_HOLYSTAFF_AVALON" }]
  })]))[0];
  await run("authenticated", C, "update public.events set status = 'open' where id = $1", [ev.id]);
  const CODE = ev.share_code;
  const T1 = "8".repeat(32), T2 = "9".repeat(32);
  const up = (role, sub, token, payload) => rows(role, sub, "select public.sign_up($1, $2, $3::jsonb) as s", [CODE, token, JSON.stringify(payload)]).then(r => r[0].s);
  const sheet = (role, sub, token) => rows(role, sub, "select public.event_by_code($1, $2) as s", [CODE, token]).then(r => r[0].s);
  const confirm = (role, sub, token, yes) => rows(role, sub, "select public.confirm_sign_up($1, $2, $3) as c", [CODE, token, yes]).then(r => r[0].c);
  const confirmCode = (role, sub, token, yes) => code_(role, sub, "select public.confirm_sign_up($1, $2, $3)", [CODE, token, yes]);
  const mark = (sub, id, status) => rows("authenticated", sub, "select public.mark_attendance($1, $2) as m", [id, status]).then(r => r[0].m);
  const markCode = (sub, id, status) => code_("authenticated", sub, "select public.mark_attendance($1, $2)", [id, status]);
  const record = async where => (await db.query(`select id, signup_id, user_id, guest_token_hash, player_name, position, weapon_id, declared, status, marked_by, marked_at from public.attendance where event_id = $1 and ${where}`, [ev.id])).rows[0];
  const records = async () => (await db.query("select player_name, status, position from public.attendance where event_id = $1 order by created_at", [ev.id])).rows;

  const g1 = await up("anon", null, T1, { player_name: "Gus", position: 1, weapons: ["2H_LONGBOW"] });
  const f1 = await up("authenticated", F, null, { position: 2 });
  const disc = (await rows("authenticated", K2, "select public.add_player($1, $2::jsonb) as a", [ev.id, JSON.stringify({ player_name: "Disc" })]))[0].a;
  const rg = await record("player_name = 'Gus'"), rf = await record("player_name = 'Eff'"), rd = await record("player_name = 'Disc'");
  check("a sign-up makes a record: signed_up, the name, the slot, the declared weapons, the same identity as the sign-up",
        rg && rg.status === "signed_up" && rg.position === 1 && same(rg.declared, ["2H_LONGBOW"]) && rg.signup_id === g1.id
        && rg.guest_token_hash === (await db.query("select guest_token_hash from public.signups where id = $1", [g1.id])).rows[0].guest_token_hash
        && rf && rf.user_id === F && rf.signup_id === f1.id && rf.position === 2
        && rd && rd.position === null && rd.signup_id === disc.id, { rg, rf, rd });
  await rows("authenticated", K2, "select public.move_signup($1, $2)", [g1.id, 3]);
  check("a move keeps the record in step", (await record("player_name = 'Gus'")).position === 3);
  check("the sheet carries the record: each sign-up's status, the record list, the player's own",
        await (async () => { const s = await sheet("anon", null, T1);
          return s.signups.every(r => r.attendance === "signed_up" && r.attendance_id) && s.attendance.length === 3
            && s.mine.attendance === "signed_up" && s.attendance.every(r => !("guest_token_hash" in r) && !("user_id" in r)); })());

  /* confirming */
  check("a guest confirms with the token, and unconfirms",
        (await confirm("anon", null, T1, true)).status === "confirmed" && (await sheet("anon", null, T1)).mine.attendance === "confirmed"
        && (await confirm("anon", null, T1, false)).status === "signed_up");
  check("an account confirms without a token", (await confirm("authenticated", F, null, true)).status === "confirmed");
  check("without a token, or with one that names nobody, a guest has nothing to confirm",
        await confirmCode("anon", null, null, true) === "P0002" && await confirmCode("anon", null, T2, true) === "P0002");
  check("a player marks no attendance: a guest's statement without the token reaches no row, an account's own row is refused by the guard, another's by the policy; a member marks nobody's",
        await affected("anon", null, "update public.attendance set status = 'attended' where id = $1", [rg.id]) === 0
        && await markCode(F, rf.id, "attended") === "42501" && await markCode(F, rg.id, "attended") === "42501"
        && await markCode(F, rd.id, "no_show") === "42501"
        && (await record("player_name = 'Eff'")).status === "confirmed");
  check("a guest cannot touch another's record (the token decides)",
        await affected("anon", null, "update public.attendance set status = 'confirmed' where id = $1", [rd.id]) === 0);

  /* the caller's marks */
  const marked = await mark(K2, rf.id, "attended");
  check("a caller marks attended: the mark carries who and when",
        marked.status === "attended" && marked.marked_at && (await record("player_name = 'Eff'")).marked_by === K2);
  check("a caller's mark is any listed status; a status off the list is refused by the check",
        (await mark(K2, rd.id, "no_show")).status === "no_show" && (await mark(K2, rd.id, "signed_up")).status === "signed_up"
        && await markCode(K2, rd.id, "late") === "23514");

  /* the claim goes, the record stays */
  await confirm("anon", null, T1, true);
  await rows("anon", null, "select public.cancel_sign_up($1, $2)", [CODE, T1]);
  const rgc = await record("player_name = 'Gus'");
  check("a cancellation keeps the record as cancelled, its claim gone, its slot remembered",
        rgc && rgc.id === rg.id && rgc.status === "cancelled" && rgc.signup_id === null && rgc.position === 3
        && (await db.query("select count(*)::int as n from public.signups where id = $1", [g1.id])).rows[0].n === 0);
  const g1b = await up("anon", null, T1, { player_name: "Gus", position: 3 });
  const rgb = await record("player_name = 'Gus'");
  check("signing up again brings the same record back to signed_up, cleared of any mark",
        rgb.id === rg.id && rgb.status === "signed_up" && rgb.signup_id === g1b.id && rgb.marked_by === null);
  await run("authenticated", K2, "delete from public.signups where id = $1", [disc.id]);
  check("the caller's removal is a cancellation on the record", (await record("player_name = 'Disc'")).status === "cancelled");
  check("a mark already made survives the claim going: Eff attended, then removed, stays attended",
        await affected("authenticated", K2, "delete from public.signups where id = $1", [f1.id]) === 1
        && (await record("player_name = 'Eff'")).status === "attended" && (await record("player_name = 'Eff'")).signup_id === null);

  /* adoption carries the record */
  await up("anon", null, T2, { player_name: "Wye", position: 2 });
  const adopted = await up("authenticated", Y3, T2, { position: 2 });
  const ry = await record("player_name = 'Wye'");
  check("an account adopting its browser's guest sign-up takes the record with it",
        ry && ry.user_id === Y3 && ry.guest_token_hash === null && ry.signup_id === adopted.id);
  const res = (await rows("authenticated", K2, "select public.add_player($1, $2::jsonb) as a", [ev.id, JSON.stringify({ player_name: "Res" })]))[0].a;

  /* completion settles */
  await run("authenticated", C, "update public.events set status = 'locked' where id = $1", [ev.id]);
  await run("authenticated", C, "update public.events set status = 'completed' where id = $1", [ev.id]);
  const rg2 = await record("player_name = 'Gus'"), rr = await record("player_name = 'Res'"), ry2 = await record("player_name = 'Wye'");
  check("completion settles the record: a reserve is a reserve; a slot holder keeps their status and gets the slot's weapon and their declared weapons",
        rr.status === "reserve" && rr.position === null
        && rg2.status === "signed_up" && rg2.weapon_id === "MAIN_HOLYSTAFF_AVALON"
        && ry2.status === "signed_up" && ry2.weapon_id === "MAIN_MACE_HELL", { rg2, rr, ry2 });
  check("after completion a player confirms no more; the caller still marks",
        await confirmCode("anon", null, T1, true) === "55000"
        && (await mark(K2, rg2.id, "attended")).status === "attended");
  check("mark_all_attended marks everyone still signed up or confirmed in a slot, and says how many",
        (await rows("authenticated", K2, "select public.mark_all_attended($1) as n", [ev.id]))[0].n === 1
        && (await record("player_name = 'Wye'")).status === "attended"
        && (await rows("authenticated", K2, "select public.mark_all_attended($1) as n", [ev.id]))[0].n === 0
        && (await rows("authenticated", F, "select public.mark_all_attended($1) as n", [ev.id]))[0].n === 0);
  check("the record reads through the code after completion, marks included",
        (await sheet("anon", null, null)).attendance.filter(r => r.status === "attended").length === 3);

  /* grants, broadcasts, cascades */
  check("no API role writes a record directly: no insert, no delete, no column but the status",
        await code_("anon", null, "insert into public.attendance (event_id, guest_token_hash, player_name) values ($1, repeat('a', 64), 'X')", [ev.id]) === "42501"
        && await code_("authenticated", K2, "insert into public.attendance (event_id, user_id, player_name) values ($1, $2, 'X')", [ev.id, K2]) === "42501"
        && await code_("authenticated", K2, "delete from public.attendance where id = $1", [rg.id]) === "42501"
        && await code_("authenticated", K2, "update public.attendance set position = 1 where id = $1", [rg.id]) === "42501"
        && await code_("authenticated", K2, "update public.attendance set marked_by = null where id = $1", [rg.id]) === "42501");
  await db.query("delete from realtime.messages");
  await mark(K2, rg2.id, "no_show");
  check("a mark is a change on the sheet: one broadcast on the CTA's topic",
        (await db.query("select payload from realtime.messages where topic = $1", [`cta:${CODE}`])).rows.map(r => `${r.payload.table}:${r.payload.op}`).join() === "attendance:UPDATE");
  check("no API role calls the record's triggers",
        await code_("authenticated", K2, "select public.attendance_record()") === "42501"
        && await code_("authenticated", K2, "select public.attendance_guard()") === "42501");
  await run("supabase_auth_admin", null, "delete from auth.users where id = $1", [Y3]);
  check("deleting an account deletes its records", (await db.query("select count(*)::int as n from public.attendance where id = $1", [ry.id])).rows[0].n === 0);
  await run("authenticated", C, "delete from public.events where id = $1", [ev.id]);
  check("deleting the CTA deletes its records", (await records()).length === 0);
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
  await db.query("delete from realtime.messages");
}

/* 15 - analytics: facts over completed CTAs, computed on read as the caller */
{
  const code_ = code;
  const F = "00000000-0000-4000-8000-00000000000f";
  const K2 = "00000000-0000-4000-8000-000000000014";
  const X = "00000000-0000-4000-8000-000000000011";
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy Facts", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K2, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K2]);
  const SLOTS = [{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: "MAIN_HOLYSTAFF_AVALON" }];
  const T1 = "5".repeat(32);
  const makeEvent = async (name, starts) => {
    const ev = (await rows("authenticated", C, "select * from public.save_event($1::jsonb)", [JSON.stringify({
      guild_id: g.id, name, starts_at: starts, content: "castle", status: "draft", slots: SLOTS })]))[0];
    await run("authenticated", C, "update public.events set status = 'open' where id = $1", [ev.id]);
    return ev;
  };
  const up = (role, sub, ev, token, payload) => rows(role, sub, "select public.sign_up($1, $2, $3::jsonb) as s", [ev.share_code, token, JSON.stringify(payload)]).then(r => r[0].s);
  const add = (ev, payload) => rows("authenticated", K2, "select public.add_player($1, $2::jsonb) as a", [ev.id, JSON.stringify(payload)]).then(r => r[0].a);
  const markOf = async (ev, name, status) => {
    const id = (await db.query("select id from public.attendance where event_id = $1 and player_name = $2", [ev.id, name])).rows[0].id;
    return rows("authenticated", K2, "select public.mark_attendance($1, $2)", [id, status]);
  };
  const complete = async ev => {
    await run("authenticated", C, "update public.events set status = 'locked' where id = $1", [ev.id]);
    await run("authenticated", C, "update public.events set status = 'completed' where id = $1", [ev.id]);
  };

  /* the first CTA: Gus (guest) attended in slot 1, Eff no-show in slot 2, Disc (added) attended in slot 3 */
  const e1 = await makeEvent("Facts one", "2026-10-01T18:00:00Z");
  await up("anon", null, e1, T1, { player_name: "Gus", position: 1 });
  await up("authenticated", F, e1, null, { position: 2 });
  await add(e1, { player_name: "Disc", position: 3 });
  await complete(e1);
  await markOf(e1, "Gus", "attended");
  await markOf(e1, "Eff", "no_show");
  await markOf(e1, "Disc", "attended");
  /* the second: Gus attended in slot 1, Eff attended in slot 2, Res a reserve */
  const e2 = await makeEvent("Facts two", "2026-10-08T18:00:00Z");
  await up("anon", null, e2, T1, { player_name: "Gus", position: 1 });
  await up("authenticated", F, e2, null, { position: 2 });
  await add(e2, { player_name: "Res" });
  await complete(e2);
  await markOf(e2, "Gus", "attended");
  await markOf(e2, "Eff", "attended");
  /* a third, still open: its sign-ups are not history */
  const e3 = await makeEvent("Facts three", "2026-10-15T18:00:00Z");
  await up("authenticated", F, e3, null, { position: 1 });

  const facts = (await rows("authenticated", F, "select public.guild_history($1) as f", [g.id]))[0].f;
  check("a member reads the guild's totals over completed CTAs alone: two CTAs, six records, four attended, one no-show, one reserve, a show rate of four in five, a fill of five slots in six",
        facts.totals.ctas === 2 && facts.totals.records === 6 && facts.totals.attended === 4 && facts.totals.no_show === 1
        && facts.totals.reserve === 1 && facts.totals.unmarked === 0 && facts.totals.cancelled === 0
        && Number(facts.totals.show_rate) === 0.8 && Number(facts.totals.fill) === 0.833, facts.totals);
  check("the completed CTAs come latest first, each with its counts",
        facts.ctas.length === 2 && facts.ctas[0].name === "Facts two" && facts.ctas[0].claimed === 2 && facts.ctas[0].slots === 3
        && facts.ctas[0].attended === 2 && facts.ctas[0].reserve === 1
        && facts.ctas[1].name === "Facts one" && facts.ctas[1].claimed === 3 && facts.ctas[1].no_show === 1, facts.ctas);
  const names = facts.players.map(p => p.name);
  check("the players come attended first, then CTAs, then name: Gus, Eff, Disc, Res", same(names, ["Gus", "Eff", "Disc", "Res"]), names);
  const gus = facts.players[0], eff = facts.players[1], res = facts.players[3];
  check("a guest is one player by name across CTAs: two CTAs, two attended, a rate of one, the Longbow played twice",
        gus.account === false && gus.ctas === 2 && gus.attended === 2 && Number(gus.show_rate) === 1
        && same(gus.weapons, [{ n: 2, weapon_id: "2H_LONGBOW" }]) && gus.last_attended && gus.first_seen, gus);
  check("an account is one player by id: two CTAs, one attended, one no-show, a rate of a half, the last attended on the second CTA",
        eff.account === true && eff.ctas === 2 && eff.attended === 1 && eff.no_show === 1 && Number(eff.show_rate) === 0.5
        && String(eff.last_attended).startsWith("2026-10-08") && same(eff.weapons, [{ n: 1, weapon_id: "MAIN_MACE_HELL" }]), eff);
  check("a reserve has no rate and nothing played", res.reserve === 1 && res.show_rate === null && same(res.weapons, []), res);
  check("the weapons fielded, most played first: the Longbow twice by one player, then the two played once",
        same(facts.weapons.map(w => `${w.weapon_id}:${w.n}:${w.players}`), ["2H_LONGBOW:2:1", "MAIN_HOLYSTAFF_AVALON:1:1", "MAIN_MACE_HELL:1:1"]), facts.weapons);
  check("the open CTA and its sign-ups are not history", !facts.ctas.some(c => c.name === "Facts three") && facts.totals.records === 6);
  const outside = (await rows("authenticated", X, "select public.guild_history($1) as f", [g.id]))[0].f;
  check("an outsider gets empty facts, not a refusal: the policies show them no CTA",
        outside.totals.ctas === 0 && outside.totals.records === 0 && outside.totals.show_rate === null && same(outside.players, []) && same(outside.ctas, []) && same(outside.weapons, []), outside);
  check("anon cannot ask", await code_("anon", null, "select public.guild_history($1)", [g.id]) === "42501");
  check("a guild with no completed CTA has zero facts", (await rows("authenticated", C, "select public.guild_history(gen_random_uuid()) as f"))[0].f.totals.ctas === 0);
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
  await db.query("delete from realtime.messages");
}

/* 16 - import: a guild's weapon aliases, the names its callers matched */
{
  const code_ = code;
  const F = "00000000-0000-4000-8000-00000000000f";
  const K2 = "00000000-0000-4000-8000-000000000014";
  const X = "00000000-0000-4000-8000-000000000011";
  const g = (await rows("authenticated", C, "select * from public.create_guild($1, $2)", ["Zaddy Names", "europe"]))[0];
  const gCode = (await db.query("select join_code from public.guilds where id = $1", [g.id])).rows[0].join_code;
  await run("authenticated", F, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", K2, "select * from public.join_guild($1)", [gCode]);
  await run("authenticated", C, "update public.guild_members set role = 'caller' where guild_id = $1 and user_id = $2", [g.id, K2]);
  const save = (sub, list) => rows("authenticated", sub, "select public.save_weapon_aliases($1, $2::jsonb) as n", [g.id, JSON.stringify(list)]).then(r => r[0].n);
  const saveCode = (sub, list) => code_("authenticated", sub, "select public.save_weapon_aliases($1, $2::jsonb)", [g.id, JSON.stringify(list)]);
  const list = sub => rows("authenticated", sub, "select alias, weapon_id, created_by from public.weapon_aliases where guild_id = $1 order by alias", [g.id]);
  const count = async () => (await db.query("select count(*)::int as n from public.weapon_aliases where guild_id = $1", [g.id])).rows[0].n;

  check("a caller saves the names an import matched: three rows, the count back",
        await save(K2, [{ alias: "perma", weapon_id: "2H_ICECRYSTAL_UNDEAD" }, { alias: "1h holy", weapon_id: "MAIN_HOLYSTAFF" }, { alias: "zaddy bow", weapon_id: "2H_LONGBOW" }]) === 3);
  const seen = await list(F);
  check("a member reads the guild's names, each carrying who added it",
        seen.length === 3 && seen.every(r => r.created_by === K2) && seen[0].alias === "1h holy" && seen[2].weapon_id === "2H_LONGBOW", seen);
  check("an outsider reads none; anon reads nothing",
        (await list(X)).length === 0 && await code_("anon", null, "select * from public.weapon_aliases") === "42501");
  check("a member saves none, nor an outsider: the insert policy is the caller roles'",
        await saveCode(F, [{ alias: "bow thing", weapon_id: "2H_BOW" }]) === "42501"
        && await saveCode(X, [{ alias: "bow thing", weapon_id: "2H_BOW" }]) === "42501" && await count() === 3);
  check("saving a held name again changes its weapon and counts once; the same weapon again counts nothing",
        await save(K2, [{ alias: "perma", weapon_id: "2H_FROSTSTAFF" }]) === 1
        && (await list(K2)).find(r => r.alias === "perma").weapon_id === "2H_FROSTSTAFF"
        && await save(K2, [{ alias: "perma", weapon_id: "2H_FROSTSTAFF" }]) === 0 && await count() === 3);
  check("a name off the form is refused: upper case, a double space, punctuation, empty, too long; a weapon off the key form too",
        await saveCode(K2, [{ alias: "Perma", weapon_id: "2H_FROSTSTAFF" }]) === "23514"
        && await saveCode(K2, [{ alias: "great  arcane", weapon_id: "2H_ARCANESTAFF" }]) === "23514"
        && await saveCode(K2, [{ alias: "iron-clad", weapon_id: "2H_IRONCLADEDSTAFF" }]) === "23514"
        && await saveCode(K2, [{ alias: "", weapon_id: "2H_BOW" }]) === "23514"
        && await saveCode(K2, [{ alias: "a".repeat(65), weapon_id: "2H_BOW" }]) === "23514"
        && await saveCode(K2, [{ alias: "bow thing", weapon_id: "not a key" }]) === "23514"
        && await saveCode(K2, [{ alias: "bow thing" }]) === "23502");
  check("a save is bounded and must be a list", await saveCode(K2, Array.from({ length: 101 }, (_, i) => ({ alias: `n${i}`, weapon_id: "2H_BOW" }))) === "23514"
        && await saveCode(K2, { alias: "x", weapon_id: "2H_BOW" }) === "22023");
  check("no API role sets who added a name: created_by is the server's",
        await code_("authenticated", K2, "insert into public.weapon_aliases (guild_id, alias, weapon_id, created_by) values ($1, 'x', '2H_BOW', $2)", [g.id, C]) === "42501"
        && await code_("authenticated", K2, "update public.weapon_aliases set alias = 'y' where guild_id = $1 and alias = 'perma'", [g.id]) === "42501");
  check("a caller deletes a name; a member deletes nothing",
        (await run("authenticated", F, "delete from public.weapon_aliases where guild_id = $1 and alias = 'perma'", [g.id])).affectedRows === 0
        && (await run("authenticated", K2, "delete from public.weapon_aliases where guild_id = $1 and alias = 'perma'", [g.id])).affectedRows === 1 && await count() === 2);
  /* two names held; 498 more reach the bound */
  for (let batch = 0; batch < 5; batch++) {
    await save(K2, Array.from({ length: batch < 4 ? 100 : 98 }, (_, i) => ({ alias: `name ${batch * 100 + i}`, weapon_id: "2H_BOW" })));
  }
  check("a guild keeps at most 500 names; a held name still changes at the bound",
        await count() === 500 && await saveCode(K2, [{ alias: "one more", weapon_id: "2H_BOW" }]) === "23514"
        && await save(K2, [{ alias: "name 7", weapon_id: "2H_WARBOW" }]) === 1 && await count() === 500);
  check("anon cannot call the save; no API role calls the guard",
        await code_("anon", null, "select public.save_weapon_aliases($1, '[]'::jsonb)", [g.id]) === "42501"
        && await code_("authenticated", K2, "select public.weapon_aliases_guard()") === "42501");
  await run("authenticated", C, "delete from public.guilds where id = $1", [g.id]);
  check("deleting the guild deletes its names", await count() === 0);
}

} catch (e) {
  fail++;
  console.log("FAIL  the run stopped: " + (e.stack || e.message));
}

await db.close();
console.log(`\n${pass}/${pass + fail} row-level security tests passed`);
process.exit(fail ? 1 : 0);
