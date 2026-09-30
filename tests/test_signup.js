/* Sign-up tests - dashboard/_signup.js.
 *
 * The account modules run together in a vm context with no document, as
 * the page loads them: the helpers and the pure functions load, and each
 * UI block returns before touching the DOM. The helpers run against a
 * stub client that records every call, so what the page sends to
 * Supabase is pinned without a network; tests/test_supabase_rls.mjs pins
 * what the database does with it.
 *
 * Pinned: the link and the code in it, the claim token's form and key,
 * the board (claimants per slot, reserves, free slots, counts),
 * validation on the database's bounds, the payload, a profile's lists as
 * the first declaration, database errors as sentences, and what each
 * helper sends.
 *
 * Run:  node tests/test_signup.js
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
const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from() { throw new Error("the sign-up module reaches tables through its functions alone"); },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

(async () => {

/* 1 - the link, the code, the token */
{
  const fromSearch = run("codeFromSearch"), link = run("signupLink");
  check("the code rides the page address as ?cta=", fromSearch("?cta=A1B2C3D4E5") === "A1B2C3D4E5" && fromSearch("?x=1&cta=a1b2c3d4e5") === "A1B2C3D4E5");
  check("no code, a malformed code or another parameter is no sheet",
        fromSearch("") === null && fromSearch("?cta=short") === null && fromSearch("?comp=A1B2C3D4E5") === null && fromSearch(null) === null);
  check("the link is this page with the code as its one parameter, whatever hash or search the page had",
        link("A1B2C3D4E5", "https://x.test/albion/index.html#c=castle&p=A") === "https://x.test/albion/index.html?cta=A1B2C3D4E5"
        && link(" a1b2c3d4e5 ", "https://x.test/?cta=OLD#h") === "https://x.test/?cta=A1B2C3D4E5");
  check("a link's code reads back", fromSearch(new URL(link("A1B2C3D4E5", "https://x.test/index.html")).search) === "A1B2C3D4E5");
  const token = run("newClaimToken")(new Uint8Array([0, 1, 15, 16, 255, 128, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]));
  check("a claim token is 16 bytes as 32 hex characters", token === "00010f10ff80070809 0a0b0c0d0e0f10".replace(" ", "") && run("CLAIM_TOKEN_RE").test(token));
  check("the token is kept per CTA", run("claimTokenKey")("a1b2c3d4e5") === "cta-claim:A1B2C3D4E5");
}

/* 2 - the board */
{
  const board = run("sheetBoard");
  const slots = [{ position: 2, weapon_id: "MAIN_MACE_HELL", role: "engage" }, { position: 1, weapon_id: "2H_LONGBOW" }, { position: 3, weapon_id: null }];
  const signups = [
    { id: "s1", position: 1, player_name: "Gus", created_at: "2026-10-01T10:00:00Z" },
    { id: "s2", position: null, player_name: "Gil", created_at: "2026-10-01T09:00:00Z" },
    { id: "s3", position: 3, player_name: "Eff", created_at: "2026-10-01T11:00:00Z" },
    { id: "s4", position: null, player_name: "Ann", created_at: "2026-10-01T08:00:00Z" },
  ];
  const b = board(slots, signups);
  check("each slot in position order with its claimant; the free slots listed",
        same(b.rows.map(r => `${r.position}:${r.claimant ? r.claimant.player_name : "-"}`), ["1:Gus", "2:-", "3:Eff"]) && same(b.free, [2]), b.rows);
  check("reserves are the sign-ups without a slot, first come first",
        same(b.reserves.map(r => r.player_name), ["Ann", "Gil"]));
  check("the counts", same(b.counts, { slots: 3, claimed: 2, free: 1, reserves: 2 }), b.counts);
  check("an empty CTA is an empty board", same(board([], []), { rows: [], reserves: [], free: [], counts: { slots: 0, claimed: 0, free: 0, reserves: 0 } }));
}

