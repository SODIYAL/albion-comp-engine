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

} catch (e) {
  fail++;
  console.log("FAIL  the run stopped: " + (e.stack || e.message));
}

await db.close();
console.log(`\n${pass}/${pass + fail} row-level security tests passed`);
process.exit(fail ? 1 : 0);