/* 3 - validation and the payload */
{
  const v = run("validateSignup");
  const allowed = new Set([2, 3]);
  const ok = { playerName: "Gus", position: "2", itemPower: "1450", weapons: ["2H_LONGBOW"], note: "late" };
  check("a good guest sign-up passes", same(v(ok, { guest: true, allowed }), {}), v(ok, { guest: true, allowed }));
  check("a guest needs a name within the account name bound; an account does not",
        !!v(Object.assign({}, ok, { playerName: " " }), { guest: true, allowed }).playerName
        && !!v(Object.assign({}, ok, { playerName: "x".repeat(run("ACCOUNT_NAME_MAX") + 1) }), { guest: true, allowed }).playerName
        && same(v(Object.assign({}, ok, { playerName: "" }), { guest: false, allowed }), {}));
  check("the slot is one of the allowed positions, or none (a reserve)",
        !!v(Object.assign({}, ok, { position: "1" }), { guest: true, allowed }).position
        && same(v(Object.assign({}, ok, { position: "" }), { guest: true, allowed }), {})
        && same(v(Object.assign({}, ok, { position: null }), { guest: true, allowed }), {}));
  check("item power is optional, a whole number within the bound",
        same(v(Object.assign({}, ok, { itemPower: "" }), { guest: true, allowed }), {})
        && !!v(Object.assign({}, ok, { itemPower: "3001" }), { guest: true, allowed }).itemPower
        && !!v(Object.assign({}, ok, { itemPower: "12.5" }), { guest: true, allowed }).itemPower
        && !!v(Object.assign({}, ok, { itemPower: "-1" }), { guest: true, allowed }).itemPower);
  check("weapons are dataset keys, each once, at most the bound",
        !!v(Object.assign({}, ok, { weapons: ["not a key"] }), { guest: true, allowed }).weapons
        && !!v(Object.assign({}, ok, { weapons: ["2H_BOW", "2H_BOW"] }), { guest: true, allowed }).weapons
        && !!v(Object.assign({}, ok, { weapons: Array.from({ length: run("SIGNUP_WEAPONS_MAX") + 1 }, (_, i) => `W${i}`) }), { guest: true, allowed }).weapons
        && same(v(Object.assign({}, ok, { weapons: [] }), { guest: true, allowed }), {}));
  check("the note is bounded", !!v(Object.assign({}, ok, { note: "n".repeat(run("SIGNUP_NOTE_MAX") + 1) }), { guest: true, allowed }).note);

  const payload = run("signupPayload");
  check("the payload: a numeric slot or null, trimmed name, numeric item power or null, the flag, the weapons, the note",
        same(payload({ position: "2", playerName: " Gus ", itemPower: "1450", canSwap: 1, weapons: ["A", "B"], note: " late " }),
             { position: 2, player_name: "Gus", item_power: 1450, can_swap: true, weapons: ["A", "B"], note: "late" })
        && same(payload({ position: "", playerName: "", itemPower: "", canSwap: false, weapons: null, note: "" }),
                { position: null, player_name: "", item_power: null, can_swap: false, weapons: [], note: "" }));
  check("a profile's lists become the first declaration: main first, then can also play, each once, at most the bound",
        same(run("weaponsFromLists")({ main: ["A", "B"], secondary: ["B", "C"] }), ["A", "B", "C"])
        && run("weaponsFromLists")({ main: Array.from({ length: 12 }, (_, i) => `W${i}`), secondary: [] }).length === run("SIGNUP_WEAPONS_MAX")
        && same(run("weaponsFromLists")(null), []));
  const S = run("SHEET_STATUS_MSG");
  check("every status but open has a sentence for the sheet", S.open === "" && S.draft && S.locked && S.completed);
}

/* 4 - error wording */
{
  const msg = run("signupErrorMessage"), M = run("SIGNUP_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["function missing", { code: "PGRST202", message: "Could not find the function" }, M.missing],
    ["no CTA", { code: "P0002", message: "no CTA has this code" }, M.noEvent],
    ["not open", { code: "55000", message: "sign-up is not open for this CTA" }, M.closed],
    ["slot taken", { code: "23505", message: "duplicate key value violates unique constraint signups_one_per_slot" }, M.taken],
    ["slot gone", { code: "23503", message: "violates foreign key constraint signups_slot" }, M.noSlot],
    ["a guest without a name", { code: "23502", message: "a guest sign-up needs a name" }, M.needsName],
    ["an account without a character", { code: "23502", message: "name your character in the profile first" }, M.needsCharacter],
    ["no token", { code: "42501", message: "a guest sign-up needs a claim token" }, M.needsToken],
    ["full", { code: "23514", message: "a CTA takes at most 120 sign-ups" }, M.full],
    ["a bad weapon", { code: "23514", message: "a declared weapon is not a weapon key" }, M.badWeapon],
    ["refused", { code: "42501", message: "new row violates row-level security policy" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: the bound in the sentence is the bound in force", M.full.includes(String(run("SIGNUPS_MAX"))));
}

/* 5 - what the helpers send */
{
  CALLS.length = 0;
  REPLY["rpc:event_by_code"] = { data: { event: { id: "e1" } }, error: null };
  const s = await run("loadSheet")("A1B2C3D4E5", "tok");
  check("loadSheet asks event_by_code with the code and the token", same(CALLS[0], { rpc: "event_by_code", args: { code: "A1B2C3D4E5", token: "tok" } }) && s.event.id === "e1");
  CALLS.length = 0;
  await run("loadSheet")("A1B2C3D4E5", null);
  check("without a token, null rides along", CALLS[0].args.token === null);

  CALLS.length = 0;
  REPLY["rpc:sign_up"] = { data: { id: "s1", position: 2 }, error: null };
  const r = await run("submitSignUp")("A1B2C3D4E5", "tok", { position: "2", playerName: " Gus ", itemPower: "1450", canSwap: true, weapons: ["A"], note: "" });
  check("submitSignUp sends sign_up with the code, the token and the payload",
        CALLS[0].rpc === "sign_up" && CALLS[0].args.code === "A1B2C3D4E5" && CALLS[0].args.token === "tok"
        && same(CALLS[0].args.signup, { position: 2, player_name: "Gus", item_power: 1450, can_swap: true, weapons: ["A"], note: "" }) && r.position === 2, CALLS[0]);

  CALLS.length = 0;
  REPLY["rpc:cancel_sign_up"] = { data: true, error: null };
  const gone = await run("cancelSignUp")("A1B2C3D4E5", "tok");
  check("cancelSignUp sends cancel_sign_up and reads the answer", same(CALLS[0], { rpc: "cancel_sign_up", args: { code: "A1B2C3D4E5", token: "tok" } }) && gone === true);
  REPLY["rpc:cancel_sign_up"] = { data: false, error: null };
  check("no sign-up to cancel is false", (await run("cancelSignUp")("A1B2C3D4E5", null)) === false);

  const src = fs.readFileSync(path.join(DASH, "_signup.js"), "utf8");
  check("the module reaches the database through its three functions alone", !/\.from\("/.test(src) && /rpc\("event_by_code"/.test(src) && /rpc\("sign_up"/.test(src) && /rpc\("cancel_sign_up"/.test(src));
  check("the module touches the planner through the address bar alone",
        /location\.hash/.test(src) && !/\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine/.test(src));
  check("the claim token lives in localStorage and leaves the browser only inside a statement",
        /localStorage\.(getItem|setItem|removeItem)\(claimTokenKey\(/.test(src) && !/console\.log\(.*token/.test(src));
}

console.log(`\n${pass}/${pass + fail} sign-up tests passed`);
process.exit(fail ? 1 : 0);
})();
